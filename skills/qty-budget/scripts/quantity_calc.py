"""P33 數量計算書（土石方數量計算表＋工程數量計算表），格式依業主範例 11-1、11-2。
資料來源：設計圖冊 v2.3（P-01 平面、X-01/X-02 橫斷面 section_areas_v3.csv、S-01～S-06 標準圖 v2.6）。
輸出 xlsx（保留公式；所有數量由「參數」工作表連結計算），PDF 由 Excel 重算後匯出（quantity_calc_pdf.ps1）。
用法：python -I quantity_calc.py --case <案件資料夾> [--areas section_areas_v3.csv] --stamp YYYYMMDD_HHMM
（--case 省略時用本檔所在資料夾；--areas 為相對於案件資料夾的斷面積 csv）
參考實作：工項、參數、圖號都是 P33 東山街案的，新案改 PARAMS、Q、NOTE。
"""
import sys, os, csv, json, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.page import PageMargins

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
CASE = os.path.abspath(arg("--case", HERE))
CFG = json.load(open(os.path.join(CASE, "case_config.json"), encoding="utf-8-sig"))
CODE = CFG.get("case_code", "P33")
stamp = arg("--stamp", datetime.datetime.now().strftime("%Y%m%d_%H%M"))
AREAS = os.path.join(CASE, arg("--areas", "section_areas_v3.csv"))
VER = "v1.5"
PROJ = CFG["title_block"]["project"]
OUT = os.path.join(CFG["out_dir"], f"{CFG['file_prefix']}{stamp}_{CODE}_數量計算書_{VER}.xlsx")

FN = "微軟正黑體"; DK = "1F2D3A"; HD = "3E5C76"
HF = PatternFill("solid", fgColor=HD); SF = PatternFill("solid", fgColor="D8DEE4"); TF = PatternFill("solid", fgColor="ECEFF2")
thin = Side(style="thin", color="7A8A99"); BD = Border(left=thin, right=thin, top=thin, bottom=thin)

def style_header(ws, row, ncol, h=44):
    for j in range(1, ncol + 1):
        c = ws.cell(row, j); c.font = Font(name=FN, size=25, bold=True, color="FFFFFF"); c.fill = HF; c.border = BD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = h

def body(c, fmt=None, align="center", bold=False, size=14, fill=None):
    c.font = Font(name=FN, size=size, bold=bold, color=DK); c.border = BD
    c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)
    if fmt: c.number_format = fmt
    if fill: c.fill = fill

def page(ws, title, landscape=True, paper="A4", rows="1:1", fit_w=1):
    ws.print_title_rows = rows
    ws.page_setup.paperSize = ws.PAPERSIZE_A4 if paper == "A4" else ws.PAPERSIZE_A3
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.fitToWidth = fit_w; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.8, bottom=0.7, header=0.3, footer=0.3)
    ws.oddHeader.center.text = f"{PROJ}　{title}"; ws.oddHeader.center.size = 12
    ws.oddFooter.center.text = "辰璟工程技術顧問有限公司　第 &P 頁／共 &N 頁"; ws.oddFooter.center.size = 12

wb = Workbook()

# ======================================================================
# 參數（所有計算式的來源；每項附圖號出處）
# ======================================================================
wp = wb.active; wp.title = "參數"
P = {}   # 名稱 -> 儲存格位址（參數!$C$n）
PARAMS = [
    ("#", "一、長度（平面配置圖 P-01、橫斷面 X-01／X-02）"),
    ("LA", "A 側（西）新設箱涵式側溝長度", 111.53, "m", "P-01 主要構造物數量表 #A"),
    ("LB", "B 側（東）新設箱涵式側溝長度", 110.48, "m", "P-01 主要構造物數量表 #B"),
    ("NA", "A 側溝身淨長（兩端交接面之間）", "=110.56-0.97", "m", "X-01、X-02：A 側交接面 側溝樁距 0.97～110.56（集水井段另計）"),
    ("NB", "B 側溝身淨長（兩端交接面之間）", "=109.51-0.97", "m", "X-01、X-02：B 側交接面 側溝樁距 0.97～109.51（集水井段另計）"),
    ("RA", "A 側既有暗溝 50×80 拆除長度", 113.43, "m", "P-01 主要構造物數量表 拆除"),
    ("RB", "B 側既有暗溝 50×85 拆除長度", 112.38, "m", "P-01 主要構造物數量表 拆除"),
    ("NW", "側溝式箱涵集水井座數", 4, "座", "P-01：#AC1、#AC2、#BC1、#BC2"),
    ("#", "二、箱涵式側溝每公尺數量（S-01 每公尺數量表、鋼筋表）"),
    ("QC", "溝體混凝土 210 kgf/cm²（含內角加腋 20×20）", 0.740, "m³/m", "S-01 每公尺數量表"),
    ("QB", "墊層混凝土 140 kgf/cm²（寬 150×厚 10）", 0.150, "m³/m", "S-01 每公尺數量表"),
    ("QF", "溝體模板（內壁 2×1.00＋外壁 2×1.20）", 4.40, "m²/m", "S-01 每公尺數量表"),
    ("QBF", "墊層模板（兩側 2×0.10）", "=2*0.1", "m²/m", "S-01 剖面：墊層 t=10"),
    ("R16", "溝體鋼筋 D16（A 筋 L=360 @15）", "=100/15*3.60*1.56", "kg/m", "S-01 側溝鋼筋 A；D16 單位重 1.560 kg/m"),
    ("R13", "溝體鋼筋 D13（B 320、C 110 @15；D 105 @15 兩側）", "=100/15*(3.20+1.10+2*1.05)*0.994", "kg/m", "S-01 側溝鋼筋 B～D；D13 單位重 0.994 kg/m"),
    ("QK", "場鑄緣石混凝土 280 kgf/cm²（20×15）", "=0.20*0.15", "m³/m", "S-01 每公尺數量表"),
    ("QKF", "場鑄緣石模板（兩側 2×0.15）", "=2*0.15", "m²/m", "S-01 剖面：緣石高 15"),
    ("RE", "側溝縱向配力筋（側溝 E）D13 @25 內外兩層，含搭接", 31.11, "kg/m", "S-01 v2.8 每公尺數量表 31.1；配筋檢核表 v1.2 第 7.15 項"),
    ("RK13", "場鑄緣石鋼筋 D13（編號 12）", 3.78, "kg/m", "S-02 場鑄緣石鋼筋表"),
    ("RK10", "場鑄緣石鋼筋 D10（編號 13）", 2.02, "kg/m", "S-02 場鑄緣石鋼筋表"),
    ("#", "三、集水井（S-01 集水井剖面，內徑 150×150）"),
    ("WI", "集水井內淨寬", 1.50, "m", "S-01、P-01"),
    ("WT", "集水井井壁厚", 0.20, "m", "S-01"),
    ("WH", "集水井內淨深（蓋板底至井底）", 1.30, "m", "S-01 集水井剖面 130"),
    ("WS", "集水井底版厚", 0.20, "m", "S-01 集水井剖面 20"),
    ("WB", "集水井墊層厚", 0.10, "m", "S-01 集水井剖面 10"),
    ("WO", "集水井外寬", "=WI+2*WT", "m", "計算"),
    ("WOP", "每座井壁側溝開口（110×100，1 處）", "=1.10*1.00", "m²", "S-01；開口數【待確認】"),
    ("STEP", "人孔踏步間距", 0.30, "m", "S-01-1 附註 4、S-02 附註 4"),
    ("#", "四、預鑄溝蓋板（S-01、S-02）"),
    ("CBL", "預鑄溝蓋板沿溝長度（每塊）", 1.00, "m", "S-02 甲、乙種蓋板 100×150"),
    ("CBK", "甲種蓋板間隔（每 5 m 一處）", 5, "m", "S-01 平面圖"),
    ("#", "五、臨時擋土（S-03）"),
    ("PS", "鋼軌樁間距", 1.00, "m", "S-03 鋼軌樁 L=300 @100"),
    ("PL", "鋼軌樁長度", 3.00, "m", "S-03"),
    ("PD", "開挖深度（背插鐵板高度）", 1.53, "m", "S-03 註 1、G-02 一.5"),
    ("#", "六、路面與其他"),
    ("ACW", "AC 路面修復寬度（溝蓋板路內側）", 0.40, "m", "S-01-1 平面圖 40【待確認】"),
    ("ACT", "AC 面層厚度", 0.05, "m", "S-01：AC 面層 t=5"),
    ("EJ", "伸縮縫間距", 10, "m", "S-01 註 2：每 10 m 設伸縮縫"),
    ("#", "七、臨時鋼管護欄（使用者 2026-11-06 要求編列；詳 S-03）"),
    ("GW", "開挖端部寬（路外側 10＋集水井外寬 190＋路內側 30）", "=0.10+1.90+0.30", "m", "S-01 開挖線、S-03 開挖寬"),
]
wp.append(["代號", "參數項目", "數值", "單位", "出處（圖號）"])
style_header(wp, 1, 5)
r = 1
for p in PARAMS:
    r += 1
    if p[0] == "#":
        wp.cell(r, 2, p[1]); wp.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        body(wp.cell(r, 1), align="left", bold=True, size=18, fill=SF); wp.cell(r, 2).font = Font(name=FN, size=18, bold=True, color=DK)
        wp.cell(r, 1).value = p[1]; wp.row_dimensions[r].height = 32; continue
    k, name, val, unit, src = p
    P[k] = f"參數!$C${r}"
    wp.cell(r, 1, k); wp.cell(r, 2, name); wp.cell(r, 4, unit); wp.cell(r, 5, src)
    wp.cell(r, 3, val)
    for j, al in zip(range(1, 6), ["center", "left", "right", "center", "left"]):
        body(wp.cell(r, j), align=al)
    wp.cell(r, 3).number_format = "0" if unit in ("座",) or k in ("CBK", "EJ") else "0.00##"
    wp.row_dimensions[r].height = 30 if len(name) < 22 and len(src) < 28 else 46
# 參數內引用其他參數：外寬＝內寬＋2×壁厚
wo_row = int(P["WO"].split("$")[-1])
wp.cell(wo_row, 3).value = f"={P['WI'].split('!')[1]}+2*{P['WT'].split('!')[1]}"
for col, w in zip("ABCDE", [9, 52, 14, 10, 62]): wp.column_dimensions[col].width = w
wp.freeze_panes = "B2"; page(wp, "數量計算參數")

def R(expr):
    """把 {代號} 換成參數儲存格位址"""
    out = expr
    for k in sorted(P, key=len, reverse=True): out = out.replace("{" + k + "}", P[k])
    return out

# ======================================================================
# 土石方數量計算表（11-1 格式：樁號、距離、挖方、填方）
# ======================================================================
rows = list(csv.DictReader(open(AREAS, encoding="utf-8-sig")))
we = wb.create_sheet("土石方數量計算表")
NL = chr(10)
H1 = [NL.join(h.split("|")) for h in ["側別", "中心線|樁號", "側溝|樁距|m", "斷面|類別", "距離|m", "挖方|斷面積|m²", "挖方|平均|斷面積|m²", "挖方|土方量|m³",
      "填方|斷面積|m²", "填方|平均|斷面積|m²", "填方|土方量|m³", "附註"]]
we.append(H1); style_header(we, 1, len(H1), 120)
r = 1; side_tot = {}
for side, nm in (("A", "A 側（西）"), ("B", "B 側（東）")):
    r += 1; we.cell(r, 1, f"{nm}　新設箱涵式側溝（L＝{'111.53' if side == 'A' else '110.48'} m）")
    we.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(H1))
    body(we.cell(r, 1), align="left", bold=True, size=18, fill=SF); we.row_dimensions[r].height = 32
    sr = [x for x in rows if x["側"] == side]
    st = [(float(x["側溝樁距m"]), x["中心線樁號"], x["類別"], float(x["挖方m2"]), float(x["回填m2"]), x["說明"]) for x in sr]
    st.sort(key=lambda t: t[0])
    # 兩端集水井外緣：自最外側井斷面往外延伸半井外寬 0.95 m（同井斷面積）
    st = [(st[0][0] - 0.95, "—", "集水井外緣", st[0][3], st[0][4], "井外緣（井斷面外推 0.95 m）")] + st + \
         [(st[-1][0] + 0.95, "—", "集水井外緣", st[-1][3], st[-1][4], "井外緣（井斷面外推 0.95 m）")]
    first = r + 1
    for i, (s, cl, kind, ca, fa, note) in enumerate(st):
        r += 1
        we.cell(r, 1, side); we.cell(r, 2, cl); we.cell(r, 3, round(s, 2)); we.cell(r, 4, kind)
        we.cell(r, 6, ca); we.cell(r, 9, fa); we.cell(r, 12, note if note.startswith("井外緣") or not note else "切斷面：" + note)
        if i > 0:
            we.cell(r, 5, f"=C{r}-C{r-1}")
            we.cell(r, 7, f"=(F{r}+F{r-1})/2"); we.cell(r, 8, f"=ROUND(E{r}*G{r},2)")
            we.cell(r, 10, f"=(I{r}+I{r-1})/2"); we.cell(r, 11, f"=ROUND(E{r}*J{r},2)")
        for j in range(1, 13):
            body(we.cell(r, j), fmt="0.00" if j in (3, 5, 6, 7, 8, 9, 10, 11) else None, align="left" if j == 12 else "center")
        we.row_dimensions[r].height = 30
    last = r
    r += 1; we.cell(r, 1, f"{side} 側小計")
    we.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    we.cell(r, 5, f"=SUM(E{first}:E{last})"); we.cell(r, 8, f"=SUM(H{first}:H{last})"); we.cell(r, 11, f"=SUM(K{first}:K{last})")
    for j in range(1, 13): body(we.cell(r, j), fmt="0.00", bold=True, fill=TF)
    we.row_dimensions[r].height = 30
    side_tot[side] = r
r += 1; we.cell(r, 1, "總　計"); we.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
we.cell(r, 8, f"=H{side_tot['A']}+H{side_tot['B']}"); we.cell(r, 11, f"=K{side_tot['A']}+K{side_tot['B']}")
we.cell(r, 12, "自然方；未換算鬆方")
for j in range(1, 13): body(we.cell(r, j), fmt="0.00", bold=True, fill=SF, align="left" if j == 12 else "center")
we.row_dimensions[r].height = 34
EW_TOT = r
r += 2
notes_e = ["附註：",
           "1. 斷面積取自設計橫斷面圖 X-01、X-02（section_areas_v3）：挖方以整地後地面（SG）至開挖底（墊層底），開挖寬＝路外側外壁外 10 cm＋溝外寬＋路內側外壁外 30 cm。",
           "2. 填方為溝外壁至擋土樁之施工空間回填（扣除溝蓋板厚 23 cm 範圍之路面）。",
           "3. 體積用平均斷面法 V＝(A₁＋A₂)÷2×L，L 為兩斷面之側溝樁距差；斷面變化處（集水井↔側溝）平均斷面法有誤差，以集水井個別外緣斷面收尾。",
           "4. 兩端集水井外緣斷面：以最外側集水井斷面往外延伸半個井外寬（190÷2＝95 cm），使用者 2026-11-06 同意；交通維持圖 S-04 開挖施工區同步改為 L≒112.9 m。",
           "5. 量體為自然方，未換算鬆方；餘土＝挖方－填方，運棄依臺中市營建剩餘土石方規定處理。"]
for t in notes_e:
    we.cell(r, 1, t); we.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12)
    we.cell(r, 1).font = Font(name=FN, size=14, color=DK); we.cell(r, 1).alignment = Alignment(wrap_text=True, vertical="center")
    we.row_dimensions[r].height = 30 if len(t) < 70 else 48; r += 1
for col, w in zip("ABCDEFGHIJKL", [9, 16, 13, 14, 12, 14, 14, 15, 14, 14, 15, 36]): we.column_dimensions[col].width = w
we.freeze_panes = "B2"; page(we, "土石方數量計算表")
TA = f"土石方數量計算表!$E${side_tot['A']}"; TB = f"土石方數量計算表!$E${side_tot['B']}"
EX = f"土石方數量計算表!$H${EW_TOT}"; FL = f"土石方數量計算表!$K${EW_TOT}"

# ======================================================================
# 集水井計算（個別幾何＋鋼筋）
# ======================================================================
ww = wb.create_sheet("集水井計算")
ww.append(["項次", "項目", "計算式", "每座數量", "單位", "座數", "合計", "出處"])
style_header(ww, 1, 8)
WBAR = [("A", "D16", 4.60, 1.560), ("B", "D13", 4.20, 0.994), ("C", "D13", 1.50, 0.994), ("D", "D13", 1.05, 0.994),
        ("E", "D13", 2.20, 0.994), ("F", "D13", 1.80, 0.994), ("G", "D13", 1.80, 0.994)]
items_w = [
    ("1", "井體混凝土 210（外寬²×(淨深＋底版)－內寬²×淨深－側溝開口×壁厚）",
     "={WO}^2*({WH}+{WS})-{WI}^2*{WH}-{WOP}*{WT}", "m³", "S-01 集水井剖面"),
    ("2", "墊層混凝土 140（外寬²×墊層厚）", "={WO}^2*{WB}", "m³", "S-01 集水井剖面"),
    ("3", "井體模板（外壁 4×外寬×(淨深＋底版)＋內壁 4×內寬×淨深－開口 2 面）",
     "=4*{WO}*({WH}+{WS})+4*{WI}*{WH}-2*{WOP}", "m²", "S-01 集水井剖面"),
    ("4", "墊層模板（4×外寬×墊層厚）", "=4*{WO}*{WB}", "m²", "S-01"),
    ("5", "塑膠包覆人孔踏步（(淨深＋蓋板 0.23)÷間距，取整）", "=ROUNDDOWN(({WH}+0.23)/{STEP},0)", "個", "S-01-1 附註 4"),
]
r = 1
for it in items_w:
    r += 1
    no, name, f, unit, src = it
    ww.cell(r, 1, no); ww.cell(r, 2, name); ww.cell(r, 3, f[1:].replace("{", "").replace("}", "")); ww.cell(r, 4, R(f))
    ww.cell(r, 5, unit); ww.cell(r, 6, f"={P['NW']}"); ww.cell(r, 7, f"=ROUND(D{r}*F{r},2)"); ww.cell(r, 8, src)
    for j in range(1, 9): body(ww.cell(r, j), fmt="0.00" if j in (4, 7) else ("0" if j == 6 else None), align="left" if j in (2, 3, 8) else "center")
    ww.row_dimensions[r].height = 48
W_ROW = {"conc": 2, "bed": 3, "form": 4, "bform": 5, "step": 6}
r += 1; ww.cell(r, 1, "集水井鋼筋（每座；S-01 集水井鋼筋 A～G @15，E 為井壁水平環筋，與側溝 E 不同）"); ww.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
body(ww.cell(r, 1), align="left", bold=True, size=18, fill=SF); ww.row_dimensions[r].height = 32
r += 1
for j, t in enumerate(["編號", "直徑", "支數計算", "支數", "長度 m", "單位重 kg/m", "重量 kg", "說明"], 1):
    ww.cell(r, j, t); body(ww.cell(r, j), bold=True, fill=TF)
ww.row_dimensions[r].height = 30
rb0 = r + 1
for mk, dia, L, uw in WBAR:
    r += 1
    if mk in ("A", "B", "C", "D", "G"):
        ncalc, n, note = "2 向×(外寬÷0.15＋1)", R("=2*(ROUNDUP({WO}/0.15,0)+1)"), "兩向等距配置"
    else:
        ncalc, n, note = "2 組×((淨深＋底版)÷0.15＋1)", R("=2*(ROUNDUP(({WH}+{WS})/0.15,0)+1)"), "井壁水平框架筋，每層 2 支"
    ww.cell(r, 1, mk); ww.cell(r, 2, dia); ww.cell(r, 3, ncalc); ww.cell(r, 4, n); ww.cell(r, 5, L); ww.cell(r, 6, uw)
    ww.cell(r, 7, f"=ROUND(D{r}*E{r}*F{r},2)"); ww.cell(r, 8, note + "（使用者同意採用）")
    for j in range(1, 9): body(ww.cell(r, j), fmt={4: "0", 5: "0.00", 6: "0.000", 7: "0.00"}.get(j), align="left" if j in (3, 8) else "center")
    ww.row_dimensions[r].height = 30
rb1 = r
r += 1; ww.cell(r, 1, "每座小計 D16"); ww.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
ww.cell(r, 7, f'=SUMIF(B{rb0}:B{rb1},"D16",G{rb0}:G{rb1})'); W16 = r
for j in range(1, 9): body(ww.cell(r, j), fmt="0.00", bold=True, fill=TF)
r += 1; ww.cell(r, 1, "每座小計 D13"); ww.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
ww.cell(r, 7, f'=SUMIF(B{rb0}:B{rb1},"D13",G{rb0}:G{rb1})'); W13 = r
for j in range(1, 9): body(ww.cell(r, j), fmt="0.00", bold=True, fill=TF)
for rr in (W16, W13): ww.row_dimensions[rr].height = 30
for col, w in zip("ABCDEFGH", [12, 58, 40, 14, 12, 12, 14, 30]): ww.column_dimensions[col].width = w
ww.freeze_panes = "B2"; page(ww, "集水井數量計算")
WS_ = "集水井計算!"

# ======================================================================
# 工程數量計算表（11-2 格式：項次、項目、計算式、數量、單位）
# ======================================================================
wq = wb.create_sheet("工程數量計算表", 0)
H2 = ["項次", "工程項目", "計算式（詳圖號）", "計算值", "設計數量", "單位", "備註"]
wq.append(H2); style_header(wq, 1, len(H2))
# (項次, 項目, 計算式文字, Excel 公式（{代號}＝參數）, 取整方式, 單位, 備註)；項次 "#" 為大項
Q = [
    ("#", "一", "假設及拆除工程"),
    ("1", "既有暗溝打除（含廢料運棄）", "A 側 50×80 暗溝 113.43＋B 側 50×85 暗溝 112.38（詳 P-01）", "={RA}+{RB}", 2, "m", "斷面壁厚未知，運棄量【待補】"),
    ("2", "AC 路面切割", "A 側 111.53＋B 側 110.48（路內側開挖線，詳 P-01、S-01）", "={LA}+{LB}", 2, "m", "路外側貼既有溝外緣，不切割【待確認】"),
    ("3", "臨時擋土鋼軌樁 L=3 m 打設及拔除", "每側 2 排×(L÷1.0 取整＋1)：2×(112＋1)＋2×(111＋1)（詳 S-03）",
     "=2*(ROUNDUP({LA}/{PS},0)+1)+2*(ROUNDUP({LB}/{PS},0)+1)", "int", "支", "規格由廠商施工計畫檢算；以實做結算"),
    ("4", "臨時擋土背插鐵板", "每側 2 面×L×開挖深 1.53：2×(111.53＋110.48)×1.53（詳 S-03）", "=2*({LA}+{LB})*{PD}", 2, "m²", "厚度依施工計畫"),
    ("5", "臨時鋼管護欄（設置及拆除）", "各側開挖長＋兩端：A (112.91＋2×2.30)＋B (112.91＋2×2.30)（詳土石方數量計算表、S-03、S-04）",
     "=" + TA + "+2*{GW}+" + TB + "+2*{GW}", 2, "m", "只設路內側＋兩端（使用者 2026-11-06 確認）"),
    ("#", "二", "土方工程"),
    ("1", "構造物開挖（機械，詳土方計算）", "土石方數量計算表 挖方總計", "=" + EX, 2, "m³", "自然方"),
    ("2", "構造物回填（回填土，機械，詳土方計算）", "土石方數量計算表 填方總計", "=" + FL, 2, "m³", "回填材料（土／CLSM）【待確認】"),
    ("3", "餘土處理（運棄土資場）", "挖方－填方", "=" + EX + "-" + FL, 2, "m³", "自然方；運距【待補】"),
    ("#", "三", "結構工程"),
    ("1", "140 kgf/cm² 混凝土（墊層）", "溝身 (109.59＋108.54)×0.150＋集水井 4×0.361（詳 S-01、集水井計算）",
     "=({NA}+{NB})*{QB}+" + WS_ + "$G$3", 2, "m³", ""),
    ("2", "210 kgf/cm² 混凝土（箱涵式側溝溝體、集水井）", "溝身 (109.59＋108.54)×0.740＋集水井 4×2.27（詳 S-01、集水井計算）",
     "=({NA}+{NB})*{QC}+" + WS_ + "$G$2", 2, "m³", "含內角加腋（使用者確認採 0.74）"),
    ("3", "280 kgf/cm² 混凝土（場鑄緣石）", "(111.53＋110.48)×0.20×0.15（詳 S-01、S-02）", "=({LA}+{LB})*{QK}", 2, "m³", "使用者確認採 280"),
    ("4", "普通模板（溝體、集水井、墊層、緣石）",
     "溝身 (109.59＋108.54)×(4.40＋0.20)＋集水井 4×(17.00＋0.76)＋緣石 (111.53＋110.48)×0.30",
     "=({NA}+{NB})*({QF}+{QBF})+" + WS_ + "$G$4+" + WS_ + "$G$5+({LA}+{LB})*{QKF}", 2, "m²", ""),
    ("5", "鋼筋，竹節鋼筋 SD420W（D16）", "溝身 (109.59＋108.54)×37.44＋集水井 4×每座 D16（詳 S-01、集水井計算）",
     "=({NA}+{NB})*{R16}+" + WS_ + f"$G${W16}*{{NW}}", 2, "kg", "側溝 E 為 D13，列於第 6 項"),
    ("6", "鋼筋，竹節鋼筋 SD280W（D10、D13）",
     "溝身 (109.59＋108.54)×(42.41＋側溝 E 31.11)＋集水井 4×每座 D13＋緣石 (111.53＋110.48)×(3.78＋2.02)",
     "=({NA}+{NB})*({R13}+{RE})+" + WS_ + f"$G${W13}*{{NW}}+({{LA}}+{{LB}})*({{RK13}}+{{RK10}})", 2, "kg", "縱向筋詳配筋檢核表 v1.2 第 7 節"),
    ("7", "鋼筋合計", "第 5 項＋第 6 項，換算公噸", "=({F5})/1000", 3, "T", ""),
    ("8", "甲種預鑄溝蓋板 150×100×23（含熱浸鍍鋅格柵蓋及框）",
     "每側塊數 N＝L÷1.0 取整，甲種＝N÷5 取整：A 112÷5＋B 111÷5（詳 S-01、S-02）",
     "=ROUNDUP(ROUNDUP({LA}/{CBL},0)/{CBK},0)+ROUNDUP(ROUNDUP({LB}/{CBL},0)/{CBK},0)", "int", "塊", "每塊鋼筋 111.87 kg（S-02），含於蓋板單價"),
    ("9", "乙種預鑄溝蓋板 150×100×23",
     "每側 N－甲種：A (112－23)＋B (111－23)（詳 S-01、S-02）",
     "=ROUNDUP({LA}/{CBL},0)+ROUNDUP({LB}/{CBL},0)-E{PREV}", "int", "塊", "每塊鋼筋 82.47 kg（S-02），含於蓋板單價"),
    ("10", "側溝式箱涵集水井 內徑 150×150", "#AC1、#AC2、#BC1、#BC2（詳 P-01）", "={NW}", "int", "座", "本項為計數，材料已分列於本大項"),
    ("11", "塑膠包覆人孔踏步", "4 座×每座 5 個（詳 S-01-1、集水井計算）", "=" + WS_ + "$G$6", "int", "個", ""),
    ("12", "伸縮縫（含填縫材）", "每 10 m 一處：A 109.59÷10 取整＋B 108.54÷10 取整（詳 S-01）",
     "=ROUNDDOWN({NA}/{EJ},0)+ROUNDDOWN({NB}/{EJ},0)", "int", "處", "止水帶與填縫材規格【待確認】"),
    ("13", "新設側溝與既有排水銜接處理", "上、下游兩端各側 1 處（詳 P-01、G-02 四.5）", "=4", "int", "處", "接管方式與 RCP 管徑【待確認】"),
    ("#", "四", "路面修復工程"),
    ("1", "9.5 mm 密級配 AC 面層 t=5 cm（路面修復）", "(111.53＋110.48)×0.40（詳 S-01、S-01-1）", "=({LA}+{LB})*{ACW}", 2, "m²", "暫採 0.40 m 先編（使用者 2026-11-06）"),
    ("#", "五", "雜項工程"),
    ("1", "施工中交通維持（含標誌、拒馬、交通錐、警示燈、旗手）", "兩階段施工，詳 S-04、S-05", "=1", "int", "式", "數量依交維計畫"),
    ("2", "工程告示牌", "詳 S-06", "=1", "int", "面", ""),
    ("3", "職業安全衛生告示牌", "詳 S-06", "=1", "int", "面", ""),
    ("4", "施工期間臨時排水（維持既有側溝排水功能）", "詳 G-02 四.3", "=1", "int", "式", ""),
    ("5", "施工測量放樣", "詳 G-02 四.2", "=1", "int", "式", ""),
    ("6", "既有地下管線查證及保護", "詳 G-02 四.1", "=1", "int", "式", ""),
    ("7", "混凝土圓柱試體取樣及試驗", "依契約規定", "=1", "int", "式", ""),
    ("8", "鋼筋拉伸及彎曲試驗", "依契約規定", "=1", "int", "式", ""),
    ("9", "工地清理，竣工後清理", "詳 G-02 四.10", "=1", "int", "式", ""),
    ("10", "施工機具搬運費", "", "=1", "int", "趟", ""),
]
r = 1; ROWOF = {}; prev = None; big = None
for it in Q:
    r += 1
    if it[0] == "#":
        big = it[1]
        wq.cell(r, 1, it[1]); wq.cell(r, 2, it[2]); wq.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
        body(wq.cell(r, 1), bold=True, size=18, fill=SF); body(wq.cell(r, 2), align="left", bold=True, size=18, fill=SF)
        wq.row_dimensions[r].height = 32; continue
    no, name, txt, f, rnd, unit, note = it
    ROWOF[(big, no)] = r
    f = f.replace("{PREV}", str(prev)) if prev else f
    if "{F5}" in f: f = f.replace("({F5})", f"(E{ROWOF[('三', '5')]}+E{ROWOF[('三', '6')]})")
    wq.cell(r, 1, no); wq.cell(r, 2, name); wq.cell(r, 3, txt); wq.cell(r, 4, R(f))
    if rnd == "int": wq.cell(r, 5, f"=ROUND(D{r},0)"); fmt5 = "#,##0"
    else: wq.cell(r, 5, f"=ROUND(D{r},{rnd})"); fmt5 = "#,##0.00" if rnd == 2 else "#,##0.000"
    wq.cell(r, 6, unit); wq.cell(r, 7, note)
    for j in range(1, 8):
        body(wq.cell(r, j), fmt={4: "#,##0.000", 5: fmt5}.get(j), align="left" if j in (2, 3, 7) else ("right" if j in (4, 5) else "center"))
    L_ = max(len(name) / 18, len(txt) / 30, len(note) / 16)
    wq.row_dimensions[r].height = 30 if L_ <= 1 else (48 if L_ <= 2 else 68)
    prev = r
for col, w in zip("ABCDEFG", [8, 40, 64, 18, 20, 9, 34]): wq.column_dimensions[col].width = w
wq.freeze_panes = "C2"; page(wq, "工程數量計算表")

# ======================================================================
# 假設條件與待確認事項
# ======================================================================
wn = wb.create_sheet("假設與待確認")
wn.append(["項次", "事項", "本表採用", "影響工項"]); style_header(wn, 1, 4)
NOTE = [
    ("1", "S-01 每公尺溝體混凝土 0.740 m³ 含內角加腋（20×20×2）；X-01/X-02 斷面標示 0.70 m² 未含加腋；S-01 剖面又標「1:3 水泥砂漿整平（加腋）」",
     "採 0.740（加腋以混凝土計）；已確認（使用者 2026-11-06）", "三-2"),
    ("2", "S-01 溝體鋼筋 79.9 kg/m 只計橫向 A～D 筋，原未配縱向配力筋", "已補配 E D13 @25 內外兩層，31.11 kg/m（配筋檢核表 v1.2 第 7 節）；S-01 交繪圖員修正", "三-6"),
    ("3", "集水井鋼筋 A～G 只有長度與 @15，無支數；本表以兩向等距（外寬 190÷15＋1）估支數", "每座 D16、D13 見集水井計算；已確認（使用者 2026-11-06）", "三-5、三-6"),
    ("4", "集水井井壁側溝開口數：本表每座扣 1 處 110×100；下游出水口（接既有溝／RCP）未扣", "每座扣 1 處", "三-2、三-4"),
    ("5", "場鑄緣石強度：S-01、G-02 為 280 kgf/cm²，S-01-1 緣石配筋圖標 210", "採 280；已確認（使用者 2026-11-06）", "三-3"),
    ("6", "AC 路面修復寬度：S-01-1 引用 B20 標 40 cm；實際依道路挖掘許可修復範圍", "暫採 0.40 m 先編（使用者 2026-11-06）", "四-1、一-2"),
    ("7", "回填材料：橫斷面為一般回填土；S-03 註 4 拔樁空隙以砂或 CLSM 填實", "回填土，CLSM 未計", "二-2"),
    ("8", "既有暗溝打除只有長度，斷面壁厚未知，廢料運棄量未計", "按長度 m 計", "一-1"),
    ("9", "鋼軌樁規格（kg/m）、背插鐵板厚度、橫擋支撐由廠商施工計畫檢算", "樁以支、鐵板以 m² 計", "一-3、一-4"),
    ("10", "下游接既有溝及 RCP 管徑尚未定案", "銜接處理以 4 處 1 式計", "三-13"),
    ("11", "土方兩端集水井外緣斷面以最外井斷面外推 95 cm", "已確認（使用者 2026-11-06）；S-04 開挖施工區同步改 L≒112.9 m，交繪圖員修正", "二-1～二-3、五-1"),
    ("12", "數量為自然方、設計數量；單價、預算詳細表另案（範例 10-1～10-3）", "—", "全部"),
    ("13", "臨時鋼管護欄：詳圖 S-03、配置 S-04；路內側沿開挖線＋兩端封閉，路外側鄰房段不設（使用者 2026-11-06 確認）；規格詳 S-03（Ø48.6 鍍鋅鋼管 t=2.3、高 120、立柱 @200）",
     "路內側＋兩端，A、B 兩階段各設一次，以 m 計；已確認（使用者 2026-11-06）", "一-5"),
]
r = 1
for n_, a, b, c in NOTE:
    r += 1
    for j, v in enumerate((n_, a, b, c), 1):
        wn.cell(r, j, v); body(wn.cell(r, j), align="left" if j in (2, 3) else "center")
    wn.row_dimensions[r].height = 30 if len(a) < 40 else (48 if len(a) < 80 else 68)
for col, w in zip("ABCD", [8, 90, 36, 18]): wn.column_dimensions[col].width = w
wn.freeze_panes = "B2"; page(wn, "假設條件與待確認事項")

# ======================================================================
# 列高依文字量重算（固定列高，不用自動列高）：每格估行數＝顯示寬÷欄寬
# ======================================================================
import math
from openpyxl.utils import get_column_letter
def text_w(s, pt):
    """字元顯示寬（Excel 欄寬單位）：全形字約 2×pt/11，半形約 1.1×pt/11"""
    return sum((2.15 if ord(ch) > 0x2E80 else 1.15) * pt / 11.0 for ch in s)
def refit(ws):
    merged = {}
    for mr in ws.merged_cells.ranges:
        w = sum(ws.column_dimensions[get_column_letter(c)].width or 8.43 for c in range(mr.min_col, mr.max_col + 1))
        merged[(mr.min_row, mr.min_col)] = w
        for rr in range(mr.min_row, mr.max_row + 1):
            for cc in range(mr.min_col, mr.max_col + 1):
                if (rr, cc) != (mr.min_row, mr.min_col): merged[(rr, cc)] = -1
    for row in ws.iter_rows():
        need = 1; pt = 14
        for c in row:
            if c.value is None or merged.get((c.row, c.column)) == -1: continue
            pt = c.font.size or 14
            w = merged.get((c.row, c.column)) or (ws.column_dimensions[get_column_letter(c.column)].width or 8.43)
            s = c.value if isinstance(c.value, str) and not c.value.startswith("=") else ("0" * 12)
            lines = sum(max(1, math.ceil(text_w(part, pt) / max(w - 3.0, 1))) for part in s.split("\n"))
            need = max(need, lines)
        ws.row_dimensions[row[0].row].height = max(30, round(need * pt * 1.45 + 8))
for ws_ in wb.worksheets: refit(ws_)

wb.save(OUT)
print(OUT)
