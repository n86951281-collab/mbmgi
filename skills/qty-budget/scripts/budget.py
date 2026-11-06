"""P33 預算書（預算總表 10-1、預算詳細表 10-2、單價分析表 10-3），格式依業主範例（PCCES 壹／貳 層級）。
數量：讀數量計算書 xlsx 的 Excel 重算值（--qty 指定檔案）。
單價：臺北市 112 年度工程預算參考單價 × 物價調整係數 K；臺北市沒有的項目採範例（苗栗 115 年）單價或單價分析，並標【待確認】。
輸出 xlsx（保留公式），PDF 由 Excel 重算後匯出（quantity_calc_pdf.ps1）。
用法：python -I budget.py --case <案件資料夾> --qty <數量計算書.xlsx> --stamp YYYYMMDD_HHMM
參考實作（P33 v1.0，業主範例 10-1～10-3 版面、臺北市單價×K）；有公司舊案 PCCES 範本時改用 budget_pcces.py。
"""
import sys, os, json, math, datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.page import PageMargins
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
CASE = os.path.abspath(arg("--case", HERE))
CFG = json.load(open(os.path.join(CASE, "case_config.json"), encoding="utf-8-sig"))
CODE = CFG.get("case_code", "P33")
stamp = arg("--stamp", datetime.datetime.now().strftime("%Y%m%d_%H%M"))
QTY = arg("--qty")
if not QTY: sys.exit("請用 --qty 指定數量計算書 xlsx（Excel 重算過的版本）")
VER = "v1.0"
PROJ = CFG["title_block"]["project"]; AGENCY = CFG["title_block"]["agency"]
OUT = os.path.join(CFG["out_dir"], f"{CFG['file_prefix']}{stamp}_{CODE}_預算書_{VER}.xlsx")

# ---------------------------------------------------------------- 數量（數量計算書 Excel 重算值）
qwb = load_workbook(QTY, data_only=True); qs = qwb["工程數量計算表"]
QV = {}; big = None
for row in qs.iter_rows(min_row=2, values_only=True):
    no, name = row[0], row[1]
    if no in ("一", "二", "三", "四", "五"): big = no; continue
    if no is None or name is None: continue
    QV[f"{big}-{no}"] = (name, row[4], row[5])
QVER = os.path.basename(QTY).split("_數量計算書_")[-1].replace(".xlsx", "")
def q(k): return QV[k][1]

# ---------------------------------------------------------------- 樣式
FN = "微軟正黑體"; DK = "1F2D3A"
HF = PatternFill("solid", fgColor="3E5C76"); SF = PatternFill("solid", fgColor="D8DEE4"); TF = PatternFill("solid", fgColor="ECEFF2")
thin = Side(style="thin", color="7A8A99"); BD = Border(left=thin, right=thin, top=thin, bottom=thin)
def hdr(ws, row, ncol):
    for j in range(1, ncol + 1):
        c = ws.cell(row, j); c.font = Font(name=FN, size=25, bold=True, color="FFFFFF"); c.fill = HF; c.border = BD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
def body(c, fmt=None, align="center", bold=False, size=14, fill=None):
    c.font = Font(name=FN, size=size, bold=bold, color=DK); c.border = BD
    c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
def page(ws, title, rows="1:1", landscape=True):
    ws.print_title_rows = rows
    ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.8, bottom=0.7, header=0.3, footer=0.3)
    ws.oddHeader.center.text = f"{PROJ}　{title}"; ws.oddHeader.center.size = 12
    ws.oddFooter.center.text = "辰璟工程技術顧問有限公司　第 &P 頁／共 &N 頁"; ws.oddFooter.center.size = 12
def text_w(s, pt): return sum((2.15 if ord(ch) > 0x2E80 else 1.15) * pt / 11.0 for ch in s)
def refit(ws, skip=()):
    merged = {}
    for mr in ws.merged_cells.ranges:
        w = sum(ws.column_dimensions[get_column_letter(c)].width or 8.43 for c in range(mr.min_col, mr.max_col + 1))
        merged[(mr.min_row, mr.min_col)] = w
        for rr in range(mr.min_row, mr.max_row + 1):
            for cc in range(mr.min_col, mr.max_col + 1):
                if (rr, cc) != (mr.min_row, mr.min_col): merged[(rr, cc)] = -1
    for row in ws.iter_rows():
        if row[0].row in skip: continue
        need = 1; pt = 14
        for c in row:
            if c.value is None or merged.get((c.row, c.column)) == -1: continue
            pt = c.font.size or 14
            w = merged.get((c.row, c.column)) or (ws.column_dimensions[get_column_letter(c.column)].width or 8.43)
            s = c.value if isinstance(c.value, str) and not c.value.startswith("=") else "0" * 12
            need = max(need, sum(max(1, math.ceil(text_w(p, pt) / max(w - 3.0, 1))) for p in s.split("\n")))
        ws.row_dimensions[row[0].row].height = max(30, round(need * pt * 1.45 + 8))

wb = Workbook()

# ======================================================================
# 單價依據：每一個基本單價一列（出處、是否套 K）
# ======================================================================
wsrc = wb.active; wsrc.title = "單價依據"
TP = "臺北市112年度工程預算參考單價"; EX = "範例 10-2（苗栗 115 年）"
SRC = [
    # (代號, 名稱, 單位, 原單價, 套K, 編碼, 出處)
    ("K", "物價調整係數 K＝115年6月營造工程物價總指數 119.16÷111年 107.51", "－", "=119.16/107.51", 0, "", "主計總處 CCI（110年=100），臺中市政府採購網轉載；111年取臺北市年平均【待確認】"),
    ("RC_DEM", "機械拆除，鋼筋混凝土，含運費", "M3", 1788.91, 1, "0222010E13", f"{TP} 組合單價 第8頁 項次2"),
    ("WASTE", "餘方自行處理（房屋廢方，含水土保持）", "M3", 957.96, 1, "02323PWD0A001", f"{TP} 組合單價 第8頁 項次22"),
    ("EXC", "開挖機 0.70～0.79 m³", "時", 1500.00, 1, "E000004407001", f"{TP} 基本單價 第1頁 項次7"),
    ("LAB", "普通工", "時", 280.00, 1, "L000006000001", f"{TP} 基本單價 第1頁 項次4"),
    ("SKL", "其他技術工", "時", 375.00, 1, "L000005000001", f"{TP} 基本單價 第1頁 項次3"),
    ("FILL", "構造物回填，回填及夯實", "C.M3", 320.74, 1, "023174000A", f"{TP} 組合單價 第8頁 項次15"),
    ("SPOIL", "餘方自行處理（含水土保持），總重15t傾卸貨車", "B.M3", 721.06, 1, "023234004A", f"{TP} 組合單價 第8頁 項次20"),
    ("C140", "結構用混凝土，預拌，140kgf/cm2", "M3", 2795.83, 1, "0331023003", f"{TP} 組合單價 第9頁 項次24"),
    ("C210", "結構用混凝土，預拌，210kgf/cm2", "M3", 2991.53, 1, "0331025003", f"{TP} 組合單價 第9頁 項次26"),
    ("C280", "結構用混凝土，預拌，280kgf/cm2", "M3", 3314.13, 1, "0331027003", f"{TP} 組合單價 第9頁 項次28"),
    ("FORM3", "普通模板，丙種（U型溝、集水井、排水箱涵）", "M2", 398.61, 1, "0311011302", f"{TP} 組合單價 第9頁 項次32"),
    ("FORM2", "普通模板，乙種（預鑄蓋板用）", "M2", 631.18, 1, "0311011202", f"{TP} 組合單價 第9頁 項次31"),
    ("SD280", "鋼筋，SD280", "T", 35878.61, 1, "0321030005", f"{TP} 組合單價 第8頁 項次16"),
    ("SD420", "鋼筋，SD420", "T", 37975.69, 1, "0321050005", f"{TP} 組合單價 第8頁 項次17"),
    ("AC95", "瀝青混凝土舖面，粗粒料9.5mm，黏度AC(1)-20", "M3", 7300.95, 1, "0274205303", f"{TP} 組合單價 第8頁 項次9"),
    ("ACLAY", "瀝青混凝土舖面，鋪築及滾壓", "M3", 352.30, 1, "02742000A3", f"{TP} 組合單價 第8頁 項次7"),
    ("TACK", "瀝青黏層 RC-70", "M2", 15.65, 1, "0274711002", f"{TP} 組合單價 第8頁 項次13"),
    ("BARR", "活動型拒馬，長1.2m", "座", 1230.75, 1, "0155630A0A", f"{TP} 組合單價 第9頁 項次38"),
    ("CONE", "交通錐，高70cm", "個", 212.90, 1, "0155642007", f"{TP} 組合單價 第9頁 項次39"),
    ("LAMP", "施工警告燈號", "座", 1666.11, 1, "015568000A", f"{TP} 組合單價 第9頁 項次40"),
    ("SIGN", "施工標誌", "座", 2199.58, 1, "015566000A", f"{TP} 工程單價 第13頁 項次88"),
    ("PILE", "臨時擋土設施(鋼軌樁打拔50kg/m,L=6m,間隔100cm)", "支", 2126, 0, "0225526121D", f"{EX} 壹.一.10（本案 L=3m，沿用 L=6m 單價）【待確認】"),
    ("PLATE", "臨時擋土設施，鋼襯版（含打拔費）", "M2", 1307, 0, "CC40002", f"{EX} 壹.一.11"),
    ("PILEMOV", "搬運費，臨時擋土設施材料搬運費(來回計1次)", "次", 10455, 0, "012714000A1", f"{EX} 壹.一.15"),
    ("MOB", "施工機具搬運費（來回算一趟）", "趟", 10455, 0, "3450502200159", f"{EX} 壹.二.23"),
    ("HEAVY", "重機械拖運費(來回各1次合計算1趟)", "趟", 17425, 0, "1011010", f"{EX} 壹.一.6"),
    ("DRAIN", "擋排水費(以長度計價)", "M", 436, 0, "02600C1004012", f"{EX} 壹.二.5"),
    ("SURV", "施工測量放樣", "案", 6970, 0, "01725C4005", f"{EX} 壹.二.22"),
    ("CLEAN", "工地清理，竣工後清理", "案", 5227, 0, "SWCB0200002", f"{EX} 壹.二.6"),
    ("BOARD", "工程告示牌", "面", 3485, 0, "03053C3024", f"{EX} 壹.二.1"),
    ("OSHB", "職業安全衛生告示牌", "面", 3485, 0, "015831000ALG", f"{EX} 壹.二.2"),
    ("CORE", "混凝土鑽心試體取樣及試驗費", "組", 5227, 0, "03053C4105", f"{EX} 壹.二.16"),
    ("TENS", "竹節鋼筋拉伸試驗", "支", 871, 0, "01450A1B3H", f"{EX} 壹.二.19"),
    ("BEND", "竹節鋼筋抗彎試驗", "支", 871, 0, "01450A1B4H", f"{EX} 壹.二.20"),
    ("PIPEG", "護欄，鋼管護欄", "M", 1568, 0, "01556C2006", f"{EX} 壹.三.10【待確認訪價】"),
    ("OSHMAN", "職安人員", "人月", 10455, 0, "L000007000007", f"{EX} 壹.三.11"),
    ("LADDER", "人員安全上下設備費", "式", 13069, 0, "SWCB0056", f"{EX} 壹.三.7"),
]
wsrc.append(["代號", "名稱", "單位", "原單價", "套 K", "採用單價", "編碼", "出處"]); hdr(wsrc, 1, 8)
U = {}
for i, (k, nm, un, p, kk, code, src) in enumerate(SRC, 2):
    U[k] = f"單價依據!$F${i}"
    wsrc.cell(i, 1, k); wsrc.cell(i, 2, nm); wsrc.cell(i, 3, un); wsrc.cell(i, 4, p); wsrc.cell(i, 5, "是" if kk else "否")
    wsrc.cell(i, 6, "=D2" if k == "K" else (f"=ROUND(D{i}*$F$2,2)" if kk else f"=D{i}")); wsrc.cell(i, 7, code); wsrc.cell(i, 8, src)
    for j in range(1, 9):
        body(wsrc.cell(i, j), fmt={4: "#,##0.00", 6: "#,##0.00"}.get(j) if k != "K" else {4: "0.0000", 6: "0.0000"}.get(j),
             align="left" if j in (2, 7, 8) else ("right" if j in (4, 6) else "center"))
for col, w in zip("ABCDEFGH", [11, 50, 8, 14, 8, 14, 18, 60]): wsrc.column_dimensions[col].width = w
wsrc.freeze_panes = "B2"; page(wsrc, "單價依據")
def P(k): return U[k]

# ======================================================================
# 單價分析表（10-3 格式：每項一區塊）
# ======================================================================
wa = wb.create_sheet("單價分析表")
wa.append(["工料名稱", "單位", "數量", "單價", "複價", "編碼（備註）"]); hdr(wa, 1, 6)
AN = {}   # 項次 -> 每單位單價儲存格
def analysis(no, name, unit, code, lines, note=""):
    """lines: (工料名稱, 單位, 數量, 單價公式或數值, 類別 人/機/材/雜, 編碼)"""
    r = wa.max_row + 1
    wa.cell(r, 1, f"{no}　{name}　單位：{unit}　計價代碼：{code}"); wa.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    body(wa.cell(r, 1), align="left", bold=True, size=18, fill=SF)
    r0 = r + 1
    for nm, un, qn, pr, cat, cd in lines:
        r += 1
        wa.cell(r, 1, nm); wa.cell(r, 2, un); wa.cell(r, 3, qn); wa.cell(r, 4, pr); wa.cell(r, 5, f"=ROUND(C{r}*D{r},2)"); wa.cell(r, 6, f"{cat}｜{cd}")
        for j in range(1, 7): body(wa.cell(r, j), fmt={3: "#,##0.000", 4: "#,##0.00", 5: "#,##0.00"}.get(j), align="left" if j in (1, 6) else ("right" if j in (3, 4, 5) else "center"))
    r1 = r
    r += 1; wa.cell(r, 1, "合計"); wa.cell(r, 2, unit); wa.cell(r, 3, 1); wa.cell(r, 5, f"=SUM(E{r0}:E{r1})")
    wa.cell(r, 6, "人工 " + "、".join([]) if False else f'="人 "&TEXT(SUMIF(F{r0}:F{r1},"人*",E{r0}:E{r1}),"#,##0.00")&"／機 "&TEXT(SUMIF(F{r0}:F{r1},"機*",E{r0}:E{r1}),"#,##0.00")&"／材 "&TEXT(SUMIF(F{r0}:F{r1},"材*",E{r0}:E{r1}),"#,##0.00")&"／雜 "&TEXT(SUMIF(F{r0}:F{r1},"雜*",E{r0}:E{r1}),"#,##0.00")')
    for j in range(1, 7): body(wa.cell(r, j), fmt={3: "#,##0.000", 5: "#,##0.00"}.get(j), bold=True, fill=TF, align="left" if j == 6 else ("right" if j in (3, 5) else "center"))
    r += 1; wa.cell(r, 1, f"每 {unit} 單價計（取整數）"); wa.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    wa.cell(r, 5, f"=ROUND(E{r-1},0)"); wa.cell(r, 6, note)
    for j in range(1, 7): body(wa.cell(r, j), fmt="#,##0" if j == 5 else None, bold=True, fill=TF, align="left" if j in (1, 6) else "right")
    AN[no] = f"單價分析表!$E${r}"
    return AN[no]

A = {}
A["DEM"] = analysis("A-1", "既有暗溝打除（含廢料運棄）", "M", "0222010E13,#", [
    ("機械拆除，鋼筋混凝土，含運費（每公尺 0.49 m³）", "M3", 0.49, f"={P('RC_DEM')}", "雜", "0222010E13"),
    ("餘方自行處理（房屋廢方）", "M3", 0.49, f"={P('WASTE')}", "雜", "02323PWD0A001")],
    "每公尺量：50×80 暗溝外框 80×110－內 50×80＝0.48；50×85＝0.495，取 0.49 m³（壁厚 15 cm 假設）【待確認】")
A["CUT"] = analysis("A-2", "AC 路面切割", "M", "#", [
    ("機具操作技術工（切割機）", "時", 0.05, f"={P('SKL')}", "人", "L000005100001"),
    ("切割機具及鑽石刀片損耗", "式", 1, 30, "機", "#"),
    ("零星材料及機具損耗", "式", 1, 3, "雜", "W0127170104")], "臺北市無此項，依工率分析【待確認訪價】")
A["EXC"] = analysis("A-3", "構造物開挖，機械（含擋土樁間修整）", "M3", "02316#", [
    ("開挖機 0.70～0.79 m³（工率 25 m³/時）", "時", 0.04, f"={P('EXC')}", "機", "E000004407001"),
    ("普通工（樁間修整、清底）", "時", 0.10, f"={P('LAB')}", "人", "L000006000001"),
    ("零星材料及機具損耗（5%）", "式", 1, f"=ROUND(0.05*(0.04*{P('EXC')}+0.1*{P('LAB')}),2)", "雜", "W0127170104")],
    "臺北市無「構造物開挖，機械」，依工率分析【待確認】")
A["COVA"] = analysis("A-4", "甲種預鑄溝蓋板 150×100×23（含熱浸鍍鋅格柵蓋及框）", "塊", "#", [
    ("280 kgf/cm² 混凝土（1.50×1.00×0.23，扣格柵開口 0.73×0.63×0.23）", "M3", round(1.5 * 1.0 * 0.23 - 0.73 * 0.63 * 0.23, 3), f"={P('C280')}", "材", "0331027003"),
    ("鋼筋 SD420（D16、D19；S-02 甲種 111.87 kg，取 SD420）", "T", 0.112, f"={P('SD420')}", "材", "0321050005"),
    ("乙種模板（預鑄場）", "M2", round(2 * (1.5 + 1.0) * 0.23 + 2 * (0.73 + 0.63) * 0.23, 3), f"={P('FORM2')}", "材", "0311011202"),
    ("熱浸鍍鋅格柵蓋及框（73×63）", "組", 1, 4500, "材", "#【待確認訪價】"),
    ("吊裝及安放（技術工＋普通工各 0.5 時）", "式", 1, f"=ROUND(0.5*{P('SKL')}+0.5*{P('LAB')},2)", "人", "#")], "S-02 甲種鋼筋表")
A["COVB"] = analysis("A-5", "乙種預鑄溝蓋板 150×100×23", "塊", "#", [
    ("280 kgf/cm² 混凝土（1.50×1.00×0.23）", "M3", 0.345, f"={P('C280')}", "材", "0331027003"),
    ("鋼筋（S-02 乙種 82.47 kg：D16 61.31、D13 13.42、D19 7.74；取 SD420）", "T", 0.082, f"={P('SD420')}", "材", "0321050005"),
    ("乙種模板（預鑄場）", "M2", round(2 * (1.5 + 1.0) * 0.23, 3), f"={P('FORM2')}", "材", "0311011202"),
    ("吊裝及安放（技術工＋普通工各 0.5 時）", "式", 1, f"=ROUND(0.5*{P('SKL')}+0.5*{P('LAB')},2)", "人", "#")], "S-02 乙種鋼筋表")
A["AC"] = analysis("A-6", "9.5 mm 密級配 AC 面層 t=5 cm（路面修復）", "M2", "0274205303,#", [
    ("瀝青混凝土，粗粒料 9.5 mm（0.05 m³/m²）", "M3", 0.05, f"={P('AC95')}", "材", "0274205303"),
    ("瀝青混凝土鋪築及滾壓", "M3", 0.05, f"={P('ACLAY')}", "機", "02742000A3"),
    ("瀝青黏層 RC-70", "M2", 1, f"={P('TACK')}", "材", "0274711002")], "S-01：AC 面層 t=5")
A["STEP"] = analysis("A-7", "塑膠包覆人孔踏步", "個", "#", [
    ("塑膠包覆人孔踏步（含植入）", "個", 1, 350, "材", "#【待確認訪價】"),
    ("技術工安裝", "時", 0.2, f"={P('SKL')}", "人", "L000005000001")], "S-01-1 附註 4")
A["EJ"] = analysis("A-8", "伸縮縫（含填縫材）", "處", "#", [
    ("瀝青纖維板填縫材 t=1 cm（溝體斷面周長 2×1.2＋1.5＝3.9 m×寬 0.2 m）", "M2", 0.78, 650, "材", "#【待確認訪價】"),
    ("PU 止水填縫膠（內側周長 2×1.0＋1.1＝3.1 m）", "M", 3.1, 180, "材", "#【待確認訪價】"),
    ("技術工", "時", 1, f"={P('SKL')}", "人", "L000005000001")], "S-01 註 2 每 10 m 一處")
A["JOIN"] = analysis("A-9", "新設側溝與既有排水銜接處理", "處", "#", [
    ("210 kgf/cm² 混凝土（封口及接頭修補）", "M3", 0.5, f"={P('C210')}", "材", "0331025003"),
    ("模板丙種", "M2", 3, f"={P('FORM3')}", "材", "0311011302"),
    ("技術工＋普通工各 4 時", "式", 1, f"=ROUND(4*{P('SKL')}+4*{P('LAB')},2)", "人", "#")], "接管方式與 RCP 管徑【待確認】")
A["TRAF"] = analysis("A-10", "施工中交通維持（S-04、S-05）", "式", "01556#", [
    ("活動型拒馬，長1.2m（每階段 2 座，兩階段共用）", "座", 4, f"={P('BARR')}", "材", "0155630A0A"),
    ("交通錐，高70cm（每階段約 25 個，兩階段共用）", "個", 30, f"={P('CONE')}", "材", "0155642007"),
    ("施工警告燈號", "座", 4, f"={P('LAMP')}", "材", "015568000A"),
    ("施工標誌", "座", 2, f"={P('SIGN')}", "材", "015566000A"),
    ("交通指揮人員（旗手 2 人×40 工作天×8 時）", "時", 640, f"={P('LAB')}", "人", "L000006000001")],
    "數量依 S-04 示意圖估；工期 40 工作天【待確認】")
A["TEST"] = analysis("A-11", "鋼筋拉伸及彎曲試驗", "式", "01450#", [
    ("竹節鋼筋拉伸試驗（D13、D16 各 2 支）", "支", 4, f"={P('TENS')}", "雜", "01450A1B3H"),
    ("竹節鋼筋抗彎試驗（D13、D16 各 2 支）", "支", 4, f"={P('BEND')}", "雜", "01450A1B4H")], "抽驗頻率依契約【待確認】")
A["CONC"] = analysis("A-12", "混凝土試體取樣及試驗", "式", "03053#", [
    ("混凝土試體取樣及試驗（210：約 170 m³，每 100 m³ 1 組，取 2 組；140、280 各 1 組）", "組", 4, f"={P('CORE')}", "雜", "03053C4105")], "依契約規定【待確認】")
A["DRN"] = analysis("A-13", "施工期間臨時排水（維持既有側溝排水功能）", "式", "02600#", [
    ("擋排水費（以長度計價，A 111.53＋B 110.48）", "M", 222.01, f"={P('DRAIN')}", "雜", "02600C1004012")], "G-02 四.3")
for col, w in zip("ABCDEF", [60, 8, 13, 14, 18, 42]): wa.column_dimensions[col].width = w
wa.freeze_panes = "A2"; page(wa, "單價分析表")

# ======================================================================
# 預算詳細表（10-2）
# ======================================================================
wd = wb.create_sheet("預算詳細表", 0)
wd.append(["項次", "項目及說明", "單位", "數量", "單價", "複價", "編碼（備註）"]); hdr(wd, 1, 7)
U0 = lambda k: f"=ROUND({P(k)},0)"
AU = lambda k: f"={A[k]}"
D = [
    ("H1", "壹", "發包工程費"),
    ("H2", "壹.一", "施工費用（工作費＋材料費）"),
    ("壹.一.1", "既有暗溝打除（含廢料運棄）", "M", q("一-1"), AU("DEM"), "0222010E13,#，詳單價分析表 A-1", "一-1"),
    ("壹.一.2", "AC 路面切割", "M", q("一-2"), AU("CUT"), "#，詳單價分析表 A-2", "一-2"),
    ("壹.一.3", "臨時擋土設施（鋼軌樁打拔 50kg/m，L=3m，間隔 100cm）", "支", q("一-3"), U0("PILE"), "0225526121D,#（含打拔費）", "一-3"),
    ("壹.一.4", "臨時擋土設施，鋼襯版（背插鐵板）", "M2", q("一-4"), U0("PLATE"), "CC40002,#（含打拔費）", "一-4"),
    ("壹.一.5", "搬運費，臨時擋土設施材料搬運費（來回計 1 次，兩階段）", "次", 2, U0("PILEMOV"), "012714000A1", "S-04 兩階段"),
    ("壹.一.6", "構造物開挖，機械", "M3", q("二-1"), AU("EXC"), "02316#，詳單價分析表 A-3", "二-1"),
    ("壹.一.7", "構造物回填，回填及夯實", "M3", q("二-2"), U0("FILL"), "023174000A", "二-2"),
    ("壹.一.8", "餘方自行處理（含水土保持），總重 15t 傾卸貨車", "M3", q("二-3"), U0("SPOIL"), "023234004A，運距及收容費【待確認】", "二-3"),
    ("壹.一.9", "結構用混凝土，預拌，140kgf/cm2（墊層）", "M3", q("三-1"), U0("C140"), "0331023003", "三-1"),
    ("壹.一.10", "結構用混凝土，預拌，210kgf/cm2（溝體、集水井）", "M3", q("三-2"), U0("C210"), "0331025003", "三-2"),
    ("壹.一.11", "結構用混凝土，預拌，280kgf/cm2（場鑄緣石）", "M3", q("三-3"), U0("C280"), "0331027003", "三-3"),
    ("壹.一.12", "普通模板，丙種（U型溝、集水井）", "M2", q("三-4"), U0("FORM3"), "0311011302", "三-4"),
    ("壹.一.13", "鋼筋，SD420（D16）", "T", f"=ROUND({q('三-5')}/1000,3)", U0("SD420"), "0321050005", "三-5（kg÷1000）"),
    ("壹.一.14", "鋼筋，SD280（D10、D13）", "T", f"=ROUND({q('三-6')}/1000,3)", U0("SD280"), "0321030005", "三-6（kg÷1000）"),
    ("壹.一.15", "甲種預鑄溝蓋板 150×100×23（含熱浸鍍鋅格柵蓋及框）", "塊", q("三-8"), AU("COVA"), "#，詳單價分析表 A-4", "三-8"),
    ("壹.一.16", "乙種預鑄溝蓋板 150×100×23", "塊", q("三-9"), AU("COVB"), "#，詳單價分析表 A-5", "三-9"),
    ("壹.一.17", "塑膠包覆人孔踏步", "個", q("三-11"), AU("STEP"), "#，詳單價分析表 A-7", "三-11"),
    ("壹.一.18", "伸縮縫（含填縫材）", "處", q("三-12"), AU("EJ"), "#，詳單價分析表 A-8", "三-12"),
    ("壹.一.19", "新設側溝與既有排水銜接處理", "處", q("三-13"), AU("JOIN"), "#，詳單價分析表 A-9", "三-13"),
    ("壹.一.20", "9.5mm 密級配 AC 面層 t=5cm（路面修復）", "M2", q("四-1"), AU("AC"), "0274205303,#，詳單價分析表 A-6", "四-1"),
    ("壹.一.21", "施工中交通維持", "式", 1, AU("TRAF"), "01556#，詳單價分析表 A-10", "五-1"),
    ("壹.一.22", "重機械拖運費（來回各 1 次合計算 1 趟）", "趟", 1, U0("HEAVY"), "1011010", "—"),
    ("H2", "壹.二", "雜項工程"),
    ("壹.二.1", "工程告示牌", "面", q("五-2"), U0("BOARD"), "03053C3024，可重複使用", "五-2"),
    ("壹.二.2", "施工期間臨時排水（擋排水費）", "式", q("五-4"), AU("DRN"), "02600C1004012,#，詳單價分析表 A-13", "五-4"),
    ("壹.二.3", "施工測量放樣", "案", q("五-5"), U0("SURV"), "01725C4005,#", "五-5"),
    ("壹.二.4", "既有地下管線查證及保護", "式", q("五-6"), 5227, "#【待確認】", "五-6"),
    ("壹.二.5", "混凝土試體取樣及試驗", "式", q("五-7"), AU("CONC"), "03053#，詳單價分析表 A-12", "五-7"),
    ("壹.二.6", "鋼筋拉伸及彎曲試驗", "式", q("五-8"), AU("TEST"), "01450#，詳單價分析表 A-11", "五-8"),
    ("壹.二.7", "工地清理，竣工後清理", "案", q("五-9"), U0("CLEAN"), "SWCB0200002,#", "五-9"),
    ("壹.二.8", "施工機具搬運費", "趟", q("五-10"), U0("MOB"), "3450502200159，來回算一趟", "五-10"),
    ("H2", "壹.三", "職業安全衛生費（依決標金額總價調整各項單價時，廠商報價之安全衛生經費項目編列金額低於機關所訂底價之同項金額者，該報價金額不隨之調低；高於同項底價金額者，調整後不得低於底價金額）"),
    ("壹.三.1", "職業安全衛生告示牌", "面", q("五-3"), U0("OSHB"), "015831000ALG,#", "五-3"),
    ("壹.三.2", "護欄，鋼管護欄（臨時，設置及拆除）", "M", q("一-5"), U0("PIPEG"), "01556C2006，詳 S-03、S-04", "一-5"),
    ("壹.三.3", "人員安全上下設備費（開挖深 1.53 m）", "式", 1, U0("LADDER"), "SWCB0056，租用含拆裝", "—"),
    ("壹.三.4", "職安人員", "人月", 2, U0("OSHMAN"), "L000007000007，工期 2 個月【待確認】", "—"),
    ("壹.三.5", "工作手套", "雙", 20, 17, "215145511,#", "範例 壹.三.1"),
    ("壹.三.6", "安全帽（硬質）", "頂", 10, 436, "01450A1380,#", "範例 壹.三.3"),
    ("壹.三.7", "安全鞋", "雙", 10, 871, "0151001022,#", "範例 壹.三.4"),
    ("壹.三.8", "警示帶（200 公尺長）", "捲", 2, 348, "CC0000000011", "範例 壹.三.5"),
    ("壹.三.9", "職業安全衛生，教育訓練", "次", 1, 3485, "015743000E", "範例 壹.三.12"),
    ("壹.三.10", "職業安全衛生，宣導", "次", 1, 1742, "015744000E", "範例 壹.三.13"),
    ("壹.三.11", "漏電無熔線斷路器", "只", 1, 3485, "015742B106", "範例 壹.三.27"),
    ("壹.三.12", "急救箱", "組", 1, 1045, "M015742A108", "範例 壹.三.28"),
    ("壹.三.13", "其他安全衛生設施及管理維護費", "式", 1, 5719, "0158100315", "範例 壹.三.32"),
    ("H2", "壹.四", "環境保護費"),
    ("壹.四.1", "環境保護，環保宣導", "式", 1, 6970, "0157260004", "範例 壹.四.1"),
    ("壹.四.2", "車輛沖洗設施費", "式", 1, 10455, "0123456167,#", "範例 壹.四.2"),
    ("壹.四.3", "工地清潔費", "式", 1, 10455, "0123456489,#", "範例 壹.四.3"),
    ("壹.四.4", "工地灑水費", "式", 1, 6970, "0123456597,#", "範例 壹.四.4"),
    ("壹.四.5", "其他環保措施及操作費", "式", 1, 4356, "0123456187,#", "範例 壹.四.5"),
]
r = 1; SUBROW = {}; cur = None; items_rows = {}
for it in D:
    r += 1
    if it[0] == "H1":
        wd.cell(r, 1, it[1]); wd.cell(r, 2, it[2]); wd.cell(r, 3, "式")
        for j in range(1, 8): body(wd.cell(r, j), align="left" if j == 2 else "center", bold=True, size=18, fill=SF)
        SUBROW["壹"] = r; continue
    if it[0] == "H2":
        cur = it[1]; wd.cell(r, 1, it[1]); wd.cell(r, 2, it[2]); wd.cell(r, 3, "式"); wd.cell(r, 4, 1)
        for j in range(1, 8): body(wd.cell(r, j), fmt={4: "#,##0.000", 6: "#,##0"}.get(j), align="left" if j in (2, 7) else ("right" if j in (4, 5, 6) else "center"), bold=True, fill=TF)
        SUBROW[cur] = r; items_rows[cur] = []; continue
    no, nm, un, qn, up, code, qref = it
    wd.cell(r, 1, no); wd.cell(r, 2, nm); wd.cell(r, 3, un); wd.cell(r, 4, qn); wd.cell(r, 5, up)
    wd.cell(r, 6, f"=ROUND(D{r}*E{r},0)"); wd.cell(r, 7, f"{code}；數量出處：數量計算書 {QVER} {qref}" if qref not in ("—",) and not qref.startswith("範例") and not qref.startswith("S-") else f"{code}" + (f"；{qref}" if qref != "—" else ""))
    for j in range(1, 8): body(wd.cell(r, j), fmt={4: "#,##0.000", 5: "#,##0", 6: "#,##0"}.get(j), align="left" if j in (2, 7) else ("right" if j in (4, 5, 6) else "center"))
    items_rows[cur].append(r)
for k, rows_ in items_rows.items():
    sr = SUBROW[k]; wd.cell(sr, 6, "=" + "+".join(f"F{x}" for x in rows_)); wd.cell(sr, 5, f"=F{sr}")
    wd.cell(sr, 5).number_format = "#,##0"
# 壹.五～壹.七、貳
R1, R2, R3, R4 = (f"F{SUBROW[k]}" for k in ("壹.一", "壹.二", "壹.三", "壹.四"))
TAIL = [
    ("壹.五", "施工品質管理費（分段計價）", f"=ROUND(({R1}+{R2})*參數!$C$2,0)", "（壹.一＋壹.二）×費率，分段級距【待確認】"),
    ("壹.六", "廠商利潤、管理及保險費（分段計價）", f"=ROUND(({R1}+{R2})*參數!$C$3,0)", "（壹.一＋壹.二）×費率，範例反推 11.442%，分段級距【待確認】；工程保險併入本項"),
    ("壹.七", "營業稅（壹.一～壹.六合計之 5%）", "", "5%"),
]
for no, nm, f, note in TAIL:
    r += 1; SUBROW[no] = r
    wd.cell(r, 1, no); wd.cell(r, 2, nm); wd.cell(r, 3, "式"); wd.cell(r, 4, 1); wd.cell(r, 7, note)
    if no == "壹.七":
        f = f"=ROUND(({R1}+{R2}+{R3}+{R4}+F{SUBROW['壹.五']}+F{SUBROW['壹.六']})*參數!$C$4,0)"
    wd.cell(r, 6, f); wd.cell(r, 5, f"=F{r}")
    for j in range(1, 8): body(wd.cell(r, j), fmt={4: "#,##0.000", 5: "#,##0", 6: "#,##0"}.get(j), align="left" if j in (2, 7) else ("right" if j in (4, 5, 6) else "center"), bold=True, fill=TF)
wd.cell(SUBROW["壹"], 6, "=" + "+".join(f"F{SUBROW[k]}" for k in ("壹.一", "壹.二", "壹.三", "壹.四", "壹.五", "壹.六", "壹.七")))
wd.cell(SUBROW["壹"], 6).number_format = "#,##0"
r += 1; SUBROW["貳"] = r
wd.cell(r, 1, "貳"); wd.cell(r, 2, "間接工程費"); wd.cell(r, 3, "式")
for j in range(1, 8): body(wd.cell(r, j), fmt="#,##0" if j == 6 else None, align="left" if j == 2 else ("right" if j == 6 else "center"), bold=True, size=18, fill=SF)
G = f"F{SUBROW['壹']}"
IND = [("貳.一", "空氣汙染防制費（約壹之 0.3%）", f"=ROUND({G}*參數!$C$5,0)", "壹×0.3%（照範例）；臺中市營建工程空污費依面積×工期計【待確認】"),
       ("貳.二", "工程管理費", f"=ROUND(MIN({G},5000000)*參數!$C$6+MAX(MIN({G},25000000)-5000000,0)*0.015+MAX({G}-25000000,0)*0.01,0)", "分段：500 萬元以下 3%、500～2,500 萬元部分 1.5%（工程管理費支用要點）【待確認】"),
       ("貳.三", "委外設計服務費", "=參數!$C$7", "本案委託技術服務契約金額【待補】"),
       ("貳.四", "委外監造服務費", "=參數!$C$8", "【待補】")]
ind_rows = []
for no, nm, f, note in IND:
    r += 1; ind_rows.append(r)
    wd.cell(r, 1, no); wd.cell(r, 2, nm); wd.cell(r, 3, "式"); wd.cell(r, 4, 1); wd.cell(r, 6, f); wd.cell(r, 5, f"=F{r}"); wd.cell(r, 7, note)
    for j in range(1, 8): body(wd.cell(r, j), fmt={4: "#,##0.000", 5: "#,##0", 6: "#,##0"}.get(j), align="left" if j in (2, 7) else ("right" if j in (4, 5, 6) else "center"))
wd.cell(SUBROW["貳"], 6, "=" + "+".join(f"F{x}" for x in ind_rows))
r += 1; wd.cell(r, 2, "總價（總計）"); wd.cell(r, 6, f"={G}+F{SUBROW['貳']}"); TOT = r
for j in range(1, 8): body(wd.cell(r, j), fmt="#,##0" if j == 6 else None, align="left" if j == 2 else ("right" if j == 6 else "center"), bold=True, size=18, fill=SF)
for col, w in zip("ABCDEFG", [12, 56, 8, 14, 17, 21, 48]): wd.column_dimensions[col].width = w
wd.freeze_panes = "B2"; page(wd, "預算詳細表")

# ======================================================================
# 參數（費率）
# ======================================================================
wr = wb.create_sheet("參數")
wr.append(["項目", "說明", "數值", "出處"]); hdr(wr, 1, 4)
RATES = [("品管費率", "施工品質管理費（壹.一＋壹.二）×", 0.02, "範例 10-1 反推 2.000%；分段計價級距【待確認】"),
         ("利潤管理保險費率", "廠商利潤、管理及保險費（壹.一＋壹.二）×", 0.11442, "範例 10-1 反推 11.442%；分段計價級距【待確認】"),
         ("營業稅率", "營業稅（壹.一～壹.六）×", 0.05, "營業稅法"),
         ("空污費率", "空氣汙染防制費 壹×", 0.003, "範例 10-1（約壹之 0.3%）"),
         ("工程管理費率", "工程管理費 500 萬元以下部分×（超過部分 1.5%、1%）", 0.03, "工程管理費支用要點分段計算【待確認】"),
         ("委外設計服務費", "元", 0, "【待補】本案委託技術服務契約金額"),
         ("委外監造服務費", "元", 0, "【待補】")]
for i, (a, b, c, d) in enumerate(RATES, 2):
    for j, v in enumerate((a, b, c, d), 1):
        wr.cell(i, j, v); body(wr.cell(i, j), fmt=("0.000%" if i <= 6 else "#,##0") if j == 3 else None, align="left" if j in (1, 2, 4) else "right")
for col, w in zip("ABCD", [22, 44, 14, 60]): wr.column_dimensions[col].width = w
page(wr, "費率參數")

# ======================================================================
# 預算總表（10-1）
# ======================================================================
wt = wb.create_sheet("預算總表", 0)
wt.append(["項次", "工作項目", "金額（元）", "備註"]); hdr(wt, 1, 4)
rows_t = [("壹", "發包工程費", "壹"), ("壹.一", "施工費用（工作費＋材料費）", "壹.一"), ("壹.二", "雜項工程", "壹.二"),
          ("壹.三", "職業安全衛生費", "壹.三"), ("壹.四", "環境保護費", "壹.四"), ("壹.五", "施工品質管理費（分段計價）", "壹.五"),
          ("壹.六", "廠商利潤、管理及保險費（分段計價）", "壹.六"), ("壹.七", "營業稅（壹.一～壹.六合計之 5%）", "壹.七"), ("貳", "間接工程費", "貳")]
for i, (no, nm, k) in enumerate(rows_t, 2):
    wt.cell(i, 1, no); wt.cell(i, 2, nm); wt.cell(i, 3, f"=預算詳細表!F{SUBROW[k]}"); wt.cell(i, 4, f"=預算詳細表!G{SUBROW[k]}" if k in ("壹.五", "壹.六") else "")
    bold = no in ("壹", "貳")
    for j in range(1, 5): body(wt.cell(i, j), fmt="#,##0" if j == 3 else None, align="left" if j in (2, 4) else ("right" if j == 3 else "center"), bold=bold, fill=SF if bold else None, size=18 if bold else 14)
i = len(rows_t) + 2
for no, nm, rr, note in zip(("貳.一", "貳.二", "貳.三", "貳.四"), [x[1] for x in IND], ind_rows, [x[3] for x in IND]):
    wt.cell(i, 1, no); wt.cell(i, 2, nm); wt.cell(i, 3, f"=預算詳細表!F{rr}"); wt.cell(i, 4, note)
    for j in range(1, 5): body(wt.cell(i, j), fmt="#,##0" if j == 3 else None, align="left" if j in (2, 4) else ("right" if j == 3 else "center"))
    i += 1
wt.cell(i, 2, "總價（總計）"); wt.cell(i, 3, f"=預算詳細表!F{TOT}")
for j in range(1, 5): body(wt.cell(i, j), fmt="#,##0" if j == 3 else None, align="left" if j == 2 else ("right" if j == 3 else "center"), bold=True, size=18, fill=SF)
i += 2
for t in ["註：", f"1. 數量依數量計算書 {QVER}；圖說依標準圖 v3.2、設計圖冊 v3.1。",
          "2. 單價以臺北市 112 年度工程預算參考單價 × 物價調整係數 K（詳「單價依據」）；臺北市無者採範例（苗栗 115 年）或單價分析。",
          "3. 貳.三、貳.四 委外設計、監造服務費待填契約金額；發包工程費（壹）不受影響。",
          "4. 標【待確認】者定案前須訪價或依機關規定修正，詳「假設與待確認」。"]:
    wt.cell(i, 1, t); wt.merge_cells(start_row=i, start_column=1, end_row=i, end_column=4)
    wt.cell(i, 1).font = Font(name=FN, size=14, color=DK); wt.cell(i, 1).alignment = Alignment(wrap_text=True, vertical="center"); i += 1
for col, w in zip("ABCD", [10, 46, 20, 70]): wt.column_dimensions[col].width = w
page(wt, "預算總表")
wt.oddHeader.right.text = f"機關：{AGENCY}"; wt.oddHeader.right.size = 10

# ======================================================================
# 假設與待確認
# ======================================================================
wn = wb.create_sheet("假設與待確認")
wn.append(["項次", "事項", "本預算採用", "影響項次"]); hdr(wn, 1, 4)
NOTE = [
    ("物價調整係數 K", "115年6月 CCI 119.16÷111年 107.51＝1.108；111年值取臺北市年平均，非臺北市單價訪價當月", "全部套 K 項目"),
    ("單價依據", "業主未指定單價依據；臺中市在地單價未取得，暫用臺北市 112 年單價×K", "全部"),
    ("鋼軌樁單價", "沿用範例 L=6m 2,126 元/支，本案 L=3m 偏保守", "壹.一.3"),
    ("既有暗溝打除", "暗溝壁厚未知，假設 15 cm，每公尺 0.49 m³", "壹.一.1"),
    ("構造物開挖", "臺北市無機械構造物開挖，依工率分析（開挖機 25 m³/時、修整 0.1 時/m³）", "壹.一.6"),
    ("預鑄溝蓋板", "以混凝土＋鋼筋＋模板＋吊裝分析；格柵蓋及框 4,500 元/組為假設", "壹.一.15、壹.一.16"),
    ("交通維持", "拒馬、交通錐、燈號、標誌依 S-04 估；旗手 2 人×40 工作天", "壹.一.21"),
    ("臨時鋼管護欄", "採範例 1,568 元/M（苗栗 115 年），未訪價", "壹.三.2"),
    ("職安人員", "2 人月（工期 2 個月）", "壹.三.4"),
    ("品管費、利潤管理及保險費", "依範例反推 2.000%、11.442%（基準壹.一＋壹.二），分段計價級距未套", "壹.五、壹.六"),
    ("工程管理費", "分段計算：500 萬元以下 3%、超過部分 1.5%", "貳.二"),
    ("委外設計、監造服務費", "未填（0）", "貳.三、貳.四"),
    ("餘方處理", "臺北市 15t 傾卸貨車單價；臺中土資場運距與收容費未查", "壹.一.8"),
    ("伸縮縫、人孔踏步、AC 切割、管線查證", "依假設材料價或範例類似項目，未訪價", "壹.一.2、壹.一.17、壹.一.18、壹.二.4"),
]
for i, (a, b, c) in enumerate(NOTE, 2):
    for j, v in enumerate((i - 1, a, b, c), 1):
        wn.cell(i, j, v); body(wn.cell(i, j), align="left" if j in (2, 3) else "center")
for col, w in zip("ABCD", [8, 34, 80, 26]): wn.column_dimensions[col].width = w
wn.freeze_panes = "B2"; page(wn, "假設條件與待確認事項")

for ws_ in wb.worksheets: refit(ws_)
wb.save(OUT); print(OUT)
