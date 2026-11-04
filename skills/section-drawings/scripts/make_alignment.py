"""由中心線（定線）與兩岸線產生樁號、斷面位置與法線，高程取 TIN。

用法：python -I make_alignment.py <案件設定.json>
輸入：alignment.dxf 裡的中心線圖層（一條折線）；岸線圖層（可多段，會自動依序接起來，可省略）。
輸出：alignment_npz
  cl  ：中心線每 1 m 取樣（x, y, z, 樁距），0K+000 在下游
  st  ：斷面樁距（每 20 m＋終點＋extra_stations）
  pts ：斷面中心點 (x, y, z)；tan：切線（往上游）；nrm：法線＝切線左轉 90°，指向面向下游的右岸
  W   ：面向下游右岸的岸線（nrm 正向那一側）；E：左岸的岸線
"""
import sys, os, json
import numpy as np
import ezdxf
import matplotlib.tri as mtri

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I make_alignment.py <案件設定.json>")
CFG_PATH = os.path.abspath(sys.argv[1])
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))   # 容許記事本存的 BOM
def cpath(p): return p if os.path.isabs(p) else os.path.join(os.path.dirname(CFG_PATH), p)
AL = CFG["alignment"]
SPACING = float(AL.get("spacing", 20.0))          # 斷面間距 (m)
TAN_H = 1.0                                       # 切線以前後各 1 m 求差分

d = np.load(cpath(CFG["tin_npz"]))
G = mtri.LinearTriInterpolator(mtri.Triangulation(d["points"][:, 0], d["points"][:, 1], d["triangles"]), d["points"][:, 2])
def zat(x, y): return np.ma.filled(G(np.atleast_1d(x), np.atleast_1d(y)), np.nan)

msp = ezdxf.readfile(cpath(AL.get("dxf", CFG["src_dxf"]))).modelspace()
def lines_on(layer):
    out = []
    for e in msp.query(f'LWPOLYLINE POLYLINE LINE[layer=="{layer}"]'):
        t = e.dxftype()
        if t == "LINE": P = [tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]
        elif t == "LWPOLYLINE": P = [tuple(p) for p in e.get_points("xy")]
        else: P = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if len(P) >= 2: out.append(np.array(P, float))
    return out

def chain(segs, start_near):
    """多段折線由最靠近 start_near 的端點開始，依最近端點逐段接起來"""
    segs = [s.copy() for s in segs]; out = None; cur = np.asarray(start_near, float)
    while segs:
        dist = [min(np.hypot(*(s[0] - cur)), np.hypot(*(s[-1] - cur))) for s in segs]
        s = segs.pop(int(np.argmin(dist)))
        if np.hypot(*(s[-1] - cur)) < np.hypot(*(s[0] - cur)): s = s[::-1]
        out = s if out is None else np.vstack([out, s]); cur = out[-1]
    keep = np.r_[True, np.hypot(*np.diff(out, axis=0).T) > 1e-6]
    return out[keep]

def arclen(p): return np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]

cls = lines_on(AL["centerline_layer"])
if not cls: sys.exit(f"圖層 {AL['centerline_layer']} 找不到中心線")
cl2 = chain(cls, cls[0][0])
z0, z1 = zat(*cl2[0]), zat(*cl2[-1])
if AL.get("downstream") == "end" or (AL.get("downstream") is None and z0[0] > z1[0]): cl2 = cl2[::-1]   # 0K+000 在下游
s_ = arclen(cl2); L = s_[-1]
t = np.arange(0, L, 1.0); t = np.r_[t, L] if t[-1] < L else t
xy = np.column_stack([np.interp(t, s_, cl2[:, 0]), np.interp(t, s_, cl2[:, 1])])
z = zat(xy[:, 0], xy[:, 1])
CL = np.column_stack([xy, z, t])

st = sorted(set([float(v) for v in np.arange(0, L, SPACING)] + [float(L)] + [float(v) for v in AL.get("extra_stations", []) if 0 <= v <= L]))
st = np.array(st)
def at(s): return np.array([np.interp(s, s_, cl2[:, 0]), np.interp(s, s_, cl2[:, 1])])
pts, tan = [], []
for s in st:
    a, b = at(min(s + TAN_H, L)), at(max(s - TAN_H, 0.0)); tv = (a - b) / np.hypot(*(a - b))
    p = at(s); pts.append([p[0], p[1], zat(*p)[0]]); tan.append(tv)
pts, tan = np.array(pts), np.array(tan); nrm = np.column_stack([-tan[:, 1], tan[:, 0]])

def side_bank(layer):
    segs = lines_on(layer) if layer else []
    return chain(segs, CL[0, :2]) if segs else np.zeros((0, 2))
W = side_bank(AL.get("bank_right_layer")); E = side_bank(AL.get("bank_left_layer"))
for nm, B in (("右岸", W), ("左岸", E)):                  # 檢查岸線是否在正確一側
    if len(B):
        mid = B[len(B)//2]; k = int(np.argmin(np.hypot(*(CL[:, :2] - mid).T)))
        sgn = np.dot(mid - CL[k, :2], nrm[np.argmin(np.abs(st - CL[k, 3]))])
        if (nm == "右岸") != (sgn > 0): print(f"警告：{nm}線看起來在另一側，請檢查 bank_left_layer／bank_right_layer")

out = cpath(CFG["alignment_npz"])
if os.path.exists(out): sys.exit(f"{out} 已存在，不覆蓋；請在設定檔改 alignment_npz 檔名（加版次）")
np.savez(out, cl=CL, st=st, pts=pts, tan=tan, nrm=nrm, W=W, E=E)
def sta(s):
    if abs(s - round(s)) < 1e-6: k = int(round(s)); return f"{k//1000}K+{k%1000:03d}"
    return f"{int(s)//1000}K+{s%1000:06.2f}"
print(f"全長 L={L:.2f} m；斷面 {len(st)} 刀：{sta(st[0])}～{sta(st[-1])}；中心線高程 {np.nanmin(z):.2f}～{np.nanmax(z):.2f} m")
if np.isnan(z).any(): print(f"警告：中心線有 {int(np.isnan(z).sum())} 點落在測量範圍外（高程無資料）")
print("岸線頂點數 右／左：", len(W), len(E)); print("定線：", out)
