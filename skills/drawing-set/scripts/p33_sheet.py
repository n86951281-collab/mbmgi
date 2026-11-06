"""P33 共用圖紙元件：A3 圖框／圖標欄、文字寬度、輸出 DXF／PDF／PNG、自動檢查。單位＝紙面 mm。"""
import os, math
import numpy as np
import ezdxf
from ezdxf.render import mleader as _mlr
from ezdxf.math import Vec2 as _V2
from ezdxf.enums import TextEntityAlignment as TA
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D

W_, H_ = 420.0, 297.0
TXT = 7.06; PT = 4.94; TBT = 4.94; WF = 0.5; TB_WF = 0.7
TB = dict(agency="臺中市政府水利局", agency_en="Taichung Water Resources Bureau",
          project="臺中市新社區東山街與協興街路口排水改善工程",
          designer="辰璟工程技術顧問有限公司", designer_en="Chen-Jing Engineering Co.,Ltd",
          design="陳俊廷", draft="李傳承", manager="葉旭璽", check="葉旭璽")       # 簽名欄（使用者 2026-11-06）
LS = {"DOT": (0, (1, 3)), "DASHED": (0, (6, 3)), "DOT2": (0, (1, 1.5)), "CENTER": (0, (12, 3, 3, 3)), "DASHDOT": (0, (8, 2, 1, 2))}

ML_HL = 1.8                                                          # MLEADER 多行文字在 AutoCAD 的實際行距（字高倍數，2026-11-06 實測）
CJK_W, ASC_W = 1.20, 0.66                                          # GENIE.shx 實測字寬（2026-11-06 CAD 發布量測：中文 1.20h、半形 0.66h，乘寬度係數）
def tw(s, h=TXT, wf=WF): return wf * sum(CJK_W * h if ord(ch) > 255 else ASC_W * h for ch in s)

class Sheet:
    def __init__(self, name): self.items = []; self.name = name; self.wf = WF; self.boxes = []; self.tb_ids = None
    def box(self, x0, y0, x1, y1, name=""):
        """登記框格（說明欄、表格欄、圖標欄格）：插入點落在框內的文字，估算外框不得超出框格。回傳框格，可再用 own() 指定成員。"""
        b = {"rect": (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), "name": name, "ids": None}
        self.boxes.append(b); return b
    def own(self, b, i0, i1=None):
        """指定框格成員為 items[i0:i1]（文字一路往下排、插入點可能已掉出框外時用，例如 G-02 一般說明）"""
        b["ids"] = set(range(i0, len(self.items) if i1 is None else i1)); return b
    def poly(self, pts, layer, lt=None): self.items.append(("poly", np.asarray(pts, float), layer, lt))
    def line(self, x1, y1, x2, y2, layer, lt=None): self.poly([(x1, y1), (x2, y2)], layer, lt)
    def rect(self, x, y, w, h, layer): self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], layer)
    def fill(self, pts, layer): self.items.append(("fill", np.asarray(pts, float), layer))   # 實心填滿（箭頭、實心填充）
    def image(self, path, box): self.items.append(("image", path, tuple(box)))   # 點陣底圖：box＝紙面 (x0, y0, x1, y1)
    def mleader(self, tgt, tx, ty, lines, side, h=PT):
        """多重引線（DXF 寫 MLEADER，文字 14 pt）。side=+1 文字在引線右側、-1 在左側；(tx, ty)＝文字近引線端中點。
        預覽：mltext（列入文字檢查）／mlpoly（引線）／mlfill（箭頭）"""
        n = len(lines); hl = h * ML_HL; T = np.array(tgt, float); i0 = len(self.items)
        for j, t in enumerate(lines):
            self.items.append(("mltext", (tx, ty + (n - 1) / 2 * hl - j * hl), t, "left" if side > 0 else "right", h, 0, self.wf))
        dog = np.array([tx - side * 5.0, ty]); land = np.array([tx - side * 1.0, ty])
        self.items.append(("mlpoly", np.array([T, dog, land]), "標註", None, i0))
        u = (dog - T) / np.hypot(*(dog - T)); nn = np.array([-u[1], u[0]])
        self.items.append(("mlfill", np.array([T, T + u * 2.5 + nn * 0.7, T + u * 2.5 - nn * 0.7]), "標註", None))
        self.items.append(("mlmeta", tuple(T), (tx, ty), list(lines), side, h))
    def text(self, x, y, s, ha="left", h=TXT, rot=0):
        if s.strip(): self.items.append(("text", (x, y), s, ha, h, rot, self.wf))   # 空字串不加（TextPath 無法處理）

def tbox(it):
    _, (x, y), s, ha, h, rot, wf = it; w = tw(s, h, wf); th = math.radians(rot)
    a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
    P = [(x + u * math.cos(th) - v * math.sin(th), y + u * math.sin(th) + v * math.cos(th)) for u in (a0, a0 + w) for v in (-h / 2, h / 2)]
    return (min(p[0] for p in P), min(p[1] for p in P), max(p[0] for p in P), max(p[1] for p in P))

TB_CELLS = ((10, 10, 86, 32), (86, 21, 188, 32), (86, 10, 188, 21), (188, 10, 226, 32), (226, 21, 262, 32), (226, 10, 262, 21),
            (262, 21, 298, 32), (262, 10, 298, 21), (298, 10, 392, 32), (392, 21, 410, 32), (392, 10, 410, 21))   # 圖標欄各格（與 frame 的格線一致）

def register_title_block(sh, i0, i1=None, cells=TB_CELLS):
    """把 items[i0:i1] 標為圖標欄文字，並登記圖標欄各格為框格。自己畫圖框的產生器（例如 P33 plan_view）畫完圖標欄後也要呼叫。"""
    sh.tb_ids = set(range(i0, len(sh.items) if i1 is None else i1))
    for c in cells: sh.box(*c, name="圖標欄")

def frame(sh, name, scales, no):
    i0 = len(sh.items)
    sh.rect(0, 0, W_, H_, "圖框"); sh.rect(10, 10, 400, 277, "圖框"); sh.rect(10, 10, 400, 22, "圖標欄")
    for x in (86, 188, 226, 298, 392): sh.line(x, 10, x, 32, "圖標欄")
    for x0, x1 in ((86, 188), (226, 298), (392, 410)): sh.line(x0, 21, x1, 21, "圖標欄")
    sh.line(262, 10, 262, 32, "圖標欄")
    yc = (14.94, 20.88, 26.82); sh.wf = TB_WF
    sh.text(48, yc[2], "主辦機關", "center", TBT); sh.text(48, yc[1], TB["agency"], "center", TBT); sh.text(48, yc[0], TB["agency_en"], "center", TBT)
    sh.wf = 0.55                                                      # 工程名稱：GENIE 實際字寬比估算寬約 3～5%，係數收到 0.62 留餘裕（2026-11-06 CAD 實測超框）
    sh.text(89.5, 26.5, "工程名稱：" + TB["project"], "left", TBT); sh.wf = TB_WF
    sh.text(89.5, 15.5, "圖　名：" + name, "left", TBT)
    sh.text(207, yc[2], "比例尺", "center", TBT)
    if len(scales) == 1: sh.text(207, yc[1], scales[0], "center", TBT)
    else: sh.text(207, yc[1], scales[0], "center", TBT); sh.text(207, yc[0], scales[1], "center", TBT)
    sh.text(229.5, 26.5, "設計：" + TB["design"], "left", TBT); sh.text(265.5, 26.5, "主管：" + TB["manager"], "left", TBT)
    sh.text(229.5, 15.5, "繪圖：" + TB["draft"], "left", TBT); sh.text(265.5, 15.5, "校核：" + TB["check"], "left", TBT)
    sh.text(345, yc[2], "設計單位", "center", TBT); sh.text(345, yc[1], TB["designer"], "center", TBT); sh.text(345, yc[0], TB["designer_en"], "center", TBT)
    sh.text(401, 26.5, "圖號", "center", TBT); sh.text(401, 15.5, no, "center", TBT); sh.wf = WF
    register_title_block(sh, i0)

def check(sh, design_layers, **kw):
    """文字重疊、文字壓設計線、出界（圖標欄文字不計出界）、引線壓字；
    另加（2026-11-06）框格溢出、引線交叉、其他線壓字、字級不足、字距線過近（警告），參數見 _check_ext，例如 check(sh, L, near_line=False)。
    回傳 CheckResult：解包仍是 (重疊, 壓線＋引線壓字, 出界)，全部項目看 .detail，是否全過看 .ok"""
    TT = [it for it in sh.items if it[0] in ("text", "mltext")]
    T_ = [tbox(it) for it in TT]
    lead = 0
    for k, it in enumerate(sh.items):
        if it[0] != "mlpoly": continue
        own = {id(x) for x in sh.items[it[4]:k]}
        for q, r in zip(TT, T_):
            if id(q) in own: continue
            a, b = it[1][0], it[1][1]
            if any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 40)):
                lead += 1
                if os.environ.get("P33_DEBUG"): print("   引線壓字：", q[2])
    over = sum(1 for i in range(len(T_)) for j in range(i + 1, len(T_)) if T_[i][0] < T_[j][2] and T_[j][0] < T_[i][2] and T_[i][1] < T_[j][3] and T_[j][1] < T_[i][3])
    outb = sum(1 for r in T_ if (r[1] + r[3]) / 2 > 32 and (r[0] < 10 or r[2] > 410 or r[1] < 32 or r[3] > 287))
    segs = [(a, b) for it in sh.items if it[0] == "poly" and it[2] in design_layers for a, b in zip(it[1][:-1], it[1][1:])]
    press = sum(1 for r in T_ if any(any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 30)) for a, b in segs))
    if os.environ.get("P33_DEBUG"):
        for i in range(len(T_)):
            r = T_[i]
            if (r[1] + r[3]) / 2 > 32 and (r[0] < 10 or r[2] > 410 or r[1] < 32 or r[3] > 287): print("   出界：", TT[i][2], [round(v, 1) for v in r])
            for j in range(i + 1, len(T_)):
                q = T_[j]
                if r[0] < q[2] and q[0] < r[2] and r[1] < q[3] and q[1] < r[3]: print("   重疊：", TT[i][2], "／", TT[j][2])
            if any(any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 30)) for a, b in segs): print("   壓線：", TT[i][2], [round(v, 1) for v in r])
    ext = _check_ext(sh, design_layers, TT, T_, **kw)
    msg = f"[檢查] {sh.name}：文字重疊 {over}、文字壓線 {press}、出界 {outb}、引線壓字 {lead}"
    msg += "".join(f"、{k} {v}" for k, v in ext.items() if k != "字距線過近")
    if "字距線過近" in ext: msg += f"；警告：字距線過近 {ext['字距線過近']}"
    print(msg)
    return CheckResult((over, press + lead, outb), dict(文字重疊=over, 文字壓線=press, 出界=outb, 引線壓字=lead, **ext))

# ---------------- 2026-11-06 補強檢查（P33 自動檢查漏掉、靠人工才發現的問題） ----------------
class CheckResult(tuple):
    """向下相容：仍是 (重疊, 壓線＋引線壓字, 出界) 三元組；新增 .detail（各項計數）、.fail（不含警告的總數）、.ok"""
    WARN = ("字距線過近",)
    def __new__(cls, base, detail):
        r = super().__new__(cls, base); r.detail = detail; return r
    @property
    def fail(self): return sum(v for k, v in self.detail.items() if k not in self.WARN)
    @property
    def ok(self): return self.fail == 0

IGNORE_ANY = ("格線", "主格線")                         # 舊線壓字：不檢查的圖層（縱斷面格線本來就穿過框內）
IGNORE_NEAR = ("表格", "圖框", "圖標欄", "資料帶")       # 字距線過近：表格、資料帶的格線本來就貼字，不列警告

def _seg_in_rect(a, b, r, eps=1e-6):
    """線段 ab 是否穿過矩形 r=(x0,y0,x1,y1) 的內部（Liang–Barsky 裁切，只碰邊不算）"""
    x0, y0, x1, y1 = r[0] + eps, r[1] + eps, r[2] - eps, r[3] - eps
    if x0 >= x1 or y0 >= y1: return False
    dx, dy = b[0] - a[0], b[1] - a[1]; t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0: return False
            continue
        t = q / p
        if p < 0: t0 = max(t0, t)
        else: t1 = min(t1, t)
        if t0 > t1: return False
    return (t1 - t0) * math.hypot(dx, dy) > 1e-6

def _seg_cross(a, b, c, d, tol=0.1):
    """兩線段是否交叉；交點落在任一線段端點 tol mm 內（例如共用箭頭點）不算"""
    r = (b[0] - a[0], b[1] - a[1]); s = (d[0] - c[0], d[1] - c[1]); den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12: return False                                   # 平行（含共線）不計
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den; u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if not (0 <= t <= 1 and 0 <= u <= 1): return False
    la, lc = math.hypot(*r), math.hypot(*s)
    return min(t * la, (1 - t) * la, u * lc, (1 - u) * lc) > tol

def _along_edge(it, a, b, touch):
    """線段是否與文字平行、貼在字框頂邊或底邊 touch×字高 以內，且重疊長度 ≥ max(字寬 30%, 1 mm)。
    （引線的水平連字線接在字中間、詳圖號圓圈的短弦都不算）"""
    _, (x, y), s, ha, h, rot, wf = it; w = tw(s, h, wf); th = math.radians(rot); c, sn = math.cos(th), math.sin(th)
    a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
    loc = lambda p: ((p[0] - x) * c + (p[1] - y) * sn, -(p[0] - x) * sn + (p[1] - y) * c)
    (u1, v1), (u2, v2) = loc(a), loc(b); du, dv = u2 - u1, v2 - v1
    if abs(du) < 1e-9 or abs(dv) > 0.05 * abs(du): return False
    ov = min(max(u1, u2), a0 + w) - max(min(u1, u2), a0)
    if ov < max(0.3 * w, 1.0): return False
    t = touch * h; vm = (v1 + v2) / 2
    return abs(abs(vm) - h / 2) <= t

def _check_ext(sh, design_layers, TT, T_, boxes=True, leader_cross=True, any_line=True, near_line=True, min_size=True,
               box_pad=0.0, touch=0.03, near_ratio=0.5, min_h=PT, ignore_layers=IGNORE_ANY, near_ignore=IGNORE_NEAR):
    """新增五項；各項可用參數關閉。回傳 {項目: 數量}。P33_DEBUG=1 時逐筆列出。"""
    dbg = os.environ.get("P33_DEBUG"); out = {}
    idx = [i for i, it in enumerate(sh.items) if it[0] in ("text", "mltext")]          # 與 TT、T_ 同序
    def show(tag, s, r=None): dbg and print(f"   {tag}：", s, [round(v, 1) for v in r] if r else "")
    # 1. 框格溢出：登記的框格（圖標欄各格、說明欄…）內的文字，外框不得超出；非圖標欄文字不得伸進圖標欄
    if boxes:
        n = 0
        for b in getattr(sh, "boxes", []):
            x0, y0, x1, y1 = b["rect"]
            for i, it, r in zip(idx, TT, T_):
                mem = (i in b["ids"]) if b["ids"] is not None else (x0 <= it[1][0] <= x1 and y0 <= it[1][1] <= y1)
                if mem and (r[0] < x0 + box_pad or r[2] > x1 - box_pad or r[1] < y0 + box_pad or r[3] > y1 - box_pad):
                    n += 1; show(f"框格溢出（{b['name']}）", it[2], r)
        tb = getattr(sh, "tb_ids", None)
        if tb is not None:
            for i, it, r in zip(idx, TT, T_):
                if i not in tb and r[0] < 410 and r[2] > 10 and r[1] < 32 and r[3] > 10:
                    n += 1; show("伸進圖標欄", it[2], r)
        out["框格溢出"] = n
    # 2. 引線交叉：MLEADER 引線兩兩不交叉；連字線段（第 2 段起）也不得穿過其他文字（第 1 段已在「引線壓字」）
    if leader_cross:
        L = [(k, it) for k, it in enumerate(sh.items) if it[0] == "mlpoly"]
        n = 0
        for p in range(len(L)):
            for q in range(p + 1, len(L)):
                A, B = L[p][1][1], L[q][1][1]
                if any(_seg_cross(A[i], A[i + 1], B[j], B[j + 1]) for i in range(len(A) - 1) for j in range(len(B) - 1)):
                    n += 1; show("引線交叉", "／".join(sh.items[L[w][1][4]][2] for w in (p, q)))   # 各引線第一行文字
        for k, it in L:
            own = set(range(it[4], k)); P = it[1]
            for i, q_, r in zip(idx, TT, T_):
                if i in own: continue
                if any(_seg_in_rect(P[j], P[j + 1], r) for j in range(1, len(P) - 1)): n += 1; show("連字線壓字", q_[2], r)
        out["引線交叉"] = n
    segs_all = [(a, b, it[2]) for it in sh.items if it[0] == "poly" and it[2] not in ignore_layers for a, b in zip(it[1][:-1], it[1][1:])]
    # 3. 其他線壓字（舊線壓字）：所有圖層的線（不只 design_layers）穿過字框內部；另抓「平行貼在字頂或字底」的線
    #    （P33 S-04 的殘留短線剛好落在字框頂邊，y 相等，只看框內部抓不到）。已在「文字壓線」計過的文字不重算。
    if any_line:
        n = 0
        segs_d = [(a, b) for it in sh.items if it[0] == "poly" and it[2] in design_layers for a, b in zip(it[1][:-1], it[1][1:])]
        for it, r in zip(TT, T_):
            if any(_seg_in_rect(a, b, r) for a, b in segs_d): continue
            hit = [ly for a, b, ly in segs_all if ly not in design_layers and _seg_in_rect(a, b, r)]
            if not hit: hit = [ly for a, b, ly in segs_all if _along_edge(it, a, b, touch)]
            if hit: n += 1; show(f"其他線壓字（{hit[0]}）", it[2], r)
        out["其他線壓字"] = n
    # 4. 字級下限：任何文字不得小於 14 pt（4.94 mm）
    if min_size:
        n = 0
        for it in TT:
            if it[4] < min_h - 0.01: n += 1; show(f"字級不足 h={it[4]:.2f}", it[2])
        out["字級不足"] = n
    # 5. 字距線過近（警告）：文字外框外擴 near_ratio×字高 內有線（本身沒壓到），例如尺寸字貼著尺寸線
    if near_line:
        n = 0
        for it, r in zip(TT, T_):
            g = near_ratio * it[4]; R = (r[0] - g, r[1] - g, r[2] + g, r[3] + g)
            near = [ly for a, b, ly in segs_all if ly not in near_ignore and not _seg_in_rect(a, b, r) and not _along_edge(it, a, b, touch) and _seg_in_rect(a, b, R)]
            if near: n += 1; show(f"字距線過近（{near[0]}）", it[2], r)
        out["字距線過近"] = n
    return out

def save(sheets, layers, out_dir, prev_dir, base):
    """layers: 名稱 → (ACI, 線型, 預覽色, 預覽線寬mm)。DXF 各張橫向並排、間隔 450 mm。"""
    os.makedirs(prev_dir, exist_ok=True)
    doc = ezdxf.new("R2018", setup=True); doc.header["$LTSCALE"] = 5
    doc.styles.add("GENIE", font="GENISO.shx").dxf.bigfont = "GENIE.shx"
    for nm, (aci, lt, *_r) in layers.items(): doc.layers.add(nm, color=aci, linetype=lt or "CONTINUOUS")
    if "標註" not in doc.layers: doc.layers.add("標註", color=7)
    m = doc.modelspace()
    for k, sh in enumerate(sheets):
        ox = k * 450.0
        for it in sh.items:
            if it[0] in ("mltext", "mlpoly", "mlfill"): continue
            if it[0] == "fill":
                hh = m.add_hatch(dxfattribs={"layer": it[2]}); hh.paths.add_polyline_path([(p[0] + ox, p[1]) for p in it[1]], is_closed=True); continue
            if it[0] == "mlmeta":
                _, tgt, (tx, ty), lines, side, h = it
                ml = m.add_multileader_mtext("Standard", dxfattribs={"layer": "標註"})
                ml.set_content("\\P".join(f"\\W{WF};{t}" for t in lines), char_height=h, style="GENIE",
                               alignment=_mlr.TextAlignment.left if side > 0 else _mlr.TextAlignment.right)
                ml.set_arrow_properties(size=2.5); ml.set_connection_properties(landing_gap=1.0, dogleg_length=4.0)
                ml.set_connection_types(left=_mlr.HorizontalConnection.middle_of_text, right=_mlr.HorizontalConnection.middle_of_text)  # 連字線接整段文字中間（同預覽）
                ml.add_leader_line(_mlr.ConnectionSide.left if side > 0 else _mlr.ConnectionSide.right, [_V2(tgt[0] + ox, tgt[1])])
                ml.build(insert=_V2(tx + ox, ty + ((len(lines) - 1) * h * ML_HL + h) / 2)); continue   # insert＝文字塊頂端；預覽以 ty 為字塊中心   # 行距 1.5h（AutoCAD 預設 1.667h×係數）
            if it[0] == "image":                                # DXF 以 IMAGE 參照同資料夾的 PNG
                from PIL import Image as _Im
                _, pth, (x0, y0, x1, y1) = it; wpx, hpx = _Im.open(pth).size
                if "底圖" not in doc.layers: doc.layers.add("底圖", color=7)
                idef = doc.add_image_def(filename=os.path.basename(pth), size_in_pixel=(wpx, hpx))
                m.add_image(idef, insert=(x0 + ox, y0), size_in_units=(x1 - x0, y1 - y0), dxfattribs={"layer": "底圖"})
                continue
            if it[0] == "poly":
                at = {"layer": it[2]}
                if it[3] and it[3] != layers[it[2]][1]: at["linetype"] = it[3]
                if (it[3] or layers[it[2]][1]) == "DOT2": at["ltscale"] = 0.1      # 樣板 v4.0：原始地面線 DOT2 個別比例 0.1
                m.add_lwpolyline([(p[0] + ox, p[1]) for p in it[1]], dxfattribs=at)
            else:
                _, (x, y), s, ha, h, rot, wf = it
                t = m.add_text(s, height=h, rotation=rot, dxfattribs={"layer": "文字", "style": "GENIE", "width": wf})
                t.set_placement((x + ox, y), align={"left": TA.MIDDLE_LEFT, "center": TA.MIDDLE_CENTER, "right": TA.MIDDLE_RIGHT}[ha])
    dxf_path = os.path.join(out_dir, base + ".dxf")
    if os.path.exists(dxf_path): raise SystemExit(f"{dxf_path} 已存在，不覆蓋")
    doc.saveas(dxf_path)
    fp = FontProperties(fname=r"C:\Windows\Fonts\msjhl.ttc")
    pdf_path = os.path.join(out_dir, base + ".pdf"); pngs = []
    with PdfPages(pdf_path) as pdf:
        for k, sh in enumerate(sheets):
            fig = plt.figure(figsize=(W_ / 25.4, H_ / 25.4)); ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, W_); ax.set_ylim(0, H_); ax.set_aspect("equal"); ax.axis("off")
            for it in sh.items:
                if it[0] == "image":
                    _, pth, (x0, y0, x1, y1) = it
                    ax.imshow(plt.imread(pth), extent=(x0, x1, y0, y1), zorder=0, interpolation="lanczos"); continue
                if it[0] == "mlmeta": continue
                if it[0] == "fill": ax.fill(it[1][:, 0], it[1][:, 1], color=layers.get(it[2], (0, 0, "#000000"))[2], lw=0); continue
                if it[0] == "mlfill": ax.fill(it[1][:, 0], it[1][:, 1], color="#000000", lw=0); continue
                if it[0] == "mlpoly": ax.plot(it[1][:, 0], it[1][:, 1], color="#000000", lw=0.18 * 72 / 25.4); continue
                if it[0] == "poly":
                    aci, lt0, col, lw = layers[it[2]]; lt = it[3] or lt0
                    ax.plot(it[1][:, 0], it[1][:, 1], color=col, lw=lw * 72 / 25.4, ls=LS.get(lt, "-"), solid_capstyle="butt")
                else:
                    _, (x, y), s, ha, h, rot, wf = it
                    tp = TextPath((0, 0), s, size=h, prop=fp); w = tw(s, h, wf); sx = w / max(tp.get_extents().x1, 1e-6)
                    a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
                    ax.add_patch(PathPatch(Affine2D().scale(sx, 1).translate(a0, -h * 0.40).rotate_deg(rot).translate(x, y).transform_path(tp), color="#000000", lw=0))
            ax.set_xlim(0, W_); ax.set_ylim(0, H_)
            pdf.savefig(fig); png = os.path.join(prev_dir, f"{base}_p{k+1}.png"); fig.savefig(png, dpi=200); plt.close(fig); pngs.append(png)
    return dxf_path, pdf_path, pngs
