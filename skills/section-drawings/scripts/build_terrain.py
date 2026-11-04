"""由測量圖 DXF 建原始地形 TIN，並以高程點抽驗。

用法：python -I build_terrain.py <案件設定.json>
輸入：等高線（POLYLINE，頂點帶 Z）＋高程點（INSERT，插入點帶 Z）；地物不帶 Z，不進 TIN。
輸出：tin_npz（points: N×3、triangles: M×3）與同名 _qa.txt 抽驗報告。
"""
import sys, os, json, math
import numpy as np
import ezdxf
import matplotlib.tri as mtri

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I build_terrain.py <案件設定.json>")
CFG_PATH = os.path.abspath(sys.argv[1])
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))   # 容許記事本存的 BOM
def cpath(p): return p if os.path.isabs(p) else os.path.join(os.path.dirname(CFG_PATH), p)
LY = CFG["layers"]; TR = CFG.get("terrain", {})
STEP = float(TR.get("densify_step", 1.0))       # 等高線沿線加密間距 (m)
MAX_EDGE = float(TR.get("max_edge", 40.0))      # 邊長超過此值的三角形視為測量範圍外 (m)

msp = ezdxf.readfile(cpath(CFG["src_dxf"])).modelspace()

def densify(pts, closed):
    p = [tuple(v) for v in pts]
    if closed: p.append(p[0])
    out = []
    for a, b in zip(p[:-1], p[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, math.ceil(L / STEP))
        for i in range(n):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2]))
    out.append(p[-1])
    return out

def contour_vertices(e):
    if e.dxftype() == "LWPOLYLINE":
        z = e.dxf.elevation
        return [(x, y, z) for x, y in e.get_points("xy")]
    return [tuple(v.dxf.location) for v in e.vertices]

cont_pts = []; n_cont = {}
for lay in (LY["contour_minor"], LY["contour_major"]):
    es = list(msp.query(f'POLYLINE LWPOLYLINE[layer=="{lay}"]')); n_cont[lay] = len(es)
    for e in es: cont_pts += densify(contour_vertices(e), e.is_closed)
cont_pts = np.array(cont_pts)
spot_layer = LY.get("spot_insert_layer", "0")
spots = np.array([tuple(e.dxf.insert) for e in msp.query(f'INSERT[layer=="{spot_layer}"]') if e.dxf.insert.z > 0])
if len(cont_pts) == 0: sys.exit("找不到等高線，請檢查 layers.contour_minor／contour_major")
if np.any(cont_pts[:, 2] == 0): print("警告：有等高線 Z=0，可能沒有帶高程")

def dedupe(a):
    k = np.round(a[:, :2], 3)
    _, idx = np.unique(k, axis=0, return_index=True)
    return a[np.sort(idx)]

def make_tri(pts):
    t = mtri.Triangulation(pts[:, 0], pts[:, 1])
    tri = t.triangles; P = pts[tri][:, :, :2]
    edge = np.max(np.stack([np.hypot(*(P[:, i] - P[:, (i + 1) % 3]).T) for i in range(3)]), axis=0)
    keep = edge <= MAX_EDGE
    return mtri.Triangulation(pts[:, 0], pts[:, 1], tri[keep]), int((~keep).sum())

# ---------- 抽驗：只用等高線建 TIN，回頭比對高程點 ----------
qa = {}
if len(spots):
    cp = dedupe(cont_pts); t0, _ = make_tri(cp)
    zi = np.ma.filled(mtri.LinearTriInterpolator(t0, cp[:, 2])(spots[:, 0], spots[:, 1]), np.nan)
    ok = ~np.isnan(zi); err = zi[ok] - spots[ok, 2]
    qa = dict(n_all=int(len(spots)), n_in=int(ok.sum()), rmse=round(float(np.sqrt(np.mean(err**2))), 3),
              mae=round(float(np.mean(np.abs(err))), 3), p90=round(float(np.percentile(np.abs(err), 90)), 3),
              maxabs=round(float(np.max(np.abs(err))), 3), bias=round(float(np.mean(err)), 3))
    worst = np.argsort(-np.abs(err))[:5]
    qa_worst = [(round(float(spots[ok][i, 0]), 2), round(float(spots[ok][i, 1]), 2), round(float(spots[ok][i, 2]), 2), round(float(zi[ok][i]), 2)) for i in worst]

# ---------- 正式 TIN：等高線＋高程點 ----------
allp = dedupe(np.vstack([cont_pts, spots]) if len(spots) else cont_pts)
tin, removed = make_tri(allp)
P = allp[tin.triangles]
area = float(np.sum(0.5 * np.abs((P[:, 1, 0]-P[:, 0, 0])*(P[:, 2, 1]-P[:, 0, 1]) - (P[:, 2, 0]-P[:, 0, 0])*(P[:, 1, 1]-P[:, 0, 1]))))
flat = int(np.sum(np.ptp(P[:, :, 2], axis=1) < 1e-9))

out = cpath(CFG["tin_npz"])
if os.path.exists(out): sys.exit(f"{out} 已存在，不覆蓋；請在設定檔改 tin_npz 檔名（加版次）")
np.savez(out, points=allp, triangles=tin.triangles.astype(np.int32))
lines = [f"等高線條數：{n_cont}", f"加密後等高線點：{len(cont_pts)}；高程點：{len(spots)}；去重後總點數：{len(allp)}",
         f"三角形：{len(tin.triangles)}（邊長 > {MAX_EDGE} m 刪除 {removed}；三頂點同高的平三角形 {flat}）；面積 {area:.0f} m²",
         f"高程範圍：{allp[:, 2].min():.3f}～{allp[:, 2].max():.3f} m",
         f"抽驗（只用等高線建 TIN，比對高程點，單位 m）：{qa}" if qa else "抽驗：沒有高程點，未抽驗"]
if qa: lines.append(f"誤差最大 5 點（x, y, 高程點, TIN）：{qa_worst}")
open(os.path.splitext(out)[0] + "_qa.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines)); print("TIN：", out)
