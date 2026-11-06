"""P33 工程數量計算表（A4 直式），格式依使用者提供範本：象鼻段 數量計算表_1150922v1.xlsx
欄位：項目｜數量（算式＋詳圖號）｜≒｜總計｜單位；工項下依構造物分列，再列「合計」；總計取整數，鋼筋另列 kg 與 T。
數值依據：數量計算書 v1.5（標準圖 v3.2、設計圖冊 v3.1）。同時輸出 json 供預算書讀取（總計）。
用法：python -I qty_table.py --case <案件資料夾> --stamp YYYYMMDD_HHMM
（--case 省略時用本檔所在資料夾；總計 json 寫到案件資料夾 qty_table_<版次>.json）
參考實作：工項、算式、圖號都是 P33 東山街案的，新案逐項改寫；取整規則（各構造物先 ROUND 到整數再合計）全案一致。
"""
import sys, os, json, math, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.worksheet.page import PageMargins
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
CASE = os.path.abspath(arg("--case", HERE))
CFG = json.load(open(os.path.join(CASE, "case_config.json"), encoding="utf-8-sig"))
CODE = CFG.get("case_code", "P33"); SITE = CFG.get("site", "臺中市新社區")
stamp = arg("--stamp", datetime.datetime.now().strftime("%Y%m%d_%H%M"))
VER = "v2.0"
OUT = os.path.join(CFG["out_dir"], f"{CFG['file_prefix']}{stamp}_{CODE}_工程數量計算表_A4直式_{VER}.xlsx")
JOUT = os.path.join(CASE, f"qty_table_{VER}.json")

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

# 構造物名稱
SA, SB, WL, CB = "A 側箱涵式側溝", "B 側箱涵式側溝", "集水井（4 座）", "場鑄緣石"

big("一", "土方工程")
single(1, "構造物開挖，機械（詳土方計算）", "331.94+333.58", "331.94+333.58", "X-01、X-02", "m3", "EXC")
single(2, "構造物回填，回填及夯實（詳土方計算）", "59.04+59.19", "59.04+59.19", "X-01、X-02", "m3", "FILL")
item(3, "餘方自行處理，運棄土資場（挖方－回填）")
r += 1; cell(r, 1, ""); cell(r, 2, "{EXC}-{FILL}"); cell(r, 3, "≒", font=TNR, h="center")
cell(r, 4, f"=D{TOT['EXC']}-D{TOT['FILL']}", font=TNR, h="right", fmt=NUM); cell(r, 5, "m3", h="center"); TOT["SPOIL"] = r

big("二", "土木工程")
item(1, "既有暗溝打除（含廢料運棄）")
a = sub("A 側 50×80 暗溝", "113.43", "113.43", "P-01", "m"); b = sub("B 側 50×85 暗溝", "112.38", "112.38", "P-01", "m"); total([a, b], "m", "DEM")
item(2, "AC 路面切割")
a = sub(SA, "111.53", "111.53", "P-01", "m"); b = sub(SB, "110.48", "110.48", "P-01", "m"); total([a, b], "m", "CUT")
item(3, "臨時擋土設施，鋼軌樁 L=3m @100cm 打設及拔除")
a = sub(SA, "2*(112+1)", "2*(112+1)", "S-03", "支"); b = sub(SB, "2*(111+1)", "2*(111+1)", "S-03", "支"); total([a, b], "支", "PILE")
item(4, "臨時擋土設施，背插鐵板（鋼襯版）")
a = sub(SA, "2*111.53*1.53", "2*111.53*1.53", "S-03", "m2"); b = sub(SB, "2*110.48*1.53", "2*110.48*1.53", "S-03", "m2"); total([a, b], "m2", "PLATE")
item(5, "臨時鋼管護欄（設置及拆除）")
a = sub(SA, "112.91+2*2.30", "112.91+2*2.3", "S-03、S-04", "m"); b = sub(SB, "112.91+2*2.30", "112.91+2*2.3", "S-03、S-04", "m"); total([a, b], "m", "GUARD")
item(6, "140kgf/cm2 混凝土（墊層）")
a = sub(SA, "109.59*0.150", "109.59*0.15", "S-01", "m3"); b = sub(SB, "108.54*0.150", "108.54*0.15", "S-01", "m3")
c = sub(WL, "4*1.90*1.90*0.10", "4*1.9*1.9*0.1", "S-01", "m3"); total([a, b, c], "m3", "C140")
item(7, "210kgf/cm2 混凝土（溝體、集水井）")
a = sub(SA, "109.59*0.740", "109.59*0.74", "S-01", "m3"); b = sub(SB, "108.54*0.740", "108.54*0.74", "S-01", "m3")
c = sub(WL, "4*(1.90*1.90*1.50-1.50*1.50*1.30-1.10*0.20)", "4*(1.9*1.9*1.5-1.5*1.5*1.3-1.1*0.2)", "S-01", "m3"); total([a, b, c], "m3", "C210")
item(8, "280kgf/cm2 混凝土（場鑄緣石 20×15）")
a = sub(SA, "111.53*0.20*0.15", "111.53*0.2*0.15", "S-01、S-01-1", "m3"); b = sub(SB, "110.48*0.20*0.15", "110.48*0.2*0.15", "S-01、S-01-1", "m3"); total([a, b], "m3", "C280")
item(9, "普通模板，丙種（溝體、集水井、墊層、緣石）")
a = sub(SA, "109.59*(4.40+0.20)", "109.59*(4.4+0.2)", "S-01", "m2"); b = sub(SB, "108.54*(4.40+0.20)", "108.54*(4.4+0.2)", "S-01", "m2")
c = sub(WL, "4*(17.00+0.76)", "4*(17+0.76)", "S-01", "m2"); d = sub(CB, "(111.53+110.48)*0.30", "(111.53+110.48)*0.3", "S-01", "m2"); total([a, b, c, d], "m2", "FORM")
item(10, "鋼筋，竹節鋼筋（SD420W，D16）")
a = sub(SA, "109.59*37.44", "109.59*37.44", "S-01", "kg"); b = sub(SB, "108.54*37.44", "108.54*37.44", "S-01", "kg")
c = sub(WL, "4*200.93", "4*200.93", "S-01", "kg"); t = total([a, b, c], "kg", None, "合計(kg)")
r += 1; cell(r, 1, "合計(T)", h="right"); cell(r, 2, f"{{D{t}}}/1,000"); cell(r, 3, "≒", font=TNR, h="center")
cell(r, 4, f"=ROUND(D{t}/1000,2)", font=TNR, h="right", fmt=NUM); cell(r, 5, "T", h="center"); TOT["SD420"] = r
item(11, "鋼筋，竹節鋼筋（SD280W，D10、D13）")
a = sub(SA, "109.59*(42.41+31.11)", "109.59*(42.41+31.11)", "S-01", "kg"); b = sub(SB, "108.54*(42.41+31.11)", "108.54*(42.41+31.11)", "S-01", "kg")
c = sub(WL, "4*325.43", "4*325.43", "S-01", "kg"); d = sub(CB, "(111.53+110.48)*(3.78+2.02)", "(111.53+110.48)*(3.78+2.02)", "S-02", "kg")
t = total([a, b, c, d], "kg", None, "合計(kg)")
r += 1; cell(r, 1, "合計(T)", h="right"); cell(r, 2, f"{{D{t}}}/1,000"); cell(r, 3, "≒", font=TNR, h="center")
cell(r, 4, f"=ROUND(D{t}/1000,2)", font=TNR, h="right", fmt=NUM); cell(r, 5, "T", h="center"); TOT["SD280"] = r
item(12, "甲種預鑄溝蓋板 150×100×23（含熱浸鍍鋅格柵蓋及框）")
a = sub(SA, "112/5", "112/5", "S-01、S-02", "塊", "ROUNDUP"); b = sub(SB, "111/5", "111/5", "S-01、S-02", "塊", "ROUNDUP"); total([a, b], "塊", "COVA")
item(13, "乙種預鑄溝蓋板 150×100×23")
a = sub(SA, "112-23", "112-23", "S-01、S-02", "塊"); b = sub(SB, "111-23", "111-23", "S-01、S-02", "塊"); total([a, b], "塊", "COVB")
single(14, "側溝式箱涵集水井 內徑 150×150（#AC1、#AC2、#BC1、#BC2）", "4", "4", "P-01", "座", "WELL")
single(15, "塑膠包覆人孔踏步", "4*5", "4*5", "S-01、S-01-1", "個", "STEP")
item(16, "伸縮縫（含填縫材，每 10 m 一處）")
a = sub(SA, "109.59/10", "109.59/10", "S-01", "處", "ROUNDDOWN"); b = sub(SB, "108.54/10", "108.54/10", "S-01", "處", "ROUNDDOWN"); total([a, b], "處", "EJ")
single(17, "新設側溝與既有排水銜接處理（上、下游兩端各側 1 處）", "2*2", "2*2", "P-01", "處", "JOIN")
item(18, "9.5mm 密級配 AC 面層 t=5cm（路面修復，寬 0.40 m）")
a = sub(SA, "111.53*0.40", "111.53*0.4", "S-01、S-01-1", "m2"); b = sub(SB, "110.48*0.40", "110.48*0.4", "S-01、S-01-1", "m2"); total([a, b], "m2", "AC")

big("三", "雜項工程")
for i, (nm, un, key) in enumerate([("施工中交通維持（詳 S-04、S-05）", "式", "TRAF"), ("工程告示牌（詳 S-06）", "面", "BOARD"),
                                    ("職業安全衛生告示牌（詳 S-06）", "面", "OSHB"), ("施工期間臨時排水（擋排水費）", "式", "DRN"),
                                    ("施工測量放樣", "案", "SURV"), ("既有地下管線查證及保護", "式", "PIPE"),
                                    ("混凝土試體取樣及試驗", "式", "CONC"), ("鋼筋拉伸及彎曲試驗", "式", "TEST"),
                                    ("工地清理，竣工後清理", "案", "CLEAN"), ("施工機具搬運費", "趟", "MOB")], 1):
    r += 1
    cell(r, 1, i, font=TNR, h="center"); cell(r, 2, nm); cell(r, 3, "≒", font=TNR, h="center"); cell(r, 4, 1, font=TNR, h="right", fmt=NUM); cell(r, 5, un, h="center")
    TOT[key] = r
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
ws.oddFooter.center.text = "辰璟工程技術顧問有限公司"; ws.oddFooter.center.size = 12
ws.freeze_panes = "A6"
wb.save(OUT)

# ---- 總計（供預算書）：以 Python 同式計算
json.dump({k: ev(v) for k, v in TOT.items()}, open(JOUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(OUT)
