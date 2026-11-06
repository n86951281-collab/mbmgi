"""平面配置圖 P-01（ditch-design，由 P33 plan_view 一般化）：A3 橫式 1/500 一張（--scale 200 時分 2 張），定線轉正，0K+000 在左。

畫：測量圖地物（layers.features）、SF 地物（sf_dxf）、既有側溝標示、道路中心線、側溝中心線、新設側溝與集水井（design.ditches[]、wells[]）、
    臨時擋土樁列（temp_shoring）、斷面切線、多重引線、IP 座標表、主要構造物數量表（含 demolish[] 拆除項）、測量圖圖例表。
用法：python plan_view.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM] [--scale 500]
"""
import sys, os, json, math, datetime
import numpy as np
import ezdxf
from ezdxf.enums import TextEntityAlignment as TA
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D
from matplotlib.path import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
dd.sheet_module()
import plan_base as PB

CFG = dd.CFG; P_ = dd.P_; stamp = dd.stamp
OUT = dd.OUT; PREV = os.path.join(OUT, "04_平面圖"); os.makedirs(PREV, exist_ok=True)
WORK_GAP = dd.WORK_GAP               # 溝外壁外側施工空間（樁號標註退距用）
OUTER = P_["W"] / 2 + P_["t_wall"]   # 溝中心到外壁

# ---------------- 圖紙（與 design_profiles.py 同一套版面）----------------
W_, H_ = 420.0, 297.0
TXT = 7.06; PT = 4.94; TBT = 4.94; WF = 0.5; TB_WF = 0.7
SCALE = float(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else float(dd.get("plot.plan_scale", 500)); K = 1000 / SCALE   # 1/500 一張全配置；1/200 分 2 張
TB = dd.TB
LAYERS = {   # 名稱: (ACI, 線型, 預覽色, 預覽線寬mm)
    "圖框": (7, None, "#000000", 0.50), "圖標欄": (7, None, "#000000", 0.35),
    "地物": (253, None, "#A3A3A3", 0.212), "既有側溝": (252, None, "#666666", 0.30),
    "SF地物": (253, None, "#A3A3A3", 0.15), "圖例表": (7, None, "#000000", 0.18),
    "中心線1": (22, "CENTER", "#000000", 0.20), "副定線": (149, "DASHED", "#000000", 0.20),
    "斷面切線": (149, "DASHED", "#000000", 0.18),
    "設計側溝": (7, None, "#000000", 0.60), "集水井": (7, None, "#000000", 0.60),
    "標註": (7, None, "#000000", 0.18), "鋼軌樁": (7, None, "#000000", 0.35), "文字": (7, None, "#000000", 0.0),
}
from p33_sheet import tw
class Sheet:
    def __init__(self, name): self.items = []; self.name = name; self.wf = WF
    def poly(self, pts, layer, lt=None): self.items.append(("poly", np.asarray(pts, float), layer, lt))
    def line(self, x1, y1, x2, y2, layer, lt=None): self.poly([(x1, y1), (x2, y2)], layer, lt)
    def rect(self, x, y, w, h, layer): self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], layer)
    def text(self, x, y, s, ha="left", h=TXT, rot=0): self.items.append(("text", (x, y), s, ha, h, rot, self.wf))
def tbox(it):
    _, (x, y), s, ha, h, rot, wf = it; w = tw(s, h, wf); th = math.radians(rot)
    a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
    P = [(x + u * math.cos(th) - v * math.sin(th), y + u * math.sin(th) + v * math.cos(th)) for u in (a0, a0 + w) for v in (-h / 2, h / 2)]
    return (min(p[0] for p in P), min(p[1] for p in P), max(p[0] for p in P), max(p[1] for p in P))
def frame(sh, name, scale, no):
    sh.rect(0, 0, W_, H_, "圖框"); sh.rect(10, 10, 400, 277, "圖框"); sh.rect(10, 10, 400, 22, "圖標欄")
    for x in (86, 188, 226, 298, 392): sh.line(x, 10, x, 32, "圖標欄")
    for x0, x1 in ((86, 188), (226, 298), (392, 410)): sh.line(x0, 21, x1, 21, "圖標欄")
    sh.line(262, 10, 262, 32, "圖標欄")
    yc = (14.94, 20.88, 26.82); sh.wf = TB_WF
    sh.text(48, yc[2], "主辦機關", "center", TBT); sh.text(48, yc[1], TB["agency"], "center", TBT); sh.text(48, yc[0], TB["agency_en"], "center", TBT)
    sh.wf = 0.55; sh.text(89.5, 26.5, "工程名稱：" + TB["project"], "left", TBT); sh.wf = TB_WF   # 同 p33_sheet：GENIE 實測字寬
    sh.text(89.5, 15.5, "圖　名：" + name, "left", TBT)
    sh.text(207, yc[2], "比例尺", "center", TBT); sh.text(207, yc[1], scale, "center", TBT)
    import p33_sheet as _S
    sh.text(229.5, 26.5, "設計：" + _S.TB["design"], "left", TBT); sh.text(265.5, 26.5, "主管：" + _S.TB["manager"], "left", TBT)
    sh.text(229.5, 15.5, "繪圖：" + _S.TB["draft"], "left", TBT); sh.text(265.5, 15.5, "校核：" + _S.TB["check"], "left", TBT)
    sh.text(345, yc[2], "設計單位", "center", TBT); sh.text(345, yc[1], TB["designer"], "center", TBT); sh.text(345, yc[0], TB["designer_en"], "center", TBT)
    sh.text(401, 26.5, "圖號", "center", TBT); sh.text(401, 15.5, no, "center", TBT); sh.wf = WF


# ---------------- 幾何 ----------------
src = PB._src; msp = src.modelspace()
CLn = PB.CLn
C0 = PB.C0; Lc = PB.Lc; tv = PB.tv; nv = PB.nv                                       # nv：tv 左轉 90°
VY = 182.0                                            # 中心線紙面 y
VIEW = (16.0, 114.0, 404.0, 250.0)                    # 平面視窗：上留圖例、下留說明與測量圖例表
_ra = CFG["alignment"].get("plan_range", [-30.0, Lc + 30.0])                           # 平面圖中心線樁距範圍
SHEETS = [tuple(_ra)] if SCALE >= 500 else [(_ra[0] + 24.0, (_ra[0] + _ra[1]) / 2 + 6.0), ((_ra[0] + _ra[1]) / 2 - 10.0, _ra[1] - 28.0)]   # 1/200 兩張重疊 16 m
VX0 = 0.0
def T(P):
    d = np.atleast_2d(P)[:, :2] - C0
    return np.column_stack([VX0 + (d @ tv) * K, VY + (d @ nv) * K])
def clip(P, r):
    """折線裁到矩形 r 內（逐段 Liang–Barsky）"""
    out, cur = [], []
    for p, q in zip(P[:-1], P[1:]):
        dx, dy = q[0] - p[0], q[1] - p[1]; t0, t1 = 0.0, 1.0; ok = True
        for pp, qq in ((-dx, p[0] - r[0]), (dx, r[2] - p[0]), (-dy, p[1] - r[1]), (dy, r[3] - p[1])):
            if pp == 0:
                if qq < 0: ok = False; break
            else:
                t = qq / pp
                if pp < 0: t0 = max(t0, t)
                else: t1 = min(t1, t)
        if not ok or t0 > t1:
            if len(cur) > 1: out.append(np.array(cur))
            cur = []; continue
        a = p + (q - p) * t0; b = q if t1 >= 1 else p + (q - p) * t1
        if cur and t0 <= 0: cur.append(b)
        else:
            if len(cur) > 1: out.append(np.array(cur))
            cur = [a, b]
        if t1 < 1:
            out.append(np.array(cur)); cur = []
    if len(cur) > 1: out.append(np.array(cur))
    return out

LG = CFG["legend"]["box"]
def ent_pts(v):
    t = v.dxftype()
    if t == "LINE": return [np.array([tuple(v.dxf.start)[:2], tuple(v.dxf.end)[:2]])]
    if t == "POLYLINE": P = [(x.dxf.location.x, x.dxf.location.y) for x in v.vertices]
    elif t == "LWPOLYLINE": P = [tuple(p) for p in v.get_points("xy")]
    elif t == "HATCH":                                   # 圖塊內的填線：邊界＋填線線段
        import ezdxf.path
        from ezdxf.render import hatching
        out = [np.array([(p.x, p.y) for p in bp.flattening(0.05)]) for bp in ezdxf.path.from_hatch(v)]
        try: out += [np.array([(a.x, a.y), (b.x, b.y)]) for a, b in hatching.hatch_entity(v)]
        except Exception: pass
        return [q for q in out if len(q) > 1]
    elif t in ("CIRCLE", "ARC"):
        a0, a1 = (0, 360) if t == "CIRCLE" else (v.dxf.start_angle, v.dxf.end_angle + (360 if v.dxf.end_angle < v.dxf.start_angle else 0))
        a = np.radians(np.linspace(a0, a1, 25)); c = v.dxf.center; r = v.dxf.radius
        return [np.column_stack([c.x + r * np.cos(a), c.y + r * np.sin(a)])]
    else: return []
    if len(P) < 2: return []
    if getattr(v, "is_closed", False): P.append(P[0])
    return [np.array(P)]

FEATS = [(P, lay) for P, lay in PB.FEATS if lay != "SF地物"]   # (世界座標折線, 圖層)：測量圖地物、既有側溝（plan_base 同一套讀法）
FTXT = list(PB.FTXT)                                   # 地物符號內的文字（臨時屋棚「T」、PC 路面「P.C.」）：(世界座標, 字串)
MLAB = PB.MLAB
half_w = P_["well_in"] / 2 + P_["well_wall"]

def overlaps(b, placed): return any(b[0] < q[2] and q[0] < b[2] and b[1] < q[3] and q[1] < b[3] for q in placed)

# ---------------- SF（地物）：NAS 測量圖資料夾 SF(地物).dwg 轉 DXF ----------------
SF = [(P, lay) for P, lay in PB.FEATS if lay == "SF地物"]
print(f"SF 折線段：{len(SF)}")

# ---------------- 測量圖圖例表（BLOCK 圖層）：符號＋名稱成對取出，重排成 4 欄 ----------------
LEG_ITEMS = []
_LGL = CFG["legend"].get("layer", "BLOCK"); _LSX = CFG["legend"].get("split_x", (LG[0] + LG[2]) / 2)   # 圖例表圖層、左右欄分界 x
_ins = [e for e in msp.query(f'INSERT[layer=="{_LGL}"]')]
_txt = [e for e in msp.query(f'TEXT[layer=="{_LGL}"]') if e.dxf.text not in ("圖示", "地物名稱", "圖例表")]
for e in _ins:
    ip = np.array(e.dxf.insert)[:2]
    cand = [t for t in _txt if 0 < t.dxf.insert[0] - ip[0] < 6 and abs(t.dxf.insert[1] - ip[1]) < 0.8]
    if not cand: continue
    t = min(cand, key=lambda t: t.dxf.insert[0] - ip[0])
    segs = [q - ip for v in e.virtual_entities() for q in ent_pts(v)]
    stx = "".join(v.dxf.text for v in e.virtual_entities() if v.dxftype() == "TEXT")
    LEG_ITEMS.append((ip[0] > _LSX, -ip[1], t.dxf.text, segs, stx))
LEG_ITEMS.sort(key=lambda r: (r[0], r[1]))               # 照原表順序：左欄由上而下，再右欄
print(f"測量圖圖例：{len(LEG_ITEMS)} 項")

def draw_survey_legend(sh):
    NC, RH_ = 4, 7.0; CW_ = 17.0 + max(tw(r[2], PT) for r in LEG_ITEMS) + 2.0      # 2026-11-06：縮小間距，以不壓線、不重疊為準
    x0 = 404.0 - NC * CW_; nr = math.ceil(len(LEG_ITEMS) / NC)
    ytop = 110.0; ybot = ytop - RH_ * (nr + 1)
    sh.rect(x0, ybot, NC * CW_, ytop - ybot, "圖例表"); sh.line(x0, ytop - RH_, x0 + NC * CW_, ytop - RH_, "圖例表")
    sh.text(x0 + NC * CW_ / 2, ytop - RH_ / 2, "圖例表（依原測量圖）", "center", PT)
    for k in range(1, NC): sh.line(x0 + k * CW_, ybot, x0 + k * CW_, ytop - RH_, "圖例表")
    for k, (_, _, name, segs, stx) in enumerate(LEG_ITEMS):
        col, row = k // nr, k % nr
        cx = x0 + col * CW_; cy = ytop - RH_ * (row + 1.5)
        if segs:
            allp = np.vstack(segs); lo, hi = allp.min(axis=0), allp.max(axis=0); ext = np.maximum(hi - lo, 1e-6)
            f = min(11.0 / ext[0], 5.0 / ext[1], 8.0)       # 符號框 11×5 mm
            mid = (lo + hi) / 2
            for q in segs: sh.poly(np.column_stack([cx + 8.0 + (q[:, 0] - mid[0]) * f, cy + (q[:, 1] - mid[1]) * f]), "圖例表")
        if stx: sh.text(cx + 8.0, cy, stx, "center", PT)
        sh.text(cx + 16.0, cy, name, "left", PT)

sheets = []
for no, (sa, sb) in enumerate(SHEETS, 1):
    VX0 = VIEW[0] + 8.0 - sa * K
    sh = Sheet("新設側溝平面配置圖" + (f"({no}/{len(SHEETS)})" if len(SHEETS) > 1 else "")); frame(sh, sh.name, f"1/{SCALE:.0f}", f"P-{no:02d}"); sheets.append(sh)
    xa, xb = T((C0 + tv * sa)[None, :])[0][0], T((C0 + tv * sb)[None, :])[0][0]
    V = (max(VIEW[0], xa), VIEW[1], min(VIEW[2], xb), VIEW[3])
    for P, lay in FEATS + SF:
        for q in clip(T(P), V): sh.poly(q, lay)
    for p, s in FTXT:                                  # 符號文字（14 pt）
        q = T(p[None, :])[0]
        if V[0] + 2 < q[0] < V[2] - 2 and V[1] + 3 < q[1] < V[3] - 3: sh.text(q[0], q[1], s, "center", PT)
    for P, lay in [(CLn, "中心線1")] + [(PB.SIDES[k][0], "副定線") for k in PB.KEYS]:
        u0 = (P[1] - P[0]) / np.hypot(*(P[1] - P[0]))
        for q in clip(T(np.array([P[0] - u0 * 8, P[1] + u0 * 8])), V): sh.poly(q, lay)
    for key in PB.KEYS:                                # side：路外側（中心線左＝-nv，右＝+nv）
        P, side = PB.SIDES[key]
        L = float(np.hypot(*(P[1] - P[0]))); u = (P[1] - P[0]) / L; n = np.array([-u[1], u[0]])
        for off in (-OUTER, OUTER, -P_["W"] / 2, P_["W"] / 2):
            for q in clip(T(np.array([P[0] + u * half_w + n * off, P[0] + u * (L - half_w) + n * off])), V): sh.poly(q, "設計側溝")
        for sc in (0.0, L):
            c = PB.well_center(key, sc)
            for hw in (P_["well_in"] / 2, half_w):
                Q = np.array([c + u * hw + n * hw, c - u * hw + n * hw, c - u * hw - n * hw, c + u * hw - n * hw, c + u * hw + n * hw])
                for q in clip(T(Q), V): sh.poly(q, "集水井")
        outw = nv * side
        for sp in ([v for v in np.arange(10.0, L - 2.0, 10.0)] if False else []):   # （2026-11-06 改由斷面切線樁號標示）1/200 每 10 m 標副定線樁號；1/500 只標中心線斷面樁號
            p = P[0] + u * sp; q0 = T((p + outw * (OUTER + WORK_GAP + 0.3))[None, :])[0]
            if not (V[0] + 6 < q0[0] < V[2] - 6): continue
            lab = f"{key}0K+{sp:06.2f}" if abs(sp - round(sp)) > 1e-6 else f"{key}0K+{int(round(sp)):03d}"
            y1 = q0[1] + side * 3.0; sh.line(q0[0], q0[1], q0[0], y1, "標註")
            sh.text(q0[0], y1 + side * 1.5, lab, "left" if side > 0 else "right", PT, 90)
        for Ln in PB.pile_lines(key):                     # 臨時擋土鋼軌樁（開挖邊，@1.0 m）
            for q in clip(T(Ln), V): sh.poly(q, "鋼軌樁")
        for pp in T(PB.pile_points(key)):
            if V[0] < pp[0] < V[2]: sh.rect(pp[0] - 0.35, pp[1] - 0.35, 0.7, 0.7, "鋼軌樁")
    # 斷面切線：道路中心線 0K+000 樁號（與橫斷面圖 X-01、X-02 同），左右各 9 m；設施斷面另標樁號
    for st_, note_ in PB.section_cuts():
        c_ = C0 + tv * st_; q = T(np.array([c_ - nv * 9.0, c_ + nv * 9.0]))
        if not (V[0] < q[0][0] < V[2]): continue
        for qq in clip(q, V): sh.poly(qq, "斷面切線", "DASHED")
        if note_ == "集水井":
            top_ = q[1] if q[1][1] > q[0][1] else q[0]
            sh.text(top_[0], min(top_[1], V[3]) + 1.5, f"0K+{st_:06.2f}", "left", PT, 90)
    # 集水井標註（多重引線式：避開房屋、樁號與已放文字）
    HP = [Path(T(h)) for h in PB.HOUSES]
    LEADS = []                                            # 已放引線（含落線）：新引線不得與之相交
    def seg_x(p1, p2, p3, p4):
        d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return d(p1, p2, p3) * d(p1, p2, p4) < 0 and d(p3, p4, p1) * d(p3, p4, p2) < 0
    def clear_of_houses(pts): return not any(h.contains_points(pts).any() for h in HP)
    DSEG = np.array([(a[0], a[1], b[0], b[1]) for it in sh.items if it[0] == "poly" and it[2] in ("設計側溝", "集水井", "鋼軌樁", "中心線1", "副定線") for a, b in zip(it[1][:-1], it[1][1:])])
    def box_hits_design(b, m=1.0):
        """線段與（外擴 m 的）文字框相交：Liang–Barsky 逐段"""
        x0, y0, x1, y1 = b[0] - m, b[1] - m, b[2] + m, b[3] + m
        for ax, ay, bx, by in DSEG:
            if max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1: continue
            if clip(np.array([(ax, ay), (bx, by)]), (x0, y0, x1, y1)): return True
        return False
    WI_ = P_["well_in"] * 100; LABS = []
    for key in reversed(PB.KEYS):
        P, side = PB.SIDES[key]
        L = float(np.hypot(*(P[1] - P[0]))); u = (P[1] - P[0]) / L
        for j, sc in enumerate((0.0, L)):
            if (key, j) not in PB.WELL_ID: continue
            LABS.append((key, side, PB.well_center(key, sc), f"新設側溝式箱涵集水井 {PB.WELL_ID[(key, j)]}（{WI_:.0f}×{WI_:.0f} cm）1 座"))
        LABS.append((key, side, P[0] + u * (0.5 * L) + nv * side * OUTER, f"新設側溝式箱涵 #{key}（W×H＝{P_['W']*100:.0f}×{P_['H']*100:.0f} cm）L＝{L:.2f} m"))
    for key, side, wp, lab in LABS:
            c = T(wp[None, :])[0]
            if not (V[0] < c[0] < V[2]): continue
            placed0 = [tbox(it) for it in sh.items if it[0] == "text"]
            best = None
            for dy in (14, 20, 26, 32, 38, 44, 50, 56, 62, -44, -50, -56, -62, -68):   # 負值：跨到道路另一側
                for dx in sorted(set(list(range(-90, 91, 6))) - {0}, key=abs):
                    xx = c[0] + dx; yy = c[1] + side * dy; ha = "left" if dx > 0 else "right"
                    it = ("text", (xx, yy), lab, ha, PT, 0, WF); b = tbox(it)
                    if not (V[0] < b[0] and b[2] < V[2] and V[1] < b[1] and b[3] < V[3]): continue
                    grid = np.array([(gx, gy) for gx in np.linspace(b[0] - 1, b[2] + 1, 25) for gy in np.linspace(b[1] - 1, b[3] + 1, 5)])
                    seg = np.array([c + (np.array([xx, yy - np.sign(dy) * side * 3.0]) - c) * t for t in np.linspace(0.08, 1, 30)])
                    seg_hit_txt = any(r[0] - 0.5 < px < r[2] + 0.5 and r[1] - 0.5 < py < r[3] + 0.5 for px, py in seg for r in placed0)
                    w_ = tw(lab, PT) * (1 if dx > 0 else -1); ey = yy - np.sign(dy) * side * 3.0
                    seg_hit_txt = seg_hit_txt or any(seg_x(c, (xx, ey), a, b_) or seg_x((xx, ey), (xx + w_, ey), a, b_) for a, b_ in LEADS)
                    if clear_of_houses(np.vstack([grid, seg])) and not overlaps([b[0] - 1.5, b[1] - 1.5, b[2] + 1.5, b[3] + 1.5], placed0) and not box_hits_design(b) and not seg_hit_txt: best = (xx, yy, it); break
                if best: break
            if best is None: print(f"[注意] {lab}：找不到避開房屋的位置，維持預設"); xx, yy = c[0] + 8, c[1] + side * 22; it = ("text", (xx, yy), lab, "left", PT, 0, WF)
            else: xx, yy, it = best
            sgn = 1 if it[3] == "left" else -1
            sd = side if (yy - c[1]) * side > 0 else -side
            sh.line(c[0], c[1], xx, yy - sd * 3.0, "標註"); sh.line(xx, yy - sd * 3.0, xx + sgn * tw(lab, PT), yy - sd * 3.0, "標註")
            LEADS += [((c[0], c[1]), (xx, yy - sd * 3.0)), ((xx, yy - sd * 3.0), (xx + sgn * tw(lab, PT), yy - sd * 3.0))]
            sh.items.append(it)
            sh.poly([(c[0], c[1]), (c[0] + (xx - c[0]) * 0.06 + 0.6, c[1] + (yy - side * 3 - c[1]) * 0.06), (c[0] + (xx - c[0]) * 0.06 - 0.6, c[1] + (yy - side * 3 - c[1]) * 0.06), (c[0], c[1])], "標註")
    # IP（A0K、B0K 起終點）
    IPS = []
    for key in PB.KEYS:
        P = PB.SIDES[key][0]; L = float(np.hypot(*(P[1] - P[0])))
        for p, s_, nm in ((P[0], 0.0, f"IP{key}1"), (P[1], L, f"IP{key}2")):
            q = T(p[None, :])[0]; a = np.radians(np.linspace(0, 360, 25))
            sh.poly(np.column_stack([q[0] + 1.2 * np.cos(a), q[1] + 1.2 * np.sin(a)]), "標註"); IPS.append((nm, key, s_, p))
    # 道路中心線樁號：水平字，貼在中心線上方
    for sp in sorted(set(list(np.arange(0, Lc, 20.0)) + [Lc])):
        q = T((C0 + tv * sp)[None, :])[0]
        if not (V[0] < q[0] < V[2]): continue
        lab = f"0K+{sp:06.2f}" if abs(sp - round(sp)) > 1e-6 else f"0K+{int(round(sp)):03d}"
        sh.line(q[0], q[1] - 1.2, q[0], q[1] + 1.2, "標註")
        sh.text(q[0] + 0.8, q[1] + 0.5 + PT / 2, lab, "left", PT)
    placed = [tbox(it) for it in sh.items if it[0] == "text"]
    for p, s in MLAB:
        q = T(p[None, :])[0]
        if not (V[0] + 5 < q[0] < V[2] - 5 and V[1] + 3 < q[1] < V[3] - 3): continue
        for dx, dy in ((0, 0), (0, 6), (0, -6), (-10, 0), (10, 0), (0, 12), (0, -12), (-10, 6), (10, -6), (0, 18), (0, -18)):
            it = ("text", (q[0] + dx, q[1] + dy), s, "center", PT, 0, WF); b = tbox(it)
            if not overlaps(b, placed) and V[1] < b[1] and b[3] < V[3] and not box_hits_design(b):
                sh.items.append(it); placed.append(b); break
    # 地物符號字（P.C.、T）與標註重疊時，移除符號字
    TX = [k for k, it in enumerate(sh.items) if it[0] == "text"]; drop = set()
    for i in TX:
        if sh.items[i][2] not in ("P.C.", "T"): continue
        bi = tbox(sh.items[i])
        if any(j != i and j not in drop and overlaps(bi, [tbox(sh.items[j])]) for j in TX): drop.add(i)
    sh.items = [it for k, it in enumerate(sh.items) if k not in drop]
    # 指北針、水流方向、圖例
    nvec = np.array([np.array([0, 1]) @ tv, np.array([0, 1]) @ nv]); nvec /= np.hypot(*nvec)
    cN = np.array([30.0, 266.0]); tip = cN + nvec * 6; tail = cN - nvec * 6; pn = np.array([-nvec[1], nvec[0]])
    sh.line(*tail, *tip, "標註"); sh.poly([tip - nvec * 3 + pn * 1.5, tip, tip - nvec * 3 - pn * 1.5], "標註")
    sh.text(*(tip + nvec * 4.5), "N", "center", PT)
    _dn = CFG["alignment"].get("downstream_dir", "")
    sh.text(48.0, 276.0, f"水流方向：往 0K+000{'（' + _dn + '）' if _dn else ''}", "left", PT)
    sh.line(48.0, 266.0, 68.0, 266.0, "標註"); sh.poly([(51.0, 267.5), (48.0, 266.0), (51.0, 264.5)], "標註")
    x = 130.0; y = 276.0
    for lay, lab in (("中心線1", "道路中心線"), ("副定線", "／".join(PB.KEYS) + " 側溝中心線"), ("設計側溝", f"新設側溝式箱涵 {P_['W']*100:.0f}×{P_['H']*100:.0f}")):
        sh.line(x, y, x + 10, y, lay); x += 12.5; sh.text(x, y, lab, "left", PT); x += tw(lab, PT) + 6
    x = 130.0; y = 266.0
    for lay, lab in (("集水井", "側溝式箱涵集水井"), ("鋼軌樁", "臨時鋼軌樁"), ("既有側溝", "既有側溝（拆除）"), ("地物", "測量地物")):
        sh.line(x, y, x + 10, y, lay); x += 12.5; sh.text(x, y, lab, "left", PT); x += tw(lab, PT) + 6
    if len(SHEETS) > 1:
        t = f"接續第 {no+1} 頁" if no < len(SHEETS) else f"由第 {no-1} 頁接續"
        sh.text(400.0, 256.0, t, "right", PT)
    rows_ = [("點名", "樁號", "X(E)", "Y(N)")] + [(nm, f"{key}0K+{s_:06.2f}".replace("+000.00", "+000"), f"{p[0]:.3f}", f"{p[1]:.3f}") for nm, key, s_, p in IPS]
    cw_ = [16.0, 30.0, 30.0, 32.0]; cx_ = np.r_[18.0, 18.0 + np.cumsum(cw_)]; ytp = 104.0; rh_ = 7.4
    sh.text(18.0, ytp + 5.5, "IP 座標表（側溝中心線起終點）", "left", PT)
    for k, r in enumerate(rows_):
        for j, v_ in enumerate(r): sh.text((cx_[j] + cx_[j + 1]) / 2, ytp - rh_ * (k + 0.5), v_, "center", PT)
        sh.line(cx_[0], ytp - rh_ * (k + 1), cx_[-1], ytp - rh_ * (k + 1), "圖例表")
    sh.line(cx_[0], ytp, cx_[-1], ytp, "圖例表")
    for xx_ in cx_: sh.line(xx_, ytp, xx_, ytp - rh_ * len(rows_), "圖例表")
    LEN = {k: float(np.hypot(*(PB.SIDES[k][0][1] - PB.SIDES[k][0][0]))) for k in PB.KEYS}
    QT = [("編號", "項目", "尺寸 cm", "數量")] + \
         [(PB.WELL_ID[(k, j)], "側溝式箱涵集水井", f"{WI_:.0f}×{WI_:.0f}", "1 座") for k in PB.KEYS for j in (0, 1) if (k, j) in PB.WELL_ID] + \
         [(dd.DITCH[k]["id"], "側溝式箱涵", f"{P_['W']*100:.0f}×{P_['H']*100:.0f}", f"{LEN[k]:.2f} m") for k in PB.KEYS] + \
         [("拆除", r["name"], r["size"], f"{LEN[r['side']] + 2 * half_w:.2f} m") for r in CFG.get("demolish", []) if r.get("demolish", True)]   # 拆除長＝側溝長＋兩端井外寬
    cw2 = [14.0, 40.0, 20.0, 22.0]; cx2 = np.r_[132.0, 132.0 + np.cumsum(cw2)]; yt2 = 104.0; rq = 6.6
    sh.text(132.0, yt2 + 5.0, "主要構造物數量表", "left", PT)
    for k, r in enumerate(QT):
        for j, v_ in enumerate(r): sh.text((cx2[j] + cx2[j + 1]) / 2, yt2 - rq * (k + 0.5), v_, "center", PT)
        sh.line(cx2[0], yt2 - rq * (k + 1), cx2[-1], yt2 - rq * (k + 1), "圖例表")
    sh.line(cx2[0], yt2, cx2[-1], yt2, "圖例表")
    for xx_ in cx2: sh.line(xx_, yt2, xx_, yt2 - rq * len(QT), "圖例表")
    _sd = "、".join(f"{d['side']} 側為{d['dir']}側" for d in dd.DITCHES if d.get("dir"))
    notes = [f"說明：1. 0K+000 在下游{'（' + _dn + '端）' if _dn else ''}，{_sd + '；' if _sd else ''}座標 TWD97。",
             f"2. 既有暗溝打除，新溝外壁貼既有溝外側邊線施作；溝底高程詳 {'、'.join(f'PP-{i:02d}' for i in range(1, len(PB.KEYS) + 1))}。",
             f"3. 臨時擋土{dd.SHO.get('type', '鋼軌樁')}（S-03）；圖示房屋線為簷口，打設前確認鄰房基礎。"]
    for k, t in enumerate(notes): sh.text(18.0, 56.0 - 8.0 * k, t, "left", PT)
    draw_survey_legend(sh)

# ---------- 檢查 ----------
for sh in sheets:
    _sg = [(a, b) for it in sh.items if it[0] == "poly" and it[2] in ("設計側溝", "集水井", "中心線1", "副定線") for a, b in zip(it[1][:-1], it[1][1:])]
    def _hit(r): return any(any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 30)) for a, b in _sg)
    sh.items = [it for it in sh.items if not (it[0] == "text" and it[2] in {s_ for _, s_ in FTXT} and _hit(tbox(it)))]   # 測量符號字壓到設計線就不畫
    T_ = [tbox(it) for it in sh.items if it[0] == "text"]
    over = sum(1 for i in range(len(T_)) for j in range(i + 1, len(T_)) if T_[i][0] < T_[j][2] and T_[j][0] < T_[i][2] and T_[i][1] < T_[j][3] and T_[j][1] < T_[i][3])
    outb = sum(1 for r in T_ if (r[1] + r[3]) / 2 > 32 and (r[0] < 10 or r[2] > 410 or r[1] < 32 or r[3] > 287))
    for it in sh.items:
        if it[0] == 'text':
            r = tbox(it)
            if (r[1] + r[3]) / 2 > 32 and (r[0] < 10 or r[2] > 410 or r[1] < 32 or r[3] > 287): print('   出界：', it[2], [round(v, 1) for v in r])
    segs = [(a, b) for it in sh.items if it[0] == "poly" and it[2] in ("設計側溝", "集水井", "中心線1", "副定線") for a, b in zip(it[1][:-1], it[1][1:])]
    press = sum(1 for r in T_ if any(any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 30)) for a, b in segs))
    TT = [it for it in sh.items if it[0] == "text"]
    for i in range(len(T_)):
        for j in range(i + 1, len(T_)):
            if T_[i][0] < T_[j][2] and T_[j][0] < T_[i][2] and T_[i][1] < T_[j][3] and T_[j][1] < T_[i][3]: print("   重疊：", TT[i][2], "／", TT[j][2])
        r = T_[i]
        if any(any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 30)) for a, b in segs): print("   壓線：", TT[i][2], [round(v, 1) for v in r])
    print(f"[檢查] {sh.name}：文字重疊 {over}、文字壓設計線 {press}、出界 {outb}（地物線與文字的交疊未計）")

# ---------- 輸出 ----------
base = f"{dd.PRE}{stamp}_A3_新設側溝平面配置圖_1-{SCALE:.0f}_{dd.ver('plan_view')}_TWD97_GENIE"

doc = ezdxf.new("R2018", setup=True); doc.header["$LTSCALE"] = 5
doc.styles.add("GENIE", font="GENISO.shx").dxf.bigfont = "GENIE.shx"
for nm, (aci, lt, *_r) in LAYERS.items(): doc.layers.add(nm, color=aci, linetype=lt or "CONTINUOUS")
m = doc.modelspace()
for k, sh in enumerate(sheets):
    ox = k * 450.0
    for it in sh.items:
        if it[0] == "poly": m.add_lwpolyline([(p[0] + ox, p[1]) for p in it[1]], dxfattribs={"layer": it[2]})
        else:
            _, (x, y), s, ha, h, rot, wf = it
            t = m.add_text(s, height=h, rotation=rot, dxfattribs={"layer": "文字", "style": "GENIE", "width": wf})
            t.set_placement((x + ox, y), align={"left": TA.MIDDLE_LEFT, "center": TA.MIDDLE_CENTER, "right": TA.MIDDLE_RIGHT}[ha])
dxf_path = os.path.join(OUT, base + ".dxf")
if os.path.exists(dxf_path): sys.exit(f"{dxf_path} 已存在，不覆蓋")
doc.saveas(dxf_path)
fp = FontProperties(fname=r"C:\Windows\Fonts\msjhl.ttc")
pdf_path = os.path.join(OUT, base + ".pdf")
with PdfPages(pdf_path) as pdf:
    for k, sh in enumerate(sheets):
        fig = plt.figure(figsize=(W_ / 25.4, H_ / 25.4)); ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, W_); ax.set_ylim(0, H_); ax.set_aspect("equal"); ax.axis("off")
        for it in sh.items:
            if it[0] == "poly":
                aci, lt, col, lw = LAYERS[it[2]]
                ax.plot(it[1][:, 0], it[1][:, 1], color=col, lw=lw * 72 / 25.4, ls={"DASHED": (0, (6, 3)), "CENTER": (0, (12, 3, 3, 3))}.get(lt, "-"))
            else:
                _, (x, y), s, ha, h, rot, wf = it
                tp = TextPath((0, 0), s, size=h, prop=fp); w = tw(s, h, wf); sx = w / max(tp.get_extents().x1, 1e-6)
                a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
                ax.add_patch(PathPatch(Affine2D().scale(sx, 1).translate(a0, -h * 0.40).rotate_deg(rot).translate(x, y).transform_path(tp), color="#000000", lw=0))
        pdf.savefig(fig); png = os.path.join(PREV, f"{base}_p{k+1}.png"); fig.savefig(png, dpi=200); plt.close(fig); print("PNG：", png)
print("DXF：", dxf_path); print("PDF：", pdf_path)









