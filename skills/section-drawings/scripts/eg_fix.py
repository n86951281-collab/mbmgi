"""依使用者在 CAD 手改的橫斷面地面線（V2），回寫修正原地形 EG TIN，全域套用。

前置：先把使用者 V2 橫斷面 DWG 轉 DXF，與程式原輸出逐刀比對，取出各刀地面線（比對差異見 SKILL cad-v2-feedback），
存成 edits_npy：np.save(檔名, {"orig": {樁號: [N×2 陣列(x, z), …]}, "user": {樁號: [...]}}, allow_pickle=True)
  樁號：沿 alignment.centerline_layer 的樁距 (m)；x：斷面橫距 (m)，正向＝沿樁號前進方向的左側法向 (−ty, tx)；
  z：高程 (m)。「user」要包含使用者沒改的刀（dz＝0 也要列），內插才有錨點。
做法：
  1. 各刀取 dz(x)＝使用者線－原 EG（每 xs_step m）；原 EG 無資料處取使用者線高程（絕對值）。
  2. 刀與刀之間依樁距線性內插 dz（兩側都有絕對值時內插絕對值）；樁號範圍外以最近兩刀線性外插。
  3. 中心線 s_range、橫距 band（兩側對稱）內刪除原 EG 點，改放 xs_step × xs_step 格點（修正後高程）。
  4. 重建 EG TIN（邊長 > terrain.max_edge 的三角形刪除）。band 以外不動；整地框內的 SG 要另跑 build_sg.py 重建。
用法：python -I eg_fix.py <案件設定.json>
設定鍵（eg_fix）：
  edits_npy  比對結果檔；src_tin 原 EG（預設 tin_npz）；out_tin 輸出（加版次，不覆蓋）
  band       [內, 外] 修正帶橫距 (m)；P33 為 [5.2, 9.5]（整地框外到斷面邊）
  xs_step    格點間距 (m)，預設 0.5
  s_range    [起, 終] 樁距 (m)；終點填 null 表示中心線全長；預設 [0, null]
輸出：out_tin 與同名 _qa.txt（各刀修正帶內新 EG－使用者線最大差）。
重建後把 tin_npz（或 sg.eg_tin_npz）改指向 out_tin，再重跑 build_sg.py 與出圖。
參考實作：P33 新社東山（2026-11-06，0K+040～100 框外擋牆／屋台突起壓平）。
"""
import sys, os, json
import numpy as np
import ezdxf
import matplotlib.tri as mtri

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I eg_fix.py <案件設定.json>")
CFG_PATH = os.path.abspath(sys.argv[1])
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))
def cpath(p): return p if os.path.isabs(p) else os.path.join(os.path.dirname(CFG_PATH), p)
MAX_EDGE = float(CFG.get("terrain", {}).get("max_edge", 40.0))
EF = CFG["eg_fix"]
B_IN, B_OUT = [float(v) for v in EF.get("band", [5.2, 9.5])]
STEP = float(EF.get("xs_step", 0.5))
out = cpath(EF["out_tin"])
if os.path.exists(out): sys.exit(f"{out} 已存在，不覆蓋；請在設定檔改 eg_fix.out_tin 檔名（加版次）")

E = np.load(cpath(EF["edits_npy"]), allow_pickle=True).item()
d = np.load(cpath(EF.get("src_tin", CFG["tin_npz"]))); P0 = d["points"]
G0 = mtri.LinearTriInterpolator(mtri.Triangulation(P0[:, 0], P0[:, 1], d["triangles"]), P0[:, 2])

# ---------- 中心線（多段線；樁距 s、左側法向 nv）----------
AL = CFG["alignment"]
e = ezdxf.readfile(cpath(AL["dxf"])).modelspace().query(f'LWPOLYLINE[layer=="{AL["centerline_layer"]}"]').first
if e is None: sys.exit(f"定線 DXF 找不到 {AL['centerline_layer']} 圖層的 LWPOLYLINE")
CL = np.array([tuple(p) for p in e.get_points("xy")])
seg = np.diff(CL, axis=0); seg_len = np.hypot(*seg.T); cum = np.r_[0.0, np.cumsum(seg_len)]; Lc = float(cum[-1])
TV = seg / seg_len[:, None]; NV = np.column_stack([-TV[:, 1], TV[:, 0]])
def frame(s):
    """樁距 s（可超出兩端，沿首末段外延）→ 中心線點、切向、左側法向"""
    s = np.atleast_1d(np.asarray(s, dtype=float))
    i = np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(seg) - 1)
    return CL[i] + TV[i] * (s - cum[i])[:, None], TV[i], NV[i]
def station_offset(xy):
    """點投影到中心線：回傳樁距、橫距（左正）。超出兩端時沿首末段外延"""
    best_d = np.full(len(xy), np.inf); S = np.zeros(len(xy)); X = np.zeros(len(xy))
    for k in range(len(seg)):
        t = (xy - CL[k]) @ TV[k]
        if k > 0: t = np.maximum(t, 0)
        if k < len(seg) - 1: t = np.minimum(t, seg_len[k])
        foot = CL[k] + np.outer(t, TV[k]); dd = np.hypot(*(xy - foot).T)
        m = dd < best_d; best_d[m] = dd[m]; S[m] = cum[k] + t[m]; X[m] = ((xy - CL[k]) @ NV[k])[m]
    return S, X
def eg(s, x):
    c, _, n = frame(s); p = c + n * np.asarray(x)[:, None]
    return np.ma.filled(G0(p[:, 0], p[:, 1]), np.nan)

s0, s1 = EF.get("s_range", [0.0, None]); s0 = float(s0); s1 = Lc if s1 is None else float(s1)
XS = np.arange(-B_OUT, B_OUT + STEP / 50, STEP); BAND = (np.abs(XS) >= B_IN)
STS = sorted(E["user"].keys())
if len(STS) < 2: sys.exit("edits_npy 至少要有兩刀（含使用者沒改的刀）")
DZ, ZU = {}, {}
for st in STS:
    u = np.vstack(E["user"][st]); u = u[np.argsort(u[:, 0])]
    o = np.vstack(E["orig"][st]) if st in E.get("orig", {}) else None
    zu = np.interp(XS, u[:, 0], u[:, 1], left=np.nan, right=np.nan)
    # 使用者線端點離斷面邊 < 0.6 m 時外延到斷面邊（P33：線畫到 ±9.0 附近，帶寬到 ±9.5）
    zu[XS < u[:, 0].min()] = u[0, 1] if u[0, 0] < -B_OUT + 0.6 else np.nan
    zu[XS > u[:, 0].max()] = u[-1, 1] if u[-1, 0] > B_OUT - 0.6 else np.nan
    n_chg = "—"
    if o is not None:
        o = o[np.argsort(o[:, 0])]; zo = np.interp(XS, o[:, 0], o[:, 1], left=np.nan, right=np.nan)
        n_chg = int(((np.abs(np.nan_to_num(zu - zo, nan=9)) > 0.02) & BAND).sum())
    ze = eg(np.full(len(XS), st), XS)                       # 出圖的原線可能被框頂截斷，dz 一律對 EG 本身取
    DZ[st] = np.where(~np.isnan(ze) & ~np.isnan(zu), zu - ze, 0.0)   # 使用者 V2 線（含未改部分）即為使用者認可的地面
    ZU[st] = zu
    print(f"樁距 {st:7.2f}：修正帶內與原線差 > 0.02 m 的點 {n_chg}，dz {DZ[st].min():+.2f}～{DZ[st].max():+.2f}")

s_grid = np.arange(s0, s1 + 1e-9, STEP); s_grid = np.r_[s_grid, s1] if s_grid[-1] < s1 else s_grid
new = []
for s in s_grid:
    i = np.searchsorted(STS, s) - 1; i = min(max(i, 0), len(STS) - 2); a, b = STS[i], STS[i + 1]; t = (s - a) / (b - a)
    dz = (1 - t) * DZ[a] + t * DZ[b]
    zabs = (1 - t) * ZU[a] + t * ZU[b]                      # 兩端皆有絕對值才有值
    ze = eg(np.full(len(XS), s), XS)
    z = np.where(~np.isnan(ze), ze + dz, zabs)
    c, _, n = frame(s)
    for x, zz in zip(XS[BAND], z[BAND]):
        if not np.isnan(zz): new.append((*(c[0] + n[0] * x), zz))
new = np.array(new)
sp, xp = station_offset(P0[:, :2]); h = STEP / 2
drop = (sp >= s0 - h) & (sp <= s1 + h) & (np.abs(xp) >= B_IN - h) & (np.abs(xp) <= B_OUT + h)
pts = np.vstack([P0[~drop], new])
t = mtri.Triangulation(pts[:, 0], pts[:, 1]); tri = t.triangles; PP = pts[tri][:, :, :2]
edge = np.max(np.stack([np.hypot(*(PP[:, i] - PP[:, (i + 1) % 3]).T) for i in range(3)]), axis=0); tri = tri[edge <= MAX_EDGE]
np.savez(out, points=pts, triangles=tri.astype(np.int32))
# QA：各刀修正帶內，新 EG 與使用者線的差
G1 = mtri.LinearTriInterpolator(mtri.Triangulation(pts[:, 0], pts[:, 1], tri), pts[:, 2])
lines = [f"EG 修正：來源 {os.path.basename(cpath(EF.get('src_tin', CFG['tin_npz'])))}；刪修正帶原點 {int(drop.sum())}、加修正格點 {len(new)}；"
         f"點數 {len(pts)}、三角形 {len(tri)}；修正帶 橫距 {B_IN}～{B_OUT} m、樁距 {s0:.2f}～{s1:.2f} m"]
for st in STS:
    u = np.vstack(E["user"][st]); m = np.abs(u[:, 0]) >= B_IN + 0.3
    if not m.any(): continue
    c, _, n = frame(st); p = c + np.outer(u[m, 0], n[0]); z1 = np.ma.filled(G1(p[:, 0], p[:, 1]), np.nan)
    lines.append(f"樁距 {st:7.2f} 修正帶：新 EG－使用者線 最大 {np.nanmax(np.abs(z1 - u[m, 1])):.3f} m")
open(os.path.splitext(out)[0] + "_qa.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n"); print("\n".join(lines))
print("EG：", out)
