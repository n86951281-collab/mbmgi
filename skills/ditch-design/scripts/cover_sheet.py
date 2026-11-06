"""設計圖冊封面（ditch-design，由 P33 cover_sheet 一般化；A3 橫式，不列入圖目錄張次）。
工程名稱 30 pt、「設 計 圖」45 pt、主辦機關與設計單位 20 pt、中華民國年月（取 --stamp 的年月）；雙線外框，不放圖標欄。
用法：python cover_sheet.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
S = dd.sheet_module()
from p33_sheet import Sheet, check, save, W_, H_

stamp = dd.stamp; OUT = dd.OUT; PREV = os.path.join(OUT, "00_前頁")
base = f"{dd.PRE}{stamp}_A3_設計圖冊封面_{dd.ver('cover')}"
LAYERS = {"圖框": (7, None, "#000000", 0.70), "細框": (7, None, "#000000", 0.25), "文字": (7, None, "#000000", 0.0)}
PT30, PT45, PT20 = 10.58, 15.88, 7.06                                 # 30 pt、45 pt、20 pt（mm）
roc = int(stamp[:4]) - 1911; mon = int(stamp[4:6])

sh = Sheet("封面")
sh.rect(10, 10, W_ - 20, H_ - 20, "圖框"); sh.rect(14, 14, W_ - 28, H_ - 28, "細框")
sh.wf = 0.8
sh.text(W_ / 2, 210.0, dd.TB["project"], "center", PT30)
sh.wf = 1.0
sh.text(W_ / 2, 160.0, "設　計　圖", "center", PT45)
sh.wf = 0.8
sh.line(W_ / 2 - 70, 140.0, W_ / 2 + 70, 140.0, "細框")
sh.text(W_ / 2, 112.0, "主辦機關：" + dd.TB["agency"], "center", PT20)
sh.text(W_ / 2, 96.0, "設計單位：" + dd.TB["designer"], "center", PT20)
sh.text(W_ / 2, 58.0, f"中華民國 {roc} 年 {mon} 月", "center", PT20)
check(sh, ("圖框", "細框"))
dxf, pdf, pngs = save([sh], LAYERS, OUT, PREV, base)
print("DXF：", dxf); print("PDF：", pdf); [print("PNG：", p) for p in pngs]
