"""原始地形平面總圖、縱斷面、橫斷面出圖產生器（A3 橫式，樣板 v4.0）。

用法：python -I section_drawings.py <案件設定.json> [--stamp YYYYMMDD_HHMM]
案件相關的路徑、圖層、座標、圖標欄都在設定檔，本檔不放案件資料；設定格式見 templates/case_config.example.json。
"""
import sys, os, json, datetime, math
import numpy as np
import ezdxf
from ezdxf.enums import TextEntityAlignment as TA
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.tri as mtri

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2: sys.exit("用法：python -I section_drawings.py <案件設定.json> [--stamp YYYYMMDD_HHMM]")
CFG_PATH = os.path.abspath(sys.argv[1])
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))   # 容許記事本存的 BOM
HERE = os.path.dirname(os.path.abspath(__file__))
def cpath(p): return p if os.path.isabs(p) else os.path.join(os.path.dirname(CFG_PATH), p)   # 設定檔內的相對路徑以設定檔所在資料夾為準
OUT_DIR = cpath(CFG["out_dir"])
PREV = cpath(CFG.get("preview_dir", CFG["out_dir"]))       # 預覽 PNG 資料夾
SRC = cpath(CFG["src_dxf"])                               # 原始地形 DXF
stamp = sys.argv[sys.argv.index("--stamp") + 1] if "--stamp" in sys.argv else datetime.datetime.now().strftime("%Y%m%d_%H%M")
PREFIX = CFG.get("file_prefix", "")                       # 例：「（桃園）」
VER = CFG.get("version", "v1.0")
os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(PREV, exist_ok=True)
LY_SRC = CFG["layers"]; PLAN = CFG["plan"]; LEG = CFG.get("legend")

# ---------- 圖標欄資訊（未提供者標【待補】）----------
TB_INFO = dict(agency="【機關名稱待補】", agency_en="【Agency name TBD】", project="【工程名稱待補】",
               designer="辰璟工程技術顧問有限公司", designer_en="Chen-Jing Engineering Co.,Ltd")
TB_INFO.update(CFG.get("title_block", {}))

c = np.load(cpath(CFG["alignment_npz"]))
d = np.load(cpath(CFG["tin_npz"]))
CL = c["cl"]; ST = c["st"]; PTS = c["pts"]; NRM = c["nrm"]; BW = c["W"]; BE = c["E"]
tin = mtri.Triangulation(d["points"][:, 0], d["points"][:, 1], d["triangles"])
G = mtri.LinearTriInterpolator(tin, d["points"][:, 2])

def sta(s):
    if abs(s - round(s)) < 1e-6:
        k = int(round(s)); return f"{k//1000}K+{k%1000:03d}"
    return f"{int(s)//1000}K+{s%1000:06.2f}"

def cut(p0, n, bank, maxd=80.0):
    a, b = bank[:-1], bank[1:]; r = b - a
    den = n[0]*r[:, 1] - n[1]*r[:, 0]
    dx, dy = a[:, 0]-p0[0], a[:, 1]-p0[1]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (dx*r[:, 1] - dy*r[:, 0]) / den
        u = (dx*n[1] - dy*n[0]) / den
    ok = (np.abs(den) > 1e-12) & (u >= 0) & (u <= 1) & (np.abs(t) <= maxd)
    return t[ok]

# ---------- 圖紙抽象：單位 = 紙面 mm ----------
W_, H_ = 420.0, 297.0
TXT = 7.06      # 20 pt
TBT = 4.94      # 14 pt (圖標欄)
# 圖層設定依使用者 v3 DWG（2026-11-03）：顏色 ACI 照其檔；RGB 為 None 者只用 ACI（DXF 不寫真彩）
# 名稱: (ACI, 真彩 RGB 或 None, 線寬mm, 圖層線型, 預覽顏色)
LAYERS = {
    "圖框": (7, None, 0.50, None, "#000000"),
    "圖標欄": (7, None, 0.35, None, "#000000"),
    "資料帶": (7, None, 0.25, None, "#000000"),
    "格線": (254, None, 0.13, None, "#A0A0A0"),          # v4：1 m 格線最淺（黑白 CTB → #CCCCCC）
    "主格線": (253, None, 0.18, None, "#808080"),        # 5 m 格線次淺（#A3A3A3）
    "原始地面線": (252, None, 0.70, None, "#000000"),    # v4：地面線比格線深（#666666）
    "計畫溪床線": (157, "#3E5C76", 1.00, None, "#3E5C76"),
    "中心線1": (22, "#C0392B", 0.35, "DASHED", "#C0392B"),
    "斷面中心線": (22, "#C0392B", 0.25, "DASHDOT", "#C0392B"),
    "岸線": (157, "#3E5C76", 0.50, None, "#3E5C76"),
    "斷面切線": (149, "#2B4560", 0.25, "DASHED", "#2B4560"),
    "計曲線": (252, None, 0.25, None, "#6F89A3"),        # v4：5 m 等高線較深（#666666）
    "首曲線": (254, None, 0.09, None, "#B3C0CE"),        # v4：1 m 等高線較淺（#CCCCCC）
    "地物": (253, "#9AA9B8", 0.13, None, "#9AA9B8"),
    "標註": (7, None, 0.25, None, "#000000"),
    "水流方向": (157, "#3E5C76", 0.35, None, "#3E5C76"),
    "文字": (7, None, 0.0, None, "#000000"),
}

WF = 0.5        # 圖框（圖標欄）以外的文字寬度係數
TB_WF = 0.7     # 圖標欄文字寬度係數（依使用者 v3 DWG 縱斷面圖標欄）

def tw(s, h=TXT, wf=None):
    return (WF if wf is None else wf) * sum(h if ord(ch) > 255 else 0.6*h for ch in s)

class Sheet:
    def __init__(self, name): self.items = []; self.name = name; self.wf = WF
    def poly(self, pts, layer, lt=None, lts=1.0): self.items.append(("poly", np.asarray(pts, float), layer, lt, lts))   # lt：個別線型（None＝隨圖層）
    def line(self, x1, y1, x2, y2, layer, lt=None, lts=1.0): self.poly([(x1, y1), (x2, y2)], layer, lt, lts)
    def rect(self, x, y, w, h, layer): self.poly([(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)], layer)
    def text(self, x, y, s, ha="left", h=TXT, rot=0): self.items.append(("text", (x, y), s, ha, h, rot, self.wf))

def mkt(x, y, s, ha="left", h=TXT, rot=0): return ("text", (x, y), s, ha, h, rot, WF)

def tpieces(it, pad=0.0):
    """文字外框（任意角度）：沿文字方向切成小段，各段取軸向外框"""
    _, (x, y), s, ha, h, rot, wf = it
    w = tw(s, h, wf)
    if rot in (0, 90):
        b = tbox(it); return [(b[0]-pad, b[1]-pad, b[2]+pad, b[3]+pad)]
    th = math.radians(rot); c, sn = math.cos(th), math.sin(th)
    a0 = 0 if ha == "left" else -w/2 if ha == "center" else -w
    k = max(1, int(w/1.5)); out = []
    for i in range(k):
        u0 = a0 + w*i/k; u1 = a0 + w*(i+1)/k
        pts = [(x + u*c - v*sn, y + u*sn + v*c) for u in (u0, u1) for v in (-h/2, h/2)]
        xs_ = [p[0] for p in pts]; ys_ = [p[1] for p in pts]
        out.append((min(xs_)-pad, min(ys_)-pad, max(xs_)+pad, max(ys_)+pad))
    return out

def tbox(it):
    _, (x, y), s, ha, h, rot, wf = it
    w = tw(s, h, wf)
    if rot not in (0, 90):
        pcs = tpieces(it)
        return (min(p[0] for p in pcs), min(p[1] for p in pcs), max(p[2] for p in pcs), max(p[3] for p in pcs))
    if rot == 0:
        x0 = x if ha == "left" else x - w/2 if ha == "center" else x - w
        return (x0, y - h/2, x0 + w, y + h/2)
    y0 = y if ha == "left" else y - w/2 if ha == "center" else y - w
    return (x - h/2, y0, x + h/2, y0 + w)

def seg_rect(S, r):
    x0, y0, x1, y1 = r
    dx = S[:, 2]-S[:, 0]; dy = S[:, 3]-S[:, 1]
    t0 = np.zeros(len(S)); t1 = np.ones(len(S)); ok = np.ones(len(S), bool)
    for p, q in ((-dx, S[:, 0]-x0), (dx, x1-S[:, 0]), (-dy, S[:, 1]-y0), (dy, y1-S[:, 1])):
        par = (p == 0)
        ok &= ~(par & (q < 0))
        with np.errstate(divide="ignore", invalid="ignore"):
            t = q / p
        neg = (p < 0) & ~par; pos = (p > 0) & ~par
        t0 = np.where(neg, np.maximum(t0, t), t0)
        t1 = np.where(pos, np.minimum(t1, t), t1)
    return ok & (t0 <= t1)

def lb(p, q, r):
    x0, y0, x1, y1 = r
    dx, dy = q[0]-p[0], q[1]-p[1]; t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0]-x0), (dx, x1-p[0]), (-dy, p[1]-y0), (dy, y1-p[1])):
        if pp == 0:
            if qq < 0: return None
        else:
            t = qq/pp
            if pp < 0: t0 = max(t0, t)
            else: t1 = min(t1, t)
    return (t0, t1) if t0 <= t1 else None

def clip_poly(P, frame, drops):
    """保留 frame 內、扣除 drops 矩形內的線段，回傳多條折線"""
    out = []; cur = []; prev_full = False
    for i in range(len(P)-1):
        p, q = P[i], P[i+1]
        iv = lb(p, q, frame)
        if iv is None:
            if len(cur) > 1: out.append(np.array(cur))
            cur = []; prev_full = False; continue
        keep = [iv]
        for r in drops:
            if max(p[0], q[0]) < r[0] or min(p[0], q[0]) > r[2] or max(p[1], q[1]) < r[1] or min(p[1], q[1]) > r[3]:
                continue
            h = lb(p, q, r)
            if h is None: continue
            nk = []
            for a, b in keep:
                if h[1] <= a or h[0] >= b: nk.append((a, b)); continue
                if h[0] > a: nk.append((a, h[0]))
                if h[1] < b: nk.append((h[1], b))
            keep = nk
        for a, b in keep:
            pa = p + (q-p)*a; pb = p + (q-p)*b
            if cur and a <= 1e-9 and prev_full: cur.append(pb)
            else:
                if len(cur) > 1: out.append(np.array(cur))
                cur = [pa, pb]
            prev_full = b >= 1-1e-9
            if b < 1-1e-9:
                if len(cur) > 1: out.append(np.array(cur))
                cur = []; prev_full = False
        if not keep: prev_full = False
    if len(cur) > 1: out.append(np.array(cur))
    return out

def frame(sh, name, scales, no):
    sh.rect(0, 0, W_, H_, "圖框"); sh.rect(10, 10, 400, 277, "圖框")
    sh.rect(10, 10, 400, 22, "圖標欄")
    for x in (86, 188, 226, 298, 392): sh.line(x, 10, x, 32, "圖標欄")
    for x0, x1 in ((86, 188), (226, 298), (392, 410)): sh.line(x0, 21, x1, 21, "圖標欄")
    sh.line(262, 10, 262, 32, "圖標欄")
    yc = (14.94, 20.88, 26.82)
    sh.wf = TB_WF                                 # 圖標欄文字寬度係數（依使用者在 CAD 的調整：0.8）
    sh.text(48, yc[2], "主辦機關", "center", TBT); sh.text(48, yc[1], TB_INFO["agency"], "center", TBT)
    sh.text(48, yc[0], TB_INFO["agency_en"], "center", TBT)
    sh.text(89.5, 26.5, "工程名稱：" + TB_INFO["project"], "left", TBT)
    sh.text(89.5, 15.5, "圖　名：" + name, "left", TBT)
    sh.text(207, yc[2], "比例尺", "center", TBT)
    if len(scales) == 1: sh.text(207, yc[1], scales[0], "center", TBT)
    else:
        sh.text(207, yc[1], scales[0], "center", TBT); sh.text(207, yc[0], scales[1], "center", TBT)
    sh.text(229.5, 26.5, "設計：", "left", TBT); sh.text(265.5, 26.5, "主管：", "left", TBT)
    sh.text(229.5, 15.5, "繪圖：", "left", TBT); sh.text(265.5, 15.5, "校核：", "left", TBT)
    sh.text(345, yc[2], "設計單位", "center", TBT); sh.text(345, yc[1], TB_INFO["designer"], "center", TBT)
    sh.text(345, yc[0], TB_INFO["designer_en"], "center", TBT)
    sh.text(401, 26.5, "圖號", "center", TBT); sh.text(401, 15.5, no, "center", TBT)
    sh.wf = WF

def dimtick(sh, x, y):
    sh.line(x-1.5, y-1.5, x+1.5, y+1.5, "標註")

sheets = []
sheetno = 0
def new_sheet(name, scales):
    global sheetno
    sheetno += 1
    sh = Sheet(name); frame(sh, name, scales, f"{sheetno:02d}"); sheets.append(sh); return sh

# ======================================================================
# 一、平面總圖 1/1000
# ======================================================================
doc_src = ezdxf.readfile(SRC); msrc = doc_src.modelspace()
def polys(layer):
    return [np.array([(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]) for e in msrc.query(f'POLYLINE[layer=="{layer}"]')]
ctr1, ctr5 = polys(LY_SRC["contour_minor"]), polys(LY_SRC["contour_major"])
feat = []
for lay in LY_SRC["features"]:
    feat += polys(lay)
for lay in LY_SRC.get("feature_circles", []):
    for e in msrc.query(f'CIRCLE[layer=="{lay}"]'):
        a = np.linspace(0, 2*np.pi, 37)
        feat.append(np.column_stack([e.dxf.center.x + e.dxf.radius*np.cos(a), e.dxf.center.y + e.dxf.radius*np.sin(a)]))
LG_BOX = tuple(LEG["box"]) if LEG else (0.0, 0.0, 0.0, 0.0)   # 原始測量圖「圖例表」所在範圍（世界座標 x0, y0, x1, y1）
SKIP_BLOCKS = set(LY_SRC.get("skip_blocks", ["POINT", "CPOINT", "N", "NORTH"]))   # 高程點、控制點、指北針等不當地物畫
def ent_polys(v):
    """LINE／POLYLINE／LWPOLYLINE／CIRCLE → 折線（世界座標）"""
    t = v.dxftype()
    if t == "LINE": return [np.array([tuple(v.dxf.start)[:2], tuple(v.dxf.end)[:2]])]
    if t in ("POLYLINE", "LWPOLYLINE"):
        P = [(x.dxf.location.x, x.dxf.location.y) for x in v.vertices] if t == "POLYLINE" else [tuple(p) for p in v.get_points("xy")]
        if len(P) < 2: return []
        if v.is_closed: P.append(P[0])
        return [np.array(P)]
    if t == "CIRCLE":
        a = np.linspace(0, 2*np.pi, 25); c = v.dxf.center; r = v.dxf.radius
        return [np.column_stack([c.x + r*np.cos(a), c.y + r*np.sin(a)])]
    return []
for e in msrc.query("INSERT"):                                # 地物符號（電力桿、水塔、導線點…）：圖例表內的不重複畫
    ip = e.dxf.insert
    if e.dxf.name in SKIP_BLOCKS: continue
    if LG_BOX[0] <= ip.x <= LG_BOX[2] and LG_BOX[1] <= ip.y <= LG_BOX[3]: continue
    for v in e.virtual_entities(): feat += ent_polys(v)

Ec, Nc = PLAN["center_world"]; MX0, MY0 = PLAN.get("center_paper", (111.0, 160.5)); SCP = 1.0   # 世界座標 (Ec, Nc) 置於紙面 (MX0, MY0)；1/1000 → 1 mm/m
def PM(P): P = np.asarray(P, float); return np.column_stack([MX0 + (P[:, 0]-Ec)*SCP, MY0 + (P[:, 1]-Nc)*SCP])
FR = tuple(PLAN.get("frame", (26.0, 48.0, 196.0, 285.0)))          # 圖廓（紙面 mm）
sh = new_sheet("原始地形平面總圖", ["1/1000"])
sh.rect(FR[0], FR[1], FR[2]-FR[0], FR[3]-FR[1], "圖框")
# 座標刻度 (TWD97)
for E in PLAN["ticks_e"]:
    x = MX0 + (E-Ec)*SCP
    sh.line(x, FR[1], x, FR[1]+3, "標註"); sh.text(x, 42, f"{E}", "center")
for N in PLAN["ticks_n"]:
    y = MY0 + (N-Nc)*SCP
    sh.line(FR[0], y, FR[0]+3, y, "標註"); sh.text(19.5, y, f"{N}", "center", TXT, 90)
# 中心線、岸線、斷面切線與樁號
sh.poly(PM(CL[:, :2]), "中心線1", "CENTER", 0.1)
sh.poly(PM(BW), "岸線"); sh.poly(PM(BE), "岸線")
sec_ends = []
for s, p, n in zip(ST, PTS, NRM):
    a = p[:2] + n*20.0; b = p[:2] - n*20.0
    A = PM([a])[0]; B = PM([b])[0]
    sh.poly([A, B], "斷面切線")
    sec_ends.append((s, A, B))
# 定線左側（上游方向的左手邊）水流方向箭頭：向下游、平行定線、每 50 m 一個、距定線 2 字元
ARW_OFF, ARW_L, ARW_H = 0.5*TXT, 8.0, 2.5
arrow_drops = []
for sa_ in np.arange(PLAN.get("arrow_start", 15.0), ST[-1], 50.0):   # 預設 15、65、115…：避開 20 m 一刀的斷面線
    P0 = PM([[np.interp(sa_, CL[:, 3], CL[:, 0]), np.interp(sa_, CL[:, 3], CL[:, 1])]])[0]
    P1 = PM([[np.interp(sa_+1, CL[:, 3], CL[:, 0]), np.interp(sa_+1, CL[:, 3], CL[:, 1])]])[0]
    P2 = PM([[np.interp(sa_-1, CL[:, 3], CL[:, 0]), np.interp(sa_-1, CL[:, 3], CL[:, 1])]])[0]
    t = (P1 - P2) / np.hypot(*(P1 - P2)); nl = np.array([-t[1], t[0]])
    C = P0 + nl*ARW_OFF; tip = C - t*ARW_L/2; tail = C + t*ARW_L/2
    sh.poly([tail, tip], "水流方向")
    sh.poly([tip + t*ARW_H + nl*1.3, tip, tip + t*ARW_H - nl*1.3], "水流方向")
    for f in np.linspace(0, 1, 6):
        q = tail + (tip - tail)*f; arrow_drops.append((q[0]-2.2, q[1]-2.2, q[0]+2.2, q[1]+2.2))
# 樁號：沿斷面線方向（與取樣線平行），接在西端外側；與其他文字、線條相碰時，垂直斷面線方向微移
def obstacles():
    segs = []
    for it in sh.items:
        if it[0] == "poly":
            for a_, b_ in zip(it[1][:-1], it[1][1:]): segs.append((a_[0], a_[1], b_[0], b_[1]))
    return np.array(segs)
placed = []
for s, A, B in sec_ends[::-1]:                              # 由上游往下游排，上游端受圖框限制最緊
    dd = B - A; dd = dd / np.hypot(*dd)                    # 西端 → 東端（往右讀）
    ang = math.degrees(math.atan2(dd[1], dd[0])); pv = np.array([-dd[1], dd[0]])
    base = A - dd * 5.0; S_ = obstacles(); done = False
    for o in (0, 1.5, -1.5, 3, -3, 4.5, -4.5, 6, -6, 8, -8, 10, -10):
        anchor = base + pv * o
        it = mkt(anchor[0], anchor[1], sta(s), "right", TXT, ang)
        pcs = tpieces(it, 0.5)
        if any(seg_rect(S_, r).any() for r in pcs): continue
        if any(p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3] for p in pcs for pl in placed for q in pl): continue
        sh.items.append(it); placed.append(pcs); done = True; break
    if not done:
        print("樁號未能避開：", sta(s), "anchor", np.round(base, 1), "ang", round(ang, 1))
        for o in (0, 3, -3):
            anchor = base + pv * o; it = mkt(anchor[0], anchor[1], sta(s), "right", TXT, ang)
            hit = [r for r in tpieces(it, 0.5) if seg_rect(S_, r).any()]
            print("  o", o, "線條相碰片段數", len(hit), "bbox", np.round(tbox(it), 1))
# 等高線與地物：扣除文字框、箭頭後再畫
drops = []
for it in sh.items:
    if it[0] == "text":
        for r in tpieces(it, 1.5):
            if FR[0] < r[0] and r[2] < FR[2] and FR[1] < r[1] and r[3] < FR[3]: drops.append(r)
drops += arrow_drops
inner = (FR[0], FR[1], FR[2], FR[3])
for lay, group in (("首曲線", ctr1), ("計曲線", ctr5), ("地物", feat)):
    for P in group:
        for q in clip_poly(PM(P), inner, drops): sh.poly(q, lay)
# 圖例表：沿用原始測量圖 DXF 的「圖例表」（表格線、圖示、地物名稱），等比放大 LGS 倍置於右上；文字改 14 pt（表名 20 pt）
from ezdxf import bbox as _bbox
def draw_legend():
    lg_ents = []
    for e in msrc.query(f'*[layer=="{LEG["layer"]}"]'):
        b_ = _bbox.extents([e])
        if b_.has_data and LG_BOX[0] <= b_.extmin.x and b_.extmax.x <= LG_BOX[2] and LG_BOX[1] <= b_.extmin.y and b_.extmax.y <= LG_BOX[3]:
            lg_ents.append(e)
    if not lg_ents: print("  圖例表：範圍內找不到實體，請檢查 legend.box 與 legend.layer"); return
    lgb = _bbox.extents(lg_ents); LGX0, LGY1 = lgb.extmin.x, lgb.extmax.y
    LGS = LEG.get("scale", 4.9); TX0, TY1 = LEG.get("anchor_paper", (203.0, 285.0))   # 圖例表左上角置於紙面 (TX0, TY1)
    bank_layers = set(LEG.get("bank_layers", []))
    def LG(P): P = np.asarray(P, float); return np.column_stack([TX0 + (P[:, 0]-LGX0)*LGS, TY1 + (P[:, 1]-LGY1)*LGS])
    def lg_text(t_, h_):
        al_, p_, *_ = t_.get_placement(); q_ = LG([tuple(p_)[:2]])[0]; nm_ = al_.name
        ha_ = "center" if nm_.endswith("CENTER") or nm_ == "MIDDLE" else "right" if nm_.endswith("RIGHT") else "left"
        sh.text(q_[0], q_[1], t_.dxf.text, ha_, h_)
    for e in lg_ents:
        if e.dxftype() == "TEXT": lg_text(e, TXT if e.dxf.height >= 1.4 else TBT)
        elif e.dxftype() == "INSERT":
            ves = list(e.virtual_entities())
            txs = [v for v in ves if v.dxftype() == "TEXT"]
            geo = [(LG(P), "岸線" if v.dxf.layer in bank_layers else "地物") for v in ves if v.dxftype() != "TEXT" for P in ent_polys(v)]
            if txs and geo:                                       # 符號內含文字（如變壓箱座的 E）：符號放大到能容納 14 pt 字
                allp = np.vstack([g[0] for g in geo]); c_ = (allp.min(0) + allp.max(0)) / 2; hh = np.ptp(allp[:, 1])
                k_ = max(1.0, 2.0 * TBT / max(hh, 1e-6))
                geo = [(c_ + (P - c_) * k_, ly) for P, ly in geo]
                for v in txs: sh.text(c_[0], c_[1], v.dxf.text, "center", TBT)
            else:
                for v in txs: lg_text(v, TBT)
            for P, ly in geo: sh.poly(P, ly)
        else:
            for P in ent_polys(e): sh.poly(LG(P), "圖標欄")
    print(f"  圖例表：{len(lg_ents)} 個實體，放大 {LGS} 倍，範圍 x {TX0:.1f}～{TX0+(lgb.extmax.x-LGX0)*LGS:.1f}、y {TY1-(LGY1-lgb.extmin.y)*LGS:.1f}～{TY1:.1f}")
if LEG: draw_legend()
else: print("  圖例表：設定檔未指定 legend，本次不畫")
# 指北針與比例尺
sh.poly([(225, 56), (220, 42), (225, 46), (230, 42), (225, 56)], "標註"); sh.text(225, 65.5, "N", "center")
sh.text(312, 68, "比例尺 1/1000", "center")
sh.rect(262, 54, 100, 3.5, "標註"); sh.line(312, 54, 312, 57.5, "標註")
for x, t in ((262, "0"), (312, "50"), (362, "100 m")): sh.text(x, 42, t, "center")

# ======================================================================
# 二、縱斷面 H=1/700, V=1/500，全段併成一張（上方附平面視埠）
#     資料帶文字一律逆時針旋轉 90°；圖框以外文字寬度係數 0.5
# ======================================================================
SHOW_VIEWPORT = False
HS, VS = 500.0, 250.0
XM, YM = 1000/HS, 1000/VS
PT = TBT                       # 資料帶數值、圖例 14 pt
BX0 = 18.0                     # 縱斷面框左緣（左側高程軸文字在其外側）
TCW = 25.0                     # 資料帶左側列標題框寬（列標題橫排置中；依使用者 v3 DWG）
DX0 = BX0 + TCW + 1.4          # 資料帶右側方框起點（44.4）
X0 = DX0 + 8.9                 # 起點樁號 x（53.3）
rows = [("距離", 34.0, 17.0), ("樁號", 54.0, 19.0), ("原始高程", 76.0, 17.0), ("坡度(%)", 96.0, 17.0)]
ROWD = {nm: (y0, h) for nm, y0, h in rows}
PY0 = 118.0
VY1 = 285.0
PROF = CFG.get("profile", {})
_b = [0.0] + [float(x) for x in PROF.get("split_at", [])] + [float(ST[-1])]   # 分張樁號（每張約 120 m），例：[120]
splits = list(zip(_b[:-1], _b[1:]))

def cl_at(s):
    return np.array([np.interp(s, CL[:, 3], CL[:, 0]), np.interp(s, CL[:, 3], CL[:, 1])])

def draw_viewport(sh, sa, sb, x0v, x1v, y0v, y1v, sts):
    """平面視埠：與縱斷面同水平比例，以 sa～sb 弦向轉正；不含取樣線；含里程、定線、兩岸線、等高線、地物"""
    Pa, Pb = cl_at(sa), cl_at(sb)
    u_ = (Pb - Pa) / np.hypot(*(Pb - Pa)); w_ = np.array([-u_[1], u_[0]])          # w_ = 左側（上游方向看）
    lat = np.r_[(CL[:, :2] - Pa) @ w_, (BW - Pa) @ w_, (BE - Pa) @ w_]
    vmid = (lat.min() + lat.max()) / 2; yc = (y0v + y1v) / 2
    def T(P):
        d = np.asarray(P, float) - Pa
        return np.column_stack([X0 + (d @ u_) * XM, yc + ((d @ w_) - vmid) * XM])
    print(f"  視埠：側向 {lat.min():.1f}～{lat.max():.1f} m（含兩岸線），需高 {(lat.max()-lat.min())*XM:.1f} mm，視埠高 {y1v-y0v:.1f} mm")
    vx0 = DX0
    fr = (vx0, y0v, x1v, y1v)
    sh.rect(vx0, y0v, x1v - vx0, y1v - y0v, "資料帶")
    sh.rect(x0v, y0v, TCW, y1v - y0v, "資料帶")                 # 左側標題框
    sh.text(x0v + TCW/2, y0v + (y1v - y0v)*0.62, "平面圖 1/700", "center", PT, 90)
    for q in clip_poly(T(CL[:, :2]), fr, []): sh.poly(q, "中心線1")
    for B_ in (BW, BE):
        for q in clip_poly(T(B_), fr, []): sh.poly(q, "岸線")
    for s in sts:
        c = T(cl_at(s)[None, :])[0]
        tp = T(cl_at(s + 1)[None, :])[0] - T(cl_at(s - 1)[None, :])[0]; tp = tp / np.hypot(*tp); nrm_ = np.array([-tp[1], tp[0]])
        sh.line(c[0] - nrm_[0]*1.5, c[1] - nrm_[1]*1.5, c[0] + nrm_[0]*1.5, c[1] + nrm_[1]*1.5, "標註")
    S_ = np.array([(a_[0], a_[1], b_[0], b_[1]) for it in sh.items if it[0] == "poly" for a_, b_ in zip(it[1][:-1], it[1][1:])])
    placed_ = []
    for s in sts:
        c = T(cl_at(s)[None, :])[0]; ok_ = False
        for dx_, dy in [(a_, b_) for a_ in (0.0, 6.0, 12.0) for b_ in (5.0, -5.0, 8.5, -8.5, 12.0, -12.0, 15.5, -15.5, 19.0, -19.0, 22.5, -22.5)]:
            it = mkt(c[0] + dx_, c[1] + dy, sta(s), "center", PT, 0)
            b = tbox(it)
            if b[0] < vx0 + 0.8: continue
            if b[1] < y0v + 0.8 or b[3] > y1v - 0.8: continue
            pcs = tpieces(it, 0.5)
            if any(seg_rect(S_, r).any() for r in pcs): continue
            if any(p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3] for p in pcs for pl in placed_ for q in pl): continue
            sh.items.append(it); placed_.append(pcs); ok_ = True; break
        if not ok_: print("  視埠里程未能避開：", sta(s))
    # 指北針（置於左側標題框下部，北向依弦向轉正後的方向）
    npv = np.array([u_[1], w_[1]]); npv = npv / np.hypot(*npv)
    cN = np.array([x0v + TCW/2, y0v + (y1v - y0v)*0.22]); tipN = cN + npv * 3.0; tailN = cN - npv * 3.0
    sh.line(tailN[0], tailN[1], tipN[0], tipN[1], "標註")
    pN = np.array([-npv[1], npv[0]])
    sh.poly([tipN - npv*2.2 + pN*1.1, tipN, tipN - npv*2.2 - pN*1.1], "標註")
    sh.text(tipN[0] + npv[0]*4.2, tipN[1] + npv[1]*4.2, "N", "center", PT)
    drops_ = []
    for it in sh.items:
        if it[0] == "text":
            for r in tpieces(it, 1.5):
                if vx0 < r[0] and r[2] < x1v and y0v < r[1] and r[3] < y1v: drops_.append(r)
    for lay, group in (("首曲線", ctr1), ("計曲線", ctr5), ("地物", feat)):
        for P in group:
            for q in clip_poly(T(P), fr, drops_): sh.poly(q, lay)

for pi, sa_sb in enumerate(splits):
    sh = new_sheet(f"原始地形縱斷面圖({pi+1}/{len(splits)})", [f"H=1/{HS:.0f}", f"V=1/{VS:.0f}"])
    sa, sb = sa_sb
    mz = (CL[:, 3] >= sa - 1e-9) & (CL[:, 3] <= sb + 1e-9)
    zlo, zhi = CL[mz, 2].min(), CL[mz, 2].max()
    BASE_Z = math.floor(zlo - 3); TOP_Z = math.ceil(zhi + 3)          # 原地形線 ±3 m（取整數 m）
    PY1 = PY0 + (TOP_Z - BASE_Z) * YM
    x_end = X0 + (sb - sa) * XM
    BX1 = x_end + 3.1
    xs = lambda s: X0 + (s - sa) * XM
    ys = lambda z: PY0 + (z - BASE_Z) * YM
    print(f"縱斷面：高程 {BASE_Z}～{TOP_Z} m，框高 {PY1-PY0:.1f} mm，PY1={PY1:.1f}，x_end={x_end:.1f}，BX1={BX1:.1f}")
    sh.rect(BX0, PY0, BX1 - BX0, PY1 - PY0, "資料帶")
    for z in np.arange(BASE_Z + 1, TOP_Z, 1.0):                   # 只畫水平格線：每 5 m 虛線（DASHED）、每 1 m 點線（DOT）；不畫豎向格線
        if z % 5 == 0: sh.line(BX0, ys(z), BX1, ys(z), "主格線", "DASHED")
        else: sh.line(BX0, ys(z), BX1, ys(z), "格線", "DOT")
    for z in np.arange(BASE_Z, TOP_Z + 0.1, 1.0):
        if z % 5 == 0:
            sh.text(BX0 - 2, ys(z), f"{z:.0f}", "right", PT); sh.text(BX1 + 1.3, ys(z), f"{z:.0f}", "left", PT)
    sts = [s for s in ST if sa - 1e-9 <= s <= sb + 1e-9]
    xst = [xs(s) for s in sts]
    for nm, y0, h in rows:
        sh.rect(BX0, y0, TCW, h, "資料帶"); sh.rect(DX0, y0, BX1 - DX0, h, "資料帶")
        sh.text(BX0 + TCW/2, y0 + h/2, nm, "center", TXT)           # 列標題橫排
    sh.poly(np.column_stack([xs(CL[mz, 3]), ys(CL[mz, 2])]), "原始地面線", "DOT2", 0.1)
    zst = {s: np.interp(s, CL[:, 3], CL[:, 2]) for s in sts}
    for lo_ in ("樁號", "原始高程"):                                 # 樁號刻度：單一短線，自下列框頂往上 2.5 mm（不碰上列）
        gb = ROWD[lo_][0] + ROWD[lo_][1]
        for x_ in xst: sh.line(x_, gb, x_, gb + 2.5, "資料帶")
    for i, s in enumerate(sts):                                    # 數值對齊樁號（旋轉字左移 0.7 mm 以目視置中）
        y0, h = ROWD["樁號"]; sh.text(xst[i] - 0.7, y0 + h/2, sta(s), "center", PT, 90)
        y0, h = ROWD["原始高程"]; sh.text(xst[i] - 0.7, y0 + h/2, f"{zst[s]:.2f}", "center", PT, 90)
    y0, h = ROWD["距離"]; yd = y0 + 4.5
    sh.line(xst[0], yd, xst[-1], yd, "標註")
    for x_ in xst: sh.line(x_, yd - 1.3, x_, yd + 1.3, "資料帶")       # 尺寸線端點：垂直短線 ±1.3 mm
    for a, b, xa, xb in zip(sts[:-1], sts[1:], xst[:-1], xst[1:]):
        y0, h = ROWD["坡度(%)"]; sh.text((xa + xb) / 2, y0 + h/2, f"{(zst[b]-zst[a])/(b-a)*100:.1f}", "center", PT, 90)
        y0, h = ROWD["距離"]; sh.text((xa + xb) / 2, y0 + 10.5, f"L={b-a:.2f}", "center", PT)
    # 圖例（單列 14 pt）
    LY = PY1 + 6.0
    x = BX0
    sh.text(x, LY, "圖例", "left", PT); x += tw("圖例", PT) + 5        # 間距依使用者 v3 DWG
    sh.line(x, LY, x + 10, LY, "原始地面線"); x += 10 + 2.5
    t = "原始地形（中心線1）"; sh.text(x, LY, t, "left", PT); x += tw(t, PT) + 5
    sh.line(x, LY, x + 10, LY, "計畫溪床線"); x += 10 + 2.5
    sh.text(x, LY, "計畫溪床線（待設計）", "left", PT)
    xr = BX1 - 1.0
    if pi < len(splits) - 1:
        t2 = f"接續第 {pi+2} 頁"; sh.text(xr, LY, t2, "right", PT); xr -= tw(t2, PT) + 7
    if pi > 0: sh.text(xr, LY, f"由第 {pi} 頁接續", "right", PT)
    if SHOW_VIEWPORT: draw_viewport(sh, sa, sb, BX0, BX1, PY1 + 11.0, VY1, sts)


# ======================================================================
# 三、橫斷面 1/300（框底＝該斷面原地形最低點往下 5 m，取 5 m 倍數）
# ======================================================================
SC = 1000/300.0
HALF = 20.0
u = np.arange(-HALF, HALF + 1e-9, 0.25)
secs = []
for s, p, n in zip(ST, PTS, NRM):
    xy = p[None, :2] + u[:, None] * n[None, :]       # +u = +n = 西側 = 右岸(面向下游)
    z = np.ma.filled(G(xy[:, 0], xy[:, 1]), np.nan)
    tw_ = cut(p[:2], n, BW); te_ = cut(p[:2], n, BE)
    tw_ = tw_[tw_ > 0]; te_ = te_[te_ < 0]
    dW = tw_.min() if len(tw_) else np.nan; dE = -te_.max() if len(te_) else np.nan
    gz = lambda uu: float(np.ma.filled(G(np.array([p[0]+uu*n[0]]), np.array([p[1]+uu*n[1]])), np.nan)[0])
    secs.append((s, p[2], z, dW, dE, gz(dW) if not np.isnan(dW) else np.nan, gz(-dE) if not np.isnan(dE) else np.nan))
per_sheet = 4
SEC_NOTES = False
npg = int(np.ceil(len(secs) / per_sheet))
CW, CH = 200.0, 253.0/2
for pi in range(npg):
    sh = new_sheet(f"原始地形橫斷面圖({pi+1}/{npg})", ["1/300"])
    chunk = secs[pi * per_sheet:(pi + 1) * per_sheet]
    for idx, (s, zc, z, dW, dE, zW, zE) in enumerate(chunk):
        col, row = idx % 2, idx // 2
        cx0 = 10 + col * CW; y0 = 287 - (row + 1) * CH; xc = cx0 + CW/2
        zmin = np.nanmin(np.r_[z, zc]); zmax = np.nanmax(np.r_[z, zc])
        base = int(math.floor(zmin - 5)); top = int(math.ceil(zmax + 5))      # 該斷面原地形 ±5 m（取整數 m）
        yb = y0 + 22.0; yt = yb + (top-base)*SC
        bx0, bx1 = xc - HALF*SC, xc + HALF*SC
        yz = lambda zz: yb + (zz-base)*SC
        sh.rect(bx0, yb, bx1-bx0, yt-yb, "資料帶")
        for zz in range(base+1, top):                                   # 每 5 m 實線、每 1 m 點線（DOT）
            if zz % 5 == 0: sh.line(bx0, yz(zz), bx1, yz(zz), "主格線")
            else: sh.line(bx0, yz(zz), bx1, yz(zz), "格線", "DOT")
        for zz in range(base, top+1):
            if zz % 5 == 0:
                sh.text(bx0-3, yz(zz), f"{zz}", "right"); sh.text(bx1+3, yz(zz), f"{zz}", "left")
        for uu in range(-20, 21, 5):
            if abs(uu) == 20: continue
            if uu % 10 == 0: sh.line(xc+uu*SC, yb, xc+uu*SC, yt, "主格線")
            else: sh.line(xc+uu*SC, yb, xc+uu*SC, yt, "格線", "DOT")
        for uu, lab in zip((-20, -10, 0, 10, 20), ("左20", "10", "0", "10", "右20")):
            sh.text(xc+uu*SC, y0+14, lab, "center")
        ok = ~np.isnan(z); runs = []; cur = []
        for i in range(len(u)):
            if ok[i]: cur.append(i)
            elif cur: runs.append(cur); cur = []
        if cur: runs.append(cur)
        for r in runs:
            if len(r) > 1: sh.poly(np.column_stack([xc + u[r]*SC, yz(z[r])]), "原始地面線")
        sh.line(xc, yb, xc, yt, "斷面中心線"); sh.text(xc, yt + 5.5, "CL", "center")
        if not (np.isnan(dW) or np.isnan(dE)):
            xr, xl = xc + dW*SC, xc - dE*SC; yd = yt + 12.0
            sh.line(xl, yd, xr, yd, "標註"); dimtick(sh, xl, yd); dimtick(sh, xr, yd)
            for xx, zz in ((xl, zE), (xr, zW)):
                ye = yz(zz) + 1.5 if not np.isnan(zz) else yt
                sh.line(xx, yd + 1.5, xx, ye, "標註")
            sh.text((xl+xr)/2, yd + 3.5 + 3.53, f"{(dW+dE)*100:.0f}", "center")
        lab = sta(s); sh.text(bx0+10, y0+5.0, lab)
        sh.line(bx0+10, y0+0.5, bx0+10+tw(lab)+2, y0+0.5, "標註")
        sh.text(xc+5, y0+5.0, "挖：— m²　填：— m²")
    if SEC_NOTES and pi == npg-1 and len(chunk) % 2 == 1:      # 末頁剩半列：右側空格放說明（使用者 2026-11-03 要求不加）
        n_ = len(chunk); ncx0 = 10 + CW; ntop = 287 - (n_ // 2) * CH; nwid = CW
        lines = ["說明", "1. 本圖為原始地形橫斷面，", "    設計護岸及固床工俟設計後補繪。", "2. 比例 H=V=1/300；高程單位 m；", "    河寬尺寸單位 cm。",
                 "3. 斷面面向下游，左岸在左；", "    0K+000 為下游起點。", "4. 斷面框為該斷面原地形", "    最低點往下、最高點往上各 5 m。",
                 "5. 斷面線條提前中止處，", "    為地形測量範圍外（無資料）。",
                 "6. 兩岸線未與斷面線交會者", "    （0K+000、0K+228.90）不標河寬。", "7. 挖、填面積俟設計後填入。"]
        ph = 3.5*2 + 8.8*(len(lines)-1) + TXT
        ytop = ntop - 6
        sh.rect(ncx0+3, ytop - ph, nwid-6, ph, "圖標欄")
        for k, t in enumerate(lines): sh.text(ncx0 + 3 + 3.5, ytop - 3.5 - TXT/2 - 8.8*k, t)

# ---------- 自動檢查：文字與線條、文字與文字 ----------
def check(sh):
    segs = []; lays = []
    for it in sh.items:
        if it[0] == "poly":
            P = it[1]
            for a, b in zip(P[:-1], P[1:]): segs.append((a[0], a[1], b[0], b[1])); lays.append(it[2])
    S = np.array(segs); L = np.array(lays); bad = []
    texts = [it for it in sh.items if it[0] == "text"]
    for it in texts:
        x0, y0, x1, y1 = tbox(it)
        if x0 < 10 or x1 > 410 or y0 < 10 or y1 > 287: bad.append(("出界", it[2]))
        for r in tpieces(it, 0.5):
            h = seg_rect(S, r)
            if h.any(): bad.append((it[2], sorted(set(L[h])))); break
    bx = [tbox(it) for it in texts]; pc = [tpieces(it) for it in texts]
    for i in range(len(texts)):
        for j in range(i+1, len(texts)):
            a, b = bx[i], bx[j]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                if any(p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3] for p in pc[i] for q in pc[j]):
                    bad.append(("文字重疊", texts[i][2], texts[j][2]))
    return bad
for k, sh in enumerate(sheets):
    bad = check(sh); print(f"[檢查] 第{k+1}張 {sh.name}：{len(bad)} 處", bad[:12])

# ---------- 輸出 DXF（全部圖紙橫向並排，每張間隔 450 mm；文字寬度係數用 TEXT.width）----------
def snap_lw(lw):
    valid = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211]
    return min(valid, key=lambda v: abs(v - lw*100))
doc = ezdxf.new("R2018", setup=True); doc.header["$INSUNITS"] = 4; doc.header["$LTSCALE"] = 5.0
doc.styles.add("GENIE", font="GENIE.shx"); doc.styles.add("GENISO", font="GENISO.shx")
for nm, (aci, col, lw, lt, _pc) in LAYERS.items():
    la = doc.layers.add(nm, color=aci)
    if col: la.rgb = tuple(int(col[i:i+2], 16) for i in (1, 3, 5))
    if lw > 0: la.dxf.lineweight = snap_lw(lw)
    if lt: la.dxf.linetype = lt
msp = doc.modelspace()
doc.header["$PSTYLEMODE"] = 1                                   # 顏色相依列印型式（CTB）
msp.dxf_layout.dxf.current_style_sheet = "A3-圖筆(黑白).ctb"       # 預設黑白圖筆；有航照或彩色外參才改全彩
for k, sh in enumerate(sheets):
    ox = k * 450.0
    for it in sh.items:
        if it[0] == "poly":
            at_ = {"layer": it[2]}
            if it[3]: at_["linetype"] = it[3]
            if it[4] != 1.0: at_["ltscale"] = it[4]
            pts = it[1] + np.array([ox, 0]); msp.add_lwpolyline(pts.tolist(), dxfattribs=at_)
        else:
            _, (x, y), s, ha, h, rot, wf = it
            st_ = "GENISO" if s.isascii() else "GENIE"
            t = msp.add_text(s, height=h, rotation=rot, dxfattribs={"layer": "文字", "style": st_, "width": wf})
            al = {"left": TA.MIDDLE_LEFT, "center": TA.MIDDLE_CENTER, "right": TA.MIDDLE_RIGHT}[ha]
            t.set_placement((x + ox, y), align=al)
dxf_out = os.path.join(OUT_DIR, f"{PREFIX}{stamp}_A3_縱橫斷面圖說_{VER}_TWD97_GENIE.dxf")
if os.path.exists(dxf_out): sys.exit(f"{dxf_out} 已存在，不覆蓋；請等下一分鐘再跑，或在設定檔升版號")
doc.saveas(dxf_out); print("DXF:", dxf_out)

# ---------- 輸出 PNG（A3 橫式，200 dpi → 2339×1654，手機可直接檢視）----------
plt.rcParams["font.family"] = ["Microsoft JhengHei", "sans-serif"]
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D
from matplotlib.textpath import TextToPath
from matplotlib.path import Path as MPath
import re as _re
FONTS = CFG.get("fonts", {})
def font_file(key, default):
    p = FONTS.get(key, default)
    if not os.path.exists(p): sys.exit(f"找不到字型檔 {p}（設定檔 fonts.{key}）")
    return p
FP_CJK = FontProperties(fname=font_file("cjk", r"C:\Windows\Fonts\msjhl.ttc"))   # 預覽中文用微軟正黑體 Light（細字，接近 GENIE 單線字）
# ---------- 列印型式：使用者的 ZWCAD「A3-圖筆(黑白).ctb」（依 ACI 決定列印色、線寬、濃度）----------
import zlib
from ezdxf.colors import DXF_DEFAULT_COLORS, int2rgb
HAS_COLOR_XREF = bool(CFG.get("has_color_xref", False))   # 有航照圖或彩色外部參考時設 true → 用全彩
CTB_NAME = f"A3-圖筆({'全彩' if HAS_COLOR_XREF else '黑白'}).ctb"
def find_ctb():
    """依序找：設定檔 ctb_dir → SKILL 的 assets/plot-styles → mbmgi 倉庫的 cad/plot-styles"""
    dirs = ([cpath(CFG["ctb_dir"])] if "ctb_dir" in CFG else []) + [
        os.path.join(HERE, "..", "assets", "plot-styles"), os.path.join(HERE, "..", "..", "..", "cad", "plot-styles")]
    for dd in dirs:
        p = os.path.join(dd, CTB_NAME)
        if os.path.exists(p): return os.path.normpath(p)
    sys.exit(f"找不到圖筆 {CTB_NAME}，請在設定檔指定 ctb_dir")
CTB = find_ctb(); print("圖筆：", CTB)
def load_ctb(path):
    t = zlib.decompress(open(path, "rb").read()[60:]).decode("latin-1")
    lwt = {int(a): float(b) for a, b in _re.findall(r"(\d+)=([\d.]+)", t.split("custom_lineweight_table{")[1].split("}")[0])}
    out = {}
    for i, b in _re.findall(r"\n (\d+)\{(.*?)\n \}", t.split("plot_style{")[1], _re.S):
        kv = dict(_re.findall(r"\n\s+(\w+)=([^\n]*)", b))
        col = int(kv["color"]) & 0xFFFFFFFF; pol = int(kv.get("color_policy", "1")); lwi = int(kv.get("lineweight", "255"))
        explicit = (col & 0xFFFFFF) if (pol & 4) and col != 0xFFFFFFFF else None     # color_policy 含 4＝指定色，否則隨物件色
        out[int(i) + 1] = (explicit, None if lwi == 255 else lwt.get(lwi), int(kv.get("screen", "100")))
    return out
CTBT = load_ctb(CTB)
def plot_style(layer):
    aci, rgb, lw, _lt, _pc = LAYERS[layer]
    ex, clw, scr = CTBT[aci]
    if ex is not None: r, g, b = int2rgb(ex)
    elif rgb: r, g, b = (int(rgb[i:i+2], 16) for i in (1, 3, 5))
    else: r, g, b = (0, 0, 0) if aci == 7 else int2rgb(DXF_DEFAULT_COLORS[aci])
    r, g, b = (round(255 - (255 - v) * scr / 100) for v in (r, g, b))            # 濃度（screening）
    return f"#{r:02X}{g:02X}{b:02X}", (clw if clw is not None else lw)
for _ly in LAYERS: print(f"  列印型式 {_ly}：", plot_style(_ly))
FP_ISO = FontProperties(fname=font_file("iso", r"C:\Windows\Fonts\GENISO.ttf"))   # 半形字元（數字、英文、符號）用 GENISO
_t2p = TextToPath()
def mixed_path(s, h):
    """半形字用 GENISO、全形字用微軟正黑體，依序串接成單一路徑；回傳 (路徑, 總寬)"""
    iso = []; cjk = []; xo = 0.0
    for run in _re.findall(r"[\x00-\x7f]+|[^\x00-\x7f]+", s):
        is_iso = ord(run[0]) < 128
        fp = (FP_ISO if is_iso else FP_CJK).copy(); fp.set_size(h)
        wr = _t2p.get_text_width_height_descent(run, fp, False)[0]
        if run.strip():
            (iso if is_iso else cjk).append(TextPath((xo, 0), run.replace("$", r"\$"), size=h, prop=fp))
        xo += wr
    nul = MPath([(0, 0), (0, 0)], [MPath.MOVETO, MPath.LINETO])
    return (MPath.make_compound_path(*iso) if iso else nul), (MPath.make_compound_path(*cjk) if cjk else nul), max(xo, 1e-6)
MM = 72 / 25.4
nprof = len(splits)
def outname(k):
    if k == 0: return os.path.join(PREV, f"{PREFIX}{stamp}_A3_平面總圖_{VER}.png")
    if k <= nprof: return os.path.join(PREV, f"{PREFIX}{stamp}_A3_縱斷面圖_{VER}_p{k}.png")
    return os.path.join(PREV, f"{PREFIX}{stamp}_A3_橫斷面圖_{VER}_p{k-nprof}.png")
pdf_out = os.path.join(OUT_DIR, f"{PREFIX}{stamp}_A3_縱橫斷面圖說_{VER}.pdf")
LTPAT = {"DOT": [0.0, -0.25], "DOT2": [0.0, -0.125], "DASHED": [0.5, -0.25], "DASHDOT": [0.5, -0.25, 0.0, -0.25],
         "CENTER": [1.25, -0.25, 0.25, -0.25]}                      # AutoCAD acad.lin 圖樣（單位：圖面單位，× LTSCALE × 個別比例）
def mpl_ls(lt, lts, lw_mm):
    if not lt: return "-"
    seg = [abs(v) * 5.0 * lts for v in LTPAT[lt]]
    if lt in ("DOT", "DOT2") and seg[1] < 0.3: return "-"           # 點距過密（如 DOT2×0.1）視同實線
    return (0, tuple(max(v, 0.05) / lw_mm for v in seg))
plt.rcParams["pdf.fonttype"] = 42
pdf = PdfPages(pdf_out)
for k, sh in enumerate(sheets):
    fig = plt.figure(figsize=(W_/25.4, H_/25.4), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W_); ax.set_ylim(0, H_); ax.axis("off")
    for it in sh.items:
        if it[0] == "poly":
            lt_l = LAYERS[it[2]][3]; col, lw = plot_style(it[2])
            lt = it[3] or lt_l; lts = it[4]; lwm = max(lw, 0.05)
            ax.plot(it[1][:, 0], it[1][:, 1], color=col, lw=lwm * MM, ls=mpl_ls(lt, lts, lwm),
                    solid_capstyle="butt", dash_capstyle="round" if lt in ("DOT", "DOT2") else "butt")
        else:
            _, (x, y), s, ha, h, rot, wf = it
            p_iso, p_cjk, wa = mixed_path(s, h)
            w_ = tw(s, h, wf)
            a0 = 0 if ha == "left" else -w_/2 if ha == "center" else -w_
            tr = (Affine2D().scale(w_/wa, 1.0).translate(a0, -0.37*h).rotate_deg(rot).translate(x, y))
            col_, tlw = plot_style("文字")
            ax.add_patch(PathPatch(tr.transform_path(p_cjk), fc=col_, ec="none", lw=0))
            ax.add_patch(PathPatch(tr.transform_path(p_iso), fc=col_, ec=col_, lw=tlw*MM, joinstyle="round"))   # GENISO 單線字：描邊寬＝CTB 線寬
    pdf.savefig(fig, facecolor="white"); fig.savefig(outname(k), dpi=100, facecolor="white"); plt.close(fig)
    print("PNG:", outname(k))
pdf.close(); print('PDF:', pdf_out)
