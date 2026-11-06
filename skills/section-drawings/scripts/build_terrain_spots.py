"""測量圖只有高程點、沒有等高線時，以高程點直接建原地形 TIN（EG），並以留一法抽驗。

與 build_terrain.py 的差異：沒有等高線可做「等高線 TIN 比對高程點」，改用留一法
（每次拿掉一點，由其餘點內插，再與該點比對）抽驗。
非路面點（擋牆頂、既有溝底等）可依高程點代碼剔除：先跑 spot_codes.py 看代碼分布，
請使用者確認要剔除哪些代碼，寫進 terrain.spot_exclude_codes（預設不剔除）。

用法：python -I build_terrain_spots.py <案件設定.json>
設定鍵：
  src_dxf、tin_npz、layers.spot_insert_layer、terrain.max_edge（沿用 build_terrain.py）
  terrain.spot_desc_tag       高程點代碼屬性標籤（預設 "DESC"）
  terrain.spot_elev_tag       高程屬性標籤，用來和插入點 Z 比對（預設 "ELEV"）
  terrain.spot_exclude_codes  要剔除的代碼清單（預設 []，P33 未剔除）
輸出：tin_npz（points: N×3、triangles: M×3）與同名 _qa.txt 抽驗報告。
參考實作：P33 新社東山（2026-11-05）。
"""
import sys, os, json, collections
import numpy as np
import ezdxf
import matplotlib.tri as mtri

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I build_terrain_spots.py <案件設定.json>")
CFG_PATH = os.path.abspath(sys.argv[1])
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))
def cpath(p): return p if os.path.isabs(p) else os.path.join(os.path.dirname(CFG_PATH), p)
LY = CFG["layers"]; TR = CFG.get("terrain", {})
MAX_EDGE = float(TR.get("max_edge", 40.0))
DESC = TR.get("spot_desc_tag", "DESC"); ELEV = TR.get("spot_elev_tag", "ELEV")
EXCL = set(TR.get("spot_exclude_codes", []))

out = cpath(CFG["tin_npz"])
if os.path.exists(out): sys.exit(f"{out} 已存在，不覆蓋；請在設定檔改 tin_npz 檔名（加版次）")

msp = ezdxf.readfile(cpath(CFG["src_dxf"])).modelspace()
ins = [e for e in msp.query(f'INSERT[layer=="{LY["spot_insert_layer"]}"]') if e.dxf.insert.z > 0]
if not ins: sys.exit("找不到高程點（INSERT，Z>0），請檢查 layers.spot_insert_layer")
def attr(e, tag):
    for a in e.attribs:
        if a.dxf.tag == tag: return a.dxf.text
    return None
codes = [attr(e, DESC) or "" for e in ins]
drop = np.array([c in EXCL for c in codes], dtype=bool)
n_drop = collections.Counter(c for c in codes if c in EXCL)
spots = np.array([tuple(e.dxf.insert) for e in ins])[~drop]
# 屬性高程與插入點 Z 是否一致
diff = []
for e in ins:
    t = attr(e, ELEV)
    try: diff.append(abs(float(t) - e.dxf.insert.z))
    except (TypeError, ValueError): pass
k = np.round(spots[:, :2], 3); _, idx = np.unique(k, axis=0, return_index=True); pts = spots[np.sort(idx)]

def make_tri(p):
    t = mtri.Triangulation(p[:, 0], p[:, 1]); tri = t.triangles; P = p[tri][:, :, :2]
    edge = np.max(np.stack([np.hypot(*(P[:, i] - P[:, (i + 1) % 3]).T) for i in range(3)]), axis=0)
    keep = edge <= MAX_EDGE
    return mtri.Triangulation(p[:, 0], p[:, 1], tri[keep]), int((~keep).sum())

tin, removed = make_tri(pts)
# 留一法抽驗（每點重建一次三角網；點數上千時要跑數分鐘）
err = []; rec = []
for i in range(len(pts)):
    q = np.delete(pts, i, axis=0); t, _ = make_tri(q)
    z = np.ma.filled(mtri.LinearTriInterpolator(t, q[:, 2])(pts[i:i+1, 0], pts[i:i+1, 1]), np.nan)[0]
    if not np.isnan(z): err.append(z - pts[i, 2]); rec.append((round(float(pts[i, 0]), 2), round(float(pts[i, 1]), 2), round(float(pts[i, 2]), 2), round(float(z), 2)))
err = np.array(err)
worst = [rec[j] for j in np.argsort(-np.abs(err))[:5]]
P = pts[tin.triangles]
area = float(np.sum(0.5 * np.abs((P[:, 1, 0]-P[:, 0, 0])*(P[:, 2, 1]-P[:, 0, 1]) - (P[:, 2, 0]-P[:, 0, 0])*(P[:, 1, 1]-P[:, 0, 1]))))
np.savez(out, points=pts, triangles=tin.triangles.astype(np.int32))
lines = [f"高程點（{LY['spot_insert_layer']} 圖層 INSERT，Z>0）：{len(ins)}；依代碼剔除 {int(drop.sum())}"
         f"{dict(n_drop) if n_drop else ''}；去重後 {len(pts)}；{ELEV} 屬性與插入點 Z 最大差 {round(max(diff), 3) if diff else 'NA'} m",
         f"三角形：{len(tin.triangles)}（邊長 > {MAX_EDGE} m 刪除 {removed}）；面積 {area:.0f} m²",
         f"高程範圍：{pts[:, 2].min():.3f}～{pts[:, 2].max():.3f} m",
         f"留一法抽驗 n={len(err)}：RMSE {np.sqrt(np.mean(err**2)):.3f}、MAE {np.mean(np.abs(err)):.3f}、P90 {np.percentile(np.abs(err), 90):.3f}、最大 {np.max(np.abs(err)):.3f}、偏差 {np.mean(err):.3f} m",
         f"誤差最大 5 點（x, y, 高程點, 內插）：{worst}"]
open(os.path.splitext(out)[0] + "_qa.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines)); print("TIN：", out)
