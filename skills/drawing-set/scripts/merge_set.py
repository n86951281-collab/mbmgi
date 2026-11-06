"""P33 新社東山街側溝：把最新版各圖 PDF 合併成一份列印用圖冊（書籤依圖號）。
圖目錄已在第 1 張「工程位置圖及圖目錄」（front_sheets.py，目錄內容存 toc_v1.json），本檔不再另產目錄頁。
用法：python -I merge_set.py --stamp YYYYMMDD_HHMM
各圖檔名寫在 PARTS，換版時改這裡。
"""
import sys, os, json, datetime
from pypdf import PdfReader, PdfWriter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "case_config.json"), encoding="utf-8-sig"))
OUT = CFG["out_dir"]; PRE = CFG["file_prefix"]
stamp = sys.argv[sys.argv.index("--stamp") + 1] if "--stamp" in sys.argv else datetime.datetime.now().strftime("%Y%m%d_%H%M")
TOC = json.load(open(os.path.join(HERE, "toc_v2.json"), encoding="utf-8"))

PARTS = [   # 檔名, 頁數（2026-11-06：字寬依 GENIE 實測校正、圖標欄工程名稱不超框、G-02 不溢出）
    (f"{PRE}20261106_2100_A3_工程位置圖及一般說明_v2.1_TWD97_GENIE.pdf", 2),
    (f"{PRE}20261106_2100_A3_地籍套繪圖_1-500_v1.4_TWD97_GENIE.pdf", 1),
    (f"{PRE}20261106_2050_A3_新設側溝平面配置圖_1-500_v4.2_TWD97_GENIE.pdf", 1),
    (f"{PRE}20261106_2100_A3_平面及縱斷面圖_A0K_B0K_v1.5_SG_TWD97_GENIE.pdf", 2),
    (f"{PRE}20261106_2100_A3_設計橫斷面圖_v3.4_SG_TWD97_GENIE.pdf", 2),
    (f"{PRE}20261106_2100_A3_標準圖S01-S06_v3.3_TWD97_GENIE.pdf", 6),
]
w = PdfWriter(); k = 0
COVER = f"{PRE}20261106_1810_A3_設計圖冊封面_v1.0.pdf"                  # 封面（不列入圖目錄張次）
for p in PdfReader(os.path.join(OUT, COVER)).pages: w.add_page(p); w.add_outline_item("封面", 0)
for fn, n in PARTS:
    r = PdfReader(os.path.join(OUT, fn))
    if len(r.pages) != n: sys.exit(f"{fn}：頁數 {len(r.pages)}，應為 {n}")
    for p in r.pages:
        w.add_page(p); no, nm, _ = TOC[k]; w.add_outline_item(f"{k+1:02d} {no} {nm}", k + 1); k += 1
if k != len(TOC): sys.exit(f"合併 {k} 頁，圖目錄 {len(TOC)} 張，不符")
out = os.path.join(OUT, f"{PRE}{stamp}_A3_設計圖冊_v3.6_SG.pdf")
if os.path.exists(out): sys.exit(f"{out} 已存在，不覆蓋")
w.write(out)
chk = PdfReader(out)
sizes = {(round(float(p.mediabox.width) / 72 * 25.4), round(float(p.mediabox.height) / 72 * 25.4)) for p in chk.pages}
print("頁數：", len(chk.pages), "紙張(mm)：", sizes); print("PDF：", out)
