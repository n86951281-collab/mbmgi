"""P33 新社東山街側溝：設計圖冊封面（A3 橫式，使用者 2026-11-06 要求）。不列入圖目錄張次。
用法：python cover_sheet.py --stamp YYYYMMDD_HHMM
"""
import sys, os, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p33_sheet as S
from p33_sheet import Sheet, check, save, W_, H_

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "case_config.json"), encoding="utf-8-sig"))
stamp = sys.argv[sys.argv.index("--stamp") + 1] if "--stamp" in sys.argv else datetime.datetime.now().strftime("%Y%m%d_%H%M")
OUT = CFG["out_dir"]; PREV = os.path.join(OUT, "00_前頁")
base = f"{CFG['file_prefix']}{stamp}_A3_設計圖冊封面_v1.0"
LAYERS = {"圖框": (7, None, "#000000", 0.70), "細框": (7, None, "#000000", 0.25), "文字": (7, None, "#000000", 0.0)}
PT30, PT45, PT20 = 10.58, 15.88, 7.06                                 # 30 pt、45 pt、20 pt（mm）
roc = int(stamp[:4]) - 1911; mon = int(stamp[4:6])

sh = Sheet("封面")
sh.rect(10, 10, W_ - 20, H_ - 20, "圖框"); sh.rect(14, 14, W_ - 28, H_ - 28, "細框")
sh.wf = 0.8
sh.text(W_ / 2, 210.0, CFG["title_block"]["project"], "center", PT30)
sh.wf = 1.0
sh.text(W_ / 2, 160.0, "設　計　圖", "center", PT45)
sh.wf = 0.8
sh.line(W_ / 2 - 70, 140.0, W_ / 2 + 70, 140.0, "細框")
sh.text(W_ / 2, 112.0, "主辦機關：" + CFG["title_block"]["agency"], "center", PT20)
sh.text(W_ / 2, 96.0, "設計單位：辰璟工程技術顧問有限公司", "center", PT20)
sh.text(W_ / 2, 58.0, f"中華民國 {roc} 年 {mon} 月", "center", PT20)
over, press, outb = check(sh, ("圖框", "細框"))
dxf, pdf, pngs = save([sh], LAYERS, OUT, PREV, base)
print("DXF：", dxf); print("PDF：", pdf); [print("PNG：", p) for p in pngs]
