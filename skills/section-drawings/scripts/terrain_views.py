"""原始地形立體預覽：四個正向（東、南、西、北）＋四個斜角（東北、東南、西南、西北），帶等高線。

用法：python -I terrain_views.py <案件設定.json> [--stamp YYYYMMDD_HHMM]
TIN 以 terrain.view_grid_step（預設 0.1 m）的格網重新取樣後上色，格網越細越不會有鋸齒，但越慢。
輸出：preview_dir 下 8 張 PNG（A3 橫式 2 倍解析度）。
"""
import sys, os, json, datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.colors import LinearSegmentedColormap, LightSource, Normalize

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I terrain_views.py <案件設定.json> [--stamp YYYYMMDD_HHMM]")
CFG_PATH = os.path.abspath(sys.argv[1])
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))   # 容許記事本存的 BOM
def cpath(p): return p if os.path.isabs(p) else os.path.join(os.path.dirname(CFG_PATH), p)
stamp = sys.argv[sys.argv.index("--stamp") + 1] if "--stamp" in sys.argv else datetime.datetime.now().strftime("%Y%m%d_%H%M")
PREV = cpath(CFG.get("preview_dir", CFG["out_dir"])); os.makedirs(PREV, exist_ok=True)
PREFIX = CFG.get("file_prefix", ""); TR = CFG.get("terrain", {})
STEP = float(TR.get("view_grid_step", 0.25)); VEX = float(TR.get("view_vertical_exaggeration", 2.0)); ELEV = 35
plt.rcParams["font.family"] = ["Microsoft JhengHei", "sans-serif"]

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
    """等高線畫進地表顏色：與右、下相鄰格的高程跨過 interval 倍數的格子上色（線寬固定一格，陡坡不會糊成一片），背面自然被遮住"""
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
Zm = np.ma.array(Zf, mask=~valid)                                     # 測量範圍外不畫（不內插、不外插）
X0, Y0 = GX.min(), GY.min()
views = [("北", 90), ("東", 0), ("南", -90), ("西", 180), ("東北", 45), ("東南", -45), ("西南", -135), ("西北", 135)]
for name, az in views:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=100)
    ax = fig.add_axes([0.0, 0.0, 1.0, 0.93], projection="3d")
    ax.plot_surface(GX - X0, GY - Y0, Zm, facecolors=rgb, rstride=1, cstride=1, linewidth=0, antialiased=False, shade=False)
    ax.set_box_aspect((np.ptp(GX), np.ptp(GY), (np.nanmax(Zf) - np.nanmin(Zf)) * VEX), zoom=float(TR.get("view_zoom", 1.9)))
    ax.view_init(elev=ELEV, azim=az); ax.set_axis_off()
    fig.text(0.03, 0.95, f"原始地形立體圖｜由{name}向看（垂直放大 {VEX:g} 倍；格網 {STEP:g} m；等高線 首曲線 1 m、計曲線 5 m）", fontsize=20, color="#1F2D3A")
    out = os.path.join(PREV, f"{PREFIX}{stamp}_原始地形立體圖_{name}向.png")
    fig.savefig(out, dpi=200, facecolor="white"); plt.close(fig); print("PNG：", out)
