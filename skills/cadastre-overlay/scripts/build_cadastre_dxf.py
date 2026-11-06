"""把定位後的地籍線與地號寫成獨立 DXF（TWD97，公尺）。
圖層：地籍線（地籍界線）、地號（地號、段名、引線）；圖層名、顏色、線型、字型、字高取設定檔 output。
地號避讓：留在自己的地塊內、不壓地籍線、不和其他文字互疊；放不下的窄長條地用引線標，沿道路（road_axis_e）的往路外側標。
用法：python build_cadastre_dxf.py <dump資料夾> <reg.json> <輸出 cadastre.dxf> <overlay_config.json>"""
import sys, json, pathlib
import numpy as np, ezdxf
from common import load_config, load_reg, xf

D = pathlib.Path(sys.argv[1]); reg = load_reg(sys.argv[2]); out = sys.argv[3]; CFG = load_config(sys.argv[4])
PC, OC = CFG['pdf'], CFG['output']
res = json.loads((D / 'parsed.json').read_text(encoding='utf-8'))
SECTION = {pg: v['section_full'] for pg, v in PC['pages'].items()}
LAYER_LINE, LAYER_LOT = list(OC['layers'])[:2]            # 第 1 個＝地籍線、第 2 個＝地號
TXT_H = OC['text_height_m']                                # m; 2.5 ≈ 14 pt at 1/500
SEC_H = OC.get('section_text_height_m', 2 * TXT_H)
c0 = PC['map_clip_pt']; CLIP = (c0[0], c0[1], c0[2], c0[3])  # map window on the PDF page (pt)
RGB, TOL = PC['cadastral_stroke_rgb'], PC.get('rgb_tol', 0.01)
MINW, LBL = PC.get('min_line_width', 0.05), PC.get('label_max_size_pt', 6)
ST = OC['text_style']

doc = ezdxf.new('R2018', setup=False); doc.header['$INSUNITS'] = 6
for name, a in OC['layers'].items():
    lt = a.get('linetype', 'Continuous')
    if lt not in doc.linetypes:
        from ezdxf.tools.standards import setup_linetypes
        setup_linetypes(doc)
    doc.layers.add(name, color=a['color'], linetype=lt)
doc.styles.add(ST['name'], font=ST['font']).dxf.bigfont = ST['bigfont']
doc.styles.get(ST['name']).dxf.width = ST['width']
msp = doc.modelspace()
inside = lambda p: CLIP[0] - 0.5 <= p[0] <= CLIP[2] + 0.5 and CLIP[1] - 0.5 <= p[1] <= CLIP[3] + 0.5
is_cad = lambda col: col and all(abs(col[i] - RGB[i]) <= TOL for i in range(3))
stats = {}
for page, r in reg.items():
    seen = set(); nl = 0
    for p in res[page]['paths']:
        if p['op'] != 'S' or p['lw'] < MINW or not is_cad(p['col']): continue
        pts = [q for q in p['pts'] if inside(q)]
        if len(pts) < 2 or len(pts) != len(p['pts']): continue
        # drop zero-length duplicates & duplicate shared edges
        W = xf(pts, r); W = W[np.r_[True, np.hypot(*np.diff(W, axis=0).T) > 1e-3]]
        key = tuple(np.round(W, 2).ravel())
        if len(W) < 2 or key in seen or tuple(np.round(W[::-1], 2).ravel()) in seen: continue
        seen.add(key)
        closed = len(W) > 3 and np.hypot(*(W[0] - W[-1])) < 1e-3
        msp.add_lwpolyline([tuple(v) for v in (W[:-1] if closed else W)], close=closed, dxfattribs={'layer': LAYER_LINE})
        nl += 1
    nt = 0
    for t in res[page]['texts']:
        if t['size'] >= LBL or not inside((t['x'], t['y'])): continue
        W = xf([(t['x'], t['y'])], r)[0]
        msp.add_text(t['text'].strip(), height=TXT_H, dxfattribs={'layer': LAYER_LOT, 'style': ST['name'], 'width': ST['width']}) \
           .set_placement((W[0], W[1]))
        nt += 1
    stats[page] = {'section': SECTION[page], 'polylines': nl, 'lot_labels': nt}
# ---- label de-confliction: keep each lot number inside its own parcel, off every boundary line
polys = [np.array([tuple(v[:2]) for v in e.get_points('xy')]) for e in msp.query('LWPOLYLINE') if e.closed]
segs = np.vstack([np.c_[p, np.roll(p, -1, axis=0)] for p in polys] +
                 [np.c_[np.array([tuple(v[:2]) for v in e.get_points('xy')])[:-1], np.array([tuple(v[:2]) for v in e.get_points('xy')])[1:]]
                  for e in msp.query('LWPOLYLINE') if not e.closed])
CW = 0.9 * ST['width']          # GENISO char width factor * width factor
def tbox(x, y, n, rot, h):
    w = n * h * CW
    if rot == 0: return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]])
    return np.array([[x, y], [x, y + w], [x - h, y + w], [x - h, y]])     # 90°: text reads upward
def clear(B):
    x0, y0 = B.min(0) - 0.15; x1, y1 = B.max(0) + 0.15
    m = (np.maximum(segs[:, 0], segs[:, 2]) >= x0) & (np.minimum(segs[:, 0], segs[:, 2]) <= x1) & \
        (np.maximum(segs[:, 1], segs[:, 3]) >= y0) & (np.minimum(segs[:, 1], segs[:, 3]) <= y1)
    if not m.any(): return True
    s = segs[m]; t = np.linspace(0, 1, 25)[:, None]
    for a in s:
        P = a[:2] + (a[2:] - a[:2]) * t
        if np.any((P[:, 0] > x0) & (P[:, 0] < x1) & (P[:, 1] > y0) & (P[:, 1] < y1)): return False
    return True
def crosses(p, q):
    """True if segment p-q properly intersects any cadastral segment."""
    a, b = segs[:, :2], segs[:, 2:]
    def orient(u, v, w): return (v[..., 0] - u[..., 0]) * (w[..., 1] - u[..., 1]) - (v[..., 1] - u[..., 1]) * (w[..., 0] - u[..., 0])
    P = np.broadcast_to(p, a.shape); Q = np.broadcast_to(q, a.shape)
    o1, o2 = orient(P, Q, a), orient(P, Q, b); o3, o4 = orient(a, b, P), orient(a, b, Q)
    return bool(np.any((o1 * o2 < 0) & (o3 * o4 < 0)))
placed = []
def free(B):
    lo, hi = B.min(0) - 0.3, B.max(0) + 0.3
    return clear(B) and not any(np.all((lo < tb.max(0)) & (hi > tb.min(0))) for tb in placed)
ROAD_E = OC.get('road_axis_e')          # e.g. P33 永興段／協中段 section line along 東山街
ROAD_BAND = OC.get('road_axis_band_m', 15)
def place(e, ref, h, allow_leader=True):
    """Move TEXT e to the nearest free spot reachable from ref without crossing a boundary; else leader."""
    n = len(e.dxf.text); best = None
    for r in np.arange(0, 25.01, 0.5):
        ring = [(dx, dy) for dx in np.arange(-r, r + 0.01, 0.5) for dy in np.arange(-r, r + 0.01, 0.5) if max(abs(dx), abs(dy)) == r]
        for rot in (0, 90):
            for dx, dy in ring:
                B = tbox(0, 0, n, rot, h); c = ref + (dx, dy) - B.mean(0); B = B + c
                if crosses(ref, B.mean(0)) or not free(B): continue
                d = np.hypot(dx, dy) + (2 if rot else 0)
                if best is None or d < best[0]: best = (d, c, rot)
        if best and best[0] <= r: break
    if best:
        e.dxf.insert = tuple(best[1]); e.dxf.rotation = best[2]; return 'moved'
    if not allow_leader: return 'unresolved'
    for r in np.arange(3, 40.01, 0.5):
        for dx in np.arange(-r, r + 0.01, 0.5):
            for dy in np.arange(-r, r + 0.01, 0.5):
                if max(abs(dx), abs(dy)) != r: continue
                if ROAD_E is not None and abs(ref[0] - ROAD_E) < ROAD_BAND and dx * (ref[0] - ROAD_E) <= 0: continue   # along the road: put text on the outer side
                B = tbox(0, 0, n, 0, h); c = ref + (dx, dy) - B.mean(0); B = B + c
                tip = np.clip(ref, B.min(0), B.max(0))
                # leader must not run through another label
                P = ref + (tip - ref) * np.linspace(0.05, 0.95, 15)[:, None]
                if not free(B) or any(np.any(np.all((P > tb.min(0)) & (P < tb.max(0)), axis=1)) for tb in placed): continue
                msp.add_line(tuple(ref), tuple(tip), dxfattribs={'layer': LAYER_LOT})
                e.dxf.insert = tuple(c); e.dxf.rotation = 0; return 'leader'
    return 'unresolved'

labels = [e for e in msp.query('TEXT') if e.dxf.layer == LAYER_LOT]
refs = {id(e): np.array([e.dxf.insert.x + 0.3, e.dxf.insert.y + 0.3]) for e in labels}   # start of the land-office label: inside its lot
ok0 = [e for e in labels if clear(tbox(e.dxf.insert.x, e.dxf.insert.y, len(e.dxf.text), 0, TXT_H))]
todo = [e for e in labels if e not in ok0]
outcome = {}
for e in ok0:                                            # keep untouched labels, unless they collide with one already kept
    B = tbox(e.dxf.insert.x, e.dxf.insert.y, len(e.dxf.text), 0, TXT_H)
    if free(B): placed.append(B)
    else: todo.append(e)
for e in todo:
    res_ = place(e, refs[id(e)], TXT_H); outcome.setdefault(res_, []).append(e.dxf.text)
    placed.append(tbox(e.dxf.insert.x, e.dxf.insert.y, len(e.dxf.text), e.dxf.get('rotation', 0), TXT_H))
# section names, inside each page's parcels away from the road
for page, pos in OC.get('section_label_pdf', {}).items():
    if page not in reg: continue
    W = xf([pos], reg[page])[0]; name = SECTION[page]
    t = msp.add_text(name, height=SEC_H, dxfattribs={'layer': LAYER_LOT, 'style': ST['name'], 'width': ST['width']})
    t.set_placement((W[0], W[1]))
    if not free(tbox(W[0], W[1], len(name), 0, SEC_H)): outcome.setdefault('section_' + place(t, W, SEC_H, False), []).append(page)
    placed.append(tbox(t.dxf.insert.x, t.dxf.insert.y, len(name), t.dxf.get('rotation', 0), SEC_H))
stats['label_outcome'] = {k: (len(v) if k == 'moved' else v) for k, v in outcome.items()}
doc.saveas(out)
print(json.dumps(stats, ensure_ascii=False))
if any(k.endswith('unresolved') for k in outcome): print('有地號放不下（unresolved），要看預覽手動處理')
