"""設計縱斷面（ditch-design，由 P33 design_profiles 一般化）：各側溝（design.ditches[]）設計溝頂、溝底、開挖底。

設計條件全部讀 ditch_config.json（design.*，唯一來源；不再另存 design_param json 當輸入）：
- design.ground＝SG：溝蓋板頂貼 SG 地形（逐 1 m），溝牆頂＝SG－蓋板厚；
  design.ground＝EG：溝頂＝路面－蓋板厚，取單一直線縱坡（最小平方擬合，再下移至全線不凸出路面）。
- 溝底＝溝頂－H；起終點設集水井，井底＝溝底－沉砂深 design.sump；挖深＝地面－（溝底－底版－墊層）。
- 路面點：高程點（layers.spot_insert_layer）中與中心線高差 ≦ design.road_tol 者建「路面 TIN」。
用法：python design_profiles.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
輸出：work_dir/design_profile_<側別>.csv、work_dir/design_param.json（紀錄用）、A3 設計縱斷面 DXF＋PDF＋PNG（檢核用，非圖冊）。
"""
import sys, os, json, csv, math, datetime
import numpy as np
import ezdxf
from ezdxf.enums import TextEntityAlignment as TA
from ezdxf.render import mleader
from ezdxf.math import Vec2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
CFG = dd.CFG; stamp = dd.stamp
OUT = dd.OUT; PREV = os.path.join(OUT, "03_設計縱斷面"); os.makedirs(PREV, exist_ok=True)

PARAM = dict(dd.P_)                                   # design.*（ditch_config.json）
P_ = PARAM

# ---------------- 路面 TIN ----------------
msp = ezdxf.readfile(dd.src(CFG["src_dxf"]), encoding="utf-8").modelspace()
alg = ezdxf.readfile(dd.src(CFG["alignment"]["dxf"])).modelspace()
def line_of(layer):
    e = alg.query(f'LWPOLYLINE[layer=="{layer}"]').first
    return np.array([tuple(p) for p in e.get_points("xy")])
_cl = CFG["alignment"].get("centerline") or line_of(CFG["alignment"].get("centerline_layer", "中心線1"))   # 兩端點 TWD97（優先）或定線 DXF 中心線
C0 = np.array(_cl[0], float); C1 = np.array(_cl[1], float)
Lc = np.hypot(*(C1 - C0)); tv = (C1 - C0) / Lc; nr = np.array([tv[1], -tv[0]])
pts = np.array([tuple(e.dxf.insert) for e in msp.query(f'INSERT[layer=="{CFG["layers"]["spot_insert_layer"]}"]') if e.dxf.insert.z > 0])
s_ = (pts[:, :2] - C0) @ tv; o_ = (pts[:, :2] - C0) @ nr
cm = np.abs(o_) < 1.0
order = np.argsort(s_[cm]); cs, cz = s_[cm][order], pts[cm, 2][order]
dz = pts[:, 2] - np.interp(s_, cs, cz)
keep = (np.abs(o_) < 7.0) & (np.abs(dz) <= P_["road_tol"]) & (s_ > -15) & (s_ < Lc + 15)
rp = pts[keep]
print(f"路面點：{keep.sum()} / {len(pts)}（剔除與中心線高差 > {P_['road_tol']} m 的點）")
tri = mtri.Triangulation(rp[:, 0], rp[:, 1])
Groad = mtri.LinearTriInterpolator(tri, rp[:, 2])
d = np.load(dd.src(CFG["tin_npz"]))
Gall = mtri.LinearTriInterpolator(mtri.Triangulation(d["points"][:, 0], d["points"][:, 1], d["triangles"]), d["points"][:, 2])
USE_SG = dd.USE_SG                                     # design.ground：SG＝整地後地形；EG＝原地形（路面 TIN）
if USE_SG:
    ds = np.load(dd.src(CFG["sg"]["tin_npz"]))
    Groad = mtri.LinearTriInterpolator(mtri.Triangulation(ds["points"][:, 0], ds["points"][:, 1], ds["triangles"]), ds["points"][:, 2])
    print("設計地面：SG 地形", CFG["sg"]["tin_npz"], CFG["sg"]["corner_z"])
GND = dd.GND
def zat(G, xy): return np.ma.filled(G(xy[:, 0], xy[:, 1]), np.nan)

# ---------------- 副定線 ----------------
LINES = [(d["side"], d["line_layer"], line_of(d["line_layer"])) for d in dd.DITCHES]

def sta(s, pre):
    if abs(s - round(s)) < 1e-6: k = int(round(s)); return f"{pre}{k//1000}K+{k%1000:03d}"
    return f"{pre}{int(s)//1000}K+{s%1000:06.2f}"

designs = []
for key, nm, ln in LINES:
    L = float(np.hypot(*(ln[1] - ln[0])))
    s = np.r_[np.arange(0, L, 1.0), L]
    xy = ln[0] + np.outer(s / L, ln[1] - ln[0])
    road = zat(Groad, xy); raw = zat(Gall, xy)
    y = road - P_["t_cover"]
    if USE_SG:                                           # 2026-11-05 使用者：側溝（含溝蓋板）頂貼 SG 地形施作＝蓋板頂＝SG，溝牆頂＝SG－蓋板厚
        top = y.copy(); i = float(np.polyfit(s, top, 1)[0])
    else:
        i, b = np.polyfit(s, y, 1)
        b -= max(0.0, float(np.max((b + i * s) - y)))    # 下移至全線溝頂不高於「路面－蓋板厚」
        top = b + i * s
    bot = top - P_["H"]
    gap = y - top                                        # 溝頂低於路面－t 的量（蓋板座墊或路面修補）
    exc = bot - P_["t_slab"] - P_["t_bed"]
    dig = road - exc
    # 1% 對照
    b1 = np.mean(y - 0.01 * s); b1 -= max(0.0, float(np.max((b1 + 0.01 * s) - y)))
    gap1 = y - (b1 + 0.01 * s)
    wf = {0.0: bot[0] - P_["sump"], L: bot[-1] - P_["sump"]}   # 集水井底
    print(f"== {key} {nm} L={L:.2f}：路面 {road[0]:.2f}→{road[-1]:.2f}；溝頂縱坡 {i*100:.3f}%（{top[0]:.2f}→{top[-1]:.2f}）；"
          f"溝底 {bot[0]:.2f}→{bot[-1]:.2f}；溝頂低於路面－t 最大 {gap.max():.3f} m；挖深 {dig.min():.2f}～{dig.max():.2f} m")
    print(f"   固定 1% 對照：溝頂低於路面－t 最大 {gap1.max():.3f} m（平均 {gap1.mean():.3f}）")
    print(f"   集水井底：{key}0K+000 {wf[0.0]:.2f}、終點 {wf[L]:.2f}；RCP 管底 {bot[0]:.2f}／{bot[-1]:.2f}；"
          f"原地形 TIN 與路面 TIN 差 {np.nanmin(raw-road):+.2f}～{np.nanmax(raw-road):+.2f} m")
    with open(dd.work(f"design_profile_{key}.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["樁號", "樁距m", f"{GND}m", "原地形TIN高m", "溝頂高m", "溝底高m", "開挖底高m", "挖深m", "溝頂低於路面-t(m)"])
        for k in range(len(s)):
            w.writerow([sta(s[k], key), round(s[k], 2), round(road[k], 3), round(raw[k], 3), round(top[k], 3), round(bot[k], 3), round(exc[k], 3), round(dig[k], 3), round(gap[k], 3)])
    designs.append(dict(key=key, nm=nm, L=L, s=s, road=road, raw=raw, top=top, bot=bot, exc=exc, dig=dig, i=i, wf=wf))

# ======================================================================
# 出圖：A3 橫式，H=1/500、V=1/50
# ======================================================================
W_, H_ = 420.0, 297.0
TXT = 7.06; PT = 4.94; TBT = 4.94; WF = 0.5; TB_WF = 0.7
HS, VS = 500.0, 50.0; XM = 1000 / HS; YM = 1000 / VS
TB = dd.TB
LAYERS = {   # 名稱: (ACI, 線型, 預覽色, 預覽線寬mm) — 依樣板 v4.0 出圖設定表；設計線色號【待確認】
    "圖框": (7, None, "#000000", 0.50), "圖標欄": (7, None, "#000000", 0.35), "資料帶": (7, None, "#000000", 0.25),
    "格線": (254, "DOT", "#CCCCCC", 0.212), "主格線": (253, "DASHED", "#A3A3A3", 0.212),
    "原始地面線": (252, "DOT2", "#666666", 0.212), "路面線": (252, None, "#666666", 0.30),
    "設計溝頂線": (7, None, "#000000", 0.60), "設計溝底線": (7, None, "#000000", 0.60),
    "開挖線": (253, "DASHED", "#7A7A7A", 0.25), "集水井": (7, None, "#000000", 0.45), "RCP": (7, "DASHED", "#000000", 0.35),
    "標註": (7, None, "#000000", 0.18), "文字": (7, None, "#000000", 0.0),
}

def tw(s, h=TXT, wf=WF): return wf * sum(h if ord(ch) > 255 else 0.6 * h for ch in s)

class Sheet:
    def __init__(self, name): self.items = []; self.name = name; self.wf = WF; self.mls = []
    def mleader(self, tgt, tx, ty, lines, side):
        """多重引線（DXF 寫 MLEADER）：tgt 箭頭點；(tx, ty) 文字靠引線側的中點；side=+1 文字在右、-1 文字在左。
        預覽與檢查用的引線、箭頭、文字另存 mlpoly／mlfill／mltext，DXF 不重複寫。"""
        self.mls.append((tuple(tgt), (tx, ty), list(lines), side))
        n = len(lines); hl = PT * 1.5
        for j, t in enumerate(lines):
            self.items.append(("mltext", (tx, ty + (n - 1) / 2 * hl - j * hl), t, "left" if side > 0 else "right", PT, 0, self.wf))
        dog = np.array([tx - side * 5.0, ty]); land = np.array([tx - side * 1.0, ty]); T = np.array(tgt, float)
        self.items.append(("mlpoly", np.array([T, dog, land]), "標註", None))
        u = (dog - T) / np.hypot(*(dog - T)); nn = np.array([-u[1], u[0]])
        self.items.append(("mlfill", np.array([T, T + u * 2.5 + nn * 0.7, T + u * 2.5 - nn * 0.7]), "標註", None))
    def poly(self, pts, layer, lt=None): self.items.append(("poly", np.asarray(pts, float), layer, lt))
    def line(self, x1, y1, x2, y2, layer, lt=None): self.poly([(x1, y1), (x2, y2)], layer, lt)
    def rect(self, x, y, w, h, layer): self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], layer)
    def text(self, x, y, s, ha="left", h=TXT, rot=0): self.items.append(("text", (x, y), s, ha, h, rot, self.wf))

def tbox(it):
    _, (x, y), s, ha, h, rot, wf = it; w = tw(s, h, wf)
    if rot == 0:
        x0 = x if ha == "left" else x - w / 2 if ha == "center" else x - w; return (x0, y - h / 2, x0 + w, y + h / 2)
    y0 = y if ha == "left" else y - w / 2 if ha == "center" else y - w; return (x - h / 2, y0, x + h / 2, y0 + w)

def frame(sh, name, scales, no):
    sh.rect(0, 0, W_, H_, "圖框"); sh.rect(10, 10, 400, 277, "圖框"); sh.rect(10, 10, 400, 22, "圖標欄")
    for x in (86, 188, 226, 298, 392): sh.line(x, 10, x, 32, "圖標欄")
    for x0, x1 in ((86, 188), (226, 298), (392, 410)): sh.line(x0, 21, x1, 21, "圖標欄")
    sh.line(262, 10, 262, 32, "圖標欄")
    yc = (14.94, 20.88, 26.82); sh.wf = TB_WF
    sh.text(48, yc[2], "主辦機關", "center", TBT); sh.text(48, yc[1], TB["agency"], "center", TBT); sh.text(48, yc[0], TB["agency_en"], "center", TBT)
    sh.text(89.5, 26.5, "工程名稱：" + TB["project"], "left", TBT); sh.text(89.5, 15.5, "圖　名：" + name, "left", TBT)
    sh.text(207, yc[2], "比例尺", "center", TBT); sh.text(207, yc[1], scales[0], "center", TBT); sh.text(207, yc[0], scales[1], "center", TBT)
    sh.text(229.5, 26.5, "設計：", "left", TBT); sh.text(265.5, 26.5, "主管：", "left", TBT)
    sh.text(229.5, 15.5, "繪圖：", "left", TBT); sh.text(265.5, 15.5, "校核：", "left", TBT)
    sh.text(345, yc[2], "設計單位", "center", TBT); sh.text(345, yc[1], TB["designer"], "center", TBT); sh.text(345, yc[0], TB["designer_en"], "center", TBT)
    sh.text(401, 26.5, "圖號", "center", TBT); sh.text(401, 15.5, no, "center", TBT); sh.wf = WF

ROWS = ["坡度(%)", "挖深(m)", f"{GND}(m)", "溝頂高(m)", "溝底高(m)", "樁號", "單距(m)"]   # 由上而下（依業主範本 p07 列序）
RH = {"坡度(%)": 11.0, "單距(m)": 11.0, "樁號": 19.0}
TCW = 30.0; BX0 = 20.0; DX0 = BX0 + TCW
sheets = []
for no, D in enumerate(designs, 1):
    key, L, s = D["key"], D["L"], D["s"]
    sh = Sheet(f"{key}0K 設計縱斷面圖"); frame(sh, sh.name, [f"H=1/{HS:.0f}", f"V=1/{VS:.0f}"], f"{no:02d}"); sheets.append(sh)
    X0 = DX0 + 22.0                                      # 0K 位置（左側留集水井與 RCP）
    xs = lambda v: X0 + v * XM
    BX1 = xs(L) + 22.0
    # 資料帶（自下而上排）
    y = 36.0; rowy = {}
    for nm in reversed(ROWS):
        h = RH.get(nm, 16.0); rowy[nm] = (y, h); y += h
    PY0 = y
    wfv = list(D["wf"].values())
    zlo = min(min(wfv) - P_["t_slab"] - P_["t_bed"], D["exc"].min()) - 0.5
    zhi = np.nanmax(D["road"]) + 0.6                     # 框高依路面；路旁擋牆等原地形超出框者截掉
    BASE = math.floor(zlo * 2) / 2; TOP = math.ceil(zhi * 2) / 2
    ys = lambda z: PY0 + (z - BASE) * YM
    PY1 = ys(TOP)
    print(f"{key}：高程框 {BASE}～{TOP}，圖框頂 {PY1:.1f} mm")
    sh.rect(DX0, PY0, BX1 - DX0, PY1 - PY0, "資料帶")
    z = BASE
    while z <= TOP + 1e-9:
        if BASE < z < TOP:
            if abs(z - round(z)) < 1e-9: sh.line(DX0, ys(z), BX1, ys(z), "主格線", "DASHED")
            else: sh.line(DX0, ys(z), BX1, ys(z), "格線", "DOT")
        if abs(z - round(z)) < 1e-9 and BASE < z < TOP: sh.text(DX0 - 2, ys(z), f"{z:.0f}", "right", PT)
        z += 0.5
    for nm in ROWS:
        y0, h = rowy[nm]; sh.rect(BX0, y0, TCW, h, "資料帶"); sh.rect(DX0, y0, BX1 - DX0, h, "資料帶")
        sh.text(BX0 + TCW / 2, y0 + h / 2, nm, "center", PT)
    sh.text(BX0 + TCW / 2, (PY0 + PY1) / 2, "高程(m)", "center", PT, 90)
    # 原地形（全部點 TIN，點線）、路面（實線）、設計線
    if not USE_SG:                                       # SG 版不畫原地形（副定線壓在既有溝、擋牆上，線會跳動；使用者 2026-11-05 指示拿掉）
        rz = np.clip(D["raw"], BASE, TOP); ok = ~np.isnan(rz)
        sh.poly(np.column_stack([xs(s[ok]), ys(rz[ok])]), "原始地面線", "DOT2")
    sh.poly(np.column_stack([xs(s), ys(D["road"])]), "路面線")
    sh.poly(np.column_stack([xs(s), ys(D["top"])]), "設計溝頂線")
    sh.poly(np.column_stack([xs(s), ys(D["bot"])]), "設計溝底線")
    sh.poly(np.column_stack([xs(s), ys(D["exc"])]), "開挖線", "DASHED")
    # 集水井（以樁號 0、L 為井中心）與 RCP
    half = P_["well_in"] / 2
    for sc, side in ((0.0, -1), (L, 1)):
        fl = D["wf"][sc]; rd = float(np.interp(sc, s, D["road"]))      # 井頂（含蓋板）＝SG
        xi0, xi1 = xs(sc - half), xs(sc + half); xo0, xo1 = xs(sc - half - P_["well_wall"]), xs(sc + half + P_["well_wall"])
        sh.poly([(xi0, ys(rd - P_["t_cover"])), (xi0, ys(fl)), (xi1, ys(fl)), (xi1, ys(rd - P_["t_cover"]))], "集水井")
        sh.poly([(xo0, ys(rd)), (xo0, ys(fl - P_["t_slab"])), (xo1, ys(fl - P_["t_slab"])), (xo1, ys(rd)), (xo0, ys(rd))], "集水井")
        sh.line(xo0, ys(rd - P_["t_cover"]), xo1, ys(rd - P_["t_cover"]), "集水井")                  # 井蓋板底
        inv = fl + P_["sump"]; xe = xo1 if side > 0 else xo0; xr = xe + side * 12.0
        sh.line(xe, ys(inv), xr, ys(inv), "RCP", "DASHED")
    # 資料帶數值
    sts = sorted(set([float(v) for v in np.arange(0, L, 20.0)] + [L]))
    def at(v, arr): return float(np.interp(v, s, arr))
    xst = [xs(v) for v in sts]
    for v, x in zip(sts, xst):
        sh.line(x, PY0, x, ys(at(v, D["exc"])), "格線", "DOT")
        for nm, arr in (("挖深(m)", D["dig"]), (f"{GND}(m)", D["road"]), ("溝頂高(m)", D["top"]), ("溝底高(m)", D["bot"])):
            y0, h = rowy[nm]; sh.text(x - 0.7, y0 + h / 2, f"{at(v, arr):.2f}", "center", PT, 90)
        y0, h = rowy["樁號"]; sh.text(x - 0.7, y0 + h / 2, sta(v, key), "center", PT, 90)
    for a, b, xa, xb in zip(sts[:-1], sts[1:], xst[:-1], xst[1:]):
        y0, h = rowy["坡度(%)"]; sh.text((xa + xb) / 2, y0 + h / 2, f"{(at(b, D['bot']) - at(a, D['bot'])) / (b - a) * 100:.2f}", "center", PT)
        y0, h = rowy["單距(m)"]; sh.text((xa + xb) / 2, y0 + h / 2, f"{b-a:.2f}", "center", PT)
    # 多重引線：新設集水井（圖框上方）、新設道路側溝（框內）尺寸 W×H
    for sc, side in ((0.0, 1), (L, -1)):
        fl = D["wf"][sc]; rd = float(np.interp(sc, s, D["road"])); x = xs(sc)
        hw = (rd - P_["t_cover"] - fl) * 100
        sh.mleader((x, ys((rd + fl) / 2)), x + side * 9.0, PY1 + 9.0,
                   [f"新設集水井 W×H＝{P_['well_in']*100:.0f}×{hw:.0f} cm（內徑）", f"井底 {fl:.2f}／RCP 管底 {fl+P_['sump']:.2f}"], side)
    st_ = 0.28 * L; zt = at(st_, D["top"]); zb = at(st_, D["bot"]); zr = at(st_, D["road"])
    sh.mleader((xs(st_), ys((zt + zb) / 2)), xs(st_) + 14.0, ys(zr) + 11.0,
               [f"新設道路側溝 W×H＝{P_['W']*100:.0f}×{P_['H']*100:.0f} cm（含溝蓋板 t={P_['t_cover']*100:.0f}）"], 1)
    # 圖例
    LYg = PY1 + 20.0; x = BX0
    leg = [("路面線", None, "SG 整地後地面" if USE_SG else "原地面（路面）")] + \
          ([] if USE_SG else [("原始地面線", "DOT2", "原地形（含路旁擋牆、溝底點）")]) + \
          [("設計溝頂線", None, "設計溝頂／溝底"), ("開挖線", "DASHED", "開挖底")]
    for lay, lt, lab in leg:
        sh.line(x, LYg, x + 10, LYg, lay, lt); x += 12.5; sh.text(x, LYg, lab, "left", PT); x += tw(lab, PT) + 6
    # 設計條件
    notes = [(f"設計條件：U 型溝 W×H＝{P_['W']*100:.0f}×{P_['H']*100:.0f} cm，側溝及集水井蓋板頂貼 SG 地面（溝牆頂＝SG－{P_['t_cover']*100:.0f} cm），平均縱坡 {D['i']*100:.2f}%（往 {key}0K+000 排水）；"
              if USE_SG else f"設計條件：U 型溝 W×H＝{P_['W']*100:.0f}×{P_['H']*100:.0f} cm，溝頂＝路面－蓋板厚 {P_['t_cover']*100:.0f} cm，溝底縱坡 {D['i']*100:.2f}%（往 {key}0K+000 排水）；"),
             f"底版 {P_['t_slab']*100:.0f} cm＋墊層 {P_['t_bed']*100:.0f} cm；集水井內淨 {P_['well_in']*100:.0f}×{P_['well_in']*100:.0f} cm，RCP 管底高於井底 {P_['sump']*100:.0f} cm；RCP 管徑【待確認】。"]
    for k, t in enumerate(reversed(notes)): sh.text(BX0, LYg + 8.0 + 7.5 * k, t, "left", PT)

# ---------- 自動檢查：文字壓線、文字重疊、出界 ----------
def check(sh):
    segs = np.array([(a[0], a[1], b[0], b[1]) for it in sh.items if it[0] == "poly" and it[2] not in ("資料帶", "圖框", "圖標欄", "格線", "主格線")
                     for a, b in zip(it[1][:-1], it[1][1:])])
    T = [tbox(it) for it in sh.items if it[0] in ("text", "mltext")]
    def hit(r):
        x0, y0, x1, y1 = r; n = 0
        for sx0, sy0, sx1, sy1 in segs:
            for tt in np.linspace(0, 1, 40):
                px, py = sx0 + (sx1 - sx0) * tt, sy0 + (sy1 - sy0) * tt
                if x0 < px < x1 and y0 < py < y1: n += 1; break
        return n
    press = sum(1 for r in T if hit(r))
    over = sum(1 for i in range(len(T)) for j in range(i + 1, len(T))
               if T[i][0] < T[j][2] and T[j][0] < T[i][2] and T[i][1] < T[j][3] and T[j][1] < T[i][3])
    out = sum(1 for r in T if r[0] < 10 or r[2] > 410 or r[1] < 10 or r[3] > 287)
    print(f"[檢查] {sh.name}：文字壓線 {press}、文字重疊 {over}、出界 {out}")
for sh in sheets: check(sh)

# ---------- DXF ----------
base = f"{dd.PRE}{stamp}_A3_設計縱斷面圖_{'_'.join(k + '0K' for k in dd.SIDE_KEYS)}_{dd.ver('profiles')}_{dd.GROUND}_TWD97_GENIE"
doc = ezdxf.new("R2018", setup=True); doc.header["$LTSCALE"] = 5
if "GENIE" not in doc.styles: doc.styles.add("GENIE", font="GENISO.shx").dxf.bigfont = "GENIE.shx"
for nm, (aci, lt, *_r) in LAYERS.items():
    doc.layers.add(nm, color=aci, linetype=lt or "CONTINUOUS")
m = doc.modelspace()
for k, sh in enumerate(sheets):
    ox = k * 450.0
    for it in sh.items:
        if it[0] in ("mltext", "mlpoly", "mlfill"): continue          # 由下方 MLEADER 寫入
        if it[0] == "poly":
            at_ = {"layer": it[2]}
            if it[3] and it[3] != LAYERS[it[2]][1]: at_["linetype"] = it[3]
            if it[3] == "DOT2": at_["ltscale"] = 0.1
            m.add_lwpolyline([(p[0] + ox, p[1]) for p in it[1]], dxfattribs=at_)
        else:
            _, (x, y), s, ha, h, rot, wf = it
            t = m.add_text(s, height=h, rotation=rot, dxfattribs={"layer": "文字", "style": "GENIE", "width": wf})
            t.set_placement((x + ox, y), align={"left": TA.MIDDLE_LEFT, "center": TA.MIDDLE_CENTER, "right": TA.MIDDLE_RIGHT}[ha])
    for tgt, (tx, ty), lines, side in sh.mls:                       # 多重引線 MLEADER
        ml = m.add_multileader_mtext("Standard", dxfattribs={"layer": "標註"})
        ml.set_content("\\P".join(f"\\W{WF};{t}" for t in lines), char_height=PT, style="GENIE",
                       alignment=mleader.TextAlignment.left if side > 0 else mleader.TextAlignment.right)
        ml.set_arrow_properties(size=2.5)
        ml.set_connection_properties(landing_gap=1.0, dogleg_length=4.0)
        ml.add_leader_line(mleader.ConnectionSide.left if side > 0 else mleader.ConnectionSide.right, [Vec2(tgt[0] + ox, tgt[1])])
        ml.build(insert=Vec2(tx + ox, ty))
dxf_path = os.path.join(OUT, base + ".dxf")
if os.path.exists(dxf_path): sys.exit(f"{dxf_path} 已存在，不覆蓋")
doc.saveas(dxf_path)

# ---------- PDF + PNG ----------
fp = FontProperties(fname=r"C:\Windows\Fonts\msjhl.ttc")
def render(sh, ax):
    ax.set_xlim(0, W_); ax.set_ylim(0, H_); ax.set_aspect("equal"); ax.axis("off")
    for it in sh.items:
        if it[0] == "mlfill":
            ax.fill(it[1][:, 0], it[1][:, 1], color="#000000", lw=0); continue
        if it[0] in ("poly", "mlpoly"):
            aci, lt0, col, lw = LAYERS[it[2]]; lt = it[3] or lt0
            ls = {"DOT": (0, (1, 3)), "DASHED": (0, (6, 3)), "DOT2": (0, (1, 1.5))}.get(lt, "-")
            ax.plot(it[1][:, 0], it[1][:, 1], color=col, lw=lw * 72 / 25.4, ls=ls, solid_capstyle="butt")
        else:
            _, (x, y), s, ha, h, rot, wf = it
            # 預覽：TextPath 依字寬係數水平壓縮，與 DXF 的 TEXT.width 一致；字身高 ≈ h
            tp = TextPath((0, 0), s, size=h * 1.0, prop=fp)
            w = tw(s, h, wf)
            ext = tp.get_extents(); sx = w / max(ext.x1, 1e-6)
            a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
            tr = Affine2D().scale(sx, 1).translate(a0, -h * 0.40).rotate_deg(rot).translate(x, y)
            ax.add_patch(PathPatch(tr.transform_path(tp), color="#000000", lw=0))
pdf_path = os.path.join(OUT, base + ".pdf")
with PdfPages(pdf_path) as pdf:
    for k, sh in enumerate(sheets):
        fig = plt.figure(figsize=(W_ / 25.4, H_ / 25.4)); ax = fig.add_axes([0, 0, 1, 1]); render(sh, ax)
        pdf.savefig(fig); png = os.path.join(PREV, f"{base}_p{k+1}.png"); fig.savefig(png, dpi=200); plt.close(fig)
        print("PNG：", png)
print("DXF：", dxf_path); print("PDF：", pdf_path)
dd.write_json("design_param.json", {k: v for k, v in P_.items()})     # 紀錄用（rebar_check 讀這份）


