"""工程數量計算表（ditch-design，由 P33 qty_table 一般化；A4 直式），格式依使用者範本（象鼻段 數量計算表_1150922v1.xlsx）。
欄位：項目｜數量（算式＋詳圖號）｜≒｜總計｜單位；工項下依構造物分列，再列「合計」；總計取整數，鋼筋另列 kg 與 T。
工項：qty.table_file（templates/qty_table.<案>.py，以 exec 執行）。工程名稱、主辦機關、施工地點（budget.site）、版次：設定檔。
同時輸出 work_dir/qty_table.json（各工項總計，Python 同式計算），給 budget_pcces.py、schedule.py 讀。
用法：python qty_table.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
"""
import sys, os, json, math, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.worksheet.page import PageMargins
from openpyxl.utils import get_column_letter

CFG = dd.CFG; CODE = dd.CODE; SITE = dd.get("budget.site", "")
stamp = dd.stamp
VER = dd.ver("qty_table")
OUT = os.path.join(dd.OUT, f"{dd.PRE}{stamp}_{CODE}_工程數量計算表_A4直式_{VER}.xlsx")
JOUT = dd.work("qty_table.json")


def tpl(fn):
    """案件資料檔：先找本 SKILL templates/，再找 data_dir"""
    for d in (os.path.join(os.path.dirname(dd.HERE), "templates"), dd.DATA):
        if os.path.exists(os.path.join(d, fn)): return os.path.join(d, fn)
    raise SystemExit(f"找不到案件資料檔 {fn}")


KAI, TNR, DK = "標楷體", "Times New Roman", "000000"
thin = Side(style="thin", color="000000"); ALL = Border(left=thin, right=thin, top=thin, bottom=thin)
wb = Workbook(); ws = wb.active; ws.title = "數量計算表"
for col, w in zip("ABCDE", [24, 68, 6, 14, 10]): ws.column_dimensions[col].width = w

def cell(r, c, v, font=KAI, size=14, bold=False, h="left", border=True, fmt=None, wrap=True):
    x = ws.cell(r, c, v); x.font = Font(name=font, size=size, bold=bold, color=DK)
    x.alignment = Alignment(horizontal=h, vertical="center", wrap_text=wrap)
    if border: x.border = ALL
    if fmt: x.number_format = fmt
    return x

# ---- 表頭（範本 1～5 列）
ws.merge_cells("A1:E1"); cell(1, 1, CFG["title_block"]["agency"], size=20, h="center", border=False)
ws.merge_cells("A2:E2"); cell(2, 1, "工程數量計算表", size=25, bold=True, h="center", border=False)
cell(3, 1, "工程名稱：", h="center", border=False); ws.merge_cells("B3:E3"); cell(3, 2, CFG["title_block"]["project"], border=False)
cell(4, 1, "施工地點：", h="center", border=False); ws.merge_cells("B4:E4"); cell(4, 2, SITE, border=False)
for c in range(1, 6): ws.cell(4, c).border = Border(bottom=thin)
for c, t in zip(range(1, 6), ["項目", "數量", "", "總計", "單位"]): cell(5, c, t, size=18, bold=True, h="center")
ws.merge_cells("B5:C5")

r = 5; TOT = {}
NUM = "#,##0.00"
def big(no, name):
    global r; r += 1
    cell(r, 1, no, h="center", size=16, bold=True); cell(r, 2, name, size=16, bold=True)
    for c in (3, 4, 5): cell(r, c, None)
def item(no, name):
    global r; r += 1
    cell(r, 1, no, font=TNR, h="center"); cell(r, 2, name)
    for c in (3, 4, 5): cell(r, c, None)
def sub(part, expr_txt, expr_xl, ref, unit, rnd="ROUND"):
    """構造物分列：B＝算式（詳圖號）、D＝ROUND(算式,0)"""
    global r; r += 1
    cell(r, 1, part); cell(r, 2, f"{expr_txt} (詳圖號{ref})" if ref else expr_txt)
    cell(r, 3, "≒", font=TNR, h="center"); cell(r, 4, f"={rnd}({expr_xl},0)", font=TNR, h="right", fmt=NUM); cell(r, 5, unit, h="center")
    return r
def total(rows, unit, key=None, label="合計"):
    global r; r += 1
    cell(r, 1, label, h="right"); cell(r, 2, "+".join(f"{{D{x}}}" for x in rows))     # 先放占位，存檔前換成數值文字
    cell(r, 3, "≒", font=TNR, h="center"); cell(r, 4, "=" + "+".join(f"D{x}" for x in rows), font=TNR, h="right", fmt=NUM); cell(r, 5, unit, h="center")
    if key: TOT[key] = r
    return r
def single(no, name, expr_txt, expr_xl, ref, unit, key, rnd="ROUND"):
    """單列工項（無構造物分列）"""
    item(no, name)
    rr = sub("", expr_txt, expr_xl, ref, unit, rnd); TOT[key] = rr; return rr

# 工項（案件資料檔 qty.table_file，見 templates/qty_table.<案>.py）
exec(compile(open(tpl(CFG["qty"]["table_file"]), encoding="utf-8").read(), CFG["qty"]["table_file"], "exec"), globals())
LAST = r

# ---- 「合計」算式文字：以 Python 依同一公式算出各列總計，填回 B 欄（與 D 欄公式一致）
def ev(rr):
    f = ws.cell(rr, 4).value
    if isinstance(f, (int, float)): return f
    f = f.lstrip("=")
    for fn in ("ROUNDUP", "ROUNDDOWN", "ROUND"):
        pass
    import re
    def D(m): return repr(ev(int(m.group(1))))
    f = re.sub(r"D(\d+)", D, f)
    f = f.replace("ROUNDUP(", "_ru(").replace("ROUNDDOWN(", "_rd(").replace("ROUND(", "_rn(")
    def _rn(x, n): return math.floor(x * 10 ** n + 0.5 + 1e-9) / 10 ** n
    def _ru(x, n): return math.ceil(x * 10 ** n - 1e-9) / 10 ** n
    def _rd(x, n): return math.floor(x * 10 ** n + 1e-9) / 10 ** n
    # eval 僅用於本程式自己產生的算術式（數字、+-*/()、取整函式），不含外部輸入；且不提供 builtins
    return eval(f, {"__builtins__": {}, "_rn": _rn, "_ru": _ru, "_rd": _rd})
import re
def fmtn(v): return f"{v:,.0f}" if abs(v - round(v)) < 1e-9 else f"{v:,.2f}"
for rr in range(6, LAST + 1):
    b = ws.cell(rr, 2).value
    if isinstance(b, str) and "{" in b:
        b = re.sub(r"\{D(\d+)\}", lambda m: fmtn(ev(int(m.group(1)))), b)
        b = re.sub(r"\{(\w+)\}", lambda m: fmtn(ev(TOT[m.group(1)])), b)
        ws.cell(rr, 2).value = b

# ---- 列高（固定列高，依文字量估）
def tw(s, pt): return sum((2.15 if ord(ch) > 0x2E80 else 1.15) * pt / 11.0 for ch in s)
for rr in range(1, LAST + 1):
    need, pt = 1, 14
    for cc in range(1, 6):
        v = ws.cell(rr, cc).value
        if v is None or (isinstance(v, str) and v.startswith("=")): continue
        pt = ws.cell(rr, cc).font.size or 14
        w = ws.column_dimensions[get_column_letter(cc)].width
        if rr in (1, 2) or (rr in (3, 4) and cc == 2) : w = sum(ws.column_dimensions[x].width for x in "ABCDE") if rr in (1, 2) else sum(ws.column_dimensions[x].width for x in "BCDE")
        need = max(need, math.ceil(tw(str(v), pt) / max(w - 3, 1)))
    ws.row_dimensions[rr].height = max(30, round(need * pt * 1.45 + 8))

# ---- 版面（範本：A4 直式、表頭列重複、頁碼右上）
ws.print_title_rows = "1:5"; ws.print_area = f"A1:E{LAST}"
ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.orientation = "portrait"
ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.75, bottom=0.75, header=0.3, footer=0.3)
ws.oddHeader.right.text = "第 &P 頁，共 &N 頁"; ws.oddHeader.right.size = 12; ws.oddHeader.right.font = "標楷體,標準"
ws.oddFooter.center.text = dd.COMPANY; ws.oddFooter.center.size = 12
ws.freeze_panes = "A6"
wb.save(OUT)

# ---- 總計（供預算書）：以 Python 同式計算
json.dump({k: ev(v) for k, v in TOT.items()}, open(JOUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(OUT)
