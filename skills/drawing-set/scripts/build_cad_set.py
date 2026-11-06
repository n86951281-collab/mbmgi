"""P33 設計圖冊 CAD 整合：各圖 DXF 合成一個檔，模型空間每檔一列，每張圖一個 A3 配置（視埠 1:1），供 PUBLISH 連續背景列印。
使用者 2026-11-06：「cad 整理成一個 cad 檔，用開視埠方式連續表示每張圖面，發布連續後台列印」。
- 圖紙順序與 merge_set.py 相同（封面＋圖目錄 14 張），配置名「序號_圖號」（純 ASCII，PUBLISH／DSD 不怕編碼）。
- 頁面設定：DWG To PDF.pc3、ISO full bleed A3 (420×297)、置中出圖、佈滿圖紙、圖筆 A3-圖筆(黑白).ctb（交付時可改全彩）。
- 視埠：由 make_dsd.py 產生的 AutoCAD 指令檔建立（每配置 -VPORTS 0,0～420,297，ZOOM 中心＋高 297＝1:1），放「視埠」圖層（不列印）。
- 底圖 IMAGE 參照同資料夾 PNG（相對檔名），DWG 與 PNG 要放同一資料夾。
用法：python build_cad_set.py --stamp YYYYMMDD_HHMM  → 產出 combined DXF，再以 accoreconsole 另存 DWG 並產生 .dsd
"""
import sys, os, json, re, datetime
import ezdxf
from ezdxf import xref

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "case_config.json"), encoding="utf-8-sig"))
OUT = CFG["out_dir"]; PRE = CFG["file_prefix"]
stamp = sys.argv[sys.argv.index("--stamp") + 1] if "--stamp" in sys.argv else datetime.datetime.now().strftime("%Y%m%d_%H%M")
TOC = json.load(open(os.path.join(HERE, "toc_v2.json"), encoding="utf-8"))
ms = open(os.path.join(HERE, "merge_set.py"), encoding="utf-8").read()
PARTS = [(m.group(1), int(m.group(2))) for m in re.finditer(r'\(f"\{PRE\}([^"]+)\.pdf", (\d+)\)', ms)]
COVER = re.search(r'COVER = f"\{PRE\}([^"]+)\.pdf"', ms).group(1)
SHEET_DX, ROW_DY = 450.0, 400.0                                   # 各產生器 DXF 內圖紙橫向間距 450；每檔一列

doc = ezdxf.new("R2018", setup=True); doc.header["$LTSCALE"] = 5; doc.header["$PSLTSCALE"] = 1
msp = doc.modelspace()
if "視埠" not in doc.layers: doc.layers.add("視埠", color=8)
doc.layers.get("視埠").dxf.plot = 0
sheets = []                                                         # (配置名, 模型空間左下 x, y)
files = [(COVER, 1, "封面")] + [(fn, n, None) for fn, n in PARTS]
k_toc = 0
for row, (fn, n, special) in enumerate(files):
    src = ezdxf.readfile(os.path.join(OUT, PRE + fn + ".dxf"))
    before = {e.dxf.handle for e in msp}
    xref.load_modelspace(src, doc, conflict_policy=xref.ConflictPolicy.KEEP)
    dy = -row * ROW_DY
    for e in msp:
        if e.dxf.handle not in before:
            try: e.translate(0, dy, 0)
            except Exception as ex: print("  無法平移：", e.dxftype(), ex)
    for j in range(n):
        if special: name = "00_COVER"
        else:
            no = TOC[k_toc][0]; name = f"{k_toc + 1:02d}_{no}"; k_toc += 1
        sheets.append((name, j * SHEET_DX, dy))
    print(f"{row:02d} {fn}：{n} 張")
assert k_toc == len(TOC), (k_toc, len(TOC))
# 底圖 IMAGE：用輸出資料夾的絕對路徑（相對檔名在主控台出圖時不載入，2026-11-06 實測）
for d_ in doc.objects.query("IMAGEDEF"): d_.dxf.filename = os.path.join(OUT, os.path.basename(d_.dxf.filename))
for name, x0, y0 in sheets:
    lay = doc.layouts.new(name)
    lay.page_setup(size=(420, 297), margins=(0, 0, 0, 0), units="mm", offset=(0, 0), rotation=0, scale=(1, 1),   # scale 給整數會被當成標準比例編號
                   name="ISO_full_bleed_A3", device="DWG To PDF.pc3")                                                # 名稱自動補「_(420.00_x_297.00_MM)」
    lay.dxf.current_style_sheet = "A3-圖筆(黑白).ctb"
    L_ = lay.dxf_layout.dxf                                            # 使用者 2026-11-06：置中出圖＋佈滿圖紙
    L_.plot_layout_flags = (L_.plot_layout_flags | 4 | 16)             # 4＝置中、16＝使用標準比例
    L_.standard_scale_type = 0                                         # 0＝佈滿圖紙（Scaled to Fit）
    # 視埠由 AutoCAD 建立（ezdxf 建的視埠在 AutoCAD 出圖時不顯示模型內容，2026-11-06 實測），見 cad_set_dwg.scr
for nm in [l.name for l in doc.layouts if l.name not in ("Model",) and l.name not in [s[0] for s in sheets]]:
    doc.layouts.delete(nm)
out = os.path.join(OUT, f"{PRE}{stamp}_A3_設計圖冊_CAD整合_v1.7_TWD97_GENIE.dxf")
if os.path.exists(out): sys.exit(f"{out} 已存在，不覆蓋")
doc.saveas(out)
json.dump([list(s_) for s_ in sheets], open(os.path.join(HERE, "cad_set_layouts.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("配置：", len(sheets), [s[0] for s in sheets]); print("DXF：", out)
