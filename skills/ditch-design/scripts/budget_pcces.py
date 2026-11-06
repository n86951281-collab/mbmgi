"""預算書 PCCES 版面（ditch-design，由 P33 budget_pcces 一般化；版面依象鼻段 (預算書)…_ap_bdgt_1150915v1.xls）：
封面、計畫說明書、預算總表、預算詳細表、預算單價分析表、單價依據、參數（費率）、假設與待確認。
案件值：
- 單價、單價分析、詳細表工項、計畫說明書文字：budget.unit_prices_file（templates/unit_prices.<案>.json）。
- 數量：work_dir/qty_table.json（qty_table.py，各工項總計取整）。
- 工期連動：work_dir/schedule.json（schedule.py）→ 交維旗手工數、職安人月、計畫說明書預定完工期限、假設表。
- 費率：budget.rates（qc 品管、profit 利潤管理保險、tax 營業稅、air 空污、mgmt 工程管理 500 萬以下部分）、委外設計／監造費 budget.design_fee／supervision_fee。
- 表頭：title_block.agency／project、budget.site／site_detail／plan_name／project_no／account／date_roc。
單價優先序：budget.price_sources（同機關同年度舊案 > 其他範例 > 他市×K），單價依據表逐列附出處。
用法：python budget_pcces.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
"""
import sys, os, json, math, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.worksheet.page import PageMargins
from openpyxl.utils import get_column_letter

CFG = dd.CFG; CODE = dd.CODE; BG = CFG["budget"]
stamp = dd.stamp
VER = dd.ver("budget")
QJ = dd.read_json("qty_table.json")
SCH = dd.read_json("schedule.json")
AG, PJ, SITE = CFG["title_block"]["agency"], CFG["title_block"]["project"], BG.get("site", "")
OUT = os.path.join(dd.OUT, f"{dd.PRE}{stamp}_{CODE}_預算書_PCCES格式_{VER}.xlsx")


def tpl(fn):
    """案件資料檔：先找本 SKILL templates/，再找 data_dir"""
    for d in (os.path.join(os.path.dirname(dd.HERE), "templates"), dd.DATA):
        if os.path.exists(os.path.join(d, fn)): return os.path.join(d, fn)
    raise SystemExit(f"找不到案件資料檔 {fn}")


UP = json.load(open(tpl(BG["unit_prices_file"]), encoding="utf-8-sig"))
_PS = (BG.get("price_sources") or []) + ["", "", ""]
SV = dict(SRC_X=_PS[0], SRC_D=_PS[1], SRC_TP=_PS[2], days=SCH["days"], basis=SCH.get("basis", ""), flagmen=SCH["flagmen"],
          flag_work_days=SCH["flag_work_days"], osh_months=SCH["osh_months"])


def fmt_s(t):
    """文字代入（出處標籤、工期連動值）；只換已知鍵，其餘大括號原樣保留"""
    if not isinstance(t, str): return t
    for k, v in SV.items(): t = t.replace("{" + k + "}", str(v))
    return t


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
    ws.oddFooter.left.text = "編製：" + dd.COMPANY; ws.oddFooter.left.size = 12; ws.oddFooter.left.font = "標楷體,標準"
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
SRC = [tuple(fmt_s(v) for v in x) for x in UP["src"]]
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
    for r, (a, b, e, f) in ((6, ("工程名稱", PJ, "會計科目", BG.get("account", "【待補】"))), (7, ("施工地點", SITE, "工程編號", BG.get("project_no", "【待補】")))):
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
PX(wa, 7, 1, "項次：", v_="top"); PX(wa, 7, 2, f"工程編號：{BG.get('project_no', '【待補】')}", v_="top"); wa.row_dimensions[7].height = 15.75
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
def tok(v):
    """{P:代號}→單價依據儲存格、{A:鍵}→單價分析儲存格、{S:鍵}／{q:鍵}→工期、數量值"""
    if not isinstance(v, str): return v
    if v.startswith("{S:") and v.endswith("}"): return SCH[v[3:-1]]
    if v.startswith("{q:") and v.endswith("}"): return QJ[v[3:-1]]
    for k in sorted(U, key=len, reverse=True): v = v.replace("{P:" + k + "}", U[k])
    for k in A: v = v.replace("{A:" + k + "}", A[k])
    return fmt_s(v)
for an in UP["analysis"]:
    A[an["key"]] = analysis(an["no"], fmt_s(an["name"]), an["unit"], an["code"], [tuple(tok(v) for v in ln) for ln in an["lines"]])
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
D = [tuple(x) if x[0] in ("H1", "H2") else tuple(tok(v) for v in x) for x in UP["detail"]]
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
RW[0] += 2; PX(wd, RW[0], 1, f"本專案單價依據詳「單價依據」工作表；數量依工程數量計算表 {dd.ver('qty_table')}。", 10)
pc_page(wd, "$1:$8", 95, 0.39, 0.0, 0.59, 1.10, 1.46, 0.59, 9)

# ======================================================================
# 參數（費率）
# ======================================================================
wr = wb.create_sheet("參數")
wr.append(["項目", "說明", "數值", "出處"])
for j in range(1, 5): C(wr, 1, j, wr.cell(1, j).value, 10, "center", True, fill=GRAY)
RT, RN = BG["rates"], BG.get("rate_notes", {})
RATES = [("品管費率", "(壹.一+壹.二)×", RT["qc"], RN.get("qc", "")),
         ("利潤管理保險費率", "(壹.一+壹.二)×", RT["profit"], RN.get("profit", "")),
         ("營業稅率", "(壹.一~壹.六)×", RT.get("tax", 0.05), RN.get("tax", "營業稅法")),
         ("空污費率", "(壹.一~壹.六)×", RT["air"], RN.get("air", "")),
         ("工程管理費率", "500 萬元以下部分×（超過部分 1.5%、1%）", RT["mgmt"], RN.get("mgmt", "")),
         ("委外設計服務費", "元", BG.get("design_fee", 0), RN.get("design_fee", "【待補】")),
         ("委外監造服務費", "元", BG.get("supervision_fee", 0), RN.get("supervision_fee", "【待補】"))]
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
_pf = RT["profit"] * 100
NOTE_T = [t.replace("{QVER}", dd.ver("qty_table")).replace("{PROFIT}", f"{_pf:g}%") for t in UP["notes_total"]]
for t in NOTE_T:
    i += 1; wt.merge_cells(start_row=i, start_column=1, end_row=i, end_column=7); PX(wt, i, 1, t, 10); wt.row_dimensions[i].height = 19.5
pc_page(wt, "$1:$8", 95, 0.39, 0.0, 0.59, 1.02, 1.42, 0.59, 10)

# ======================================================================
# 假設與待確認
# ======================================================================
wn = wb.create_sheet("假設與待確認")
wn.append(["項次", "事項", "本預算採用", "影響項次"])
for j in range(1, 5): C(wn, 1, j, wn.cell(1, j).value, 10, "center", True, fill=GRAY)
NOTE = [tuple(fmt_s(v) for v in x) for x in UP["assumptions"]]
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
INFO = [("計畫名稱", BG.get("plan_name", "【待補】")), ("施工地點", SITE), ("編製日期", BG.get("date_roc", CFG["title_block"].get("date_roc", ""))), ("工程編號", BG.get("project_no", "【待補】"))]
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
PX(wc, 16, 1, None, 10, border=ALL); PX(wc, 16, 2, dd.COMPANY, 10, "center", wrap=True, border=ALL)
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
PLN = UP["plan"]
import plan_base as PB
_LEN = {k: round(float(PB.np.hypot(*(PB.SIDES[k][0][1] - PB.SIDES[k][0][0]))), 2) for k in PB.KEYS}
PV = dict(W_cm=dd.P_["W"] * 100, H_cm=dd.P_["H"] * 100, well_cm=dd.P_["well_in"] * 100, n_wells=len(dd.WELLS), QJ=QJ,
          L_total=sum(_LEN.values()), side_lengths="、".join(f"{k} 側 {v:.2f} 公尺" for k, v in _LEN.items()))
para("一、", f"工程名稱：{PJ}")
para("二、", f"工程地點：{BG.get('site_detail', SITE)}")
para("三、", "計畫緣由：")
para("", PLN["reason"].format(**PV), 2)
para("四、", "災害類別與工法對策：")
para("1.", "災害類別：", 1)
para("", PLN["disaster"].format(**PV), 2)
para("2.", "工法對策：", 1)
para("", PLN["method"].format(**PV), 2)
para("五、", "主要工程內容：")
for i, t in enumerate(PLN["items"], 1):
    para(f"{i}.", t.format(**PV), 1)
para("六、", "經費內容：")
assert wb["預算總表"].cell(22, 2).value == "總價(總計)" and wb["預算總表"].cell(9, 2).value == "發包工程費" and wb["預算總表"].cell(17, 2).value == "間接工程費"
for num, lab, cell_ in [("(一)", "設計經費：", "F22"), ("1.", "發包工程費：", "F9"), ("2.", "間接工程費：", "F17")]:
    para(num, f'="{lab}"&TEXT({DSUM}{cell_},"#,##0")&" 元整"', 1)
BRK = XR[0]
para("七、", "招標方式：" + PLN.get("tender", "公開招標。"))
para("八、", f"執行單位：{AG}")
para("九、", "工程效益：" + PLN.get("benefit", "【待補】"))
para("十、", f"預定完工期限：{SCH['days']} 日曆天")
para("十一、", f"施工位置：TWD97（X={CFG['plan']['center_world'][0]:.0f}，Y={CFG['plan']['center_world'][1]:.0f}）")
wx.row_breaks.append(Break(id=BRK))
wx.print_area = f"A1:D{XR[0]}"
wx.page_setup.paperSize = wx.PAPERSIZE_A4; wx.page_setup.orientation = "portrait"
wx.page_setup.fitToWidth = 1; wx.page_setup.fitToHeight = 0; wx.sheet_properties.pageSetUpPr.fitToPage = True
wx.page_margins = PageMargins(left=0.8, right=0.6, top=0.8, bottom=0.8, header=0.3, footer=0.3)

wb.save(OUT); print(OUT)
