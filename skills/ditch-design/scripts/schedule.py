"""工期（ditch-design 新增）：工期與連動參數（交維旗手工數、職安人月），輸出 xlsx（保留公式）＋ work_dir/schedule.json。

規則：
- schedule.days 有給：照用（使用者指定），推算表仍列出供對照。
- 沒給：依數量（work_dir/qty_table.json、側溝長）× 每日施工量 schedule.rates 推算，各工項依序施工（不重疊，偏保守）；
  rates 沒給的項目用本程式預設值，並標【假設】請使用者確認。
- 連動：旗手工數＝flagmen × flag_work_days（沒給時＝工期×2/3 取整【假設】）；職安人月＝ROUNDUP(工期÷30)。
  budget_pcces.py 讀 schedule.json 的 days、flag_man_days、osh_months，計畫說明書「預定完工期限」同一來源。
用法：python schedule.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM] [--pdf]
  --pdf：接著用 Excel COM 重算、存檔、匯出 PDF（qty-budget/scripts/quantity_calc_pdf.ps1）。
"""
import sys, os, math, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.page import PageMargins

SC = dd.CFG.get("schedule", {})
QJ = dd.read_json("qty_table.json")
import plan_base as PB
L_DITCH = sum(round(float(PB.np.hypot(*(PB.SIDES[k][0][1] - PB.SIDES[k][0][0]))), 2) for k in PB.KEYS)

# (鍵, 工項, 數量, 單位, 施工量預設, 施工量單位)；「m/日」工作天＝數量÷施工量，「日/座」工作天＝數量×施工量；預設值為一般小型側溝工程經驗值【假設】
DEFAULT = [("prep", "施工準備（放樣、管線查證、交維佈設）", 1, "式", 7.0, "日/式"),
           ("demolish", "既有側溝打除", QJ.get("DEM", 0), "m", 30.0, "m/日"),
           ("pile", "臨時擋土樁打設", QJ.get("PILE", 0), "支", 40.0, "支/日"),
           ("ditch", "新設側溝（開挖、墊層、溝體、蓋板）", L_DITCH, "m", 6.0, "m/日"),
           ("well", "集水井", QJ.get("WELL", len(dd.WELLS)), "座", 4.0, "日/座"),
           ("ac", "AC 路面修復", QJ.get("AC", 0), "m²", 150.0, "m²/日"),
           ("cleanup", "拔樁、完工清理", 1, "式", 5.0, "日/式")]
RATES = SC.get("rates") or {}
rows = []
for k, nm, q, u, r_def, ru in DEFAULT:
    given = k in RATES
    rows.append((nm, q, u, float(RATES[k]) if given else r_def, ru, "設定檔 schedule.rates" if given else "【假設】預設每日施工量，請確認"))
def wdays(q, r, ru): return math.ceil((q * r if ru.startswith("日/") else q / r) - 1e-9)   # 日/座：數量×；m/日：數量÷
est = sum(wdays(q, r, ru) for _, q, _, r, ru, _ in rows)
given_days = SC.get("days")
DAYS = int(given_days) if given_days else est
BASIS = SC.get("basis", "使用者指定") if given_days else "依每日施工量推算（含【假設】值）"
FLAGMEN = int(SC.get("flagmen", 2))
FWD = SC.get("flag_work_days")
FWD_ASSUMED = FWD is None
FWD = int(FWD) if FWD is not None else int(round(DAYS * 2 / 3))
OUTJ = dict(days=DAYS, basis=BASIS, estimated_days=est, calendar=SC.get("calendar", "日曆天"), flagmen=FLAGMEN, flag_work_days=FWD,
            flag_man_days=FLAGMEN * FWD, osh_months=math.ceil(DAYS / 30), assumed=[r[0] for r in rows if r[5].startswith("【假設】")] +
            (["旗手工作天（工期×2/3）"] if FWD_ASSUMED else []))
dd.write_json("schedule.json", OUTJ)

# ---------------- xlsx（Excel 規則：表頭 25 pt、內文 14 pt、灰藍表頭、列高 30、凍結、頁首案名、頁尾公司） ----------------
FN = "微軟正黑體"; DK = "1F2D3A"; HF = PatternFill("solid", fgColor="3E5C76"); SF = PatternFill("solid", fgColor="D8DEE4")
thin = Side(style="thin", color="7A8A99"); BD = Border(left=thin, right=thin, top=thin, bottom=thin)
def cell(ws, r, c, v, size=14, bold=False, fill=None, fmt=None, h="center", color=DK):
    x = ws.cell(r, c, v); x.font = Font(name=FN, size=size, bold=bold, color=color); x.border = BD
    x.alignment = Alignment(horizontal=h, vertical="center", wrap_text=True)
    if fill: x.fill = fill
    if fmt: x.number_format = fmt
    return x
wb = Workbook(); ws = wb.active; ws.title = "工期"
H = ["項次", "工項", "數量", "單位", "施工量", "施工量單位", "工作天", "依據"]
for j, t in enumerate(H, 1): cell(ws, 1, j, t, 25, True, HF, color="FFFFFF")
ws.row_dimensions[1].height = 82                                    # 25 pt 表頭兩行（窄欄換行）
for i, (nm, q, u, r, ru, src) in enumerate(rows, 2):
    for j, v in enumerate([i - 1, nm, q, u, r, ru, f"=ROUNDUP(C{i}*E{i},0)" if ru.startswith("日/") else f"=ROUNDUP(C{i}/E{i},0)", src], 1):
        cell(ws, i, j, v, fmt={3: "#,##0.00", 5: "0.00", 7: "0"}.get(j), h="left" if j in (2, 8) else "center")
    ws.row_dimensions[i].height = 30 if len(nm) < 16 and len(src) < 18 else 48
n1 = len(rows) + 1; r = n1 + 1
cell(ws, r, 1, "推算工期（各工項依序施工）", bold=True, fill=SF); ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
cell(ws, r, 7, f"=SUM(G2:G{n1})", bold=True, fill=SF, fmt="0"); cell(ws, r, 8, "日曆天", fill=SF, h="left"); R_EST = r
r += 1; cell(ws, r, 1, "採用工期", bold=True, fill=SF); ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
cell(ws, r, 7, int(given_days) if given_days else f"=G{R_EST}", bold=True, fill=SF, fmt="0"); cell(ws, r, 8, BASIS, fill=SF, h="left"); R_D = r
r += 2
for j, t in enumerate(["項次", "連動項目", "數值", "單位", "", "", "", "公式／依據"], 1): cell(ws, r, j, t, 18, True, SF)
ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=7); ws.row_dimensions[r].height = 56
LINK = [("旗手人數", FLAGMEN, "人", "schedule.flagmen"),
        ("旗手工作天", FWD if not FWD_ASSUMED else f"=ROUND(G{R_D}*2/3,0)", "天", "schedule.flag_work_days" if not FWD_ASSUMED else "【假設】工期×2/3"),
        ("交通指揮人員工數", None, "工", "旗手人數×旗手工作天（預算書 壹.一.22 單價分析）"),
        ("職安人員", f"=ROUNDUP(G{R_D}/30,0)", "人月", "工期÷30 取整（預算書 壹.三.9）")]
r0 = r + 1
for i, (nm, v, u, src) in enumerate(LINK, 1):
    r += 1
    if nm == "交通指揮人員工數": v = f"=C{r0}*C{r0 + 1}"
    for j, x in enumerate([i, nm, v, u, None, None, None, src], 1): cell(ws, r, j, x, h="left" if j in (2, 8) else "center", fmt="0" if j == 3 else None)
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=7); ws.row_dimensions[r].height = 30 if len(src) < 24 else 48
for col, w in zip("ABCDEFGH", [8, 40, 14, 9, 16, 20, 14, 56]): ws.column_dimensions[col].width = w
ws.freeze_panes = "C2"; ws.print_title_rows = "1:1"
ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.orientation = "landscape"
ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.8, bottom=0.7, header=0.3, footer=0.3)
ws.oddHeader.center.text = f"{dd.TB['project']}　工期"; ws.oddHeader.center.size = 12
ws.oddFooter.center.text = f"{dd.COMPANY}　第 &P 頁／共 &N 頁"; ws.oddFooter.center.size = 12
OUT = os.path.join(dd.OUT, f"{dd.PRE}{dd.stamp}_{dd.CODE}_工期推算_{dd.ver('schedule')}.xlsx")
if os.path.exists(OUT): raise SystemExit(f"{OUT} 已存在，不覆蓋")
wb.save(OUT)
print(f"工期 {DAYS} 日曆天（{BASIS}）；推算 {est} 天；旗手 {FLAGMEN} 人×{FWD} 天＝{FLAGMEN * FWD} 工；職安 {OUTJ['osh_months']} 人月")
if OUTJ["assumed"]: print("【假設】待確認：", "、".join(OUTJ["assumed"]))
print("XLSX：", OUT); print("JSON：", dd.work("schedule.json"))
if "--pdf" in sys.argv:
    ps1 = os.path.join(dd.SKILLS, "qty-budget", "scripts", "quantity_calc_pdf.ps1")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, "-xlsx", OUT, "-dumpdir", dd.WORK], check=True)
