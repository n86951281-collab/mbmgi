"""圖冊 PDF 合併（ditch-design，由 P33 merge_set 一般化）：封面＋各圖 PDF 依圖目錄順序合併，每張加書籤。
各圖 PDF 依「同一個 --stamp」在 out_dir 找（run_all.py 全部用同一個 stamp）；也可用 --src-stamp 指定各圖產出時的 stamp。
頁數要和圖目錄（work_dir/toc.json）一致，不一致就停。
用法：python merge_set.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM] [--src-stamp YYYYMMDD_HHMM]
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
from pypdf import PdfReader, PdfWriter

TOC = dd.read_json("toc.json")
SS = dd.arg("--src-stamp", dd.stamp)


def parts(ext):
    """(檔案, 頁數)：圖冊順序＝G（前頁 2）、L（0/1）、P-01、PP、X、S；頁數依圖目錄"""
    n = lambda pre: sum(1 for t in TOC if t[0].startswith(pre))
    g = dd.GROUND
    pat = [(f"_A3_工程位置圖及一般說明_{dd.ver('front')}_TWD97_GENIE", n("G-")),
           (f"_A3_地籍套繪圖_1-500_{dd.ver('cadastral')}_TWD97_GENIE", n("L-")),
           (f"_A3_新設側溝平面配置圖_1-*_{dd.ver('plan_view')}_TWD97_GENIE", n("P-")),
           (f"_A3_平面及縱斷面圖_*_{dd.ver('plan_profile')}_{g}_TWD97_GENIE", n("PP-")),
           (f"_A3_設計橫斷面圖_{dd.ver('cross_sections')}_{g}_TWD97_GENIE", n("X-")),
           (f"_A3_標準圖S*_{dd.ver('standard')}_TWD97_GENIE", n("S-"))]
    out = []
    for p, k in pat:
        if k == 0: continue
        f = glob.glob(os.path.join(dd.OUT, glob.escape(f"{dd.PRE}{SS}") + p + ext))
        if len(f) != 1: raise SystemExit(f"找不到或不只一個：{dd.PRE}{SS}{p}{ext} → {f}")
        out.append((f[0], k))
    return out


def cover(ext):
    f = os.path.join(dd.OUT, f"{dd.PRE}{SS}_A3_設計圖冊封面_{dd.ver('cover')}{ext}")
    if not os.path.exists(f): raise SystemExit(f"缺封面 {f}（先跑 cover_sheet.py）")
    return f


if __name__ == "__main__":
    w = PdfWriter(); k = 0
    for p in PdfReader(cover(".pdf")).pages: w.add_page(p); w.add_outline_item("封面", 0)
    for fn, n in parts(".pdf"):
        r = PdfReader(fn)
        if len(r.pages) != n: raise SystemExit(f"{fn}：頁數 {len(r.pages)}，圖目錄應為 {n}")
        for p in r.pages:
            w.add_page(p); no, nm, _ = TOC[k]; w.add_outline_item(f"{k+1:02d} {no} {nm}", k + 1); k += 1
    if k != len(TOC): raise SystemExit(f"合併 {k} 頁，圖目錄 {len(TOC)} 張，不符")
    out = os.path.join(dd.OUT, f"{dd.PRE}{dd.stamp}_A3_設計圖冊_{dd.ver('set')}_{dd.GROUND}.pdf")
    if os.path.exists(out): raise SystemExit(f"{out} 已存在，不覆蓋")
    w.write(out)
    chk = PdfReader(out)
    sizes = {(round(float(p.mediabox.width) / 72 * 25.4), round(float(p.mediabox.height) / 72 * 25.4)) for p in chk.pages}
    print("頁數：", len(chk.pages), "紙張(mm)：", sizes); print("PDF：", out)
