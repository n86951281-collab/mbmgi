"""標準圖 S（ditch-design，由 P33 standard_v3 一般化；A3 橫式 6 張）。
S-01 箱涵式側溝標準圖、S-01-1 平面圖及甲種預鑄溝蓋板、場鑄緣石配筋（引用 B20）、S-03 臨時擋土設施及臨時鋼管護欄詳圖、
S-04 施工中交通維持示意圖、S-05 交通設施詳圖、S-06 告示牌詳圖。
案件值：斷面尺寸 design.*、擋土 temp_shoring.*、引用標準圖 DXF standards.b20_dxf／a18_dxf、工程名稱與設計單位 title_block。
限制：圖面配置、鋼筋表、交維階段與告示牌內容是 P33 箱涵式側溝（B20 改 W110）專用；其他型式（U 型溝、明溝）要另寫圖面。
用法：python standard_drawings.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
"""
import sys, os, json, csv, math, datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
dd.sheet_module()
from p33_sheet import Sheet, frame, check, save, tw, tbox, PT, TXT

sys.stdout.reconfigure(encoding="utf-8")
HERE = dd.HERE; CFG = dd.CFG; P_ = dd.P_
stamp = sys.argv[sys.argv.index("--stamp") + 1] if "--stamp" in sys.argv else datetime.datetime.now().strftime("%Y%m%d_%H%M")
OUT = dd.OUT; PREV = os.path.join(OUT, "06_標準圖")
WORK_GAP = dd.WORK_GAP                # temp_shoring.offset_in：溝外壁路內側施工空間（開挖寬）

LAYERS = {
    "圖框": (7, None, "#000000", 0.50), "圖標欄": (7, None, "#000000", 0.35),
    "結構線": (7, None, "#000000", 0.50), "細線": (7, None, "#000000", 0.18), "隱藏線": (7, "DASHED", "#000000", 0.18),
    "地面線": (252, None, "#666666", 0.30), "開挖線": (253, "DASHED", "#7A7A7A", 0.30),
    "鋼軌樁": (7, None, "#000000", 0.60), "標註": (7, None, "#000000", 0.18), "表格": (7, None, "#000000", 0.25),
    "填線": (253, None, "#A3A3A3", 0.13), "文字": (7, None, "#000000", 0.0),
}

class View:
    """局部視圖：設計單位 cm → 紙面 mm（k＝mm/cm），原點 (ox, oy)"""
    def __init__(self, sh, ox, oy, k): self.sh, self.ox, self.oy, self.k = sh, ox, oy, k
    def X(self, x): return self.ox + x * self.k
    def Y(self, y): return self.oy + y * self.k
    def poly(self, pts, layer="結構線", lt=None): self.sh.poly([(self.X(x), self.Y(y)) for x, y in pts], layer, lt)
    def line(self, x1, y1, x2, y2, layer="結構線", lt=None): self.poly([(x1, y1), (x2, y2)], layer, lt)
    def rect(self, x, y, w, h, layer="結構線", lt=None): self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], layer, lt)
    def hatch(self, x, y, w, h, step=2.5):
        """斜線填線（紙面間距 step mm）"""
        X0, Y0, X1, Y1 = self.X(x), self.Y(y), self.X(x + w), self.Y(y + h)
        c = X0 - Y1 + step                                           # 斜線 y = x − c，c 由 X0−Y1 掃到 X1−Y0
        while c < X1 - Y0:
            xa, xb = max(X0, c + Y0), min(X1, c + Y1)                # 裁到矩形
            if xa < xb: self.sh.line(xa, xa - c, xb, xb - c, "填線")
            c += step
    def dimh(self, x1, x2, y, txt=None, above=True):
        Y = self.Y(y); X1, X2 = self.X(x1), self.X(x2)
        self.sh.line(X1, Y, X2, Y, "標註")
        for X in (X1, X2): self.sh.line(X - 1.2, Y - 1.2, X + 1.2, Y + 1.2, "標註"); self.sh.line(X, Y - 2.0, X, Y + 2.0, "標註")
        t = txt if txt is not None else f"{abs(x2 - x1):g}"
        self.sh.text((X1 + X2) / 2, Y + (3.6 if above else -3.6), t, "center", PT)
    def dimv(self, y1, y2, x, txt=None, left=True):
        X = self.X(x); Y1, Y2 = self.Y(y1), self.Y(y2)
        self.sh.line(X, Y1, X, Y2, "標註")
        for Y in (Y1, Y2): self.sh.line(X - 1.2, Y - 1.2, X + 1.2, Y + 1.2, "標註"); self.sh.line(X - 2.0, Y, X + 2.0, Y, "標註")
        t = txt if txt is not None else f"{abs(y2 - y1):g}"
        self.sh.text(X + (-3.6 if left else 3.6), (Y1 + Y2) / 2, t, "center", PT, 90)
    def lab(self, x, y, tx, ty, text, ha="left"):
        """引線：自 (x,y)[cm] 拉到紙面 (tx,ty)[mm] 的文字"""
        X, Y = self.X(x), self.Y(y)
        w = tw(text, PT); a, b = (tx, tx + w) if ha == "left" else (tx - w, tx)
        # 2026-11-06 使用者：照 B20 範例用多重引線（箭頭＋水平連字線），引線接文字較近一端
        if X < (a + b) / 2: self.sh.mleader((X, Y), a, ty, [text], 1)
        else: self.sh.mleader((X, Y), b, ty, [text], -1)

def title(sh, x, y, t, sub):
    w = tw(t, TXT); sh.text(x, y, t, "center", TXT)
    sh.line(x - w / 2 - 2, y - 5.0, x + w / 2 + 2, y - 5.0, "標註")
    sh.text(x, y - 10.0, sub, "center", PT)

def table(sh, x, ytop, widths, rows, rh=8.0, aligns=None):
    """表格：rows 為 list[list[str]]；字串含 \\n 時分兩行（列高自動加倍）"""
    y = ytop; W = sum(widths)
    hs = [rh * max(1, max(c.count("\n") + 1 for c in r)) for r in rows]
    sh.line(x, y, x + W, y, "表格")
    for r, h in zip(rows, hs):
        xx = x
        for j, (c, w) in enumerate(zip(r, widths)):
            lines = c.split("\n"); n = len(lines)
            for k, s in enumerate(lines):
                yy = y - h / 2 + (n - 1) * rh / 2 - k * rh
                al = (aligns[j] if aligns else "center")
                if al == "left": sh.text(xx + 1.5, yy, s, "left", PT)
                else: sh.text(xx + w / 2, yy, s, "center", PT)
            xx += w
        y -= h; sh.line(x, y, x + W, y, "表格")
    xx = x
    for w in [0] + widths:
        xx += w; sh.line(xx, ytop, xx, y, "表格")
    return y

def notes(sh, x, ytop, lines, dy=7.5):
    for k, t in enumerate(lines): sh.text(x, ytop - dy * k, t, "left", PT)
    return ytop - dy * len(lines)

sheets = []
def new(name, scales, no):
    sh = Sheet(name); frame(sh, name, scales, no); sheets.append(sh); return sh

W_IN, H_IN = P_["W"] * 100, P_["H"] * 100           # 110、100 cm（2026-11-05 晚改）
TW, TS, TB_, TC = P_["t_wall"] * 100, P_["t_slab"] * 100, P_["t_bed"] * 100, P_["t_cover"] * 100
OUT_W = W_IN + 2 * TW; GAP = WORK_GAP * 100

# ======================================================================
# S-01 箱涵式側溝標準圖（依使用者 2026-11-06 範例：箱涵式側溝剖面、集水井剖面、平面、鋼筋）
# ======================================================================
TCV = 23.0; CURB_W, CURB_H = 20.0, 15.0; HCH = 20.0                 # 預鑄溝蓋板厚、場鑄緣石、內角加腋
sh = new("箱涵式側溝標準圖", ["1:20（剖面）", "1:40（平面）"], "S-01")
v = View(sh, 80.0, 244.0, 0.5)                                       # 剖面：原點＝溝中心、路面（SG）
hw = OUT_W / 2; ybot = -(TCV + H_IN); ybed = ybot - TS - TB_
v.line(-150, 0, -hw, 0, "地面線"); v.line(hw, 0, 150, 0, "地面線")
v.rect(-hw, -TCV, OUT_W, TCV)                                        # 預鑄溝蓋板 t=23
v.rect(-hw, 0, CURB_W, CURB_H)                                       # 場鑄緣石（路外側＝左）
v.poly([(-hw, -TCV), (-hw, ybot - TS), (hw, ybot - TS), (hw, -TCV), (hw - TW, -TCV), (hw - TW, ybot + HCH), (hw - TW - HCH, ybot),
        (-hw + TW + HCH, ybot), (-hw + TW, ybot + HCH), (-hw + TW, -TCV), (-hw, -TCV)])
v.rect(-hw, ybed, OUT_W, TB_); v.hatch(-hw, ybed, OUT_W, TB_, 1.8)
v.line(-hw - 10, 0, -hw - 10, ybed, "開挖線", "DASHED"); v.line(hw + 30, 0, hw + 30, ybed, "開挖線", "DASHED")   # 路外側（左）貼外壁 10
v.line(-hw - 10, ybed, hw + 30, ybed, "開挖線", "DASHED")
LAYERS["鋼筋"] = (7, None, "#000000", 0.35)
def rebar_u(v, xl, xr, ytop, ybt, dots=True, sp=25.0):
    """U 形鋼筋（cm）＋縱向配力筋（點）"""
    v.poly([(xl, ytop), (xl, ybt), (xr, ybt), (xr, ytop)], "鋼筋")
    if dots:
        a = np.radians(np.linspace(0, 360, 9))
        pts = [(xl, y) for y in np.arange(ytop - 5, ybt, -sp)] + [(x, ybt) for x in np.arange(xl + 10, xr - 5, sp)] + [(xr, y) for y in np.arange(ytop - 5, ybt, -sp)]
        for x, y in pts: v.sh.poly(np.column_stack([v.X(x) + 0.55 * np.cos(a), v.Y(y) + 0.55 * np.sin(a)]), "鋼筋")
def bar_tag(v, x, y, tx, ty, mk):
    """鋼筋編號圈（紙面 tx, ty）＋引線到鋼筋（cm）"""
    a = np.radians(np.linspace(0, 360, 25)); v.sh.poly(np.column_stack([tx + 2.8 * np.cos(a), ty + 2.8 * np.sin(a)]), "細線")
    v.sh.text(tx, ty, mk, "center", PT)
    X, Y = v.X(x), v.Y(y); d = np.hypot(tx - X, ty - Y); v.sh.line(X, Y, tx + (X - tx) / d * 2.8, ty + (Y - ty) / d * 2.8, "細線")
CV = 5.0                                                                     # 保護層
rebar_u(v, -hw + CV, hw - CV, -TCV - 3, ybot - TS + CV)                         # A：外層 U 筋
rebar_u(v, -hw + TW - CV, hw - TW + CV, -TCV - 3, ybot + CV)                    # B：內層 U 筋
v.line(-W_IN / 2 + 10, ybot - TS / 2, W_IN / 2 - 10, ybot - TS / 2, "鋼筋")       # C：底版中層筋
for sg in (-1, 1):                                                           # D：加腋筋
    v.line(sg * (hw - TW + CV - 2), ybot + HCH + 10, sg * (hw - TW - HCH - 8), ybot + CV - 2, "鋼筋")
bar_tag(v, -hw + CV, -60, v.X(-hw + 30), v.Y(-45), "A")
bar_tag(v, hw - TW + CV, -50, v.X(hw - TW - 22), v.Y(-38), "B")
bar_tag(v, 10, ybot - TS / 2, v.X(8), v.Y(ybot + 22), "C")
bar_tag(v, -(hw - TW - 6), ybot + 12, v.X(-hw + TW + 14), v.Y(ybot + 52), "D")
bar_tag(v, hw - TW + CV, -TCV - 58, v.X(30), v.Y(-75), "E")                 # 2026-11-06 數量計算：縱向配力筋 E（A、B 兩層 U 筋上之點筋）
v.dimh(-hw, -hw + TW, 30, f"{TW:g}"); v.dimh(-hw + TW, hw - TW, 30, f"{W_IN:g}"); v.dimh(hw - TW, hw, 30, f"{TW:g}")
v.dimh(-hw, hw, 44, f"{OUT_W:g}")
v.dimv(0, -TCV, -120, f"{TCV:g}"); v.dimv(-TCV, ybot, -120, f"{H_IN:g}"); v.dimv(ybot, ybot - TS, -120, f"{TS:g}"); v.dimv(ybot - TS, ybed, -120, f"{TB_:g}")
v.dimv(0, CURB_H, -hw - 14, f"{CURB_H:g}")
v.dimh(hw - TW - HCH, hw - TW, ybot + HCH + 8, f"{HCH:g}")
for (x, y, tx, ty, t) in [(-hw + CURB_W, CURB_H, 140.0, 258.0, "場鑄緣石 20×15（詳 S-01-1）"),
                          (10, -TCV / 2, 140.0, 242.0, "甲／乙種預鑄溝蓋板 t=23（詳 S-01-1）"),
                          (hw + 20, 0, 140.0, 250.0, "AC 面層 t=5，新舊路面銜接平順"),
                          (hw - TW / 2, -60, 140.0, 222.0, "210 kgf/cm² 混凝土"),
                          (hw - TW - 8, ybot + 8, 140.0, 206.0, "加腋 20×20（與溝體同時澆置 210 kgf/cm² 混凝土）"),
                          (30, ybed + TB_ / 2, 140.0, 190.0, "140 kgf/cm² 混凝土墊層 t=10"),
                          (hw + 30, ybed + 20, 140.0, 182.0, "開挖線（路內側外壁外 30、路外側 10）")]:
    v.lab(x, y, tx, ty, t)
sh.text(v.X(0), v.Y(-TCV - 18), f"淨寬 {W_IN:g}　淨高 {H_IN:g}", "center", PT)
title(sh, 80.0, 162.0, "箱涵式側溝剖面圖", "S=1:20　單位：cm")
# 溝體鋼筋（依範例 A～D 改本案尺寸）
BARS_D = [("A", "D16", 15, [(H_IN + 10, "v"), (W_IN + 30, "h"), (H_IN + 10, "v")]),
          ("B", "D13", 15, [(H_IN, "v"), (W_IN + 10, "h"), (H_IN, "v")]),
          ("C", "D13", 15, [(W_IN, "h")]),
          ("D", "D13", 15, [(20, "v"), (65, "d"), (20, "h")])]
UW = {"D10": 0.560, "D13": 0.994, "D16": 1.56, "D19": 2.25}
def bar_sym(x0, y0, mark, dia, sp, segs, k=0.12, one=False):
    """鋼筋形狀示意＋標籤（紙面 mm）"""
    L = sum(s for s, _ in segs); pts = [(x0, y0)]; x, y = x0, y0
    if len(segs) == 3: pts = [(x0, y0 + segs[0][0] * k), (x0, y0), (x0 + segs[1][0] * k, y0), (x0 + segs[1][0] * k, y0 + segs[2][0] * k)]
    elif segs[0][1] == "h": pts = [(x0, y0), (x0 + segs[0][0] * k, y0)]
    else: pts = [(x0, y0 + 4), (x0 + 4, y0), (x0 + 10, y0)]
    sh.poly(pts, "結構線")
    cx = x0 + (16.0 if one else 26.0); a = np.radians(np.linspace(0, 360, 25)); sh.poly(np.column_stack([cx + 2.8 * np.cos(a), y0 + 3 + 2.8 * np.sin(a)]), "細線")
    sh.text(cx, y0 + 3, mark, "center", PT)
    if one: sh.text(cx + 4.5, y0 + 3, f"{dia}@{sp} L={L:g}", "left", PT)
    else: sh.text(cx + 5.0, y0 + 6.0, f"{dia} @{sp}cm", "left", PT); sh.text(cx + 5.0, y0 - 0.5, f"L={L:g}cm", "left", PT)
    return L
y_ = 202.0; WD = 0.0
sh.text(262.0, 206.0, "側溝鋼筋", "left", PT)
for mk, dia, sp, segs in BARS_D:
    L = bar_sym(262.0, y_ - 14.0, mk, dia, sp, segs, k=0.1); y_ -= 15.5
    WD += (100.0 / sp) * L / 100.0 * UW[dia] * (2 if mk == "D" else 1)
# E：縱向配力筋 D13 @25（內外兩層，沿溝向連續；每斷面 30 支；搭接 52 cm）——配筋檢核表 v1.2 第 7 節
y0e = y_ - 14.0; a_ = np.radians(np.linspace(0, 360, 13))
for xx in (264.0, 268.0, 272.0): sh.poly(np.column_stack([xx + 0.8 * np.cos(a_), y0e + 3 + 0.8 * np.sin(a_)]), "結構線")
a_ = np.radians(np.linspace(0, 360, 25)); sh.poly(np.column_stack([288.0 + 2.8 * np.cos(a_), y0e + 3 + 2.8 * np.sin(a_)]), "細線"); sh.text(288.0, y0e + 3, "E", "center", PT)
sh.text(293.0, y0e + 6.0, "D13 @25cm 內外兩層", "left", PT); sh.text(293.0, y0e - 0.5, "每斷面30支 搭接52cm", "left", PT)
WE = 30 * UW["D13"] * (1 + 0.52 / 12.0)                               # 每公尺：30 支×D13，12 m 定尺搭接 52 cm
# 集水井剖面
WI = P_["well_in"] * 100; WW = P_["well_wall"] * 100; WO = WI + 2 * WW; HWI = H_IN + P_["sump"] * 100   # 井內淨深＝溝淨高＋沉砂
v = View(sh, 71.0, 128.0, 0.5)
hwo = WO / 2; yb2 = -(TCV + HWI); ybd2 = yb2 - TS - TB_
v.line(-104, 0, -hwo, 0, "地面線"); v.line(hwo, 0, 104, 0, "地面線")
v.rect(-hwo, -TCV, WO, TCV); v.rect(-hwo, 0, CURB_W, CURB_H)
v.poly([(-hwo, -TCV), (-hwo, yb2 - TS), (hwo, yb2 - TS), (hwo, -TCV), (hwo - WW, -TCV), (hwo - WW, yb2), (-hwo + WW, yb2), (-hwo + WW, -TCV), (-hwo, -TCV)])
v.rect(-hwo, ybd2, WO, TB_); v.hatch(-hwo, ybd2, WO, TB_, 1.8)
for k_ in range(1, 4): v.line(-hwo + WW, -TCV - 30 * k_, -hwo + WW + 12, -TCV - 30 * k_, "細線")   # 踏步 @30
v.line(hwo - WW, yb2 + 30, hwo - WW - 25, yb2 + 30, "隱藏線", "DASHED")
rebar_u(v, -hwo + CV, hwo - CV, -TCV - 3, yb2 - TS + CV)                       # A
rebar_u(v, -hwo + WW - CV, hwo - WW + CV, -TCV - 3, yb2 + CV)                   # B
v.line(-WI / 2 + 10, yb2 - TS / 2, WI / 2 - 10, yb2 - TS / 2, "鋼筋")             # G：井底座橫向筋
for y_ in (-TCV - 20, -TCV - 50):                                            # E、F：井壁水平筋（示意）
    v.line(-hwo + CV, y_, -hwo + WW - CV, y_, "鋼筋"); v.line(hwo - CV, y_, hwo - WW + CV, y_, "鋼筋")
bar_tag(v, -hwo + CV, -110, v.X(-hwo + 42), v.Y(-118), "A")
bar_tag(v, hwo - WW + CV, -90, v.X(hwo - WW - 22), v.Y(-80), "B")
bar_tag(v, -hwo + WW - CV - 2, -TCV - 20, v.X(-hwo + 40), v.Y(-TCV - 20), "E")
bar_tag(v, -hwo + WW - CV - 2, -TCV - 50, v.X(-hwo + 40), v.Y(-TCV - 50), "F")
bar_tag(v, 20, yb2 - TS / 2, v.X(30), v.Y(yb2 + 30), "G")
v.dimh(-hwo, -hwo + WW, 26, f"{WW:g}"); v.dimh(-hwo + WW, hwo - WW, 26, f"{WI:g}"); v.dimh(hwo - WW, hwo, 26, f"{WW:g}")
v.dimv(0, -TCV, -100, f"{TCV:g}"); v.dimv(-TCV, yb2, -100, f"{HWI:g}"); v.dimv(yb2, yb2 - TS, -100, f"{TS:g}"); v.dimv(yb2 - TS, ybd2, -100, f"{TB_:g}")
for (x, y, tx, ty, t) in [(0, -TCV / 2, 124.0, 124.0, "甲種預鑄溝蓋板（鍍鋅格柵）"),
                          (-hwo + WW + 6, -TCV - 60, 124.0, 116.0, "塑膠包覆人孔踏步 @30"),
                          (hwo - WW - 12, yb2 + 30, 124.0, 108.0, "RCP／側溝底（高於井底 30）"),
                          (20, ybd2 + TB_ / 2, 124.0, 100.0, "140 kgf/cm² 墊層 t=10")]:
    v.lab(x, y, tx, ty, t)
title(sh, 175.0, 84.0, "集水井剖面圖", "S=1:20　單位：cm")
BARS_W = [("A", "D16", 15, [(HWI + 10, "v"), (WI + 30, "h"), (HWI + 10, "v")]), ("B", "D13", 15, [(HWI, "v"), (WI + 10, "h"), (HWI, "v")]),
          ("C", "D13", 15, [(WI, "h")]), ("D", "D13", 15, [(20, "v"), (65, "d"), (20, "h")]),
          ("E", "D13", 15, [(40, "v"), (WI - 10, "h"), (40, "v")]), ("F", "D13", 15, [(30, "v"), (WI - 30, "h"), (30, "v")]),
          ("G", "D13", 15, [(WI + 30, "h")])]
y_ = 202.0
sh.text(330.0, 206.0, "集水井鋼筋", "left", PT)
for mk, dia, sp, segs in BARS_W:
    bar_sym(330.0, y_ - 9.0, mk, dia, sp, segs, 0.05, one=True); y_ -= 10.5
# 平面（1:40，5 m 一段）
v = View(sh, 262.0, 232.0, 0.25)
Lp = 500.0
v.rect(0, 0, Lp, OUT_W); v.line(0, OUT_W - CURB_W, Lp, OUT_W - CURB_W, "細線")
for xx in np.arange(100, Lp, 100): v.line(xx, 0, xx, OUT_W - CURB_W, "細線")
v.rect(0, 0, 100, OUT_W - CURB_W, "結構線"); v.rect(13.5, 23, 73, 63 * 1.3, "細線"); v.hatch(13.5, 23, 73, 81.9, 1.2)
v.dimh(0, 100, OUT_W + 14, "100"); v.dimh(100, Lp, OUT_W + 14, f"{Lp - 100:g}")
v.dimv(0, OUT_W, -18, f"{OUT_W:g}")
sh.text(v.X(50), v.Y(-26), "甲種（每 5 m 一處）", "center", PT); sh.text(v.X(300), v.Y(-26), "乙種預鑄溝蓋板", "center", PT)
sh.text(v.X(Lp) + 3, v.Y(OUT_W - CURB_W / 2), "緣石", "left", PT)
title(sh, 324.0, 284.0 - 0.0, "箱涵式側溝平面圖", "S=1:40　單位：cm") if False else sh.text(v.X(Lp / 2), v.Y(-66), "箱涵式側溝平面圖　S=1:40", "center", PT)
conc = (2 * TW * (H_IN + TCV * 0) + OUT_W * TS + 2 * HCH * HCH / 2) / 1e4; bed = OUT_W * TB_ / 1e4
rows = [["項目（每公尺）", "單位", "數量"],
        ["溝體混凝土 210", "m³", f"{conc:.3f}"], ["墊層混凝土 140", "m³", f"{bed:.3f}"],
        ["溝體模板", "m²", f"{(2 * H_IN + 2 * (H_IN + TS)) / 100:.2f}"],
        ["溝體鋼筋 橫向（A～D）", "kg", f"{WD:.1f}"], ["溝體鋼筋 縱向（E）", "kg", f"{WE:.1f}"],
        ["預鑄溝蓋板（甲：乙＝1：4）", "塊", "1.0"], ["場鑄緣石 280", "m³", f"{CURB_W * CURB_H / 1e4:.3f}"]]
yb = table(sh, 262.0, 112.0, [76.0, 18.0, 30.0], rows, 7.0, ["left", "center", "center"])
sh.text(262.0, 117.0, "箱涵式側溝每公尺數量表", "left", PT)
notes(sh, 140.0, 52.0, ["註：1. 依業主範例箱涵式側溝改本案淨寬 110、淨高 100；鋼筋 D16、D19 用 SD420W，D10、D13 用 SD280W。",
      "　　2. 溝蓋板頂與路面（SG）齊平；每 10 m 設伸縮縫；臨時擋土詳 S-03。"], 7.0)
# ======================================================================
# S-01-1 預鑄溝蓋板、緣石詳圖及平面圖：引用臺北市工務局標準圖 B20 V2.0（平面圖、甲種蓋板、場鑄緣石）＋本案乙種蓋板、鋼筋表
# 使用者 2026-11-06：原 S-01-1 與 S-02 合併一張；縮小比例與間距，字不小於橫斷面多重引線（14 pt）
# ======================================================================
import b20_import as B20                                             # drawing-set 共用；引用圖檔改指本案 standards.*_dxf
B20.SRC = dd.src(CFG["standards"]["b20_dxf"]); B20.SRC_A18 = dd.src(CFG["standards"]["a18_dxf"])
for _k in list(B20.SRC_OF): B20.SRC_OF[_k] = B20.SRC_A18
sh = new("預鑄溝蓋板、緣石詳圖及平面圖", ["1:50、1:25", "1:12.5　單位：cm"], "S-01-1")
B20.place(sh, "plan", 12.0, 184.0, 0.8)                              # 平面 1:50
B20.place(sh, "curb", 178.0, 76.0, 0.8)                              # 場鑄緣石 1:12.5
B20.place(sh, "cov", 12.0, 40.0, 0.8)                                # 甲種蓋板 1:25
CL_ = OUT_W                                                          # 蓋板長（橫跨溝）＝溝外寬 150
v = View(sh, 190.0, 46.0, 0.2)                                       # 乙種平面 1:50（橫放：橫向＝跨溝 150）
v.rect(0, 0, CL_, 100)
for xx in (12, CL_ - 12): v.rect(xx - 3, 46, 6, 8, "細線")
for yy in np.arange(10, 100, 15): v.line(5, yy, CL_ - 5, yy, "隱藏線", "DASHED")
v.dimh(0, CL_, -14, f"{CL_:g}", above=False); v.dimv(0, 100, -14, "100")
title(sh, 254.0, 62.0, "乙種預鑄溝蓋板", "S=1:50　t=23 cm")
# 鋼筋表（依 B20，跨溝方向長度依蓋板長 150 調整）
D = CL_ - 5
TBL_A = [("1", "D19", f"{D:g}", "8", "8", D / 100), ("2", "D16", "22／50", "18／18", "7.5", None), ("3", "D16", "95", "12", "15", 0.95),
         ("4", "D13", "15│15│15", "22", "7.5", 0.45), ("5", "D19", "23／12／12", "4", "", 0.86), ("6", "D19", "85(45)／75(35)", "8／8", "", None),
         ("7", "D13", "12／8／12", "18", "15", 0.48)]
def wt(row):
    no, dia, shp, cnt, sp, L = row
    if no == "2": return 18 * 0.22 * UW[dia] + 18 * 0.50 * UW[dia], "0.22／0.50"
    if no == "6": return 16 * 0.60 * UW[dia], "0.60／0.60"
    return int(cnt) * L * UW[dia], f"{L:.2f}"
def rebar_table(x, ytop, title_, rows_):
    out = [["編號", "直徑", "形狀", "支數", "間距", "長度m", "單位重", "重量kg"]]; tot = 0.0
    for r in rows_:
        w_, Ls = wt(r); tot += w_; out.append([r[0], r[1], r[2], r[3], r[4], Ls, f"{UW[r[1]]:.3f}", f"{w_:.2f}"])
    out.append(["小計", "", "", "", "", "", "", f"{tot:.2f}"])
    sh.text(x, ytop + 4.5, title_, "left", PT)
    return table(sh, x, ytop, [10.0, 11.0, 23.0, 13.0, 10.0, 17.0, 14.0, 16.0], out, 6.6), tot
yb, tA = rebar_table(290.0, 279.0, "甲種預鑄溝蓋板鋼筋表（每塊）", TBL_A)
TBL_B = [("8", "D13", "15│15│15", "30", "15", 0.45), ("9", "D16", "95", "20", "15", 0.95), ("10", "D16", f"{D:g}", "14", "15", D / 100), ("11", "D19", "23／12／12", "4", "", 0.86)]
yb, tB = rebar_table(290.0, yb - 9.0, "乙種預鑄溝蓋板鋼筋表（每塊）", TBL_B)
TBL_C = [("12", "D13", "95", "4", "", 0.95), ("13", "D10", "10│15│10", "6", "19", 0.60)]
yb, tC = rebar_table(290.0, yb - 9.0, "場鑄緣石鋼筋表（每 m）", TBL_C)
notes(sh, 290.0, yb - 8.0, ["附註（依臺北市工務局標準圖 B20 V2.0）：",
    "1. 甲、乙種預鑄溝蓋板混凝土強度 f'c≧280 kgf/cm²。",
    "2. 蓋板設置完成後，將乙吊鈎切除，甲吊鈎切斷",
    "　 一邊後彎紮另一邊，與場鑄緣石配筋固定一起打混凝土。",
    "3. 預鑄溝蓋板保護層 3 cm。",
    "4. 集水井設塑膠包覆人孔踏步爬梯，間距 30 cm。",
    "5. 開挖深度≧150 cm 時應設擋土設施，詳 S-03。",
    "6. 熱浸鍍鋅格柵蓋及框，依鍍鋅蓋詳圖溝寬 60 cm 尺度。",
    "7. 本案渠寬 110 cm，蓋板 150×100×23 cm；鋼筋",
    "　 D16、D19 用 SD420W，D10、D13 用 SD280W。",
    "8. 圖中詳圖編號依原標準圖。"], dy=6.6)
# ======================================================================
# S-03 臨時擋土設施及鋼管護欄詳圖：A-A 橫向、B-B 縱向剖面、平面示意（上排）；鋼管護欄引用 A18 V1.0（下排，使用者 2026-11-06）
# ======================================================================
import plan_base as PB
sh = new("臨時擋土設施及臨時鋼管護欄詳圖", ["NTS", "單位：cm"], "S-03")
EXW = OUT_W + 10.0 + GAP;   # 2026-11-06 對齊 S-01：路外側 10＋溝外寬 150＋路內側 30＝190（集水井段 230）
EXW_W = P_['well_in'] * 100 + 2 * P_['well_wall'] * 100 + 10.0 + GAP; DIG = TCV + H_IN + TS + TB_; PL = PB.PILE_L * 100
# ---- A-A（橫向，垂直溝向）----
v = View(sh, 36.0, 268.0, 0.3)
v.line(-50, 0, 0, 0, "地面線"); v.line(EXW, 0, EXW + 50, 0, "地面線")
for xx in range(-48, 0, 10): v.line(xx, 0, xx + 6, 6, "細線")
for xx in range(int(EXW) + 2, int(EXW) + 50, 10): v.line(xx, 0, xx + 6, 6, "細線")
for xx in (0, EXW): v.line(xx, 8, xx, -PL + 8, "鋼軌樁")
for xx, s_ in ((0, 1), (EXW, -1)): v.line(xx + s_ * 3, 0, xx + s_ * 3, -DIG, "隱藏線", "DASHED")
v.rect(0, -45, 12, 12); v.rect(EXW - 12, -45, 12, 12); v.line(12, -39, EXW - 12, -39, "結構線")
v.line(0, -DIG, EXW, -DIG, "開挖線", "DASHED")
v.rect(10, -DIG + TB_, OUT_W, -TB_ + 0.001, "細線")
v.poly([(10, -DIG + TB_), (10, -TCV), (10 + OUT_W, -TCV), (10 + OUT_W, -DIG + TB_), (10, -DIG + TB_)], "細線")
v.dimh(0, EXW, 24, f"開挖寬 {EXW:g}（集水井段 {EXW_W:g}）")
v.dimh(0, 10, 12, ""); sh.text(v.X(0) - 4.0, v.Y(12) + 3.6, "10", "right", PT); v.dimh(10 + OUT_W, EXW, 12, f"{GAP:g}")   # 10 cm 太窄，字移到尺寸線左外側
v.dimv(0, -DIG, -24, f"開挖深 {DIG:g}"); v.dimv(8, -PL + 8, -62, f"L={PL:g}")
v.lab(EXW - 6, -39, 120.0, 264.0, "橫擋及支撐（必要時設置）")
v.lab(10 + OUT_W - 10, -TCV - 20, 120.0, 256.0, "新設箱涵式側溝 110×100")
v.lab(EXW - 3, -75, 120.0, 248.0, "背插鐵板擋土（厚度依施工計畫）")
v.lab(EXW, -120, 120.0, 240.0, f"鋼軌樁 L={PL:g} @100")
v.lab(EXW - 10, -DIG, 120.0, 232.0, "開挖面")
title(sh, 36.0 + EXW * 0.15, 176.0, "擋土支撐 A-A 剖面", "NTS　單位：cm")
# ---- B-B（縱向，沿溝向，自溝內看路外側擋土壁）----
v = View(sh, 184.0, 274.0, 0.25)
NSP = 3; LB = NSP * 100
v.line(-30, 0, LB + 30, 0, "地面線")
for xx in range(-28, LB + 28, 10): v.line(xx, 0, xx + 6, 6, "細線")
for k_ in range(NSP + 1): v.line(k_ * 100, 8, k_ * 100, -PL + 8, "鋼軌樁")
for k_ in range(NSP): v.hatch(k_ * 100 + 4, -DIG, 92, DIG, 2.2)                # 背插鐵板（樁間）
v.line(-20, -36, LB + 20, -36, "結構線"); v.line(-20, -42, LB + 20, -42, "結構線")   # 橫擋
v.line(-20, -DIG, LB + 20, -DIG, "開挖線", "DASHED")
v.line(-20, -TCV, LB + 20, -TCV, "隱藏線", "DASHED"); v.line(-20, -DIG + TB_, LB + 20, -DIG + TB_, "隱藏線", "DASHED")
v.dimh(0, 100, 22, "@100")
v.dimv(8, -PL + 8, -24, f"L={PL:g}")
v.lab(LB + 15, -TCV, 274.0, 270.0, "新設側溝")
v.lab(LB + 10, -39, 274.0, 262.0, "橫擋")
v.lab(LB - 50, -60, 274.0, 254.0, "背插鐵板")
v.lab(LB + 15, -DIG, 274.0, 246.0, "開挖面")
v.lab(LB, -220, 274.0, 238.0, "鋼軌樁")
title(sh, 184.0 + LB * 0.125, 196.0, "擋土支撐 B-B 剖面", "NTS　單位：cm")
# ---- 平面示意（每 100 一樁），標 A-A、B-B 剖切位置 ----
v = View(sh, 318.0, 180.0, 0.2)
for yy in (0, EXW):
    v.line(0, yy, 400, yy, "細線")
    for xx in range(0, 401, 100): v.rect(xx - 5, yy - 5, 10, 10, "鋼軌樁")
v.dimh(0, 100, -18, "@100", above=False); v.dimv(0, EXW, -16, f"{EXW:g}")
v.line(250, -24, 250, EXW + 24, "標註", "DASHDOT")
sh.text(v.X(250), v.Y(-32), "A", "center", PT); sh.text(v.X(250), v.Y(EXW + 32), "A", "center", PT)
v.line(-24, EXW - 15, 424, EXW - 15, "標註", "DASHDOT")
sh.text(v.X(-34), v.Y(EXW - 15), "B", "center", PT); sh.text(v.X(434), v.Y(EXW - 15), "B", "center", PT)
sh.text(v.X(200), v.Y(-60), "擋土支撐平面示意", "center", PT)
notes(sh, 300.0, 284.0, ["註：1. 開挖深約 %.0f cm，全線設鋼軌樁背插鐵板；" % DIG,
      "　　　既有暗溝先拆除後打設。",
      "　　2. 樁心：路內側外壁外 30 cm、路外側 10 cm",
      "　　　（鐵板兼外模）；集水井段路外側樁打在既有",
      "　　　側溝外緣線上；樁位詳 P-01、PP-01、PP-02。",
      "　　3. 樁規格、鐵板、橫擋由廠商施工計畫檢算，",
      "　　　經專任工程人員簽證、監造審查後施作。",
      "　　4. 拔樁後以砂或 CLSM 填實；以實做數量結算。"], dy=6.4)
# ---- 臨時鋼管護欄（使用者 2026-11-06：臨時性；開挖區路內側及兩端，設置及拆除）----
sh.text(14.0, 160.0, "臨時鋼管護欄詳圖", "left", PT); sh.line(14.0, 156.5, 60.0, 156.5, "標註")
v = View(sh, 40.0, 70.0, 0.3)                                        # 立面 1:33（2 跨）
for xx in (0, 200, 400):
    v.rect(xx - 2.5, 0, 5, 120); v.rect(xx - 20, -6, 40, 6)           # 立柱 Ø48.6＋配重底座
for yy in (60, 115):
    v.line(-30, yy, 430, yy, "結構線"); v.line(-30, yy + 4.9, 430, yy + 4.9, "結構線")
    for xx in np.arange(-25, 426, 25): v.line(xx, yy, xx + 8, yy + 4.9, "細線")   # 紅白相間反光條紋
v.dimh(0, 200, -18, "@200", above=False); v.dimh(200, 400, -18, "@200", above=False)
v.dimv(0, 120, -44, "120"); v.dimv(0, 60, -30, "60")
v.lab(300, 117, 182.0, 150.0, "橫桿 Ø48.6 mm 鍍鋅鋼管 t=2.3 mm（上下兩道）")
v.lab(250, 62, 182.0, 140.0, "漆紅白相間反光條紋")
v.lab(400, 90, 182.0, 130.0, "立柱 Ø48.6 mm 鍍鋅鋼管 @200 cm")
v.lab(410, -3, 182.0, 120.0, "配重底座（規格依施工計畫）")
sh.text(v.X(200), 46.0, "立面圖（NTS）", "center", PT)
v = View(sh, 330.0, 70.0, 0.3)                                       # 側視
v.rect(-2.5, 0, 5, 120); v.rect(-20, -6, 40, 6)
a_ = np.radians(np.linspace(0, 360, 17))
for yy in (62.5, 117.5): sh.poly(np.column_stack([v.X(-6) + 0.75 * np.cos(a_), v.Y(yy) + 0.75 * np.sin(a_)]), "結構線")
v.dimh(-20, 20, -18, "40", above=False)
sh.text(v.X(0), 46.0, "側視圖（NTS）", "center", PT)
notes(sh, 300.0, 150.0, ["臨時鋼管護欄註：",
      "1. 設於開挖區路內側沿開挖線全長及兩端封閉，",
      "　 位置詳 S-04；完工後拆除。",
      "2. 鋼管 Ø48.6 mm（1½\"）鍍鋅 t=2.3 mm，高 120 cm。"], dy=6.4)
# ======================================================================
# S-04 施工中交通維持示意圖
# ======================================================================
sh = new("施工中交通維持示意圖", ["NTS", ""], "S-04")
def road(y0, work_side, label):
    """y0：道路下緣；道路寬 30 mm（示意 9 m）；work_side：'A'（下側，西）或 'B'（上側，東）"""
    x0, x1 = 24.0, 300.0; Wd = 32.0
    sh.line(x0, y0, x1, y0, "結構線"); sh.line(x0, y0 + Wd, x1, y0 + Wd, "結構線")
    for xx in np.arange(x0, x1, 14): sh.line(xx, y0 + Wd / 2, xx + 7, y0 + Wd / 2, "細線")
    wa, wb = 90.0, 234.0
    yw0, yw1 = (y0, y0 + 9.0) if work_side == "A" else (y0 + Wd - 9.0, y0 + Wd)
    sh.rect(wa, yw0, wb - wa, yw1 - yw0, "結構線")
    for xx in np.arange(wa, wb, 3.0): sh.line(xx, yw0, min(xx + (yw1 - yw0), wb), yw1, "填線")
    yc = yw1 + 4.5 if work_side == "A" else yw0 - 4.5                 # 交通錐往車道側，與護欄立柱錯開
    for xx in np.arange(wa - 24, wb + 25, 8.0):                      # 交通錐（漸變段＋縱向）
        yy = yc if wa <= xx <= wb else (yc + (0 if work_side == "A" else 0))
        if xx < wa: yy = (yw0 if work_side == "A" else yw1) + ((xx - (wa - 24)) / 24.0) * (yc - (yw0 if work_side == "A" else yw1))
        if xx > wb: yy = (yw0 if work_side == "A" else yw1) + (((wb + 24) - xx) / 24.0) * (yc - (yw0 if work_side == "A" else yw1))
        sh.poly([(xx - 1.0, yy - 1.0), (xx, yy + 1.2), (xx + 1.0, yy - 1.0), (xx - 1.0, yy - 1.0)], "結構線")
    yg = yw1 if work_side == "A" else yw0                             # 臨時鋼管護欄：路內側沿開挖線全長＋兩端封閉（數量計算 一-5）
    yo = yw0 if work_side == "A" else yw1                             # 路外側（鄰房）不畫
    sh.poly([(wa, yo), (wa, yg), (wb, yg), (wb, yo)], "結構線")
    for xx in np.arange(wa, wb + 0.1, 12.0): sh.rect(xx - 1.0, yg - 1.0, 2.0, 2.0, "結構線")
    for xx in (wa, wb): sh.rect(xx - 1.0, (yo + yg) / 2 - 1.0, 2.0, 2.0, "結構線")
    for xx in (wa - 3.0, wb + 3.0):                                  # 拒馬
        yy = (yw0 + yw1) / 2; sh.rect(xx - 1.5, yy - 4.0, 3.0, 8.0, "結構線"); sh.line(xx - 1.5, yy - 4.0, xx + 1.5, yy + 4.0, "細線")
    for xx in (40.0, 284.0):                                         # 施工標誌（菱形）
        yy = y0 - 6.0 if work_side == "A" else y0 + Wd + 6.0
        sh.poly([(xx, yy - 3), (xx + 3, yy), (xx, yy + 3), (xx - 3, yy), (xx, yy - 3)], "結構線")
    for xx in (66.0, 258.0):                                         # 旗手
        yy = y0 - 6.0 if work_side == "A" else y0 + Wd + 6.0
        sh.rect(xx - 1.5, yy - 1.5, 3.0, 3.0, "結構線"); sh.line(xx, yy + 1.5, xx, yy + 4.0, "結構線")
    sh.line(wa, (yw1 + 12.0) if work_side == "A" else (yw0 - 12.0), wb, (yw1 + 12.0) if work_side == "A" else (yw0 - 12.0), "標註")
    sh.text((wa + wb) / 2, (yw1 + 17.5) if work_side == "A" else (yw0 - 17.5), "開挖施工區（L≒112.9 m，含兩端集水井）", "center", PT)
    yl = y0 - 16.0 if work_side == "A" else y0 + Wd + 16.0
    sh.text(40.0, yl, "施工標誌", "center", PT); sh.text(284.0, yl, "施工標誌", "center", PT)
    sh.text(66.0, yl, "旗手", "center", PT); sh.text(258.0, yl, "旗手", "center", PT)
    sh.text(162.0, y0 - 26.0 if work_side == "A" else y0 - 8.0, label, "center", TXT)
road(198.0, "B", "第一階段：B 側（東）施工、A 側維持通行")
road(96.0, "A", "第二階段：A 側（西）施工、B 側維持通行")
sh.text(178.0, 158.0, "水流往 0K+000（北）", "left", PT); sh.line(150.0, 158.0, 174.0, 158.0, "結構線"); sh.poly([(153.0, 159.5), (150.0, 158.0), (153.0, 156.5)], "結構線")
lx = 318.0; ly = 268.0; sh.text(lx, ly, "圖例：", "left", PT)
items = [("cone", "交通錐（夜間加閃光警示燈）"), ("bar", "活動型拒馬"), ("sign", "施工標誌"),
         ("flag", "旗手"), ("work", "施工路段（開挖區）"), ("rail", "臨時鋼管護欄（詳 S-03）")]
for k, (t, s) in enumerate(items):
    yy = ly - 10.0 * (k + 1); xx = lx + 4
    if t == "cone": sh.poly([(xx - 1.2, yy - 1.2), (xx, yy + 1.5), (xx + 1.2, yy - 1.2), (xx - 1.2, yy - 1.2)], "結構線")
    if t == "bar": sh.rect(xx - 1.5, yy - 3.0, 3.0, 6.0, "結構線")
    if t == "sign": sh.poly([(xx, yy - 3), (xx + 3, yy), (xx, yy + 3), (xx - 3, yy), (xx, yy - 3)], "結構線")
    if t == "flag": sh.rect(xx - 1.5, yy - 1.5, 3.0, 3.0, "結構線")
    if t == "work":
        sh.rect(xx - 3, yy - 2, 6, 4, "結構線"); sh.line(xx - 3, yy - 2, xx + 1, yy + 2, "填線")
    if t == "rail":
        sh.line(xx - 4, yy, xx + 4, yy, "結構線")
        for x_ in (xx - 4, xx, xx + 4): sh.rect(x_ - 1.0, yy - 1.0, 2.0, 2.0, "結構線")
    sh.text(lx + 12, yy, s, "left", PT)
notes(sh, 318.0, 196.0, ["註：",
      "1. 分兩階段施工，另一側維持",
      "　 通行；必要時單線雙向管制，",
      "　 兩端派旗手指揮。",
      "2. 標誌、拒馬、交通錐依交通部",
      "　 「道路交通標誌標線號誌設置",
      "　 規則」設置，距離【待確認】。",
      "3. 夜間開挖區設閃光警示燈。",
      "4. 每日收工開挖面覆蓋鋼板或",
      "　 回填，維持車行安全。",
      "5. 交維計畫報主管機關核准後",
      "　 施工【待確認】。",
      "6. 設施詳 S-05。",
      "7. 開挖區路內側及兩端設臨時鋼管",
      "　 護欄（詳 S-03）；路外側不設。"])

# ======================================================================
# S-05 交通設施詳圖（依使用者 2026-11-06 範例 35/35）
# ======================================================================
sh = new("交通設施詳圖", ["NTS", "單位：cm"], "S-05")
def diamond(cx, cy, r, kind):
    sh.poly([(cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy), (cx, cy + r)], "結構線")
    sh.poly([(cx, cy + r - 1.2), (cx + r - 1.2, cy), (cx, cy - r + 1.2), (cx - r + 1.2, cy), (cx, cy + r - 1.2)], "細線")
    if kind == "work":                                               # 施工人員（簡化圖示）
        a = np.radians(np.linspace(0, 360, 13)); sh.poly(np.column_stack([cx - 1.5 + 0.9 * np.cos(a), cy + 3.2 + 0.9 * np.sin(a)]), "結構線")
        sh.poly([(cx - 1.5, cy + 2.2), (cx - 0.8, cy - 1.0), (cx - 2.8, cy - 3.8)], "結構線"); sh.poly([(cx - 0.8, cy - 1.0), (cx + 0.2, cy - 3.8)], "結構線")
        sh.poly([(cx - 1.2, cy + 1.2), (cx + 2.2, cy - 0.6), (cx + 3.2, cy - 3.6)], "結構線"); sh.line(cx + 1.6, cy - 3.8, cx + 4.6, cy - 3.8, "結構線")
    elif kind == "close":
        for k in range(3): sh.rect(cx - 4.5, cy - 3 + k * 2.2, 9, 1.4, "結構線")
    elif kind in ("right", "left"):
        s = 1 if kind == "right" else -1
        sh.poly([(cx - s * 2, cy - 4), (cx - s * 2, cy + 3.5)], "結構線"); sh.poly([(cx - s * 3, cy + 2.2), (cx - s * 2, cy + 3.8), (cx - s * 1, cy + 2.2)], "結構線")
        sh.poly([(cx + s * 2, cy - 4), (cx + s * 2, cy - 0.5)], "結構線"); sh.line(cx + s * 1, cy - 0.5, cx + s * 3, cy - 0.5, "結構線")
    elif kind in ("detr", "detl"):
        s = 1 if kind == "detr" else -1
        sh.poly([(cx, cy - 4), (cx, cy + 1), (cx + s * 3, cy + 3.5)], "結構線"); sh.poly([(cx + s * 1.6, cy + 3.8), (cx + s * 3, cy + 3.5), (cx + s * 2.8, cy + 2.1)], "結構線")
SIGNS = [("work", "道路施工", "施1"), ("work", "道路施工", "施2"), ("work", "道路施工", "施3"),
         ("close", "道路封閉", "施4"), ("close", "道路封閉", "施5"), ("close", "道路封閉", "施6"),
         ("right", "右道封閉", "施7"), ("right", "右道封閉", "施8"), ("right", "右道封閉", "施9"),
         ("left", "左道封閉", "施10"), ("left", "左道封閉", "施11"), ("left", "左道封閉", "施12"),
         ("detr", "車輛改道", "施13"), ("detl", "車輛改道", "施14")]
for k, (kd, nm, no) in enumerate(SIGNS):
    c, r = k % 3, k // 3; cx = 30.0 + c * 27.0; cy = 268.0 - r * 30.0
    diamond(cx, cy, 8.0, kd); sh.text(cx, cy - 12.5, nm, "center", PT); sh.text(cx, cy - 18.5, f"（{no}）", "center", PT)
cx, cy = 30.0 + 2 * 27.0, 268.0 - 4 * 30.0                           # 施15、施16 繞道方向
for j, s in enumerate((-1, 1)):
    y0 = cy + 4 - j * 8; sh.rect(cx - 9, y0 - 2.5, 18, 5, "結構線"); sh.poly([(cx - s * 6, y0), (cx + s * 6, y0)], "結構線"); sh.poly([(cx + s * 4, y0 + 1.5), (cx + s * 6, y0), (cx + s * 4, y0 - 1.5)], "結構線")
sh.text(cx, cy - 12.5, "繞道方向", "center", PT); sh.text(cx, cy - 18.5, "（施15）（施16）", "center", PT)
# 拒馬（正視）＋閃光燈
v = View(sh, 118.0, 210.0, 0.36)
for yb_ in (55.0, 95.0):
    v.rect(0, yb_, 120, 20)
    for xx in range(0, 120, 20): v.poly([(xx, yb_), (min(xx + 10, 120), yb_), (min(xx + 20, 120), yb_ + 20), (min(xx + 10, 120), yb_ + 20), (xx, yb_)], "細線")
v.line(10, 0, 15, 120); v.line(110, 0, 105, 120); v.dimh(0, 120, -10, "120", above=False); v.dimv(0, 120, -12, "120")
v.rect(100, 120, 16, 10); v.line(108, 130, 108, 138, "細線")
v.lab(60, 105, 172.0, 276.0, "漆橘白相間反光條紋")
v.lab(108, 134, 172.0, 268.0, "加裝閃光燈（乾電池）")
sh.text(140.0, 194.0, "鋁質活動型拒馬", "center", PT)
# 拒6～拒8
for k, (t, kd) in enumerate((("車輛改道", "r"), ("車輛改道", "l"), ("", "s"))):
    x0, y0 = 232.0, 255.0 - k * 33.0; w_, h_ = 54.0, 22.5
    sh.rect(x0, y0, w_, h_, "結構線"); sh.rect(x0 + 1.2, y0 + 1.2, w_ - 2.4, h_ - 2.4, "細線")
    if kd == "s":
        for xx in np.arange(x0 + 2, x0 + w_ - 6, 8): sh.poly([(xx, y0 + 1.2), (xx + 5, y0 + 1.2), (xx + 5 + 20.1, y0 + h_ - 1.2), (xx + 20.1, y0 + h_ - 1.2), (xx, y0 + 1.2)], "細線") if xx + 25.1 < x0 + w_ else None
    else:
        s = 1 if kd == "r" else -1; ym = y0 + h_ / 2; sh.text(x0 + w_ / 2 - s * 4, ym, t, "center", PT)
        xa_, xb_ = (x0 + 6, x0 + w_ - 6) if s > 0 else (x0 + w_ - 6, x0 + 6)
        sh.line(xa_, ym - 6, xb_, ym - 6, "結構線"); sh.poly([(xb_ - s * 3, ym - 4), (xb_, ym - 6), (xb_ - s * 3, ym - 8)], "結構線")
    sh.text(x0 + w_ / 2, y0 - 5.0, f"拒{6 + k}", "center", PT)
sh.text(259.0, 290.0 - 6.5, "120×50（黑底白字）", "center", PT)
# 拒1～拒5（白底黑字）
for k, t in enumerate(("道路施工", "車輛慢行", "道路封閉", "道路改道", "交通管制")):
    x0, y0 = 300.0, 255.0 - k * 33.0
    sh.rect(x0, y0, 54.0, 22.5, "結構線"); sh.text(x0 + 27.0, y0 + 11.25, t, "center", TXT * 1.3)
    sh.text(x0 + 27.0, y0 - 5.0, f"拒{1 + k}", "center", PT)
sh.text(386.0, 274.0, "120×50", "center", PT); sh.text(386.0, 266.0, "白底黑字", "center", PT)
# 道路施工告示牌 90×120
v = View(sh, 118.0, 120.0, 0.45)
v.rect(0, 80, 90, 40); v.rect(0, 40, 90, 40); v.rect(0, 0, 90, 40)
sh.text(v.X(45), v.Y(100), "道路施工", "center", TXT)
for xx in (25, 55): v.poly([(xx + 12, 52), (xx, 60), (xx + 12, 68)], "結構線"); v.poly([(xx + 24, 52), (xx + 12, 60), (xx + 24, 68)], "結構線")
for xx in range(0, 90, 15): v.poly([(xx, 0), (xx + 8, 0), (min(xx + 8 + 30, 90), min(30, 90 - xx - 8) + 0), (xx + 30 if xx + 30 <= 90 else 90, 30 if xx + 30 <= 90 else 90 - xx)], "細線")
v.dimh(0, 90, 128, "90"); v.dimv(0, 120, -10, "120")
sh.text(v.X(45), 108.0, "前方施工告示牌", "center", PT)
# 交通錐
for j, xc in enumerate((186.0, 214.0)):
    v = View(sh, xc, 120.0, 0.6)
    v.poly([(-18.25, 0), (-18.25, 2.8), (-15.3, 2.8), (-2.8, 70), (2.8, 70), (15.3, 2.8), (18.25, 2.8), (18.25, 0), (-18.25, 0)])
    for y1, y2 in ((40, 52), (22, 32)):
        xa = 15.3 - (15.3 - 2.8) * (y1 - 2.8) / 67.2; xb = 15.3 - (15.3 - 2.8) * (y2 - 2.8) / 67.2
        v.poly([(-xa, y1), (-xb, y2), (xb, y2), (xa, y1), (-xa, y1)], "細線"); v.hatch(-xb, y1, 2 * xb, y2 - y1, 1.2)
v.dimv(0, 70, 26, "70", left=False)
sh.text(200.0, 108.0, "交通錐（H=70）", "center", PT)
# 活動式警示燈（直流、交流）
for j, (xc, nm) in enumerate(((246.0, "直流電式警示燈"), (277.0, "交流電式警示燈"))):
    v = View(sh, xc, 124.0, 0.42)
    v.rect(-3, 0, 6, 110); v.poly([(-8, 110), (-8, 120), (-4, 126), (4, 126), (8, 120), (8, 110), (-8, 110)])
    for yy in range(10, 100, 20): v.rect(-3, yy, 6, 10, "細線"); v.hatch(-3, yy, 6, 10, 1.0)
    if j == 0: v.rect(-18, -6, 36, 6)
    else: v.poly([(-22, -6), (0, 30), (22, -6)], "細線")
    sh.text(xc, 108.0, nm, "center", PT)
v = View(sh, 186.0, 182.0, 1.0)                                      # 前方施工 LED 警示燈示意（107×56 → 示意）
sh.rect(322.0, 48.0, 70.0, 36.0, "結構線"); sh.line(322.0, 66.0, 392.0, 66.0, "細線")
sh.text(357.0, 75.0, "前方施工", "center", TXT)
for xx in (338.0, 352.0, 366.0): sh.poly([(xx, 62.0), (xx + 6, 57.0), (xx, 52.0)], "結構線")
sh.text(357.0, 41.0, "LED 警示燈（107×56）", "center", PT)
# 活動型紐澤西式塊狀護欄
v = View(sh, 40.0, 50.0, 0.5)
v.poly([(0, 0), (60, 0), (60, 15), (40, 40), (38, 80), (22, 80), (20, 40), (0, 15), (0, 0)])
for yy in (30, 55): a = np.radians(np.linspace(0, 360, 13)); sh.poly(np.column_stack([v.X(30) + 1.2 * np.cos(a), v.Y(yy) + 1.2 * np.sin(a)]), "細線")
v.dimh(0, 60, -10, "60", above=False); v.dimv(0, 80, -10, "80")
v.lab(30, 55, 84.0, 98.0, "回填清水或砂（固定用）")
v.lab(40, 25, 84.0, 90.0, "塑膠材質，橘白相間")
v = View(sh, 150.0, 50.0, 0.4)
v.rect(0, 0, 100, 80); v.rect(12, 55, 76, 12, "細線"); v.rect(12, 38, 76, 12, "細線")
sh.text(v.X(50), v.Y(61), "貼工程級反光紙", "center", PT)
v.dimh(0, 100, 88, "100")
sh.text(170.0, 36.0 + 1.0, "活動型紐澤西式塊狀護欄詳圖", "center", PT) if False else sh.text(170.0, 42.0, "活動型紐澤西式塊狀護欄", "center", PT)
notes(sh, 218.0, 96.0, ["註：",
      "1. 施工標誌、拒馬、交通錐、警示燈依交通部「道路交通標誌標線",
      "　 號誌設置規則」及「道路交通安全規則」設置，數量依施工計畫。",
      "2. LED 警示燈示意圖僅供參考；施工前應依交維計畫設置，",
      "　 並依工程司指示調整警示內容。",
      "3. 夜間開挖區設閃光警示燈；施工標誌設置位置詳 S-04。",
      "4. 臨時鋼管護欄詳 S-03。"], dy=6.8)
# ======================================================================
# S-06 告示牌詳圖（依使用者 2026-11-06 範例 34/35 排版）
# ======================================================================
sh = new("告示牌詳圖", ["NTS", "單位：cm"], "S-06")
# (1) 工程告示牌（未達查核金額）120×75
K = 1.05; x0, ytop = 22.0, 274.0; Wd, Hd = 120 * K, 75 * K
sh.rect(x0, ytop - Hd, Wd, Hd, "結構線")
sh.text(x0 + Wd / 2, ytop - 5.0, "臺中市政府水利局", "center", PT)
rows = [("工程名稱", CFG["title_block"]["project"]), ("監造廠商", dd.COMPANY), ("施工廠商", ""), ("施工期間", "民國○○年○○月○○日至○○年○○月○○日"),
        ("工地負責人", "電話："), ("專任工程人員", "電話："), ("通報專線", "全民督工 0800-009-609"), ("經費來源", "1.中央＿(仟元)　2.地方＿(仟元)"), ("重要公告事項", "1.＿年＿月＿日：")]
rh = (Hd - 10.0) / len(rows); y = ytop - 9.5; xa, xb, xm = x0 + 2.5, x0 + Wd - 2.5, x0 + 2.5 + 30.0
sh.line(xa, y, xb, y, "表格")
for k, (a, b) in enumerate(rows):
    sh.text((xa + xm) / 2, y - rh / 2, a, "center", PT)
    if b: sh.text(xm + 1.5, y - rh / 2, b if tw(b, PT) < xb - xm - 3 else b[:int((xb - xm - 3) / 2.47)], "left", PT)
    y -= rh; sh.line(xa, y, xb, y, "表格")
for xx in (xa, xm, xb): sh.line(xx, ytop - 9.5, xx, y, "表格")
sh.line(x0, ytop + 4.0, x0 + Wd, ytop + 4.0, "標註"); sh.text(x0 + Wd / 2, ytop + 7.0, "120", "center", PT)
sh.line(x0 - 4.0, ytop, x0 - 4.0, ytop - Hd, "標註"); sh.text(x0 - 7.0, ytop - Hd / 2, "75", "center", PT, 90)
title(sh, x0 + Wd / 2, ytop - Hd - 7.0, "工程告示牌（未達查核金額）", "NTS　單位：cm")
notes(sh, x0, ytop - Hd - 24.0, ["註：1. 標示尺寸除另有註明外，均以 cm 為單位。",
                                 "　　2. 漆綠色底、白色正楷字體、線條及框。",
                                 "　　3. 工程竣工驗收後，由承商自行拆除處理。",
                                 "　　4. 告示牌得採鐵板或鋁板等材質，牌面固定",
                                 "　　　 方式配合現場地形，得固定於固定物。"], 6.8)
# (2) 工程告示牌（活動式）120×144＋支腳 25
K = 0.92; x0, ytop = 160.0, 274.0; Wd, Hp = 120 * K, 144 * K
sh.rect(x0, ytop - Hp, Wd, Hp, "結構線")
for xx in (x0 + 3 * K, x0 + Wd - 3 * K): sh.line(xx, ytop - Hp, xx, ytop - Hp - 25 * K, "結構線")
sh.text(x0 + Wd / 2, ytop - 7.0, "臺中市政府水利局工程告示牌", "center", PT)
items = ["工程名稱", "工程概要", "工程地點", "監造廠商", "施工廠商", "施工期間", "工地負責人", "品質管理人員", "職安衛人員", "專任工程人員", "空污費管制編號", "公害檢舉電話"]
rh = (Hp - 16.0) / len(items); y = ytop - 13.0; xa, xb = x0 + 3.0, x0 + Wd - 3.0; xm = xa + 30.0; xr = xb - 26.0
sh.line(xa, y, xb, y, "表格")
for k, t in enumerate(items):
    sh.text((xa + xm) / 2, y - rh / 2, t, "center", PT); y -= rh; sh.line(xa, y, xb if k in (2, 11) or k >= 11 else xr, y, "表格")
for xx in (xa, xm, xb): sh.line(xx, ytop - 13.0, xx, y, "表格")
sh.line(xr, ytop - 13.0, xr, ytop - 13.0 - rh * 6, "表格")
sh.text((xr + xb) / 2, ytop - 13.0 - rh * 1.5, "路證", "center", PT); sh.text((xr + xb) / 2, ytop - 13.0 - rh * 4.5, "施工", "center", PT)
sh.text((xr + xb) / 2, ytop - 13.0 - rh * 2.5, "張貼欄", "center", PT); sh.text((xr + xb) / 2, ytop - 13.0 - rh * 5.4, "通知單", "center", PT)
sh.line(x0 + Wd + 4.0, ytop, x0 + Wd + 4.0, ytop - Hp, "標註"); sh.text(x0 + Wd + 7.0, ytop - Hp / 2, "144", "center", PT, 90)
sh.line(x0 + Wd + 4.0, ytop - Hp, x0 + Wd + 4.0, ytop - Hp - 25 * K, "標註"); sh.text(x0 + Wd + 7.0, ytop - Hp - 12.5 * K, "25", "center", PT, 90)
sh.line(x0, ytop + 4.0, x0 + Wd, ytop + 4.0, "標註"); sh.text(x0 + Wd / 2, ytop + 7.0, "120", "center", PT)
title(sh, x0 + Wd / 2, ytop - Hp - 25 * K - 8.0, "工程告示牌（活動式）", "NTS　單位：cm　1½\"Ø 鍍鋅鋼管")
# (3) 告示牌 A 型支架（活動式）
v = View(sh, 60.0, 64.0, 0.5)
v.poly([(0, 0), (60, 150), (120, 0)]); v.line(25, 62, 95, 62); v.line(18, 45, 102, 45, "細線")
v.rect(56, 150, 8, 6, "細線")
for xx in (0, 120): v.rect(xx - 4, -6, 8, 6, "細線")
v.lab(60, 153, 128.0, 140.0, "1/2\"Ø 螺絲")
v.lab(92, 80, 128.0, 132.0, "1½\"Ø 鍍鋅鋼管")
v.lab(28, 70, 128.0, 124.0, "告示牌（8 號鋁片）")
v.lab(60, 62, 128.0, 100.0, "合疊活動式鍍鋅鐵片")
v.lab(118, -3, 128.0, 80.0, "橡膠套 H=3 cm")
title(sh, 90.0, 52.0, "告示牌（活動式）支架", "NTS")
notes(sh, 128.0, 66.0, ["註：1. 告示圍籬面材質為鋁質，厚度至少 2 mm。",
                       "　　2. 設置位置及數量依工程司指示。"], 6.8)
# (4) 職業安全衛生告示牌 150×90
K = 0.82; x0, ytop = 284.0, 178.0; Wd, Hd = 150 * K, 90 * K
sh.rect(x0, ytop - Hd, Wd, Hd, "結構線")
sh.text(x0 + Wd / 2, ytop - 6.0, "職業安全衛生告示牌", "center", TXT)
xa = x0 + 3.0; Wt = Wd - 6.0; y = ytop - 12.0
def hl(yy): sh.line(xa, yy, xa + Wt, yy, "表格")
hl(y)
for t1 in ("工程名稱：" + CFG["title_block"]["project"], "監造單位：" + dd.COMPANY):
    sh.text(xa + 1.5, y - 3.6, t1 if tw(t1, PT) < Wt - 3 else t1[:int((Wt - 3) / 2.47)], "left", PT); y -= 7.2; hl(y)
yb0 = y
for t1, t2 in (("廠商名稱：", "電話："), ("工地負責人：", "安衛管理員："), ("值班人員：", "本日出工人數：")):
    sh.text(xa + 9, y - 3.6, t1, "left", PT); sh.text(xa + Wt * 0.55, y - 3.6, t2, "left", PT); y -= 7.2
for k, ch in enumerate("施工廠商"): sh.text(xa + 4, yb0 - 3.0 - 5.3 * k, ch, "center", PT) if k < 4 else None
sh.line(xa + 8, yb0, xa + 8, y, "表格"); hl(y)
cw = Wt / 3
for k, t in enumerate(("本日工作項目", "應辦安衛事項", "特別注意事項")): sh.text(xa + cw * (k + 0.5), y - 3.6, t, "center", PT)
y -= 7.2; hl(y); y2 = ytop - Hd + 10.0
for k in (1, 2): sh.line(xa + cw * k, y + 7.2, xa + cw * k, y2, "表格")
y = y2; hl(y)
sh.text(xa + 1.5, y - 3.8, "緊急聯絡：警察局 110　消防隊 119　醫院（　）", "left", PT)
for xx in (xa, xa + Wt): sh.line(xx, ytop - 12.0, xx, y2, "表格")
sh.line(x0, ytop + 4.0, x0 + Wd, ytop + 4.0, "標註"); sh.text(x0 + Wd / 2, ytop + 7.0, "150", "center", PT)
sh.line(x0 - 4.0, ytop, x0 - 4.0, ytop - Hd, "標註"); sh.text(x0 - 7.0, ytop - Hd / 2, "90", "center", PT, 90)
title(sh, x0 + Wd / 2, ytop - Hd - 7.0, "職業安全衛生告示牌", "NTS　單位：cm")
notes(sh, x0, ytop - Hd - 24.0, ["註：1. 告示牌尺寸 150×90 cm。",
                                 "　　2. 漆白色底、藍色正楷字體、線條及框。",
                                 "　　3. 工程竣工驗收後，由承商自行拆除處理。"], 6.8)

# ---------- 檢查與輸出 ----------
for sh in sheets: check(sh, ("結構線", "鋼軌樁", "開挖線", "表格"))
base = f"{dd.PRE}{stamp}_A3_標準圖S01-S06_{dd.ver('standard')}_TWD97_GENIE"

dxf, pdf, pngs = save(sheets, LAYERS, OUT, PREV, base)
print("DXF：", dxf); print("PDF：", pdf)
for p in pngs: print("PNG：", p)
