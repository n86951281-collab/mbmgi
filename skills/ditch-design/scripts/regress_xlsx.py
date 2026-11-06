"""回歸比對：兩份 xlsx 逐工作表、逐格比對（公式文字與 Excel 重算後的值）。

用法：python regress_xlsx.py <基準.xlsx> <重跑.xlsx> [--values-only]
兩份都要先經 Excel COM 重算存檔（qty-budget/scripts/quantity_calc_pdf.ps1），值才有快取。
輸出：工作表清單差異、公式不同格數、值不同格數（數值容差 1e-6），列出前 20 筆；完全一致回傳碼 0。
"""
import sys
from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")


def cells(p, data_only):
    wb = load_workbook(p, data_only=data_only); out = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None: out[(ws.title, c.coordinate)] = c.value
    return [ws.title for ws in wb.worksheets], out


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)): return abs(a - b) <= 1e-6 * max(1.0, abs(a))
    return a == b


def compare(a, b, values_only=False, quiet=False, show=20):
    sa, fa = cells(a, False); sb, fb = cells(b, False)
    _, va = cells(a, True); _, vb = cells(b, True)
    fdiff = [] if values_only else [(k, fa.get(k), fb.get(k)) for k in sorted(set(fa) | set(fb)) if not same(fa.get(k), fb.get(k))]
    vdiff = [(k, va.get(k), vb.get(k)) for k in sorted(set(va) | set(vb)) if not same(va.get(k), vb.get(k))]
    if not quiet:
        if sa != sb: print("工作表不同：", sa, "／", sb)
        print(f"格數 {len(fa)}／{len(fb)}；公式或常數不同 {len(fdiff)} 格；重算值不同 {len(vdiff)} 格")
        for k, x, y in fdiff[:show]: print(f"  公式 {k[0]}!{k[1]}：{x!r} → {y!r}")
        for k, x, y in vdiff[:show]: print(f"  值   {k[0]}!{k[1]}：{x!r} → {y!r}")
    return dict(sheets_same=sa == sb, cells=(len(fa), len(fb)), formula_diff=len(fdiff), value_diff=len(vdiff), fdiff=fdiff, vdiff=vdiff)


if __name__ == "__main__":
    r = compare(sys.argv[1], sys.argv[2], "--values-only" in sys.argv)
    sys.exit(0 if r["sheets_same"] and r["formula_diff"] == 0 and r["value_diff"] == 0 else 1)
