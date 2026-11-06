"""地籍套繪圖 L-01（ditch-design，由 P33 cadastral_sheet 一般化）：A3 橫式 1/500，定線轉正，0K+000 在左。
只放地籍線（252 灰色虛線）、新設構造物、臨時擋土、房屋（SF）；畫面內每一塊地號都標（地籍線成面、避開設計線）。
地籍來源：cadastre.dxf 的圖塊 cadastre.block（地籍線 LWPOLYLINE、地號 TEXT，已為 TWD97）。
  先用 SKILL cadastre-overlay 把謄本 PDF 以兩個以上控制點相似轉換套到測量圖，CAD 調整後 DXFOUT 成這份 DXF。
用法：python cadastral_sheet.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
"""
import sys, os, json, math, datetime
import numpy as np
import ezdxf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
S = dd.sheet_module()
from p33_sheet import Sheet, frame, tw, tbox, PT, TXT
import plan_base as B

CFG = B.CFG; P_ = B.P_; stamp = dd.stamp
OUT = dd.OUT; PRE = dd.PRE; PREV = os.path.join(OUT, "07_地籍套繪")
if not CFG.get("cadastre", {}).get("dxf"): raise SystemExit("未設 cadastre.dxf（沒有地籍資料就不出 L-01）")
base = f"{PRE}{stamp}_A3_地籍套繪圖_1-500_{dd.ver('cadastral')}_TWD97_GENIE"
LAYERS = {"圖框": (7, None, "#000000", 0.50), "圖標欄": (7, None, "#000000", 0.35),
          "地物": (253, None, "#BDBDBD", 0.15), "SF地物": (253, None, "#C8C8C8", 0.12), "既有側溝": (252, None, "#8A8A8A", 0.25),
          "地籍線": (252, "DASHED", "#7A7A7A", 0.25), "鋼軌樁": (7, None, "#000000", 0.30), "中心線1": (22, "CENTER", "#000000", 0.18),
          "設計側溝": (7, None, "#000000", 0.60), "集水井": (7, None, "#000000", 0.60), "標註": (7, None, "#000000", 0.18),
          "圖例表": (7, None, "#000000", 0.18), "文字": (7, None, "#000000", 0.0)}

# ---------- 地籍 ----------
cd = ezdxf.readfile(dd.src(CFG["cadastre"]["dxf"]))
blk = cd.blocks[CFG["cadastre"].get("block", "0-地籍圖")]
CAD_L = [np.array([tuple(p)[:2] for p in e.get_points("xy")]) for e in blk if e.dxftype() == "LWPOLYLINE"]
CAD_T = []
for e in blk:
    if e.dxftype() != "TEXT": continue
    h = e.dxf.height; r = math.radians(e.dxf.rotation); w = sum(h if ord(c) > 255 else 0.6 * h for c in e.dxf.text)
    ip = np.array(e.dxf.insert)[:2]; d = np.array([w / 2, h / 2])
    CAD_T.append((ip + np.array([d[0] * math.cos(r) - d[1] * math.sin(r), d[0] * math.sin(r) + d[1] * math.cos(r)]), e.dxf.text))
SECT = [(p, t) for p, t in CAD_T if not any(ch.isdigit() for ch in t)]       # 段名
NOS = [(p, t) for p, t in CAD_T if any(ch.isdigit() for ch in t)]
print(f"地籍線 {len(CAD_L)}、地號 {len(NOS)}、段名 {[t for _, t in SECT]}")

# ---------- 圖紙 ----------
K = 2.0; VIEW = (16.0, 52.0, 404.0, 262.0); VY = 157.0; SA, SB = CFG["alignment"].get("plan_range", [-30.0, B.Lc + 30.0])
T = B.make_T(B.C0, VIEW[0] + 8.0 - SA * K, VY, K)
sh = Sheet("地籍套繪圖"); frame(sh, sh.name, ["1/500"], "L-01")
V = (VIEW[0], VIEW[1], VIEW[2], VIEW[3])
# 2026-11-06 使用者：只放地籍線（灰色虛線）＋新設構造物＋臨時擋土＋房屋（SF）；道路邊線、既有側溝、既有集水井不放
for P, lay in B.FEATS:
    if lay != "SF地物": continue
    for q in B.clip(T(P), V): sh.poly(q, lay)
for P in CAD_L:
    for q in B.clip(T(P), V): sh.poly(q, "地籍線", "DASHED")
for key in B.KEYS:

    polys, L, u, n = B.ditch_polys(key)
    for P, lay in polys:
        for q in B.clip(T(P), V): sh.poly(q, lay)
    for Ln in B.pile_lines(key):
        for q in B.clip(T(Ln), V): sh.poly(q, "鋼軌樁")
# 地號：地籍線成面（shapely polygonize），視窗內看得到的每一筆地都標地號（標在可見範圍內，避開設計線與其他地號）
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import polygonize, unary_union
from shapely.prepared import prep
lines_p = [LineString(T(P)) for P in CAD_L if len(P) > 1]
parcels = list(polygonize(unary_union(lines_p)))
VB = box(*V)
design = [it[1] for it in sh.items if it[0] == "poly" and it[2] in ("設計側溝", "集水井", "鋼軌樁")]
DS = unary_union([LineString(P) for P in design]).buffer(1.0)
NOS_P = [(Point(*T(p[None, :])[0]), t) for p, t in NOS]
placed = []; miss = []; nolab = 0; done = 0; multi = []
for pg in parcels:
    vis = pg.intersection(VB)
    if vis.is_empty or vis.area < 6.0: continue                     # 可見面積 < 6 mm²（約 1.5 m²）不標
    labq = [(q, t) for q, t in NOS_P if pg.contains(q)]
    if not labq: nolab += 1; miss.append(vis.representative_point()); continue
    if len(labq) > 1:                                                  # 地籍線未閉合致多筆地併成一面：各地號就原位標
        multi.extend([(q, t, vis) for q, t in labq]); continue
    s_ = labq[0][1]; w = tw(s_, PT); ok = False
    pv = prep(vis.buffer(-0.5)) if vis.buffer(-0.5).area > 0 else prep(vis)
    c0 = vis.representative_point(); cand = [(c0.x, c0.y)]
    bx = vis.bounds
    for gx in np.linspace(bx[0], bx[2], 9):
        for gy in np.linspace(bx[1], bx[3], 7): cand.append((gx, gy))
    cand.sort(key=lambda q: (q[0] - c0.x) ** 2 + (q[1] - c0.y) ** 2)
    DS2 = unary_union([LineString(P) for P in design]).buffer(0.3)
    for strict in (True, False):                                      # 先放地界內縮 0.5 mm 內；不行再放寬到整個可見範圍
        for x, y in cand:
            bb = box(x - w / 2, y - PT / 2, x + w / 2, y + PT / 2)
            if strict and (not pv.contains(bb) or bb.intersects(DS)): continue
            if not strict and (not vis.contains(Point(x, y)) or bb.intersects(DS2) or not VB.contains(bb)): continue
            if any(bb.buffer(1.0).intersects(r) for r in placed): continue
            sh.text(x, y, s_, "center", PT); placed.append(bb); ok = True; break
        if ok: break
    if not ok:                                                        # 狹長地：引線拉到地外空白處
        for dy in (8, -8, 12, -12, 16, -16, 20, -20):
            for dx in (0, 8, -8, 16, -16):
                x, y = c0.x + dx, c0.y + dy; bb = box(x - w / 2, y - PT / 2, x + w / 2, y + PT / 2)
                if not VB.contains(bb) or bb.intersects(DS2) or any(bb.intersects(r) for r in placed): continue
                sh.text(x, y, s_, "center", PT); placed.append(bb)
                ey = y - np.sign(dy) * PT / 2; sh.line(c0.x, c0.y, x, ey, "標註")
                sh.poly([(c0.x + 0.5, c0.y), (c0.x, c0.y + 0.5), (c0.x - 0.5, c0.y), (c0.x, c0.y - 0.5), (c0.x + 0.5, c0.y)], "標註")
                ok = True; break
            if ok: break
    if ok: done += 1
    else: miss.append(c0); print("   放不下：", s_)
DS2 = unary_union([LineString(P) for P in design]).buffer(0.3)
for q, t, vis in multi:                                               # 原位（地號文字點）附近找空位；原位在視窗外者標在可見範圍內
    if VB.distance(q) > 60.0: continue                                # 地號點離視窗 > 60 mm（30 m）：該筆地不在視窗內
    w = tw(t, PT); ok = False
    if VB.contains(q): cand = [(q.x + dx, q.y + dy) for dx, dy in ((0, 0), (0, 3), (0, -3), (4, 0), (-4, 0), (0, 6), (0, -6), (6, 3), (-6, -3))]
    else:
        near = vis.exterior.interpolate(vis.exterior.project(q)) if vis.geom_type == "Polygon" else vis.representative_point()
        bx = vis.bounds; cand = sorted([(gx, gy) for gx in np.linspace(bx[0], bx[2], 15) for gy in np.linspace(bx[1], bx[3], 9) if vis.contains(Point(gx, gy))],
                                       key=lambda c: (c[0] - near.x) ** 2 + (c[1] - near.y) ** 2)
    for x, y in cand:
        bb = box(x - w / 2, y - PT / 2, x + w / 2, y + PT / 2)
        if not VB.contains(bb) or bb.intersects(DS2) or any(bb.buffer(1.0).intersects(r) for r in placed): continue
        sh.text(x, y, t, "center", PT); placed.append(bb); ok = True; done += 1; break
    if not ok: print("   放不下（原位）：", t)
print(f"視窗內地籍面 {sum(1 for pg in parcels if not pg.intersection(VB).is_empty)}：已標地號 {done}、無地號資料 {nolab}、放不下 {len(miss) - nolab}")
for p, t in SECT:
    q = T(p[None, :])[0]
    if V[0] + 30 < q[0] < V[2] - 30 and V[1] + 5 < q[1] < V[3] - 5: sh.text(q[0], q[1], t, "center", PT)
# 指北、圖例
nvec = np.array([np.array([0, 1]) @ B.tv, np.array([0, 1]) @ B.nv]); nvec /= np.hypot(*nvec)
cN = np.array([30.0, 272.0]); tip = cN + nvec * 6; tail = cN - nvec * 6; pn = np.array([-nvec[1], nvec[0]])
sh.line(*tail, *tip, "標註"); sh.poly([tip - nvec * 3 + pn * 1.5, tip, tip - nvec * 3 - pn * 1.5], "標註")
sh.text(*(tip + nvec * 4.5), "N", "center", PT)
x = 60.0; y = 274.0
for lay, lab in (("地籍線", "地籍線"), ("設計側溝", f"新設箱涵式側溝 {P_['W']*100:.0f}×{P_['H']*100:.0f}"), ("集水井", "新設集水井"),
                 ("鋼軌樁", "臨時鋼軌樁"), ("SF地物", "房屋")):
    sh.line(x, y, x + 10, y, lay, "DASHED" if lay == "地籍線" else None); x += 12.5; sh.text(x, y, lab, "left", PT); x += tw(lab, PT) + 7
sh.text(x + 2, y, "123　地號", "left", PT)
notes = ["說明：1. 地籍資料套繪僅供參考，用地界線以地政機關鑑界成果為準。",
         f"2. 地段：{'、'.join(sorted(set(t for _, t in SECT)))}；施工範圍如涉及私有土地，應先取得土地使用同意始得施工。"]
for k, t in enumerate(notes): sh.text(18.0, 45.0 - 7.5 * k, t, "left", PT)

S.check(sh, ("設計側溝", "集水井", "鋼軌樁"))
dxf, pdf, pngs = S.save([sh], LAYERS, OUT, PREV, base)
print("DXF：", dxf); print("PDF：", pdf); print("PNG：", pngs)
