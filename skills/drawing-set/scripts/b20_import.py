"""引用臺北市工務局標準圖 B20 V2.0（箱涵式側溝構造詳圖）CAD 圖元，轉成 P33 Sheet 圖元（poly／text／fill）。
使用者 2026-11-06：S-01 補平面圖、甲種預鑄溝蓋板詳圖、場鑄緣石配筋圖，標註照範例全部複製，再依本公司規則調線型。
- 圖層對應（ByLayer）：CONT→結構線、STEEL→鋼筋、DIM／LABEL→標註、HIDE→隱藏線、HATCH→填線（253）、TEXT 線→細線。
- 文字一律 GENIE、14 pt（4.94 mm）以上；原圖 4.0 mm 字依縮放放大，詳圖號圓圈隨字放大。
- DIMENSION、LEADER、INSERT 以 virtual_entities 展開（尺寸線、箭頭、文字照原圖位置）。
來源：src/B20_V2.0_臺北市工務局標準圖_箱涵式側溝構造詳圖.dxf（NAS 原檔 DWG 經 accoreconsole DXFOUT，原檔只讀）。
"""
import os, re, math
import numpy as np
import ezdxf
from ezdxf import bbox, path as ezpath
from ezdxf.render import hatching
from p33_sheet import tw as S_tw

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src", "B20_V2.0_臺北市工務局標準圖_箱涵式側溝構造詳圖.dxf")
REGIONS = {"plan": (35, 410, 342, 575), "curb": (343, 410, 500, 575), "cov": (270, 236, 500, 412)}   # 原圖 A1 紙面 mm
# 臺北市工務局標準圖 A18 V1.0 鋼管護欄詳圖（道路工程）：1 護欄立面圖(築於路堤)、3、5 剖面圖（使用者 2026-11-06 加入 S-03）
SRC_A18 = os.path.join(HERE, "src", "A18_V1.0_臺北市工務局標準圖_鋼管護欄詳圖.dxf")
REGIONS.update({"a18_e1": (35, 285, 430, 525), "a18_s3": (425, 315, 592, 525), "a18_s5": (594, 315, 770, 525)})
SRC_OF = {"a18_e1": SRC_A18, "a18_s3": SRC_A18, "a18_s5": SRC_A18}
LMAP = {"CONT": "結構線", "STEEL": "鋼筋", "DIM": "標註", "LABEL": "標註", "HIDE": "隱藏線", "HATCH": "填線",
        "TEXT": "細線", "LEGEND": "細線", "Modify": "細線"}
LTMAP = {"HIDDEN": "DASHED", "HIDDEN2": "DASHED", "DASHED": "DASHED", "DASHED2": "DASHED", "CENTER": "CENTER", "CENTER2": "CENTER", "DOT": "DOT"}
PTMIN = 4.94
_CUR = [None]
_docs = {}
def _load(src=None):
    src = src or SRC
    if src not in _docs: _docs[src] = ezdxf.readfile(src)
    return _docs[src]

def _layer_lt(e, parent_layer=None):
    lay = e.dxf.layer if e.dxf.layer != "0" or parent_layer is None else parent_layer
    lt = e.dxf.get("linetype", "BYLAYER").upper()
    if lt == "BYLAYER":
        try: lt = _CUR[0].layers.get(lay).dxf.linetype.upper()
        except Exception: lt = "CONTINUOUS"
    return lay, LTMAP.get(lt)

def _prims(e, parent_layer=None, depth=0):
    """展開成 (類別, 原圖層, 線型, 資料)；類別 poly／fill／text"""
    t = e.dxftype(); out = []
    if t in ("DIMENSION", "LEADER", "INSERT", "MULTILEADER") and depth < 4:
        pl = e.dxf.layer if e.dxf.layer != "0" else parent_layer
        try:
            for v in e.virtual_entities(): out += _prims(v, pl, depth + 1)
        except Exception: pass
        return out
    lay, lt = _layer_lt(e, parent_layer)
    if t in ("TEXT", "MTEXT", "ATTRIB"):
        if t == "MTEXT":
            s = e.plain_text(split=False); h = e.dxf.char_height; ins = e.dxf.insert; ap = e.dxf.get("attachment_point", 1)
            rot = e.dxf.get("rotation", 0.0)
            if e.dxf.hasattr("text_direction"):
                d = e.dxf.text_direction; rot = math.degrees(math.atan2(d.y, d.x))
            out.append(("mtext", lay, lt, (s, h, (ins.x, ins.y), ap, rot, e.dxf.get("line_spacing_factor", 1.0))))
        else:
            s = e.plain_text(); h = e.dxf.height; ha = e.dxf.get("halign", 0); va = e.dxf.get("valign", 0)
            p = e.dxf.align_point if (ha or va) and e.dxf.hasattr("align_point") else e.dxf.insert
            out.append(("text", lay, lt, (s, h, (p.x, p.y), ha, va, e.dxf.get("rotation", 0.0))))
        return out
    if t == "SOLID" or t == "TRACE":
        pts = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx3, e.dxf.vtx2]
        out.append(("fill", lay, lt, np.array([(p.x, p.y) for p in pts]))); return out
    if t == "HATCH":
        if e.dxf.solid_fill:
            for bp in ezpath.from_hatch(e):
                q = np.array([(v.x, v.y) for v in bp.flattening(0.05)])
                if len(q) > 2: out.append(("fill", lay, lt, q))
        else:
            try:
                for a, b in hatching.hatch_entity(e): out.append(("poly", lay, lt, np.array([(a.x, a.y), (b.x, b.y)])))
            except Exception: pass
        return out
    if t == "CIRCLE":
        c = e.ocs().to_wcs(e.dxf.center); r = e.dxf.radius; a = np.linspace(0, 2 * np.pi, max(24, int(r * 8)))
        out.append(("circle", lay, lt, (c.x, c.y, r, np.column_stack([c.x + r * np.cos(a), c.y + r * np.sin(a)])))); return out
    try:
        p = ezpath.make_path(e)
        q = np.array([(v.x, v.y) for v in p.flattening(0.02)])
        if len(q) > 1: out.append(("poly", lay, lt, q))
    except Exception: pass
    return out

def region(name):
    """回傳 (圖元清單, 範圍 bbox)；圖元座標為原圖 A1 紙面 mm"""
    x0, y0, x1, y1 = REGIONS[name]; d_ = _load(SRC_OF.get(name)); _CUR[0] = d_; m = d_.modelspace(); P = []
    for e in m:
        b = bbox.extents([e])
        if not b.has_data: continue
        if b.extmin.x >= x0 and b.extmax.x <= x1 and b.extmin.y >= y0 and b.extmax.y <= y1: P += _prims(e)
    xy = np.vstack([p[3] if p[0] in ("poly", "fill") else p[3][3] if p[0] == "circle" else np.array([p[3][2]]) for p in P])
    return P, (xy[:, 0].min(), xy[:, 1].min(), xy[:, 0].max(), xy[:, 1].max())

def place(sh, name, ox, oy, k, scale_label=None, text_h=PTMIN):
    """把 B20 區塊畫到 sh：原圖 (x, y) → (ox + (x − bx0)·k, oy + (y − by0)·k)；回傳紙面 bbox"""
    P, (bx0, by0, bx1, by1) = region(name); i0 = len(sh.items)
    T = lambda q: np.column_stack([ox + (np.asarray(q)[:, 0] - bx0) * k, oy + (np.asarray(q)[:, 1] - by0) * k])
    Tp = lambda x, y: (ox + (x - bx0) * k, oy + (y - by0) * k)
    texts = [p for p in P if p[0] in ("text", "mtext")]
    balloons = []                                                      # (cx, cy, 放大倍數)
    # 詳圖號圓圈（上下兩行短字，如 3／-、4／B08）：圓圈與分隔線隨字放大，兩行字依新字高重排
    def _tc(t):
        s_, h_, (x_, y_) = t[3][0].strip(), t[3][1], t[3][2]
        return (x_ + 0.31 * h_ * len(s_), y_ - h_ / 2) if t[0] == "mtext" else (x_, y_ + h_ / 2)
    short = [t for t in texts if 0 < len(t[3][0].strip()) <= 4]
    pairs, used = [], set()
    for i, a in enumerate(short):
        for j, b in enumerate(short):
            if i == j or i in used or j in used: continue
            (xa, ya), (xb, yb) = _tc(a), _tc(b)
            if abs(xa - xb) < 3.5 and 3.0 < ya - yb < 8.0: pairs.append((a, b, ((xa + xb) / 2, (ya + yb) / 2))); used |= {i, j}
    PAIRED = {}
    for a, b, (mx, my) in pairs:
        ring = [q for k_, l_, t_, q in [(p[0], p[1], p[2], p[3]) for p in P] if k_ == "poly" and np.all(np.hypot(q[:, 0] - mx, q[:, 1] - my) < 8.0)]
        r0 = max([np.hypot(q[:, 0] - mx, q[:, 1] - my).max() for q in ring] + [6.0])
        hn_ = max(text_h, a[3][1] * k); f = max(1.0, hn_ * 1.2 / (r0 * k))
        PAIRED[id(a)] = (mx, my, +1, hn_); PAIRED[id(b)] = (mx, my, -1, hn_)
        for q in ring: q[:, 0] = mx + (q[:, 0] - mx) * f; q[:, 1] = my + (q[:, 1] - my) * f
    for kind, lay, lt, dat in P:
        L = LMAP.get(lay, "細線")
        if kind == "poly": sh.poly(T(dat), L, lt)
        elif kind == "fill": sh.fill(T(dat), "標註" if L == "填線" else L)
        elif kind == "circle":
            cx, cy, r, q = dat
            inside = [t for t in texts if math.hypot(t[3][2][0] - cx, t[3][2][1] - cy) < r * 1.2]
            if inside and r < 7.5:                                     # 詳圖號圓圈：隨字放大
                f = max(1.0, text_h / (inside[0][3][1] * k)); a_ = np.linspace(0, 2 * np.pi, 40)
                q = np.column_stack([cx + r * f * np.cos(a_), cy + r * f * np.sin(a_)]); balloons.append((cx, cy, r, f))
            sh.poly(T(q), L, lt)
    for t in texts:
        if id(t) in PAIRED:
            mx, my, sg, hn_ = PAIRED[id(t)]; X, Y = Tp(mx, my)
            sh.text(X, Y + sg * hn_ * 0.62, t[3][0].strip(), "center", hn_, 0)
    for kind, lay, lt, dat in [t for t in texts if id(t) not in PAIRED]:
        if kind == "text":
            s, h, (x, y), ha, va, rot = dat
            if not s.strip(): continue
            hn = max(text_h, h * k); th = math.radians(rot)
            hb = hn / k                                                          # 放大後字高（原圖單位）
            dy = {0: hb / 2, 1: hb / 2, 2: 0.0, 3: -hb / 2}.get(va, hb / 2)       # 基線／底對齊往上長、頂對齊往下長
            xm, ym = x - dy * math.sin(th), y + dy * math.cos(th)
            for cx, cy, r, f in balloons:                                         # 圓圈內的字：位置隨圓圈放大
                if math.hypot(x - cx, y - cy) < r * 1.2:
                    xm0, ym0 = x + h / 2 * -math.sin(th), y + h / 2 * math.cos(th)
                    if va == 2: xm0, ym0 = x, y
                    xm, ym = cx + (xm0 - cx) * f, cy + (ym0 - cy) * f; break
            s = _scale_lab(s, k, scale_label)
            X, Y = Tp(xm, ym); _emit(sh, X, Y, s, {0: "left", 1: "center", 2: "right", 4: "center"}.get(ha, "left"), hn, rot, h, k)
        else:
            s, h, (x, y), ap, rot, lsf = dat
            lines = [l for l in s.split("\n")]
            hn = max(text_h, h * k); hl = max(h * 1.667 * lsf * k, hn * 1.2); th = math.radians(rot)
            row, col = (ap - 1) // 3, (ap - 1) % 3                          # 0 上 1 中 2 下；0 左 1 中 2 右
            X, Y = Tp(x, y); n = len(lines)
            d0 = (-hn / 2, (n - 1) / 2 * hl, (n - 1) * hl + hn / 2)[row]
            if row == 0 and n == 1: d0 = -h * k + hn / 2                       # 單行：底緣不動、往上長（避免壓到下方線）
            for j, l in enumerate(lines):
                if not l.strip(): continue
                d = d0 - j * hl
                _emit(sh, X - math.sin(th) * d, Y + math.cos(th) * d, _scale_lab(l.rstrip(), k, scale_label), ("left", "center", "right")[col], hn, rot, h, k)
    _declutter(sh, i0)
    return (ox, oy, ox + (bx1 - bx0) * k, oy + (by1 - by0) * k)

def _box(it):
    _, (x, y), s_, ha, h, rot, wf = it[:7]; w = S_tw(s_, h, wf); th = math.radians(rot)
    a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
    P_ = [(x + u * math.cos(th) - v * math.sin(th), y + u * math.sin(th) + v * math.cos(th)) for u in (a0, a0 + w) for v in (-h / 2, h / 2)]
    return min(p[0] for p in P_), min(p[1] for p in P_), max(p[0] for p in P_), max(p[1] for p in P_)

def _declutter(sh, i0, hard=("結構線", "鋼筋", "表格", "標註", "細線", "隱藏線")):
    """本區文字放大後若壓到結構線、鋼筋或其他文字，沿字的法向（橫字上下、直字左右）找最小位移避開（每步 0.3 mm，至多 4 mm）"""
    segs = [(a, b) for it in sh.items[i0:] if it[0] == "poly" and it[2] in hard for a, b in zip(it[1][:-1], it[1][1:])]
    T = [k for k in range(i0, len(sh.items)) if sh.items[k][0] == "text"]
    def bad(r, me):
        for a, b in segs:
            if max(a[0], b[0]) < r[0] or min(a[0], b[0]) > r[2] or max(a[1], b[1]) < r[1] or min(a[1], b[1]) > r[3]: continue
            for t in np.linspace(0, 1, 25):
                px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                if r[0] < px < r[2] and r[1] < py < r[3]: return True
        for k in T:
            if k == me: continue
            q = _box(sh.items[k])
            if r[0] < q[2] and q[0] < r[2] and r[1] < q[3] and q[1] < r[3]: return True
        return False
    for _ in range(2):
        for k in T:
            it = sh.items[k]; r = _box(it)
            if not bad(r, k): continue
            vert = abs(((it[5] % 180) - 90)) < 1
            for d in np.arange(0.3, 14.01, 0.3):
                done = False
                for sg, ax in ((1, 0), (-1, 0), (1, 1), (-1, 1)):             # 先沿法向，再沿字向
                    if ax == 0 and d > 6.0: continue                            # 法向至多 6 mm，字向至多 14 mm
                    if (ax == 0) != vert: dx, dy = 0, sg * d
                    else: dx, dy = sg * d, 0
                    r2 = (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)
                    if not bad(r2, k):
                        sh.items[k] = (it[0], (it[1][0] + dx, it[1][1] + dy)) + tuple(it[2:]); done = True; break
                if done: break

def _emit(sh, X, Y, s, ha, hn, rot, h0, k):
    """文字中間夾圖號（連續 3 個以上空白）時拆段，各段依原圖字寬（中文約 1.24h、半形 0.62h）放回原位置"""
    if ha != "left" or not re.search(r" {3,}", s): sh.text(X, Y, s, ha, hn, rot); return
    th = math.radians(rot); pos = 0
    for seg in re.split(r"( {3,})", s):
        if seg and not seg.isspace():
            d = sum(1.24 * h0 if ord(c) > 255 else 0.62 * h0 for c in s[:pos]) * k
            sh.text(X + d * math.cos(th), Y + d * math.sin(th), seg, "left", hn, rot)
        pos += len(seg)

def _scale_lab(s, k, lab):
    m_ = re.match(r"\s*A1\s*\(1:(\d+)\)\s+A3\s*\(1:\d+\)\s*(Unit:cm)?", s)
    if not m_: return s
    return (lab or f"S=1:{int(m_.group(1)) / k:g}") + "　單位：cm"
