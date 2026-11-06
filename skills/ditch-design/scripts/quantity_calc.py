"""數量計算書（ditch-design，由 P33 quantity_calc 一般化）：參數、土石方數量計算表（平均斷面法）、集水井計算、工程數量計算表、假設與待確認。
格式依業主範例 11-1、11-2；xlsx 保留公式，所有數量由「參數」工作表連結計算；PDF 由 Excel 重算後匯出（qty-budget 的 quantity_calc_pdf.ps1）。
案件值：
- 工項、參數、計算式文字、假設表：qty.items_file（templates/qty_items.<案>.json）；參數值 "auto" 由本程式算：
  LA/LB 側溝長（定線）、NA/NB 溝身淨長（斷面積 csv 交接面樁距）、RA/RB 拆除長（側溝長＋兩端井外寬）、NW 井數、WI/WT 井內寬與壁厚、PS/PL 樁距與樁長。
- 斷面積：work_dir/section_areas.csv（cross_sections.py）。工程名稱、檔名前綴與版次：設定檔。
用法：python quantity_calc.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
"""
import sys, os, csv, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.page import PageMargins

CFG = dd.CFG; CODE = dd.CODE; stamp = dd.stamp
AREAS = dd.work("section_areas.csv")
VER = dd.ver("quantity")
PROJ = CFG["title_block"]["project"]
OUT = os.path.join(dd.OUT, f"{dd.PRE}{stamp}_{CODE}_數量計算書_{VER}.xlsx")


def tpl(fn):
    """案件資料檔：先找本 SKILL templates/，再找 data_dir"""
    for d in (os.path.join(os.path.dirname(dd.HERE), "templates"), dd.DATA):
        if os.path.exists(os.path.join(d, fn)): return os.path.join(d, fn)
    raise SystemExit(f"找不到案件資料檔 {fn}")


IT = json.load(open(tpl(CFG["qty"]["items_file"]), encoding="utf-8-sig"))
rows = list(csv.DictReader(open(AREAS, encoding="utf-8-sig")))
import plan_base as PB
LEN = {k: float(PB.np.hypot(*(PB.SIDES[k][0][1] - PB.SIDES[k][0][0]))) for k in PB.KEYS}


def auto_value(code):
    """參數 "auto"：依設定檔、定線、斷面積計算（與 P-01、X 圖同源）"""
    side = code[1] if len(code) == 2 and code[1] in LEN else None
    if code[0] == "L" and side: return round(LEN[side], 2)
    if code[0] == "R" and side: return round(LEN[side] + 2 * PB.HALF_W, 2)
    if code[0] == "N" and side and code != "NW":
        js = sorted(float(x["側溝樁距m"]) for x in rows if x["側"] == side and x["類別"] == "交接面")
        return f"={js[-1]:.2f}-{js[0]:.2f}"
    return {"NW": len(dd.WELLS), "WI": dd.P_["well_in"], "WT": dd.P_["well_wall"], "PS": dd.PILE_SP, "PL": dd.PILE_L}[code]


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
    ws.oddFooter.center.text = f"{dd.COMPANY}　第 &P 頁／共 &N 頁"; ws.oddFooter.center.size = 12

wb = Workbook()

# ======================================================================
# 參數（所有計算式的來源；每項附圖號出處）
# ======================================================================
wp = wb.active; wp.title = "參數"
P = {}   # 名稱 -> 儲存格位址（參數!$C$n）
PARAMS = []
for p in IT["params"]:
    if p[0] == "#": PARAMS.append(tuple(p)); continue
    k, name, val, unit, src_ = p[:5]
    PARAMS.append((k, name, auto_value(k) if val == "auto" else val, unit, src_))
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
we = wb.create_sheet("土石方數量計算表")
NL = chr(10)
H1 = [NL.join(h.split("|")) for h in ["側別", "中心線|樁號", "側溝|樁距|m", "斷面|類別", "距離|m", "挖方|斷面積|m²", "挖方|平均|斷面積|m²", "挖方|土方量|m³",
      "填方|斷面積|m²", "填方|平均|斷面積|m²", "填方|土方量|m³", "附註"]]
we.append(H1); style_header(we, 1, len(H1), 120)
r = 1; side_tot = {}
for side in PB.KEYS:
    nm = IT.get("side_names", {}).get(side, dd.DITCH[side].get("name", side))
    r += 1; we.cell(r, 1, f"{nm}　新設箱涵式側溝（L＝{LEN[side]:.2f} m）")
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
we.cell(r, 8, "=" + "+".join(f"H{side_tot[k]}" for k in PB.KEYS)); we.cell(r, 11, "=" + "+".join(f"K{side_tot[k]}" for k in PB.KEYS))
we.cell(r, 12, "自然方；未換算鬆方")
for j in range(1, 13): body(we.cell(r, j), fmt="0.00", bold=True, fill=SF, align="left" if j == 12 else "center")
we.row_dimensions[r].height = 34
EW_TOT = r
r += 2
notes_e = IT["earth_notes"]
for t in notes_e:
    we.cell(r, 1, t); we.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12)
    we.cell(r, 1).font = Font(name=FN, size=14, color=DK); we.cell(r, 1).alignment = Alignment(wrap_text=True, vertical="center")
    we.row_dimensions[r].height = 30 if len(t) < 70 else 48; r += 1
for col, w in zip("ABCDEFGHIJKL", [9, 16, 13, 14, 12, 14, 14, 15, 14, 14, 15, 36]): we.column_dimensions[col].width = w
we.freeze_panes = "B2"; page(we, "土石方數量計算表")
TA = f"土石方數量計算表!$E${side_tot[PB.KEYS[0]]}"; TB = f"土石方數量計算表!$E${side_tot[PB.KEYS[-1]]}"
EX = f"土石方數量計算表!$H${EW_TOT}"; FL = f"土石方數量計算表!$K${EW_TOT}"

# ======================================================================
# 集水井計算（個別幾何＋鋼筋）
# ======================================================================
ww = wb.create_sheet("集水井計算")
ww.append(["項次", "項目", "計算式", "每座數量", "單位", "座數", "合計", "出處"])
style_header(ww, 1, 8)
WBAR = [tuple(x) for x in IT["wbar"]]
items_w = [tuple(x) for x in IT["well_items"]]
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
TOK = {"{@TA}": TA, "{@TB}": TB, "{@EX}": EX, "{@FL}": FL, "{@WS}": WS_, "{@W16}": str(W16), "{@W13}": str(W13)}
def tok(f):
    for a, b in TOK.items(): f = f.replace(a, b)
    return f
Q = [tuple(x) if x[0] == "#" else tuple(x[:3]) + (tok(x[3]),) + tuple(x[4:]) for x in IT["q"]]
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
NOTE = [tuple(x) for x in IT["notes"]]
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
