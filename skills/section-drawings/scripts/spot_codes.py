"""高程點代碼（DESC）分布：各代碼點離參考線的偏距、相對參考線高程的高差，以及依偏距分箱的路面橫坡。

用途：只有高程點、沒有等高線時，先看哪些代碼是非路面點（擋牆頂、既有溝底、屋台等），
回報使用者決定是否寫進 terrain.spot_exclude_codes，再跑 build_terrain_spots.py。
本程式只列表，不改任何檔案。

用法：python -I spot_codes.py <案件設定.json>
設定鍵：
  src_dxf、layers.spot_insert_layer、terrain.spot_desc_tag（預設 "DESC"）
  terrain.spot_ref_line  參考線 [[x0, y0], [x1, y1]]（通常是道路中心線兩端）；
                         沒填時取 alignment.dxf 的 alignment.centerline_layer 第一點與最後一點。
  terrain.spot_ref_band  參考線兩側統計範圍 (m)，預設 12
參考實作：P33 新社東山（2026-11-05）。
"""
import sys, os, json, collections
import numpy as np, ezdxf

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I spot_codes.py <案件設定.json>")
CFG_PATH = os.path.abspath(sys.argv[1])
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))
def cpath(p): return p if os.path.isabs(p) else os.path.join(os.path.dirname(CFG_PATH), p)
TR = CFG.get("terrain", {}); DESC = TR.get("spot_desc_tag", "DESC"); BAND = float(TR.get("spot_ref_band", 12.0))
if TR.get("spot_ref_line"):
    C0, C1 = [np.array(p, dtype=float) for p in TR["spot_ref_line"]]
else:
    AL = CFG["alignment"]
    e = ezdxf.readfile(cpath(AL["dxf"])).modelspace().query(f'LWPOLYLINE[layer=="{AL["centerline_layer"]}"]').first
    if e is None: sys.exit("找不到參考線：請填 terrain.spot_ref_line，或先建定線 DXF")
    p = np.array([tuple(q) for q in e.get_points("xy")]); C0, C1 = p[0], p[-1]

msp = ezdxf.readfile(cpath(CFG["src_dxf"])).modelspace()
L = np.hypot(*(C1 - C0)); tv = (C1 - C0) / L; nr = np.array([tv[1], -tv[0]])   # 偏距正向＝參考線前進方向右側
rec = []
for e in msp.query(f'INSERT[layer=="{CFG["layers"]["spot_insert_layer"]}"]'):
    if e.dxf.insert.z <= 0: continue
    a = {x.dxf.tag: x.dxf.text for x in e.attribs}
    p = np.array(e.dxf.insert)
    s = float(np.dot(p[:2] - C0, tv)); o = float(np.dot(p[:2] - C0, nr))
    rec.append((a.get(DESC, ""), s, o, p[2], e.dxf.name))
cl = sorted([(s, z) for d, s, o, z, n in rec if abs(o) < 1.0 and -5 < s < L + 5])
if len(cl) < 2: sys.exit("參考線 1 m 內的高程點不足 2 點，無法當高程基準")
cs, cz = np.array(cl).T
print(f"參考線長 {L:.2f} m；偏距正向＝前進方向右側；高差＝點高程－參考線（1 m 內高程點內插）")
by = collections.defaultdict(list)
for d, s, o, z, n in rec:
    if -5 < s < L + 5 and abs(o) < BAND: by[d].append((round(o, 1), round(z - np.interp(s, cs, cz), 2)))
for d in sorted(by, key=lambda k: -len(by[k])):
    v = np.array(by[d]); print(f"{DESC}={d!r:8} n={len(v):3}  偏距 {v[:,0].min():+.1f}～{v[:,0].max():+.1f}  相對參考線高 {v[:,1].min():+.2f}～{v[:,1].max():+.2f}  中位 {np.median(v[:,1]):+.2f}")
# 依偏距分箱，看路面橫坡；某一箱高差離散很大，通常是擋牆頂、溝底點混在路面點裡
for lo in np.arange(-8, 8, 1.0):
    v = [z - np.interp(s, cs, cz) for d, s, o, z, n in rec if lo <= o < lo + 1 and 0 < s < L]
    if v: print(f"偏距 {lo:+.0f}～{lo+1:+.0f} m：n={len(v)} 高差中位 {np.median(v):+.2f} 最小 {min(v):+.2f} 最大 {max(v):+.2f}")
