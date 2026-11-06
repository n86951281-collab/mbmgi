"""P33 預算書（PCCES 版面，依象鼻段 (預算書)…_ap_bdgt_1150915v1.xls）：預算總表、預算詳細表、預算單價分析表＋單價依據、假設與待確認。
數量：工程數量計算表（qty_table_v2.0.json，總計取整數）。
單價優先序：①象鼻段 115 年 PCCES 預算書同項單價（X）②大湖範例 115 年（D）③臺北市 112 年×K（T）④單價分析（A，工資用象鼻段 115 年）。
用法：python -I budget_pcces.py --case <案件資料夾> [--qty-json qty_table_v2.0.json] --stamp YYYYMMDD_HHMM
（--case 省略時用本檔所在資料夾；--qty-json 為 qty_table.py 輸出的總計檔，相對於案件資料夾）
參考實作：單價、工項、費率、工期（90 日曆天、旗手 120 工、職安 3 人月）、計畫說明書內文都是 P33 東山街案的，新案逐項改。
"""
import sys, os, json, math, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.worksheet.page import PageMargins
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
CASE = os.path.abspath(arg("--case", HERE))
CFG = json.load(open(os.path.join(CASE, "case_config.json"), encoding="utf-8-sig"))
CODE = CFG.get("case_code", "P33")
stamp = arg("--stamp", datetime.datetime.now().strftime("%Y%m%d_%H%M"))
VER = "v2.5"
QJ = json.load(open(os.path.join(CASE, arg("--qty-json", "qty_table_v2.0.json")), encoding="utf-8-sig"))
AG, PJ, SITE = CFG["title_block"]["agency"], CFG["title_block"]["project"], CFG.get("site", "臺中市新社區")
OUT = os.path.join(CFG["out_dir"], f"{CFG['file_prefix']}{stamp}_{CODE}_預算書_PCCES格式_{VER}.xlsx")

KAI = "標楷體"; thin = Side(style="thin", color="000000"); ALL = Border(left=thin, right=thin, top=thin, bottom=thin)
GRAY = PatternFill("solid", fgColor="EEF1F4")
def C(ws, r, c, v, size=10, h="left", b=False, border=True, fmt=None, fill=None):
    x = ws.cell(r, c, v); x.font = Font(name=KAI, size=size, bold=b); x.alignment = Alignment(horizontal=h, vertical="center", wrap_text=True)
    if border: x.border = ALL
    if fmt: x.number_format = fmt
    if fill: x.fill = fill
    return x
def head(ws, title, ncol, r0=1):
    ws.merge_cells(start_row=r0, start_column=1, end_row=r0, end_column=ncol); C(ws, r0, 1, AG, 20, "center", border=False)
    ws.merge_cells(start_row=r0 + 1, start_column=1, end_row=r0 + 1, end_column=ncol); C(ws, r0 + 1, 1, title, 25, "center", True, border=False)
def info(ws, r, ncol):
    """工程名稱／會計科目、施工地點／工程編號（PCCES 表頭）"""
    C(ws, r, 1, "工程名稱", h="center"); ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=ncol - 3); C(ws, r, 2, PJ)
    C(ws, r, ncol - 2, "會計科目", h="center"); ws.merge_cells(start_row=r, start_column=ncol - 1, end_row=r, end_column=ncol); C(ws, r, ncol - 1, "【待補】")
    C(ws, r + 1, 1, "施工地點", h="center"); ws.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=ncol - 3); C(ws, r + 1, 2, SITE)
    C(ws, r + 1, ncol - 2, "工程編號", h="center"); ws.merge_cells(start_row=r + 1, start_column=ncol - 1, end_row=r + 1, end_column=ncol); C(ws, r + 1, ncol - 1, "【待補】")
    for rr in (r, r + 1):
        for cc in range(1, ncol + 1): ws.cell(rr, cc).border = ALL
def page(ws, rows):
    ws.print_title_rows = rows
    ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.75, bottom=0.6, header=0.3, footer=0.3)
    ws.oddHeader.right.text = "第 &P 頁 共 &N 頁"; ws.oddHeader.right.size = 12; ws.oddHeader.right.font = "標楷體,標準"
    ws.oddFooter.left.text = "編製：辰璟工程技術顧問有限公司"; ws.oddFooter.left.size = 12; ws.oddFooter.left.font = "標楷體,標準"
def tw(s, pt): return sum((2.3 if ord(ch) > 0x2E80 else 1.2) * pt / 11.0 for ch in s)
def refit(ws):
    merged = {}
    for mr in ws.merged_cells.ranges:
        w = sum(ws.column_dimensions[get_column_letter(c)].width or 8.43 for c in range(mr.min_col, mr.max_col + 1))
        merged[(mr.min_row, mr.min_col)] = w
        for rr in range(mr.min_row, mr.max_row + 1):
            for cc in range(mr.min_col, mr.max_col + 1):
                if (rr, cc) != (mr.min_row, mr.min_col): merged[(rr, cc)] = -1
    for row in ws.iter_rows():
        need, pt = 1, 14
        for c in row:
            if c.value is None or merged.get((c.row, c.column)) == -1: continue
            pt = c.font.size or 14
            w = merged.get((c.row, c.column)) or (ws.column_dimensions[get_column_letter(c.column)].width or 8.43)
            s = c.value if isinstance(c.value, str) and not c.value.startswith("=") else "0" * 11
            need = max(need, sum(max(1, math.ceil(tw(p, pt) / max(w - 3.5, 1))) for p in s.split("\n")))
        ws.row_dimensions[row[0].row].height = max(19.5, round(need * pt * 1.45 + 8))

wb = Workbook()
# ======================================================================
# 單價依據
# ======================================================================
ws = wb.active; ws.title = "單價依據"
X = "象鼻段 115 年 PCCES 預算書"; D_ = "大湖範例 115 年（10-2）"; TP = "臺北市 112 年單價×K"
SRC = [
    ("K", "物價調整係數 K（臺北市 112 年→115 年）", "－", "=119.16/107.51", "", "營造工程物價總指數 115.6 月 119.16÷111 年 107.51【待確認】"),
    ("SKL", "技術工", "工", 2344, "L000005000002", f"{X} 單價分析表壹.一.43"),
    ("LAB", "普通工不細分，普通工", "工", 1688, "L000006000002", f"{X} 單價分析表壹.一.43"),
    ("MCH", "機具費（小型機具）", "天", 7502, "E3511XA0002", f"{X} 單價分析表壹.一.43"),
    ("EXC", "構造物開挖，挖普通土含30%以上砂礫，機械", "M3", 84, "02316#E023", f"{X} 壹.一.1"),
    ("FILL", "構造物回填，原材料回填", "M3", 66, "0231710003", f"{X} 壹.一.4"),
    ("SPOIL", "餘方自行處理(含水土保持)，總重15t傾卸貨車", "M3", "=ROUND(721.06*$D$2,2)", "023234004A", f"{TP}：組合單價 第8頁 項次20（運棄土資場，象鼻段為現地攤平不適用）"),
    ("HEAVY", "重機械拖運費(來回各1次合計算1趟)", "趟", 18754, "1011010", f"{X} 壹.一.6"),
    ("PILEMOV", "搬運費，臨時擋土設施材料搬運費(來回計1次)", "次", 11253, "012714000A1", f"{X} 壹.一.16"),
    ("PILE", "臨時擋土設施(鋼軌樁打拔50kg/m,L=6m,間隔100cm)", "支", 2126, "0225526121D", f"{D_} 壹.一.10（本案 L=3m）【待確認】"),
    ("PLATE", "臨時擋土設施，鋼襯版（含打拔費）", "M2", 1307, "CC40002", f"{D_} 壹.一.11"),
    ("C210", "(一般地區)結構用混凝土，預拌，210kgf/cm2", "M3", 3398, "0331024005", f"{D_} 壹.一.18（含運費及澆置搗實；象鼻段偏遠地區 3,938 不適用）"),
    ("C140", "(一般地區)結構用混凝土，預拌，140kgf/cm2", "M3", "=D13-ROUND(2991.53-2795.83,0)", "0331022005", "210 單價－臺北市 140／210 價差 196【待確認】"),
    ("C280", "(一般地區)結構用混凝土，預拌，280kgf/cm2", "M3", "=D13+ROUND(3314.13-2991.53,0)", "0331026005", "210 單價＋臺北市 280／210 價差 323【待確認】"),
    ("FORM", "軀體模板", "M2", 1031, "0311022101A", f"{X} 壹.一.34"),
    ("SD280", "鋼筋，竹節鋼筋(SD280W)，連工帶料，含損耗5%及鋼筋間隔器", "T", 28132, "03210310028", f"{X} 壹.一.39"),
    ("SD420", "鋼筋，竹節鋼筋(SD420W)，連工帶料，含損耗5%及鋼筋間隔器", "T", "=ROUND(D17*37975.69/35878.61,0)", "03210510028", "SD280 單價×臺北市 SD420／SD280 價比【待確認】"),
    ("RC_DEM", "機械拆除，鋼筋混凝土，含運費", "M3", "=ROUND(1788.91*$D$2,2)", "0222010E13", f"{TP}：組合單價 第8頁 項次2"),
    ("WASTE", "餘方自行處理(房屋廢方，含水土保持)", "M3", "=ROUND(957.96*$D$2,2)", "02323PWD0A001", f"{TP}：組合單價 第8頁 項次22"),
    ("AC95", "瀝青混凝土舖面，粗粒料9.5mm，黏度AC(1)-20", "M3", "=ROUND(7300.95*$D$2,2)", "0274205303", f"{TP}：組合單價 第8頁 項次9"),
    ("ACLAY", "瀝青混凝土舖面，鋪築及滾壓", "M3", "=ROUND(352.30*$D$2,2)", "02742000A3", f"{TP}：組合單價 第8頁 項次7"),
    ("TACK", "瀝青黏層 RC-70", "M2", "=ROUND(15.65*$D$2,2)", "0274711002", f"{TP}：組合單價 第8頁 項次13"),
    ("BARR", "活動型拒馬，長1.2m", "座", "=ROUND(1230.75*$D$2,2)", "0155630A0A", f"{TP}：組合單價 第9頁 項次38"),
    ("LAMP", "施工警告燈號", "座", "=ROUND(1666.11*$D$2,2)", "015568000A", f"{TP}：組合單價 第9頁 項次40"),
    ("SIGN", "施工標誌", "座", "=ROUND(2199.58*$D$2,2)", "015566000A", f"{TP}：工程單價 第13頁 項次88"),
    ("CONE", "交通錐及連桿", "組", 392, "M0155642213", f"{X} 壹.三.6"),
    ("BOARD", "工程告示牌", "塊", 3751, "03053C3024", f"{X} 壹.二.1"),
    ("OSHB", "職業安全衛生告示牌", "面", 3751, "015831000ALG", f"{X} 壹.二.2"),
    ("DRAIN", "擋排水費", "式", 9377, "02600C100401", f"{X} 壹.二.4"),
    ("CLEAN", "工地清理，竣工前清理", "案", 5626, "SWCB0200002", f"{X} 壹.二.6"),
    ("CORE", "混凝土鑽心試體取樣及試驗費", "組", 5626, "03053C4105", f"{X} 壹.二.20"),
    ("TENS", "竹節鋼筋拉伸試驗", "根", 938, "01450A1B3H", f"{X} 壹.二.23"),
    ("BEND", "竹節鋼筋抗彎試驗", "根", 938, "01450A1B4H", f"{X} 壹.二.24"),
    ("SURV", "施工測量放樣", "案", 7502, "01725C4005", f"{X} 壹.二.26"),
    ("MOB", "施工機具搬運費", "趟", 11253, "3450502200159", f"{X} 壹.二.27"),
    ("PIPEG", "護欄，鋼管護欄（租用）", "M", 588, "01556F2001", f"{X} 壹.三.10"),
]
ws.append(["代號", "名稱", "單位", "採用單價", "編碼", "出處"])
for j in range(1, 7): C(ws, 1, j, ws.cell(1, j).value, 10, "center", True, fill=GRAY)
U = {}
for i, (k, nm, un, p, code, src) in enumerate(SRC, 2):
    U[k] = f"單價依據!$D${i}"
    for j, v in enumerate((k, nm, un, p, code, src), 1):
        C(ws, i, j, v, h="right" if j == 4 else ("center" if j in (1, 3) else "left"), fmt=("0.0000" if k == "K" else "#,##0.00") if j == 4 else None)
for col, w in zip("ABCDEF", [10, 42, 7, 15, 17, 50]): ws.column_dimensions[col].width = w
ws.freeze_panes = "B2"; page(ws, "1:1"); ws.page_setup.orientation = "landscape"
P = lambda k: U[k]

# ---- PCCES 版面工具（字型、字級、列高、欄寬、邊框依象鼻段 (預算書)…_ap_bdgt_1150915v1.xls）----
PC_TOP = Border(left=thin, right=thin, top=thin)
PC_MID = Border(left=thin, right=thin)
FOOT = "編製：" + "　" * 16 + "承辦：" + "　" * 16 + "科長："
def chunks(s, units):
    """依顯示寬（全形 2、半形 1）切段，模擬 PCCES 長字串續行"""
    out, cur, w = [], "", 0
    for ch in str(s):
        cw = 2 if ord(ch) > 0x2E80 else 1
        if w + cw > units and cur: out.append(cur); cur, w = "", 0
        cur += ch; w += cw
    if cur: out.append(cur)
    return out or [""]
def PX(ws, r, c, v, size=10, h="left", b=False, border=None, fmt=None, wrap=False, v_="center"):
    x = ws.cell(r, c, v); x.font = Font(name=KAI, size=size, bold=b); x.alignment = Alignment(horizontal=h, vertical=v_, wrap_text=wrap)
    if border is not None: x.border = border
    if fmt: x.number_format = fmt
    return x
def pc_head(ws, title, ncol, r1=1, r2=2, h2=24.0):
    ws.merge_cells(start_row=r1, start_column=1, end_row=r1, end_column=ncol); PX(ws, r1, 1, AG, 16, "center", wrap=True); ws.row_dimensions[r1].height = 24.0
    ws.merge_cells(start_row=r2, start_column=1, end_row=r2, end_column=ncol); PX(ws, r2, 1, title, 16, "center", wrap=True); ws.row_dimensions[r2].height = h2
def pc_info(ws, h6):
    """第 6、7 列：工程名稱／會計科目、施工地點／工程編號（A｜B:D｜E｜F:G）"""
    for r, (a, b, e, f) in ((6, ("工程名稱", PJ, "會計科目", "【待補】")), (7, ("施工地點", SITE, "工程編號", "【待補】"))):
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4); ws.merge_cells(start_row=r, start_column=6, end_row=r, end_column=7)
        PX(ws, r, 1, a, h="center", wrap=True); PX(ws, r, 2, b, wrap=True); PX(ws, r, 5, e, h="center", wrap=True); PX(ws, r, 6, f, wrap=True)
        for cc in range(1, 8): ws.cell(r, cc).border = ALL
    ws.row_dimensions[6].height = h6; ws.row_dimensions[7].height = 30.0
def pc_page(ws, titles, scale, L, R, T, B, H, F, hsize):
    ws.print_title_rows = titles
    ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.orientation = "portrait"
    if scale: ws.page_setup.scale = scale
    ws.page_margins = PageMargins(left=L, right=R, top=T, bottom=B, header=H, footer=F)
    ws.oddHeader.right.text = "第 &P 頁 共 &N 頁"; ws.oddHeader.right.size = hsize; ws.oddHeader.right.font = "標楷體,標準"
    ws.oddFooter.left.text = FOOT; ws.oddFooter.left.size = 10; ws.oddFooter.left.font = "標楷體,標準"
# ======================================================================
# 預算單價分析表（版面依象鼻段：欄寬 A8.33 B37.66 C7.66 D9.66 E10.33 F11.33 G12.89；區塊字級 8；首列 38.1、其餘 19.5）
# ======================================================================
wa = wb.create_sheet("預算單價分析表")
for col, w in zip("ABCDEFG", [8.33, 37.66, 7.66, 9.66, 10.33, 11.33, 12.89]): wa.column_dimensions[col].width = w
wa.column_dimensions["H"].hidden = True                                   # H：人／機／材／雜 分類（不列印）
pc_head(wa, "單價分析表[預算]", 7, 3, 4, 25.5)
wa.merge_cells("B5:E6"); PX(wa, 5, 2, f"工程名稱：{PJ}", v_="top", wrap=True); wa.row_dimensions[5].height = 15.75; wa.row_dimensions[6].height = 15.75
PX(wa, 7, 1, "項次：", v_="top"); PX(wa, 7, 2, "工程編號：【待補】", v_="top"); wa.row_dimensions[7].height = 15.75
AN = {}; NEXT = [8]
def analysis(no, name, unit, code, lines):
    r = NEXT[0]
    PX(wa, r, 1, no, 8, wrap=True, border=ALL)
    wa.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3); PX(wa, r, 2, f"工作項目：{name}", 8, wrap=True, border=ALL)
    wa.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5); PX(wa, r, 4, f"單位：{unit}", 8, "center", wrap=True, border=ALL)
    wa.merge_cells(start_row=r, start_column=6, end_row=r, end_column=7); PX(wa, r, 6, f"計價代碼：{code}", 8, "distributed", wrap=True, border=ALL)
    for cc in (3, 5, 7): wa.cell(r, cc).border = ALL
    wa.row_dimensions[r].height = 38.1
    r += 1
    PX(wa, r, 1, None, 8, border=ALL)
    for j, t in zip(range(2, 8), ["工料名稱", "單位", "數量", "單價", "複價", "編碼(備註)"]): PX(wa, r, j, t, 8, wrap=True, border=ALL)
    wa.row_dimensions[r].height = 19.5
    r0 = r + 1
    for nm, un, qn, pr, cat, cd in lines:
        r += 1
        PX(wa, r, 1, None, 8, border=ALL); PX(wa, r, 2, nm, 8, border=ALL); PX(wa, r, 3, un, 8, "center", border=ALL)
        PX(wa, r, 4, qn, 8, "right", border=ALL, fmt="#,##0.000"); PX(wa, r, 5, pr, 8, "right", border=ALL, fmt="#,##0.00")
        PX(wa, r, 6, f"=ROUND(D{r}*E{r},2)", 8, "right", border=ALL, fmt="#,##0.00"); PX(wa, r, 7, cd, 8, border=ALL)
        wa.cell(r, 8, cat); wa.row_dimensions[r].height = 19.5
    r1 = r; r += 1
    PX(wa, r, 1, None, 8, border=ALL); PX(wa, r, 2, "合計", 8, border=ALL); PX(wa, r, 3, unit, 8, "center", border=ALL)
    PX(wa, r, 4, 1, 8, "right", border=ALL, fmt="#,##0.000"); PX(wa, r, 5, None, 8, border=ALL)
    PX(wa, r, 6, f"=SUM(F{r0}:F{r1})", 8, "right", border=ALL, fmt="#,##0.00"); PX(wa, r, 7, None, 8, border=ALL)
    wa.row_dimensions[r].height = 19.5
    rs = r; r += 1
    sm = lambda t: f'TEXT(SUMIF(H{r0}:H{r1},"{t}",F{r0}:F{r1}),"#,##0.00")'
    wa.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3); wa.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=3)
    wa.merge_cells(start_row=r, start_column=4, end_row=r + 1, end_column=5); wa.merge_cells(start_row=r, start_column=6, end_row=r + 1, end_column=7)
    PX(wa, r, 2, f'="人工："&{sm("人")}&"　　機具："&{sm("機")}', 8)
    PX(wa, r + 1, 2, f'="材料："&{sm("材")}&"　　雜項："&{sm("雜")}', 8)
    PX(wa, r, 4, f"每 {unit} 單價計", 8, "center"); PX(wa, r, 6, f"=ROUND(F{rs},0)", 8, "right", fmt="#,##0")
    for rr in (r, r + 1):
        wa.row_dimensions[rr].height = 19.5
        for cc in range(1, 8): wa.cell(rr, cc).border = ALL
    AN[no] = f"預算單價分析表!$F${r}"
    NEXT[0] = r + 2
    return AN[no]
A = {}
A["DEM"] = analysis("壹.一.8", "既有暗溝打除(含廢料運棄)", "M", "0222010E13,#", [
    ("機械拆除，鋼筋混凝土，含運費(每M 0.49M3)", "M3", 0.49, f"={P('RC_DEM')}", "雜", "0222010E13"),
    ("餘方自行處理(房屋廢方)", "M3", 0.49, f"={P('WASTE')}", "雜", "02323PWD0A001")])
A["CUT"] = analysis("壹.一.9", "AC路面切割", "M", "#", [
    ("技術工（切割）", "工", 0.006, f"={P('SKL')}", "人", "L000005000002"),
    ("切割機具及鑽石刀片損耗", "式", 1, 30, "機", "#【待確認】"),
    ("零星材料及機具損耗", "式", 1, 3, "雜", "W0127170104,#")])
A["COVA"] = analysis("壹.一.16", "甲種預鑄溝蓋板150×100×23(含熱浸鍍鋅格柵蓋及框)", "塊", "#", [
    ("280kgf/cm2混凝土（扣格柵開口）", "M3", round(1.5 * 1.0 * 0.23 - 0.73 * 0.63 * 0.23, 3), f"={P('C280')}", "材", "0331026005"),
    ("鋼筋SD420W（S-02 甲種 111.87kg）", "T", 0.112, f"={P('SD420')}", "材", "03210510028"),
    ("軀體模板（預鑄場）", "M2", round(2 * (1.5 + 1.0) * 0.23 + 2 * (0.73 + 0.63) * 0.23, 3), f"={P('FORM')}", "材", "0311022101A"),
    ("熱浸鍍鋅格柵蓋及框(73×63)", "組", 1, 4500, "材", "#【待確認訪價】"),
    ("技術工（吊裝安放）", "工", 0.0625, f"={P('SKL')}", "人", "L000005000002"),
    ("普通工（吊裝安放）", "工", 0.0625, f"={P('LAB')}", "人", "L000006000002")])
A["COVB"] = analysis("壹.一.17", "乙種預鑄溝蓋板150×100×23", "塊", "#", [
    ("280kgf/cm2混凝土", "M3", 0.345, f"={P('C280')}", "材", "0331026005"),
    ("鋼筋SD420W（S-02 乙種 82.47kg）", "T", 0.082, f"={P('SD420')}", "材", "03210510028"),
    ("軀體模板（預鑄場）", "M2", round(2 * (1.5 + 1.0) * 0.23, 3), f"={P('FORM')}", "材", "0311022101A"),
    ("技術工（吊裝安放）", "工", 0.0625, f"={P('SKL')}", "人", "L000005000002"),
    ("普通工（吊裝安放）", "工", 0.0625, f"={P('LAB')}", "人", "L000006000002")])
A["STEP"] = analysis("壹.一.18", "塑膠包覆人孔踏步", "個", "#", [
    ("塑膠包覆人孔踏步", "個", 1, 350, "材", "#【待確認訪價】"),
    ("技術工（植入）", "工", 0.025, f"={P('SKL')}", "人", "L000005000002")])
A["EJ"] = analysis("壹.一.19", "伸縮縫(含填縫材)", "處", "#", [
    ("瀝青纖維板填縫材 t=1cm", "M2", 0.78, 650, "材", "#【待確認訪價】"),
    ("PU止水填縫膠", "M", 3.1, 180, "材", "#【待確認訪價】"),
    ("技術工", "工", 0.125, f"={P('SKL')}", "人", "L000005000002")])
A["JOIN"] = analysis("壹.一.20", "新設側溝與既有排水銜接處理", "處", "#", [
    ("210kgf/cm2混凝土（封口及接頭修補）", "M3", 0.5, f"={P('C210')}", "材", "0331024005"),
    ("軀體模板", "M2", 3, f"={P('FORM')}", "材", "0311022101A"),
    ("技術工", "工", 0.5, f"={P('SKL')}", "人", "L000005000002"),
    ("普通工", "工", 0.5, f"={P('LAB')}", "人", "L000006000002")])
A["AC"] = analysis("壹.一.21", "9.5mm密級配AC面層t=5cm(路面修復)", "M2", "0274205303,#", [
    ("瀝青混凝土，粗粒料9.5mm", "M3", 0.05, f"={P('AC95')}", "材", "0274205303"),
    ("瀝青混凝土鋪築及滾壓", "M3", 0.05, f"={P('ACLAY')}", "機", "02742000A3"),
    ("瀝青黏層 RC-70", "M2", 1, f"={P('TACK')}", "材", "0274711002")])
A["TRAF"] = analysis("壹.一.22", "施工中交通維持(詳S-04、S-05)", "式", "01556#", [
    ("活動型拒馬，長1.2m", "座", 4, f"={P('BARR')}", "材", "0155630A0A"),
    ("交通錐及連桿", "組", 30, f"={P('CONE')}", "材", "M0155642213"),
    ("施工警告燈號", "座", 4, f"={P('LAMP')}", "材", "015568000A"),
    ("施工標誌", "座", 2, f"={P('SIGN')}", "材", "015566000A"),
    ("交通指揮人員（旗手2人×60工作天）", "工", 120, f"={P('LAB')}", "人", "L000006000002")])
A["CONC"] = analysis("壹.二.5", "混凝土鑽心試體取樣及試驗費", "式", "03053C4105,#", [
    ("混凝土鑽心試體取樣及試驗(共4組)", "組", 4, f"={P('CORE')}", "雜", "03053C4105")])
A["TEST"] = analysis("壹.二.6", "竹節鋼筋拉伸及抗彎試驗", "式", "01450#", [
    ("竹節鋼筋拉伸試驗（D13、D16 各 2 根）", "根", 4, f"={P('TENS')}", "雜", "01450A1B3H"),
    ("竹節鋼筋抗彎試驗（D13、D16 各 2 根）", "根", 4, f"={P('BEND')}", "雜", "01450A1B4H")])
pc_page(wa, "$1:$7", None, 0.39, 0.0, 0.39, 0.55, 1.57, 0.39, 10)

# ======================================================================
# 預算詳細表（版面依象鼻段：欄寬 A11.66 B37.66 C6.66 D10.66 E10.33 F12.66 G13.33；A～C 字級 10、D～G 字級 8；列高 19.5，長字串續行）
# ======================================================================
wd = wb.create_sheet("預算詳細表", 0)
for col, w in zip("ABCDEFG", [11.66, 37.66, 6.66, 10.66, 10.33, 12.66, 13.33]): wd.column_dimensions[col].width = w
pc_head(wd, "詳細價目表[預算]", 7); pc_info(wd, 30.0)
for j, t in zip(range(1, 8), ["項 次", "項  目  及  說  明", "單 位", "數 量", "單 價", "複 價", "編碼(備註)"]):
    PX(wd, 8, j, t, 10, "centerContinuous" if j != 2 else "centerContinuous", wrap=True, border=ALL)
wd.row_dimensions[8].height = 24.0
q = lambda k: QJ[k]
P0 = lambda k: f"=ROUND({P(k)},0)"
AU = lambda k: f"={A[k]}"
RW = [8]                                                                   # 目前最後一列
def drow(no, name, unit=None, qty=None, price=None, amount=None, code=None, Bunits=34, Gunits=15):
    """寫一個 PCCES 項目（可多列續行）；回傳首列列號"""
    nm, cd = chunks(name, Bunits), chunks(code or "", Gunits)
    n = max(len(nm), len(cd)); r0 = RW[0] + 1
    for i in range(n):
        r = r0 + i; first = i == 0; bd = PC_TOP if first else PC_MID
        PX(wd, r, 1, no if first else None, 10, "center", border=bd)
        PX(wd, r, 2, nm[i] if i < len(nm) else None, 10, border=bd)
        PX(wd, r, 3, unit if first else None, 10, "center", border=bd)
        PX(wd, r, 4, qty if first else None, 8, "right", border=bd, fmt="#,##0.000")
        PX(wd, r, 5, price if first else None, 8, "right", border=bd, fmt="#,##0")
        PX(wd, r, 6, (amount.replace("{r}", str(r)) if isinstance(amount, str) else amount) if first else None, 8, "right", border=bd, fmt="#,##0")
        PX(wd, r, 7, cd[i] if i < len(cd) else None, 8, border=bd)
        wd.row_dimensions[r].height = 19.5
    RW[0] = r0 + n - 1
    return r0
D = [
    ("H1", "壹", "發包工程費"), ("H2", "壹.一", "施工費用(工作費+材料費)"),
    ("壹.一.1", "構造物開挖，挖普通土含30%以上砂礫，機械", "M3", q("EXC"), P0("EXC"), "02316#E023"),
    ("壹.一.2", "構造物回填，原材料回填", "M3", q("FILL"), P0("FILL"), "0231710003"),
    ("壹.一.3", "餘方自行處理(含水土保持)，總重15t傾卸貨車", "M3", q("SPOIL"), P0("SPOIL"), "023234004A,運距及收容費【待確認】"),
    ("壹.一.4", "重機械拖運費(來回各1次合計算1趟)", "趟", 1, P0("HEAVY"), "1011010"),
    ("壹.一.5", "臨時擋土設施(鋼軌樁打拔50kg/m,L=3m,間隔100cm)", "支", q("PILE"), P0("PILE"), "0225526121D,#(含打拔費)"),
    ("壹.一.6", "臨時擋土設施，鋼襯版", "M2", q("PLATE"), P0("PLATE"), "CC40002,#(含打拔費)"),
    ("壹.一.7", "搬運費，臨時擋土設施材料搬運費(來回計1次)", "次", 2, P0("PILEMOV"), "012714000A1,兩階段"),
    ("壹.一.8", "既有暗溝打除(含廢料運棄)", "M", q("DEM"), AU("DEM"), "0222010E13,#,詳單價分析表壹.一.8"),
    ("壹.一.9", "AC路面切割", "M", q("CUT"), AU("CUT"), "#,詳單價分析表壹.一.9"),
    ("壹.一.10", "(一般地區)結構用混凝土，預拌，140kgf/cm2", "M3", q("C140"), P0("C140"), "0331022005,#(含運費及澆置搗實)"),
    ("壹.一.11", "(一般地區)結構用混凝土，預拌，210kgf/cm2", "M3", q("C210"), P0("C210"), "0331024005,#(含運費及澆置搗實)"),
    ("壹.一.12", "(一般地區)結構用混凝土，預拌，280kgf/cm2", "M3", q("C280"), P0("C280"), "0331026005,#(含運費及澆置搗實)"),
    ("壹.一.13", "軀體模板", "M2", q("FORM"), P0("FORM"), "0311022101A,#"),
    ("壹.一.14", "鋼筋，竹節鋼筋(SD420W)", "T", q("SD420"), P0("SD420"), "03210510028,連工帶料，含損耗5%及鋼筋間隔器"),
    ("壹.一.15", "鋼筋，竹節鋼筋(SD280W)", "T", q("SD280"), P0("SD280"), "03210310028,連工帶料，含損耗5%及鋼筋間隔器"),
    ("壹.一.16", "甲種預鑄溝蓋板150×100×23(含熱浸鍍鋅格柵蓋及框)", "塊", q("COVA"), AU("COVA"), "#,詳單價分析表壹.一.16"),
    ("壹.一.17", "乙種預鑄溝蓋板150×100×23", "塊", q("COVB"), AU("COVB"), "#,詳單價分析表壹.一.17"),
    ("壹.一.18", "塑膠包覆人孔踏步", "個", q("STEP"), AU("STEP"), "#,詳單價分析表壹.一.18"),
    ("壹.一.19", "伸縮縫(含填縫材)", "處", q("EJ"), AU("EJ"), "#,詳單價分析表壹.一.19"),
    ("壹.一.20", "新設側溝與既有排水銜接處理", "處", q("JOIN"), AU("JOIN"), "#,詳單價分析表壹.一.20"),
    ("壹.一.21", "9.5mm密級配AC面層t=5cm(路面修復)", "M2", q("AC"), AU("AC"), "0274205303,#,詳單價分析表壹.一.21"),
    ("壹.一.22", "施工中交通維持", "式", 1, AU("TRAF"), "01556#,詳單價分析表壹.一.22"),
    ("H2", "壹.二", "雜項工程"),
    ("壹.二.1", "工程告示牌", "塊", 1, P0("BOARD"), "03053C3024,可重複使用"),
    ("壹.二.2", "擋排水費", "式", 1, P0("DRAIN"), "02600C100401"),
    ("壹.二.3", "施工測量放樣", "案", 1, P0("SURV"), "01725C4005,#"),
    ("壹.二.4", "既有地下管線查證及保護", "式", 1, 5626, "#【待確認】"),
    ("壹.二.5", "混凝土鑽心試體取樣及試驗費", "式", 1, AU("CONC"), "03053C4105,#,詳單價分析表壹.二.5"),
    ("壹.二.6", "竹節鋼筋拉伸及抗彎試驗", "式", 1, AU("TEST"), "01450#,詳單價分析表壹.二.6"),
    ("壹.二.7", "工地清理，竣工前清理", "案", 1, P0("CLEAN"), "SWCB0200002,#"),
    ("壹.二.8", "施工機具搬運費", "趟", 1, P0("MOB"), "3450502200159,來回算一趟"),
    ("H2", "壹.三", "職業安全衛生費"),
    ("壹.三.1", "職業安全衛生告示牌", "面", 1, P0("OSHB"), "015831000ALG,#"),
    ("壹.三.2", "護欄，鋼管護欄(臨時，詳S-03、S-04)", "M", q("GUARD"), P0("PIPEG"), "01556F2001,租用"),
    ("壹.三.3", "工作手套", "雙", 20, 20, "215145511,#"),
    ("壹.三.4", "警示燈(太陽能)", "個", 10, 392, "0155682023A"),
    ("壹.三.5", "安全帽(硬質)", "頂", 10, 490, "01450A1380,#"),
    ("壹.三.6", "安全鞋", "雙", 10, 980, "0151001022,#"),
    ("壹.三.7", "警示帶(200公尺長)", "捲", 2, 490, "CC0000000011"),
    ("壹.三.8", "人員安全上下設備費", "處", 2, 14700, "SWCB0056,租用含拆裝"),
    ("壹.三.9", "職安人員", "人月", 3, 11220, "L000007000007,工期90日曆天"),
    ("壹.三.10", "職業安全衛生，教育訓練", "次", 1, 3920, "015743000E"),
    ("壹.三.11", "職業安全衛生，宣導", "次", 1, 1960, "015744000E"),
    ("壹.三.12", "職業安全衛生，保護器材，電感防止，漏電無熔線斷路器", "只", 1, 3920, "015742B106"),
    ("壹.三.13", "產品，職業安全衛生，保護器材，意外傷害救護設備，急救箱", "組", 1, 1176, "M015742A108"),
    ("壹.三.14", "其他安全衛生設施及管理維護費", "式", 1, 8126, "0158100315"),
    ("H2", "壹.四", "環境保護費"),
    ("壹.四.1", "環境保護，環保宣導", "式", 1, 7502, "0157260004"),
    ("壹.四.2", "車輛沖洗設施費", "式", 1, 11253, "0123456167,#"),
    ("壹.四.3", "工地清潔費", "式", 1, 11253, "0123456489,#"),
    ("壹.四.4", "工地灑水費", "式", 1, 7502, "0123456597,#"),
    ("壹.四.5", "其他環保措施及操作費", "式", 1, 4689, "0123456187,#"),
]
SEC = {}; cur = None; SUB = {}
for it in D:
    if it[0] in ("H1", "H2"):
        SUB[it[1]] = drow(it[1], it[2], "式")
        if it[0] == "H2": cur = it[1]; SEC[cur] = [None, None]
        continue
    no, nm, un, qn, up, code = it
    r0 = drow(no, nm, un, qn, up, "=ROUND(D{r}*E{r},0)", code)
    if SEC[cur][0] is None: SEC[cur][0] = r0
    SEC[cur][1] = RW[0]
S = {k: f"SUM(F{a}:F{b})" for k, (a, b) in SEC.items()}
S1, S2, S3, S4 = S["壹.一"], S["壹.二"], S["壹.三"], S["壹.四"]
r5 = drow("壹.五", "施工品質管理費(分段計價)", "式", 1, "=F{r}", f"=ROUND(({S1}+{S2})*參數!$C$2,0)")
r6 = drow("壹.六", "廠商利潤、管理及保險費(分段計價)", "式", 1, "=F{r}", f"=ROUND(({S1}+{S2})*參數!$C$3,0)")
r7 = drow("壹.七", "營業稅(壹.一~壹.六合計之5%)", "式", 1, "=F{r}", f"=ROUND(({S1}+{S2}+{S3}+{S4}+F{r5}+F{r6})*參數!$C$4,0)")
for rr in (r5, r6, r7): wd.cell(rr, 5).value = f"=F{rr}"
G = f"({S1}+{S2}+{S3}+{S4}+F{r5}+F{r6}+F{r7})"; G16 = f"({S1}+{S2}+{S3}+{S4}+F{r5}+F{r6})"
SUB["貳"] = drow("貳", "間接工程費", None)
IND = [("貳.一", "空氣汙染防制費(壹.一~壹.六合計之0.35%)", f"=ROUND({G16}*參數!$C$5,0)"),
       ("貳.二", "工程管理費", f"=ROUND(MIN({G},5000000)*參數!$C$6+MAX(MIN({G},25000000)-5000000,0)*0.015+MAX({G}-25000000,0)*0.01,0)"),
       ("貳.三", "委外設計服務費", "=參數!$C$7"), ("貳.四", "委外監造服務費", "=參數!$C$8")]
ir = []
for no, nm, f in IND:
    rr = drow(no, nm, "式", 1, None, f); wd.cell(rr, 5).value = f"=F{rr}"; ir.append(rr)
TOT = drow("", "總價(總計)", None, None, None, f"={G}+" + "+".join(f"F{x}" for x in ir))
for cc in range(1, 8): wd.cell(RW[0], cc).border = ALL
RW[0] += 2; PX(wd, RW[0], 1, f"本專案單價依據詳「單價依據」工作表；數量依工程數量計算表 v2.0。", 10)
pc_page(wd, "$1:$8", 95, 0.39, 0.0, 0.59, 1.10, 1.46, 0.59, 9)

# ======================================================================
# 參數（費率）
# ======================================================================
wr = wb.create_sheet("參數")
wr.append(["項目", "說明", "數值", "出處"])
for j in range(1, 5): C(wr, 1, j, wr.cell(1, j).value, 10, "center", True, fill=GRAY)
RATES = [("品管費率", "(壹.一+壹.二)×", 0.02, "象鼻段 18,931＝(822,762+123,782)×2% 核算相符；分段級距【待確認】"),
         ("利潤管理保險費率", "(壹.一+壹.二)×", 0.08, "使用者 2026-11-06 指定 8%"),
         ("營業稅率", "(壹.一~壹.六)×", 0.05, "營業稅法"),
         ("空污費率", "(壹.一~壹.六)×", 0.0035, "象鼻段 4,897＝1,399,006×0.35% 核算相符"),
         ("工程管理費率", "500 萬元以下部分×（超過部分 1.5%、1%）", 0.03, "工程管理費支用要點分段【待確認】"),
         ("委外設計服務費", "元", 312182, "使用者 2026-11-06 提供"), ("委外監造服務費", "元", 312181, "使用者 2026-11-06 提供")]
for i, row in enumerate(RATES, 2):
    for j, v in enumerate(row, 1): C(wr, i, j, v, h="right" if j == 3 else "left", fmt=("0.000%" if i <= 6 else "#,##0") if j == 3 else None)
for col, w in zip("ABCD", [18, 32, 11, 60]): wr.column_dimensions[col].width = w
page(wr, "1:1")

# ======================================================================
# 預算總表（版面依象鼻段：欄寬 A12.66 B27.33 C6.33 D12.11 E9.66 F14.44 G17.33；字級 10；6 列 42、7 列 30、8 列 24、項目 19.5）
# ======================================================================
wt = wb.create_sheet("預算總表", 0)
for col, w in zip("ABCDEFG", [12.66, 27.33, 6.33, 12.11, 9.66, 14.44, 17.33]): wt.column_dimensions[col].width = w
pc_head(wt, "總表[預算]", 7); pc_info(wt, 42.0)
PX(wt, 8, 1, "項 次", 10, "centerContinuous", wrap=True, border=ALL); wt.merge_cells("B8:E8"); PX(wt, 8, 2, "工  作  項  目", 10, "center", wrap=True, border=ALL)
for cc in (3, 4, 5): wt.cell(8, cc).border = ALL
PX(wt, 8, 6, "金額(元)", 10, "centerContinuous", wrap=True, border=ALL); PX(wt, 8, 7, "備註", 10, "centerContinuous", wrap=True, border=ALL)
wt.row_dimensions[8].height = 24.0
DS = "預算詳細表!"
SD = {k: f"SUM({DS}F{a}:F{b})" for k, (a, b) in SEC.items()}
G_DS = f"={SD['壹.一']}+{SD['壹.二']}+{SD['壹.三']}+{SD['壹.四']}+{DS}F{r5}+{DS}F{r6}+{DS}F{r7}"
TT = [("壹", "發包工程費", G_DS),
      ("壹.一", "施工費用(工作費+材料費)", f"=SUM({DS}F{SEC['壹.一'][0]}:F{SEC['壹.一'][1]})"),
      ("壹.二", "雜項工程", f"=SUM({DS}F{SEC['壹.二'][0]}:F{SEC['壹.二'][1]})"),
      ("壹.三", "職業安全衛生費", f"=SUM({DS}F{SEC['壹.三'][0]}:F{SEC['壹.三'][1]})"),
      ("壹.四", "環境保護費", f"=SUM({DS}F{SEC['壹.四'][0]}:F{SEC['壹.四'][1]})"),
      ("壹.五", "施工品質管理費(分段計價)", f"={DS}F{r5}"), ("壹.六", "廠商利潤、管理及保險費(分段計價)", f"={DS}F{r6}"),
      ("壹.七", "營業稅(壹.一~壹.六合計之5%)", f"={DS}F{r7}"), ("貳", "間接工程費", "=" + "+".join(f"{DS}F{x}" for x in ir)),
      ("貳.一", "空氣汙染防制費(壹.一~壹.六合計之0.35%)", f"={DS}F{ir[0]}"), ("貳.二", "工程管理費", f"={DS}F{ir[1]}"),
      ("貳.三", "委外設計服務費", f"={DS}F{ir[2]}"), ("貳.四", "委外監造服務費", f"={DS}F{ir[3]}"), ("", "總價(總計)", f"={DS}F{TOT}")]
for i, (no, nm, f) in enumerate(TT, 9):
    PX(wt, i, 1, no, 10, "center", border=PC_TOP); wt.merge_cells(start_row=i, start_column=2, end_row=i, end_column=5); PX(wt, i, 2, nm, 10, wrap=True, border=PC_TOP)
    for cc in (3, 4, 5): wt.cell(i, cc).border = PC_TOP
    PX(wt, i, 6, f, 10, "right", border=PC_TOP, fmt="#,##0"); PX(wt, i, 7, None, 10, border=PC_TOP)
    wt.row_dimensions[i].height = 19.5
i = 9 + len(TT)
PX(wt, i, 1, "註", 10, "center", border=PC_TOP)
for cc in range(2, 8): PX(wt, i, cc, None, 10, border=PC_TOP)
wt.row_dimensions[i].height = 19.5
for cc in range(1, 8): wt.cell(i, cc).border = ALL
NOTE_T = ["1.單價優先採象鼻段115年PCCES預算書同項單價，其次大湖範例115年、臺北市112年×K及單價分析，詳「單價依據」。",
          "2.數量依工程數量計算表v2.0；壹.五品管費、貳.二工程管理費分段級距【待確認】；壹.六利潤管理及保險費8%。",
          "3.會計科目、工程編號【待補】。"]
for t in NOTE_T:
    i += 1; wt.merge_cells(start_row=i, start_column=1, end_row=i, end_column=7); PX(wt, i, 1, t, 10); wt.row_dimensions[i].height = 19.5
pc_page(wt, "$1:$8", 95, 0.39, 0.0, 0.59, 1.02, 1.42, 0.59, 10)

# ======================================================================
# 假設與待確認
# ======================================================================
wn = wb.create_sheet("假設與待確認")
wn.append(["項次", "事項", "本預算採用", "影響項次"])
for j in range(1, 5): C(wn, 1, j, wn.cell(1, j).value, 10, "center", True, fill=GRAY)
NOTE = [("會計科目、工程編號", "未提供", "表頭"),
        ("210 混凝土", "大湖範例一般地區 3,398；象鼻段為偏遠地區 3,938，新社東山街採一般地區", "壹.一.11"),
        ("140、280 混凝土、SD420W 鋼筋", "象鼻段無此項，以 210／SD280 單價依臺北市價差或價比推算", "壹.一.10、12、14"),
        ("模板", "改採象鼻段「軀體模板」1,031 元/M2（v1.0 為臺北市丙種×K 442）", "壹.一.13"),
        ("鋼管護欄", "改採象鼻段租用 588 元/M（v1.0 為 1,568）", "壹.三.2"),
        ("餘方處理", "需運棄土資場，象鼻段為現地回填攤平不適用；暫用臺北市×K", "壹.一.3"),
        ("鋼軌樁、鋼襯版", "象鼻段用鋼版樁不同工法；沿用大湖範例 2,126／1,307", "壹.一.5、6"),
        ("擋排水費", "採象鼻段 1 式 9,377（v1.0 以 436 元/M×222 M 計）", "壹.二.2"),
        ("利潤管理保險費", "8%×(壹.一+壹.二)，使用者 2026-11-06 指定", "壹.六"),
        ("工期", "90 日曆天（使用者 2026-11-06 指定）：交通維持旗手 2 人×60 工作天、職安人員 3 人月", "壹.一.22、壹.三.9"),
        ("委外設計、監造服務費", "312,182／312,181（使用者 2026-11-06 提供）", "貳.三、貳.四")]
for i, (a, b, c) in enumerate(NOTE, 2):
    for j, v in enumerate((i - 1, a, b, c), 1): C(wn, i, j, v, h="center" if j in (1, 4) else "left")
for col, w in zip("ABCD", [6, 26, 66, 20]): wn.column_dimensions[col].width = w
page(wn, "1:1"); wn.page_setup.orientation = "landscape"

for w in (wb["單價依據"], wr, wn): refit(w)

# ======================================================================
# 封面（依使用者提供象鼻段預算書封面：計畫資料表、工程名稱框、簽署欄、主辦機關）
# ======================================================================
wc = wb.create_sheet("封面", 0)
for col, w in zip("ABCDE", [20, 22, 3, 14, 20]): wc.column_dimensions[col].width = w
for rr in (1, 2, 7, 8, 9, 12, 13, 14): wc.row_dimensions[rr].height = 20
INFO = [("計畫名稱", "【待補】"), ("施工地點", SITE), ("編製日期", "115年11月"), ("工程編號", "【待補】")]
for i, (k, v) in enumerate(INFO, 3):
    PX(wc, i, 1, k, 10, "distributed", border=ALL); wc.merge_cells(start_row=i, start_column=2, end_row=i, end_column=5)
    PX(wc, i, 2, v, 10, border=ALL)
    for cc in range(3, 6): wc.cell(i, cc).border = ALL
    wc.row_dimensions[i].height = 26
wc.merge_cells("A10:C11"); PX(wc, 10, 1, PJ, 16, "center", wrap=True)
wc.merge_cells("D10:E11"); PX(wc, 10, 4, "預算書\n（初稿）", 14, "center", wrap=True)
for rr in (10, 11):
    wc.row_dimensions[rr].height = 34
    for cc in range(1, 6): wc.cell(rr, cc).border = Border(left=thin if cc == 1 else None, right=thin if cc == 5 else None,
                                                              top=thin if rr == 10 else None, bottom=thin if rr == 11 else None)
PX(wc, 15, 1, "承辦技師\n執業圖記及簽署", 9, "center", wrap=True, border=ALL); PX(wc, 15, 2, "委託設計公司", 9, "center", border=ALL)
wc.merge_cells("D15:E15"); PX(wc, 15, 4, "工程主辦機關", 12, "center", border=ALL); wc.cell(15, 5).border = ALL
wc.row_dimensions[15].height = 34
SIGN = ["承辦", "複審", "科長", "秘書", "副局長", "局長"]
wc.merge_cells("A16:A21"); wc.merge_cells("B16:B21")
PX(wc, 16, 1, None, 10, border=ALL); PX(wc, 16, 2, "辰璟工程技術顧問有限公司", 10, "center", wrap=True, border=ALL)
for i, t in enumerate(SIGN, 16):
    PX(wc, i, 4, t, 9, "distributed", border=ALL); PX(wc, i, 5, None, 10, border=ALL)
    for cc in (1, 2): wc.cell(i, cc).border = ALL
    wc.row_dimensions[i].height = 40
wc.merge_cells("A22:E22"); PX(wc, 22, 1, AG, 14, "center"); wc.row_dimensions[22].height = 30
wc.print_area = "A1:E22"
wc.page_setup.paperSize = wc.PAPERSIZE_A4; wc.page_setup.orientation = "portrait"
wc.page_setup.fitToWidth = 1; wc.page_setup.fitToHeight = 1; wc.sheet_properties.pageSetUpPr.fitToPage = True
wc.page_margins = PageMargins(left=0.8, right=0.6, top=1.0, bottom=1.0, header=0.3, footer=0.3)
wc.print_options.horizontalCentered = True

# ======================================================================
# 計畫說明書（依使用者提供象鼻段範本；刪除經費來源、碳排說明，其餘依本案填寫，分兩頁）
# ======================================================================
from openpyxl.worksheet.pagebreak import Break
wx = wb.create_sheet("計畫說明書", 1)
for col, w in zip("ABCD", [9, 6, 6, 62]): wx.column_dimensions[col].width = w
wx.merge_cells("A1:D1"); PX(wx, 1, 1, AG, 14, "center", True); wx.row_dimensions[1].height = 24
wx.merge_cells("A2:D2"); PX(wx, 2, 1, "計畫說明書", 14, "center", True); wx.row_dimensions[2].height = 24
XR = [2]
def para(num, text, lvl=0, h=None):
    """lvl 0：大項（A 編號、B:D 內文）；1：子項（B 編號、C:D 內文）；2：段落（D 內文，縮排）"""
    r = XR[0] + 1; XR[0] = r
    if lvl == 0:
        PX(wx, r, 1, num, 12, "right"); wx.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4); PX(wx, r, 2, text, 12, wrap=True); w = 74
    elif lvl == 1:
        PX(wx, r, 2, num, 12, "right"); wx.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4); PX(wx, r, 3, text, 12, wrap=True); w = 68
    else:
        PX(wx, r, 4, text, 12, wrap=True); w = 62
    lines = max(1, math.ceil(tw(str(text), 12) / (w - 2)))
    wx.row_dimensions[r].height = h or max(22, lines * 22)
    return r
DSUM = "預算總表!"
para("一、", f"工程名稱：{PJ}")
para("二、", "工程地點：臺中市新社區東山街（協興街路口以北）")
para("三、", "計畫緣由：")
para("", "本工程位於臺中市新社區東山街與協興街路口以北路段，現況道路兩側既有排水為 50×80 公分及 50×85 公分暗溝，"
         "排水斷面不足，豪雨時逆流溢淹路面及沿線民宅，影響居民生活及通行安全，因此成立本工程。", 2)
para("四、", "災害類別與工法對策：")
para("1.", "災害類別：", 1)
para("", "既有側溝排水斷面不足，豪雨時溢淹路面及沿線民宅，影響居民生活及通行安全。", 2)
para("2.", "工法對策：", 1)
para("", "拆除既有暗溝，於東山街兩側新設箱涵式側溝 W×H＝110×100 公分（A 側 111.53 公尺、B 側 110.48 公尺）及側溝式箱涵集水井 4 座，"
         "施工期間設臨時擋土及交通維持，提升排水容量，減少路面及民宅溢淹。", 2)
para("五、", "主要工程內容：")
for i, t in enumerate([f"新設箱涵式側溝（W×H＝110×100 公分），計 {111.53 + 110.48:.2f} 公尺",
                       "側溝式箱涵集水井（內徑 150×150 公分），計 4 座",
                       f"既有暗溝打除，計 {QJ['DEM']:,.0f} 公尺",
                       f"預鑄溝蓋板，甲種 {QJ['COVA']:,.0f} 塊、乙種 {QJ['COVB']:,.0f} 塊",
                       f"臨時擋土設施，鋼軌樁 {QJ['PILE']:,.0f} 支、鋼襯版 {QJ['PLATE']:,.0f} 平方公尺",
                       f"AC 路面修復，計 {QJ['AC']:,.0f} 平方公尺"], 1):
    para(f"{i}.", t, 1)
para("六、", "經費內容：")
assert wb["預算總表"].cell(22, 2).value == "總價(總計)" and wb["預算總表"].cell(9, 2).value == "發包工程費" and wb["預算總表"].cell(17, 2).value == "間接工程費"
for num, lab, cell_ in [("(一)", "設計經費：", "F22"), ("1.", "發包工程費：", "F9"), ("2.", "間接工程費：", "F17")]:
    para(num, f'="{lab}"&TEXT({DSUM}{cell_},"#,##0")&" 元整"', 1)
BRK = XR[0]
para("七、", "招標方式：公開招標。")
para("八、", f"執行單位：{AG}")
para("九、", "工程效益：受益人口約 30 人、道路約 115 公尺、房舍約 10 棟。")
para("十、", "預定完工期限：90 日曆天")
para("十一、", f"施工位置：TWD97（X={CFG['plan']['center_world'][0]:.0f}，Y={CFG['plan']['center_world'][1]:.0f}）")
wx.row_breaks.append(Break(id=BRK))
wx.print_area = f"A1:D{XR[0]}"
wx.page_setup.paperSize = wx.PAPERSIZE_A4; wx.page_setup.orientation = "portrait"
wx.page_setup.fitToWidth = 1; wx.page_setup.fitToHeight = 0; wx.sheet_properties.pageSetUpPr.fitToPage = True
wx.page_margins = PageMargins(left=0.8, right=0.6, top=0.8, bottom=0.8, header=0.3, footer=0.3)

wb.save(OUT); print(OUT)
