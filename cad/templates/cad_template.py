# 產生 A3 平縱橫斷面圖說樣板 DXF（不含任何案件測量資料）：圖層、顏色、線型、字型、圖筆、圖框、資料帶骨架、圖層設定表
import sys, ezdxf
from ezdxf.enums import TextEntityAlignment as TA
sys.stdout.reconfigure(encoding="utf-8")
OUT = sys.argv[1]

TXT, TBT = 7.06, 4.94            # 20 pt、14 pt（mm）
WF, TB_WF = 0.5, 0.7             # 寬度係數：圖標欄以外 0.5、圖標欄 0.7
# 圖層: (ACI, 圖層線寬mm, 圖層線型, 用途, 黑白圖筆列印結果)
LAYERS = {
    "圖框": (7, 0.50, None, "內外圖框", "黑 0.18"),
    "圖標欄": (7, 0.35, None, "圖標欄、表格線", "黑 0.18"),
    "資料帶": (7, 0.25, None, "縱斷面資料帶、斷面框", "黑 0.18"),
    "格線": (254, 0.13, None, "1 m 格線（個別線型 DOT）", "#CCCCCC 0.212"),
    "主格線": (253, 0.18, None, "5 m 格線（縱斷面 DASHED）", "#A3A3A3 0.212"),
    "原始地面線": (252, 0.70, None, "原地形線", "#666666 0.212"),
    "計畫溪床線": (157, 1.00, None, "設計線（待定）", "物件色 0.085"),
    "中心線1": (22, 0.35, "CENTER", "定線（個別比例 0.1）", "黑 0.085"),
    "斷面中心線": (22, 0.25, "DASHDOT", "橫斷面 CL", "黑 0.085"),
    "岸線": (157, 0.50, None, "兩岸線", "物件色 0.085"),
    "斷面切線": (149, 0.25, "DASHED", "平面圖橫斷面切線", "物件色 0.085"),
    "計曲線": (252, 0.25, None, "5 m 等高線", "#666666 0.212"),
    "首曲線": (254, 0.09, None, "1 m 等高線", "#CCCCCC 0.212"),
    "地物": (253, 0.13, None, "測量地物、圖例符號", "#A3A3A3 0.212"),
    "標註": (7, 0.25, None, "尺寸線、刻度", "黑 0.18"),
    "水流方向": (157, 0.35, None, "水流箭頭", "物件色 0.085"),
    "文字": (7, 0.0, None, "所有文字", "黑 0.18"),
}
def snap_lw(lw):
    valid = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211]
    return min(valid, key=lambda v: abs(v - lw*100))

doc = ezdxf.new("R2018", setup=True)
doc.header["$INSUNITS"] = 4; doc.header["$LTSCALE"] = 5.0; doc.header["$PSTYLEMODE"] = 1
doc.styles.add("GENIE", font="GENIE.shx"); doc.styles.add("GENISO", font="GENISO.shx")
for nm, (aci, lw, lt, _u, _p) in LAYERS.items():
    la = doc.layers.add(nm, color=aci)
    if lw > 0: la.dxf.lineweight = snap_lw(lw)
    if lt: la.dxf.linetype = lt
msp = doc.modelspace()
msp.dxf_layout.dxf.current_style_sheet = "A3-圖筆(黑白).ctb"

def P(pts, layer, ox, lt=None, lts=1.0):
    at = {"layer": layer}
    if lt: at["linetype"] = lt
    if lts != 1.0: at["ltscale"] = lts
    msp.add_lwpolyline([(x + ox, y) for x, y in pts], dxfattribs=at)
def L(x1, y1, x2, y2, layer, ox, lt=None, lts=1.0): P([(x1, y1), (x2, y2)], layer, ox, lt, lts)
def R(x, y, w, h, layer, ox): P([(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)], layer, ox)
def T(x, y, s, ox, ha="left", h=TXT, rot=0, wf=WF):
    t = msp.add_text(s, height=h, rotation=rot, dxfattribs={"layer": "文字", "style": "GENISO" if s.isascii() else "GENIE", "width": wf})
    t.set_placement((x + ox, y), align={"left": TA.MIDDLE_LEFT, "center": TA.MIDDLE_CENTER, "right": TA.MIDDLE_RIGHT}[ha])

def frame(ox, name, scales, no):
    R(0, 0, 420, 297, "圖框", ox); R(10, 10, 400, 277, "圖框", ox); R(10, 10, 400, 22, "圖標欄", ox)
    for x in (86, 188, 226, 262, 298, 392): L(x, 10, x, 32, "圖標欄", ox)
    for x0, x1 in ((86, 188), (226, 298), (392, 410)): L(x0, 21, x1, 21, "圖標欄", ox)
    yc = (14.94, 20.88, 26.82); tb = dict(ox=ox, h=TBT, wf=TB_WF)
    T(48, yc[2], "主辦機關", ha="center", **tb); T(48, yc[1], "【機關名稱待補】", ha="center", **tb); T(48, yc[0], "【Agency name TBD】", ha="center", **tb)
    T(89.5, 26.5, "工程名稱：【工程名稱待補】", **tb); T(89.5, 15.5, "圖　名：" + name, **tb)
    T(207, yc[2], "比例尺", ha="center", **tb)
    for s, y in zip(scales, (yc[1], yc[0])): T(207, y, s, ha="center", **tb)
    T(229.5, 26.5, "設計：", **tb); T(265.5, 26.5, "主管：", **tb); T(229.5, 15.5, "繪圖：", **tb); T(265.5, 15.5, "校核：", **tb)
    T(345, yc[2], "設計單位", ha="center", **tb); T(345, yc[1], "辰璟工程技術顧問有限公司", ha="center", **tb)
    T(345, yc[0], "Chen-Jing Engineering Co.,Ltd", ha="center", **tb)
    T(401, 26.5, "圖號", ha="center", **tb); T(401, 15.5, no, ha="center", **tb)

# 1. 平面圖樣板
ox = 0; frame(ox, "平面圖（樣板）", ["1/1000"], "01")
R(26, 48, 170, 237, "圖框", ox); T(111, 166, "平面圖區（1/1000，北朝上，TWD97 座標刻度）", ox, "center", TBT)
R(203, 149, 202.4, 136, "圖標欄", ox); T(304, 217, "圖例表：沿用原始測量圖 DXF 的圖例表（放大後置於此）", ox, "center", TBT)
P([(225, 56), (220, 42), (225, 46), (230, 42), (225, 56)], "標註", ox); T(225, 65.5, "N", ox, "center")
T(312, 68, "比例尺 1/1000", ox, "center"); R(262, 54, 100, 3.5, "標註", ox); L(312, 54, 312, 57.5, "標註", ox)
for x, t in ((262, "0"), (312, "50"), (362, "100 m")): T(x, 42, t, ox, "center")

# 2. 縱斷面樣板（H=1/500、V=1/250；每張約 120 m；框高＝原地形 ±3 m）
ox = 450; frame(ox, "縱斷面圖（樣板）", ["H=1/500", "V=1/250"], "02")
BX0, TCW, DX0, X0, PY0, XM, YM = 18.0, 25.0, 44.4, 53.3, 118.0, 2.0, 4.0
nst = 7; x_end = X0 + 120 * XM; BX1 = x_end + 3.1; nz = 31; PY1 = PY0 + nz * YM
R(BX0, PY0, BX1 - BX0, PY1 - PY0, "資料帶", ox)
for k in range(1, nz):
    y = PY0 + k * YM
    if k % 5 == 2: L(BX0, y, BX1, y, "主格線", ox, "DASHED")
    else: L(BX0, y, BX1, y, "格線", ox, "DOT")
for k in range(nz + 1):
    if k % 5 == 2:
        y = PY0 + k * YM; T(BX0 - 2, y, "EL", ox, "right", TBT); T(BX1 + 1.3, y, "EL", ox, "left", TBT)
rows = [("距離", 34.0, 17.0), ("樁號", 54.0, 19.0), ("原始高程", 76.0, 17.0), ("坡度(%)", 96.0, 17.0)]
for nm, y0, h in rows:
    R(BX0, y0, TCW, h, "資料帶", ox); R(DX0, y0, BX1 - DX0, h, "資料帶", ox); T(BX0 + TCW/2, y0 + h/2, nm, ox, "center", TXT)
xs = [X0 + 40 * i for i in range(nst)]
for gb in (73.0, 93.0):
    for x in xs: L(x, gb, x, gb + 2.5, "資料帶", ox)
for i, x in enumerate(xs):
    T(x - 0.7, 63.5, f"0K+{20*i:03d}", ox, "center", TBT, 90); T(x - 0.7, 84.5, "000.00", ox, "center", TBT, 90)
L(xs[0], 38.5, xs[-1], 38.5, "標註", ox)
for x in xs: L(x, 37.2, x, 39.8, "資料帶", ox)
for xa, xb in zip(xs[:-1], xs[1:]):
    T((xa + xb)/2, 104.5, "0.0", ox, "center", TBT, 90); T((xa + xb)/2, 44.5, "L=20.00", ox, "center", TBT)
LY = PY1 + 6.0; x = BX0
T(x, LY, "圖例", ox, "left", TBT); x += 2*TBT*WF + 5
L(x, LY, x + 10, LY, "原始地面線", ox); x += 12.5
T(x, LY, "原始地形（中心線1）", ox, "left", TBT); x += 9*TBT*WF + 5
L(x, LY, x + 10, LY, "計畫溪床線", ox); x += 12.5
T(x, LY, "計畫溪床線（待設計）", ox, "left", TBT); T(BX1 - 1.0, LY, "接續第 2 頁", ox, "right", TBT)

# 3. 橫斷面樣板（1/300；每張 4 刀；框高＝原地形 ±5 m）
ox = 900; frame(ox, "橫斷面圖（樣板）", ["1/300"], "03")
SC = 1000/300.0; CW, CH = 200.0, 253.0/2
for idx in range(4):
    col, row = idx % 2, idx // 2
    cx0 = 10 + col * CW; y0 = 287 - (row + 1) * CH; xc = cx0 + CW/2
    yb = y0 + 22.0; nzz = 18; yt = yb + nzz * SC; bx0, bx1 = xc - 20*SC, xc + 20*SC
    R(bx0, yb, bx1 - bx0, yt - yb, "資料帶", ox)
    for k in range(1, nzz):
        y = yb + k * SC
        if k % 5 == 0: L(bx0, y, bx1, y, "主格線", ox)
        else: L(bx0, y, bx1, y, "格線", ox, "DOT")
    for uu in range(-15, 20, 5):
        if uu % 10 == 0: L(xc + uu*SC, yb, xc + uu*SC, yt, "主格線", ox)
        else: L(xc + uu*SC, yb, xc + uu*SC, yt, "格線", ox, "DOT")
    for uu, lab in zip((-20, -10, 0, 10, 20), ("左20", "10", "0", "10", "右20")): T(xc + uu*SC, y0 + 14, lab, ox, "center")
    L(xc, yb, xc, yt, "斷面中心線", ox); T(xc, yt + 5.5, "CL", ox, "center")
    T(bx0 + 10, y0 + 5.0, f"0K+{20*idx:03d}", ox); L(bx0 + 10, y0 + 0.5, bx0 + 10 + 6*0.6*TXT*WF + 2, y0 + 0.5, "標註", ox)
    T(xc + 5, y0 + 5.0, "挖：— m²　填：— m²", ox)

# 4. 圖層與圖筆設定表
ox = 1350; frame(ox, "圖層與圖筆設定表（樣板）", ["NTS"], "04")
cols = [(14, "圖層"), (64, "顏色號"), (90, "範例線"), (160, "黑白圖筆列印"), (220, "用途")]
RH = 13.0; y_top = 280.0; n = len(LAYERS) + 1
R(14, y_top - RH*n, 392, RH*n, "圖標欄", ox)
for xc, _ in cols[1:]: L(xc, y_top - RH*n, xc, y_top, "圖標欄", ox)
for k in range(1, n): L(14, y_top - RH*k, 406, y_top - RH*k, "圖標欄", ox)
for xc, nm in cols: T(xc + 3.5, y_top - RH/2, nm, ox, "left", TBT)
lt_demo = {"格線": ("DOT", 1.0), "主格線": ("DASHED", 1.0), "中心線1": ("CENTER", 0.1)}
for k, (nm, (aci, lw, lt, use, pr)) in enumerate(LAYERS.items()):
    y = y_top - RH*(k + 1) - RH/2
    T(17.5, y, nm, ox, "left", TBT); T(67.5, y, str(aci), ox, "left", TBT)
    if nm != "文字":
        lt_, lts_ = lt_demo.get(nm, (None, 1.0)); L(95, y, 155, y, nm, ox, lt_, lts_)
    T(163.5, y, pr, ox, "left", TBT); T(223.5, y, use, ox, "left", TBT)
T(14, 31 + 9, "圖筆：預設 A3-圖筆(黑白).ctb；有航照圖或彩色外部參考時改 A3-圖筆(全彩).ctb。線寬以圖筆為準，圖層線寬列印時不生效。", ox, "left", TBT)
doc.saveas(OUT); print("樣板 DXF：", OUT)
