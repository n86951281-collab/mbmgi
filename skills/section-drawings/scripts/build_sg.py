"""建 SG 地形（整地後地形）＝原地形 EG TIN 套入整地面。

整地範圍：使用者的整地 DWG 先用 accoreconsole 轉 DXF（見 SKILL.md），每個整地區（分區）的外框放在一個圖層，
該圖層的 LWPOLYLINE／LINE 頂點去重後必須剛好 4 點（四邊形，北在上）。
整地面：
  - 四角高程 corner_z {NW, NE, SW, SE}：框內各點依框內相對位置 u（西→東）、v（北→南）雙線性內插（反雙線性用牛頓法求 u, v）。
  - 或單一高程 z：平整面。
做法：
  1. 刪除框內及框外 edge_buffer（預設 1 m）內的原高程點（框外緊鄰的點會讓跨框三角形把整地面拉低，P33 v1 在框邊凹 0.1 m）。
  2. 框內加約 grid_step（1 m）格點、框線每 edge_step（0.5 m）加點，高程取整地面。
  3. 框外原點保留，重建 TIN（邊長 > terrain.max_edge 的三角形刪除，與原地形同規則）。
  4. 檢核：框內密取樣與整地面理論值最大差 > 0.01 m 時停止。
  5. 依 SG 重算定線各線每 1 m 高程（profile_<圖層>_SG.csv，含原地形高程與整地差）。
用法：python -I build_sg.py <案件設定.json>
設定鍵（sg）：
  pad_dxf      整地 DXF
  pads         [{"layer": 圖層, "corner_z": {"NW":…, "NE":…, "SW":…, "SE":…}} 或 {"layer": 圖層, "z": 高程}, …]
               只有一區時也可沿用 P33 寫法：pad_layer ＋ corner_z
  eg_tin_npz   原地形 EG（預設 tin_npz；EG 修正後改指向 eg_fix 的 out_tin）
  tin_npz      SG 輸出（加版次，不覆蓋）
  edge_buffer  框外刪點距離 (m)，預設 1.0
  grid_step、edge_step  框內格點、框線加點間距 (m)，預設 1.0、0.5
  profile_layers  要輸出 SG 高程的定線圖層，預設 alignment 的中心線、左岸、右岸
  draw_eg_line {"profile": false, "cross_section": false}：設計縱、橫斷面是否另畫原地形線（見 SKILL.md）
輸出：sg.tin_npz、同名 _qa.txt、profile_<圖層>_SG.csv（放在案件設定檔同資料夾）
參考實作：P33 新社東山（2026-11-05 四角高程 NW 476.99、NE 477.00、SW 477.88、SE 477.80）。
"""
import sys, os, json, csv
import numpy as np
import ezdxf
import matplotlib.tri as mtri
from matplotlib.path import Path

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I build_sg.py <案件設定.json>")
CFG_PATH = os.path.abspath(sys.argv[1]); HERE = os.path.dirname(CFG_PATH)
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))
def cpath(p): return p if os.path.isabs(p) else os.path.join(HERE, p)
SG = CFG["sg"]; MAX_EDGE = float(CFG.get("terrain", {}).get("max_edge", 40.0))
BUF = float(SG.get("edge_buffer", 1.0)); GSTEP = float(SG.get("grid_step", 1.0)); ESTEP = float(SG.get("edge_step", 0.5))
PADS = SG.get("pads") or [{"layer": SG["pad_layer"], "corner_z": SG["corner_z"]}]
out = cpath(SG["tin_npz"])
if os.path.exists(out): sys.exit(f"{out} 已存在，不覆蓋；請在設定檔改 sg.tin_npz 檔名（加版次）")

# ---------- 整地框 ----------
pm = ezdxf.readfile(cpath(SG["pad_dxf"])).modelspace()
class Pad:
    def __init__(self, spec):
        lay = spec["layer"]; xy = []
        for e in pm.query(f'LWPOLYLINE LINE[layer=="{lay}"]'):
            xy += [p[:2] for p in e.get_points("xy")] if e.dxftype() == "LWPOLYLINE" else [tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]
        V = np.unique(np.round(np.array(xy, dtype=float), 3), axis=0) if xy else np.zeros((0, 2))
        if len(V) != 4: sys.exit(f"整地框 {lay} 頂點數 {len(V)}，應為 4")
        c = V.mean(axis=0)
        q = lambda wx, wy: V[((V[:, 0] < c[0]) == wx) & ((V[:, 1] > c[1]) == wy)]
        nw, ne, sw, se = q(True, True), q(False, True), q(True, False), q(False, False)
        if min(len(nw), len(ne), len(sw), len(se)) != 1: sys.exit(f"整地框 {lay} 無法分出西北、東北、西南、東南四角（框轉角過大），請改用單一高程 z 或請使用者標明角點")
        self.NW, self.NE, self.SW, self.SE = nw[0], ne[0], sw[0], se[0]; self.lay = lay
        if "corner_z" in spec:
            Z = spec["corner_z"]; self.z4 = (float(Z["NW"]), float(Z["NE"]), float(Z["SW"]), float(Z["SE"]))
        else:
            self.z4 = (float(spec["z"]),) * 4
        self.path = Path(np.array([self.NW, self.NE, self.SE, self.SW, self.NW]))
    def bil(self, u, v):
        return ((1 - v) * (1 - u))[:, None] * self.NW + ((1 - v) * u)[:, None] * self.NE + (v * (1 - u))[:, None] * self.SW + (v * u)[:, None] * self.SE
    def uv(self, p):
        """反雙線性：p = (1-v)[(1-u)NW + u NE] + v[(1-u)SW + u SE]，牛頓法求 (u, v)"""
        p = np.atleast_2d(p); u = np.full(len(p), 0.5); v = np.full(len(p), 0.5)
        NW, NE, SW, SE = self.NW, self.NE, self.SW, self.SE
        for _ in range(20):
            f = self.bil(u, v) - p
            du = (1 - v)[:, None] * (NE - NW) + v[:, None] * (SE - SW)
            dv = (1 - u)[:, None] * (SW - NW) + u[:, None] * (SE - NE)
            det = du[:, 0] * dv[:, 1] - du[:, 1] * dv[:, 0]
            u -= (f[:, 0] * dv[:, 1] - f[:, 1] * dv[:, 0]) / det
            v -= (du[:, 0] * f[:, 1] - du[:, 1] * f[:, 0]) / det
        return u, v
    def z(self, p):
        u, v = self.uv(p); zNW, zNE, zSW, zSE = self.z4
        return (1 - v) * ((1 - u) * zNW + u * zNE) + v * ((1 - u) * zSW + u * zSE)
    def dist_edge(self, p):
        """點到框四邊的最短距離"""
        dmin = np.full(len(p), np.inf)
        for a, b in ((self.NW, self.NE), (self.NE, self.SE), (self.SE, self.SW), (self.SW, self.NW)):
            ab = b - a; t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
            dmin = np.minimum(dmin, np.hypot(*(p - (a + np.outer(t, ab))).T))
        return dmin
    def grid(self):
        """框內格點（以 u, v 參數撒點，貼合斜框）"""
        self.Lns = np.hypot(*(self.SW - self.NW)); self.Lwe = np.hypot(*(self.NE - self.NW))
        uu, vv = np.meshgrid(np.linspace(0, 1, int(np.ceil(self.Lwe / GSTEP)) + 1), np.linspace(0, 1, int(np.ceil(self.Lns / GSTEP)) + 1))
        return self.bil(uu.ravel(), vv.ravel())
    def border(self):
        bd = []
        for a, b in ((self.NW, self.NE), (self.NE, self.SE), (self.SE, self.SW), (self.SW, self.NW)):
            n = int(np.ceil(np.hypot(*(b - a)) / ESTEP)); t = np.linspace(0, 1, n, endpoint=False)
            bd.append(a + np.outer(t, b - a))
        return np.vstack(bd)
pads = [Pad(s) for s in PADS]
for k, a in enumerate(pads):
    for b in pads[k + 1:]:
        if a.path.contains_points([b.NW, b.NE, b.SW, b.SE]).any() or b.path.contains_points([a.NW, a.NE, a.SW, a.SE]).any():
            sys.exit(f"整地框 {a.lay} 與 {b.lay} 重疊，請使用者確認分區")

# ---------- 原地形點 ----------
eg_file = SG.get("eg_tin_npz", CFG["tin_npz"])
d = np.load(cpath(eg_file)); P0 = d["points"]
G0 = mtri.LinearTriInterpolator(mtri.Triangulation(P0[:, 0], P0[:, 1], d["triangles"]), P0[:, 2])
inside = np.zeros(len(P0), dtype=bool)
for pd in pads:
    inside |= pd.path.contains_points(P0[:, :2]) | (pd.dist_edge(P0[:, :2]) < BUF)
    zc = np.ma.filled(G0(*np.array([pd.NW, pd.NE, pd.SW, pd.SE]).T), np.nan)
    print(f"整地框 {pd.lay} 角點：西北 {pd.NW}、東北 {pd.NE}、西南 {pd.SW}、東南 {pd.SE}；"
          f"給定高程 {pd.z4}；原地形在角點 {tuple(np.round(zc, 2).tolist())}（差很大時先和使用者確認角點對應）")
keep = P0[~inside]
grids = [pd.grid() for pd in pads]
newp = []
for pd, g in zip(pads, grids):
    xy = np.unique(np.round(np.vstack([g, pd.border()]), 3), axis=0)
    newp.append(np.column_stack([xy, pd.z(xy)]))
newp = np.vstack(newp)
pts = np.vstack([keep, newp])
t = mtri.Triangulation(pts[:, 0], pts[:, 1]); tri = t.triangles; PP = pts[tri][:, :, :2]
edge = np.max(np.stack([np.hypot(*(PP[:, i] - PP[:, (i + 1) % 3]).T) for i in range(3)]), axis=0)
tri = tri[edge <= MAX_EDGE]
Gs = mtri.LinearTriInterpolator(mtri.Triangulation(pts[:, 0], pts[:, 1], tri), pts[:, 2])

# ---------- QA：整地面與原地形差、與整地面理論值比對 ----------
lines = [f"原地形 {eg_file}：刪框內及框邊原高程點 {int(inside.sum())} 個；加整地點 {len(newp)} 個；SG 點數 {len(pts)}、三角形 {len(tri)}"]
for pd, grid in zip(pads, grids):
    z0 = np.ma.filled(G0(grid[:, 0], grid[:, 1]), np.nan); zs = np.ma.filled(Gs(grid[:, 0], grid[:, 1]), np.nan)
    dz = zs - z0; ok = ~np.isnan(dz)
    chk = float(np.nanmax(np.abs(zs - pd.z(grid))))
    uu2, vv2 = np.meshgrid(np.linspace(0.005, 0.995, 60), np.linspace(0.002, 0.998, 600))   # 框內密取樣（含格點之間）
    dense = pd.bil(uu2.ravel(), vv2.ravel())
    chk2 = float(np.nanmax(np.abs(np.ma.filled(Gs(dense[:, 0], dense[:, 1]), np.nan) - pd.z(dense))))
    if chk2 > 0.01: sys.exit(f"整地框 {pd.lay}：SG 與整地面理論值最大差 {chk2:.3f} m > 0.01 m，檢查框邊原高程點（edge_buffer）")
    zNW, zNE, zSW, zSE = pd.z4
    lines += [f"整地框 {pd.lay}：西北 {pd.NW}、東北 {pd.NE}、西南 {pd.SW}、東南 {pd.SE}（南北約 {pd.Lns:.1f} m、東西約 {pd.Lwe:.1f} m）",
              (f"平整面高程：{zNW}" if len(set(pd.z4)) == 1 else f"四角高程：西北 {zNW}、東北 {zNE}、西南 {zSW}、東南 {zSE}（雙線性內插）"),
              f"SG 與整地面理論值最大差：格點 {chk:.4f} m、框內密取樣 {chk2:.4f} m（框外 {BUF} m 內原高程點一併刪除）",
              f"整地面－原地形（框內）：最小 {np.min(dz[ok]):+.2f}、最大 {np.max(dz[ok]):+.2f}、平均 {np.mean(dz[ok]):+.2f} m；"
              f"填方面積比 {np.mean(dz[ok] > 0)*100:.0f}%（正＝填）"]
np.savez(out, points=pts, triangles=tri.astype(np.int32))
open(os.path.splitext(out)[0] + "_qa.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines)); print("SG：", out)

# ---------- 定線高程（SG）----------
AL = CFG["alignment"]
alg = ezdxf.readfile(cpath(AL["dxf"])).modelspace()
for nm in SG.get("profile_layers", [AL["centerline_layer"], AL["bank_left_layer"], AL["bank_right_layer"]]):
    e = alg.query(f'LWPOLYLINE[layer=="{nm}"]').first
    if e is None: print(f"定線 DXF 沒有 {nm}，略過"); continue
    V = np.array([tuple(p) for p in e.get_points("xy")])
    cum = np.r_[0.0, np.cumsum(np.hypot(*np.diff(V, axis=0).T))]; L = float(cum[-1])
    s = np.r_[np.arange(0, L, 1.0), L]
    xy = np.column_stack([np.interp(s, cum, V[:, 0]), np.interp(s, cum, V[:, 1])])
    zs_ = np.ma.filled(Gs(xy[:, 0], xy[:, 1]), np.nan); z0_ = np.ma.filled(G0(xy[:, 0], xy[:, 1]), np.nan)
    fn = os.path.join(HERE, f"profile_{nm}_SG.csv")
    with open(fn, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["樁距m", "X", "Y", "SG高程m", "原地形高程m", "整地差m(正=填)"])
        for si, (x, y), z1, z2 in zip(s, xy, zs_, z0_): w.writerow([round(si, 2), round(x, 3), round(y, 3), round(float(z1), 3), round(float(z2), 3), round(float(z1 - z2), 3)])
    print(f"{nm}：L={L:.2f}，SG 高程 起 {zs_[0]:.2f}→終 {zs_[-1]:.2f}；整地差 {np.nanmin(zs_-z0_):+.2f}～{np.nanmax(zs_-z0_):+.2f} m")
