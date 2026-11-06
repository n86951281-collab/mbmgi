"""（選用）自動配準：把每頁地籍線和測量圖的側溝、牆、房屋邊線做距離場比對，格點搜尋平移與旋轉（比例固定用標示比例尺）。
world = R(theta) * s * (p - pref) + wref
用法：python register.py <dump資料夾> <測量圖.dxf> <輸出 reg_auto.json> <overlay_config.json>
注意：地籍線與現況邊線本來就不一定重合，結果只當粗配準或交叉檢核；正式定位用 reg2.py 的控制點相似轉換。
P33 實測平均距離 0.85 m、旋轉 −0.36°／+0.14°，與網頁控制點結果差約 1 m 以上。"""
import sys, json, math, pathlib
import numpy as np, ezdxf
from common import load_config, scale_m_per_pt, survey_lines

D = pathlib.Path(sys.argv[1]); dxf = sys.argv[2]; outj = pathlib.Path(sys.argv[3]); CFG = load_config(sys.argv[4])
RC = CFG['registration']
S = scale_m_per_pt(CFG['pdf']['scale_denominator'])          # 1/3000 → 1.0583 m per pt
res = json.loads((D / 'parsed.json').read_text(encoding='utf-8'))

# ---- survey linework raster distance field
doc = ezdxf.readfile(dxf); msp = doc.modelspace()
skip = set(CFG['survey'].get('skip_layers', [])) | set(RC.get('auto_extra_skip_layers', []))
segs = []
for L, p in survey_lines(msp, skip, RC.get('auto_skip_layer_prefixes', []), close_lw=False):
    segs += list(zip(p, p[1:]))
segs = np.array(segs)
X0, Y0 = segs[..., 0].min() - 20, segs[..., 1].min() - 20
X1, Y1 = segs[..., 0].max() + 20, segs[..., 1].max() + 20
R = 0.25
nx, ny = int((X1 - X0) / R) + 1, int((Y1 - Y0) / R) + 1
occ = np.zeros((ny, nx), bool)
for (a, b) in segs:
    n = int(np.hypot(*(b - a)) / (R / 2)) + 2
    t = np.linspace(0, 1, n)
    xs = ((a[0] + (b[0] - a[0]) * t - X0) / R).astype(int); ys = ((a[1] + (b[1] - a[1]) * t - Y0) / R).astype(int)
    occ[ys, xs] = True
# chamfer 距離（兩次正反掃描）
dist = np.where(occ, 0.0, 1e6)
for _ in range(2):
    for y in range(1, ny):
        dist[y] = np.minimum(dist[y], dist[y - 1] + 1)
        dist[y, 1:] = np.minimum(dist[y, 1:], dist[y - 1, :-1] + 1.4142)
        dist[y, :-1] = np.minimum(dist[y, :-1], dist[y - 1, 1:] + 1.4142)
    for y in range(ny - 2, -1, -1):
        dist[y] = np.minimum(dist[y], dist[y + 1] + 1)
        dist[y, 1:] = np.minimum(dist[y, 1:], dist[y + 1, :-1] + 1.4142)
        dist[y, :-1] = np.minimum(dist[y, :-1], dist[y + 1, 1:] + 1.4142)
    for x in range(1, nx):
        dist[:, x] = np.minimum(dist[:, x], dist[:, x - 1] + 1)
    for x in range(nx - 2, -1, -1):
        dist[:, x] = np.minimum(dist[:, x], dist[:, x + 1] + 1)
dist *= R

def page_pts(page):
    pts = []
    for p in res[page]['paths']:
        if p['op'] != 'S' or p['lw'] < CFG['pdf'].get('min_line_width', 0.05): continue
        for a, b in zip(p['pts'], p['pts'][1:]):
            a, b = np.array(a), np.array(b); L = np.hypot(*(b - a)) * S
            n = max(2, int(L / 0.5) + 1)
            pts.append(a + np.outer(np.linspace(0, 1, n), b - a))
    return np.unique(np.round(np.vstack(pts), 3), axis=0)

def xf(P, pref, wref, th):
    c, s = math.cos(th), math.sin(th)
    q = (P - pref) * S
    return np.c_[c * q[:, 0] - s * q[:, 1], s * q[:, 0] + c * q[:, 1]] + wref

CAP = 1.5
def cost(W):
    ix = ((W[:, 0] - X0) / R).astype(int); iy = ((W[:, 1] - Y0) / R).astype(int)
    ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
    dd = dist[iy[ok], ix[ok]]
    near = dd < 6.0                       # only cadastral points inside surveyed corridor
    if near.sum() < 50: return 9, 0
    return np.minimum(dd[near], CAP).mean(), int(near.sum())

init = {k: (v['pref'], v['wref']) for k, v in (RC.get('auto_init') or RC['init']).items()}
result = {}
for page, (pref, wref) in init.items():
    P = page_pts(page); pref = np.array(pref); wref = np.array(wref)
    best = (9, None)
    for th in np.radians(np.arange(-2, 2.01, 0.25)):
        for dx in np.arange(-8, 8.01, 0.5):
            for dy in np.arange(-8, 8.01, 0.5):
                c, n = cost(xf(P, pref, wref + (dx, dy), th))
                if c < best[0]: best = (c, (th, dx, dy, n))
    th, dx, dy, n = best[1]
    for step_t, step in ((0.05, 0.1), (0.01, 0.02)):        # refine
        b2 = best
        for t2 in np.radians(np.arange(-5, 5.01) * step_t) + th:
            for ddx in np.arange(-5, 5.01) * step + dx:
                for ddy in np.arange(-5, 5.01) * step + dy:
                    c, nn = cost(xf(P, pref, wref + (ddx, ddy), t2))
                    if c < b2[0]: b2 = (c, (t2, ddx, ddy, nn))
        best = b2; th, dx, dy, n = best[1]
    result[page] = {'pref': pref.tolist(), 'wref': (wref + (dx, dy)).tolist(), 'theta_deg': math.degrees(th),
                    'scale_m_per_pt': S, 'mean_capped_dist_m': round(float(best[0]), 3), 'n_pts_used': n,
                    'source': 'register.py auto grid search vs survey linework'}
    print(page, result[page])
outj.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')
