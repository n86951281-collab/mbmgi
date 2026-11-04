"""原始地形立體預覽：四個正向（東、南、西、北）＋四個斜角（東北、東南、西南、西北），帶等高線。

用法：python -I terrain_views.py <案件設定.json> [--stamp YYYYMMDD_HHMM]
TIN 以 terrain.view_grid_step（預設 0.1 m）的格網重新取樣，每格依光影上色、等高線畫進格子顏色，
再以正射投影由遠到近疊畫（背面自然被遮住）。不用 matplotlib 3D，0.1 m 格網也能在數十秒內畫完一張。
輸出：preview_dir 下 8 張 PNG（A3 橫式，3308×2339）。
"""
import sys, os, json, datetime, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap, LightSource, Normalize

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I terrain_views.py <案件設定.json> [--stamp YYYYMMDD_HHMM]")
CFG_PATH = os.path.abspath(sys.argv[1])
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))   # 容許記事本存的 BOM
def cpath(p): return p if os.path.isabs(p) else os.path.join(os.path.dirname(CFG_PATH), p)
stamp = sys.argv[sys.argv.index("--stamp") + 1] if "--stamp" in sys.argv else datetime.datetime.now().strftime("%Y%m%d_%H%M")
PREV = cpath(CFG.get("preview_dir", CFG["out_dir"])); os.makedirs(PREV, exist_ok=True)
PREFIX = CFG.get("file_prefix", ""); TR = CFG.get("terrain", {})
STEP = float(TR.get("view_grid_step", 0.1)); VEX = float(TR.get("view_vertical_exaggeration", 2.0)); ELEV = 35
plt.rcParams["font.family"] = ["Microsoft JhengHei", "sans-serif"]

# ---------- TIN 取樣成格網（測量範圍外為空）----------
d = np.load(cpath(CFG["tin_npz"])); P, T = d["points"], d["triangles"]
X, Y, Z = P[:, 0], P[:, 1], P[:, 2]
tin = mtri.Triangulation(X, Y, T)
gx = np.arange(X.min(), X.max(), STEP); gy = np.arange(Y.min(), Y.max(), STEP)
GX, GY = np.meshgrid(gx, gy)
GZ = mtri.LinearTriInterpolator(tin, Z)(GX, GY)
valid = ~np.ma.getmaskarray(GZ)
ri = np.where(valid.any(axis=1))[0]; ci = np.where(valid.any(axis=0))[0]          # 裁到有資料的範圍
GX, GY, GZ, valid = (a[ri[0]:ri[-1]+1, ci[0]:ci[-1]+1] for a in (GX, GY, GZ, valid))
Zf = np.ma.filled(GZ, np.nan)

def crossing(interval):
    """與右、下相鄰格的高程跨過 interval 倍數的格點：等高線（線寬固定一格，陡坡不會糊成一片）"""
    with np.errstate(invalid="ignore"):
        k = np.floor(Zf / interval)
    on = np.zeros(Zf.shape, bool)
    on[:, :-1] |= k[:, :-1] != k[:, 1:]; on[:-1, :] |= k[:-1, :] != k[1:, :]
    return on & valid
on1, on5 = crossing(1.0), crossing(5.0)                                # 首曲線 1 m、計曲線 5 m
cmap = LinearSegmentedColormap.from_list("bg", ["#EEF2F6", "#B9C7D4", "#7C93A8", "#3E5C76"])   # 灰藍單色
rgb = LightSource(azdeg=315, altdeg=40).shade(np.nan_to_num(Zf, nan=float(Z.min())), cmap=cmap, norm=Normalize(Z.min(), Z.max()),
                                              blend_mode="soft", vert_exag=VEX, dx=STEP, dy=STEP)
rgb[on1] = matplotlib.colors.to_rgba("#33475B"); rgb[on5] = matplotlib.colors.to_rgba("#1F2D3A")

# ---------- 格子：四角都在測量範圍內才畫，顏色取左下角格點 ----------
cell = valid[:-1, :-1] & valid[1:, :-1] & valid[:-1, 1:] & valid[1:, 1:]
I, J = np.nonzero(cell)
Xc = GX - GX.min(); Yc = GY - GY.min(); Zc = (Zf - np.nanmin(Zf)) * VEX
def corners(A): return np.stack([A[I, J], A[I, J+1], A[I+1, J+1], A[I+1, J]], axis=1)
CX, CY, CZ = corners(Xc), corners(Yc), corners(Zc)
COL = rgb[I, J]
print(f"格網 {STEP:g} m：{len(I)} 格")

views = [("北", 90), ("東", 0), ("南", -90), ("西", 180), ("東北", 45), ("東南", -45), ("西南", -135), ("西北", 135)]
e = math.radians(ELEV)
for name, az in views:
    a = math.radians(az)
    cam = np.array([math.cos(a)*math.cos(e), math.sin(a)*math.cos(e), math.sin(e)])   # 指向觀察者
    rgt = np.array([-math.sin(a), math.cos(a), 0.0]); up = np.cross(cam, rgt)
    u = CX*rgt[0] + CY*rgt[1] + CZ*rgt[2]; v = CX*up[0] + CY*up[1] + CZ*up[2]
    depth = (CX*cam[0] + CY*cam[1] + CZ*cam[2]).mean(axis=1)
    order = np.argsort(depth)                                           # 由遠到近疊畫
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.86]); ax.set_aspect("equal"); ax.axis("off")
    ax.add_collection(PolyCollection(np.stack([u, v], axis=2)[order], facecolors=COL[order], edgecolors="face", linewidths=0.2, antialiased=False))
    ax.set_xlim(u.min(), u.max()); ax.set_ylim(v.min(), v.max())
    fig.text(0.03, 0.95, f"原始地形立體圖｜由{name}向看（垂直放大 {VEX:g} 倍；格網 {STEP:g} m；等高線 首曲線 1 m、計曲線 5 m）", fontsize=20, color="#1F2D3A")
    out = os.path.join(PREV, f"{PREFIX}{stamp}_原始地形立體圖_{name}向.png")
    fig.savefig(out, facecolor="white"); plt.close(fig); print("PNG：", out)
