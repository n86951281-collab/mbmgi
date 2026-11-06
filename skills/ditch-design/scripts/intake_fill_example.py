"""測試／示範用：把案件條件表的「東山街範例」欄抄到「填寫值」欄，範例側溝集水井列抄到填寫列，另存新檔。

用法：python intake_fill_example.py <空白條件表.xlsx> <輸出.xlsx>
輸出檔再交給 intake_to_config.py，驗證轉檔（範例值中「（無…）」「【待補】」等文字也照抄）。
"""
import sys
from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")
src, out = sys.argv[1], sys.argv[2]
wb = load_workbook(src)
ws = wb["條件表"]; head = [c.value for c in ws[2]]; ex, fv = head.index("東山街範例") + 1, head.index("填寫值") + 1
n = 0
for r in range(3, ws.max_row + 1):
    v = ws.cell(r, ex).value
    if v not in (None, "") and ws.cell(r, head.index("設定鍵") + 1).value: ws.cell(r, fv).value = v; n += 1
wi = wb["側溝與集水井"]; hi = [c.value for c in wi[2]]; note = hi.index("備註") + 1
ex_rows = [r for r in range(3, wi.max_row + 1) if "範例" in str(wi.cell(r, note).value or "")]
dst = max(ex_rows) + 1
for k, r in enumerate(ex_rows):
    for c in range(1, len(hi) + 1):
        v = wi.cell(r, c).value
        wi.cell(dst + k, c).value = "P33 東山街值抄入" if c == note else v
wb.save(out)
print(f"填寫值 {n} 格、側溝與集水井 {len(ex_rows)} 列 → {out}")
