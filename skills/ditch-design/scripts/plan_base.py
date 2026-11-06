"""平面圖共用（ditch-design，由 P33 plan_base 一般化）：定線、測量圖地物（含 SF 地物）、既有側溝文字、測量圖圖例、
新設側溝與集水井幾何、臨時擋土樁列、橫斷面切線樁號、折線裁切。所有案件值讀 ditch_config.json（dd 模組）。
由 cross_sections、plan_view、plan_profile、cadastral_sheet、standard_drawings 引用。
限制：側溝為直線（定線 DXF 各側一條兩點 LWPOLYLINE），每條側溝兩端各一座集水井。
紙面座標：定線轉正，0K+000（北、下游）在左；紙面 +y＝東（中心線左轉 90°）。
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import ezdxf
import ezdxf.path
from ezdxf.render import hatching

import dd
HERE = dd.HERE; CFG = dd.CFG; P_ = dd.P_
OUTER = P_["W"] / 2 + P_["t_wall"]; HALF_W = P_["well_in"] / 2 + P_["well_wall"]

alg = ezdxf.readfile(dd.src(CFG["alignment"]["dxf"])).modelspace()
def line_of(layer): return np.array([tuple(p) for p in alg.query(f'LWPOLYLINE[layer=="{layer}"]').first.get_points("xy")])
CLn = line_of(CFG["alignment"].get("centerline_layer", "中心線1"))
C0 = CLn[0]; Lc = float(np.hypot(*(CLn[1] - CLn[0]))); tv = (CLn[1] - CLn[0]) / Lc; nv = np.array([-tv[1], tv[0]])
# side：路外側方向（中心線左側＝-nv，右側＝+nv；面向下游左岸在左）
SIDES = {d["side"]: (line_of(d["line_layer"]), -1 if d.get("lr", "left") == "left" else 1) for d in dd.DITCHES}
KEYS = dd.SIDE_KEYS

def make_T(origin, x0, y0, K):
    """世界座標 → 紙面：origin 對到紙面 (x0, y0)，沿中心線方向為 +x，比例 K mm/m"""
    def T(P):
        d = np.atleast_2d(P)[:, :2] - origin
        return np.column_stack([x0 + (d @ tv) * K, y0 + (d @ nv) * K])
    return T

def clip(P, r):
    """折線裁到矩形 r=(x0, y0, x1, y1) 內（逐段 Liang–Barsky）"""
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

def ent_pts(v):
    t = v.dxftype()
    if t == "LINE": return [np.array([tuple(v.dxf.start)[:2], tuple(v.dxf.end)[:2]])]
    if t == "POLYLINE": P = [(x.dxf.location.x, x.dxf.location.y) for x in v.vertices]
    elif t == "LWPOLYLINE": P = [tuple(p) for p in v.get_points("xy")]
    elif t == "HATCH":
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

# ---------- 測量圖地物 ----------
_src = ezdxf.readfile(dd.src(CFG["src_dxf"]), encoding="utf-8"); msp = _src.modelspace()
LG = CFG["legend"]["box"]
SKIPB = tuple(CFG["layers"].get("skip_blocks", ["POINT", "CPOINT"]))
FEATS, FTXT = [], []                       # (世界折線, 圖層)；(世界點, 符號文字)
def _sym_text(e):
    for v in e.virtual_entities():
        if v.dxftype() == "TEXT": FTXT.append((np.array(v.dxf.insert)[:2], v.dxf.text))
for lay in CFG["layers"]["features"]:
    lay_out = "既有側溝" if CFG["layers"].get("existing_ditch_keyword", "側溝") in lay else "地物"
    for e in msp.query(f'*[layer=="{lay}"]'):
        if e.dxftype() == "INSERT":
            if e.dxf.name in SKIPB: continue
            ip = e.dxf.insert
            if LG[0] <= ip.x <= LG[2] and LG[1] <= ip.y <= LG[3]: continue
            ps = [q for v in e.virtual_entities() for q in ent_pts(v)]; _sym_text(e)
        else: ps = ent_pts(e)
        FEATS += [(P, lay_out) for P in ps]
MLAB = [(np.array(e.dxf.insert)[:2], e.plain_text()) for e in msp.query(f'MTEXT[layer=="{CFG["layers"].get("existing_ditch_label_layer", "HATCH1")}"]')]   # 既有溝名稱（110X120暗溝…）
_sfm = ezdxf.readfile(dd.src(CFG["sf_dxf"]), encoding="utf-8").modelspace() if CFG.get("sf_dxf") else []
for e in _sfm:
    if e.dxftype() == "HATCH":
        for bp in ezdxf.path.from_hatch(e):
            pts = np.array([(v.x, v.y) for v in bp.flattening(0.05)])
            if len(pts) > 1: FEATS.append((pts, "SF地物"))
        try: FEATS += [(np.array([(a.x, a.y), (b.x, b.y)]), "SF地物") for a, b in hatching.hatch_entity(e)]
        except hatching.HatchingError: pass
    elif e.dxftype() == "INSERT":
        FEATS += [(q, "SF地物") for v in e.virtual_entities() for q in ent_pts(v)]; _sym_text(e)
# 測量控制點（CPOINT 圖塊，含高程）
_cpb, _cpt = CFG["layers"].get("control_point_block", "CPOINT"), CFG["layers"].get("control_point_tag", "CNTP")
CPTS = [({a.dxf.tag: a.dxf.text for a in e.attribs}.get(_cpt, "?"), np.array(e.dxf.insert)) for e in msp.query(f'INSERT[name=="{_cpb}"]')]

# 房屋（SF 地物填線的邊界，閉合多邊形）
from matplotlib.path import Path as _Path
HOUSES = []
for e in _sfm:
    if e.dxftype() == "HATCH":
        for bp in ezdxf.path.from_hatch(e):
            pts = np.array([(v.x, v.y) for v in bp.flattening(0.05)])
            if len(pts) > 3: HOUSES.append(pts)

# ---------- 臨時擋土：鋼軌樁（使用者 2026-11-06 確認：打 3 m @1 m、背插鐵板）----------
WORK_GAP = dd.WORK_GAP; PILE_SP = dd.PILE_SP; PILE_L = dd.PILE_L    # temp_shoring.offset_in／pile_sp／pile_l
GAP_OUT = dd.GAP_OUT                               # temp_shoring.offset_out：路外側樁心距外壁（鐵板兼外模）
EXC_HALF = OUTER + WORK_GAP                        # 路內側：溝中心到開挖邊（樁心）
WELL_EXC_HALF = HALF_W + WORK_GAP
# 2026-11-06 橫斷面 V2（0K+002.20）：集水井路外側鋼軌樁打在既有側溝外緣線上（不再外凸至房屋側），
# 集水井整座往路內側移 WELL_SHIFT；井外壁＝外緣線內 10 cm（鐵板兼外模）
WELL_SHIFT = HALF_W - OUTER + GAP_OUT
def well_center(key, sc):
    """集水井中心世界座標（側溝樁距 sc＝0 或 L），已含往路內側位移"""
    P, side = SIDES[key]; L = float(np.hypot(*(P[1] - P[0]))); u = (P[1] - P[0]) / L
    return P[0] + u * sc - nv * side * WELL_SHIFT
def exc_offsets(key, well=False):
    """(路內側, 路外側) 側溝中心線到樁心距離（集水井段已含往路內位移）"""
    if well: return HALF_W + WORK_GAP + WELL_SHIFT, HALF_W + GAP_OUT - WELL_SHIFT
    return OUTER + WORK_GAP, OUTER + GAP_OUT
def pile_lines(key):
    """開挖邊（樁列）世界折線：溝段兩側直線＋兩端集水井外框；路外側開挖邊貼外壁 10 cm"""
    P, side = SIDES[key]; L = float(np.hypot(*(P[1] - P[0]))); u = (P[1] - P[0]) / L; n = np.array([-u[1], u[0]])
    so = 1 if (n @ (nv * side)) > 0 else -1                       # n 方向是否為路外側
    out = []
    WA = HALF_W + WORK_GAP                                        # 集水井沿溝向開挖半寬
    for sgn in (1, -1):
        e_in, e_out = exc_offsets(key); w_in, w_out = exc_offsets(key, True)
        e, w = (e_out, w_out) if sgn == so else (e_in, w_in)
        a, b = -WA, L + WA
        pts = [P[0] + u * a + n * sgn * w, P[0] + u * WA + n * sgn * w, P[0] + u * WA + n * sgn * e,
               P[0] + u * (L - WA) + n * sgn * e, P[0] + u * (L - WA) + n * sgn * w, P[0] + u * b + n * sgn * w]
        out.append(np.array(pts))
    w_in, w_out = exc_offsets(key, True)
    for sc in (-WA, L + WA):
        out.append(np.array([P[0] + u * sc + n * so * w_out, P[0] + u * sc - n * so * w_in]))
    return out
def pile_points(key):
    pts = []
    for Ln in pile_lines(key):
        seg = np.hypot(*np.diff(Ln, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
        for d in np.arange(0, cum[-1] + 1e-6, PILE_SP):
            i = min(np.searchsorted(cum, d, side="right") - 1, len(seg) - 1); t = (d - cum[i]) / seg[i]
            pts.append(Ln[i] + (Ln[i + 1] - Ln[i]) * t)
        pts.append(Ln[-1])
    return np.unique(np.round(np.array(pts), 3), axis=0)
def house_clearance(pts, clear=0.30):
    """各樁到最近房屋邊界的距離；在房屋內為負值"""
    out = np.full(len(pts), np.inf)
    for H in HOUSES:
        inside = _Path(H).contains_points(pts)
        a, b = H[:-1], H[1:]; ab = b - a; L2 = np.maximum((ab ** 2).sum(1), 1e-12)
        t = np.clip(((pts[:, None, :] - a[None]) * ab[None]).sum(2) / L2[None], 0, 1)
        d = np.hypot(*(pts[:, None, :] - (a[None] + t[..., None] * ab[None])).transpose(2, 0, 1)).min(1)
        out = np.minimum(out, np.where(inside, -d, d))
    return out

def ditch_polys(key):
    """新設側溝（溝外壁、溝內壁）與集水井（內、外框）的世界座標折線：[(折線, 圖層)]"""
    P, side = SIDES[key]; L = float(np.hypot(*(P[1] - P[0]))); u = (P[1] - P[0]) / L; n = np.array([-u[1], u[0]])
    out = []
    for off in (-OUTER, OUTER, -P_["W"] / 2, P_["W"] / 2):
        out.append((np.array([P[0] + u * HALF_W + n * off, P[0] + u * (L - HALF_W) + n * off]), "設計側溝"))
    for sc in (0.0, L):
        c = well_center(key, sc)
        for hw in (P_["well_in"] / 2, HALF_W):
            out.append((np.array([c + u * hw + n * hw, c - u * hw + n * hw, c - u * hw - n * hw, c + u * hw - n * hw, c + u * hw + n * hw]), "集水井"))
    return out, L, u, n

def section_cuts():
    """橫斷面樁號（道路中心線 0K+000 起算，自有設施處起切）：[(中心線樁距, 說明)]，與 cross_sections.py 同規則"""
    G = {}
    for key in KEYS:
        P, side = SIDES[key]; L = float(np.hypot(*(P[1] - P[0])))
        c0 = float((P[0] - C0) @ tv); c1 = float((P[1] - C0) @ tv); G[key] = (c0, (c1 - c0) / L, L)
    c = lambda k, s_: G[k][0] + G[k][1] * s_
    w0 = [c(k, 0.0) for k in KEYS]; w1 = [c(k, G[k][2]) for k in KEYS]
    j0 = sorted((c(k, HALF_W), k) for k in KEYS); j1 = sorted((c(k, G[k][2] - HALF_W), k) for k in KEYS)
    cuts = [(round(float(np.mean(w0)), 2), "集水井")] + [(round(x + 0.02, 2), f"{k} 側交接面") for x, k in j0]
    cuts += [(float(v), "") for v in np.arange(20.0, min(x for x, _ in j1) - 1.0, 20.0) if v > max(x for x, _ in j0) + 1.0]
    cuts += [(round(x - 0.02, 2), f"{k} 側交接面") for x, k in j1] + [(round(float(np.mean(w1)), 2), "集水井")]
    return cuts
WELL_ID = dd.WELL_ID                                # design.wells[]：(側別, 0 起點／1 終點) → 編號
def well_names(end):
    """某端（0 起點、1 終點）各側集水井編號，例：#AC1、#BC1"""
    return "、".join(WELL_ID[(k, end)] for k in KEYS if (k, end) in WELL_ID)
