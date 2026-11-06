"""設計圖冊 CAD 整合（ditch-design，由 P33 build_cad_set＋make_dsd＋make_vp_scr 一般化）。
- 各圖 DXF（與 merge_set.py 同一組檔，同一個 --stamp）用 ezdxf.xref 合成一個 DXF：模型空間每檔一列（間距 400 mm），
  每張圖一個 A3 配置，配置名「序號_圖號」（純英數）；頁面設定 DWG To PDF.pc3、ISO full bleed A3、置中、佈滿圖紙、圖筆 plot.ctb。
- 同時寫 AutoCAD 指令檔 .scr（每配置建視埠 1:1、VPORT 層不出圖、另存 DWG，可接 PUBLISH）與 PUBLISH 清單 .dsd（cp950）。
- 加 --dwg 時用 accoreconsole.exe 執行 .scr，產出 DWG（需裝 AutoCAD；路徑見 --acad，預設 AutoCAD 2022）。
用法：python build_cad_set.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM] [--src-stamp YYYYMMDD_HHMM] [--dwg] [--acad <accoreconsole.exe>]
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
import ezdxf
from ezdxf import xref
import merge_set as M

OUT, PRE, TOC = dd.OUT, dd.PRE, M.TOC
SHEET_DX, ROW_DY = 450.0, 400.0
CTB = dd.get("plot.ctb", "A3-圖筆(黑白).ctb")
doc = ezdxf.new("R2018", setup=True); doc.header["$LTSCALE"] = 5; doc.header["$PSLTSCALE"] = 1
msp = doc.modelspace()
if "視埠" not in doc.layers: doc.layers.add("視埠", color=8)
doc.layers.get("視埠").dxf.plot = 0
sheets = []
files = [(M.cover(".dxf"), 1, True)] + [(f, n, False) for f, n in M.parts(".dxf")]
k_toc = 0
for row, (fn, n, special) in enumerate(files):
    src = ezdxf.readfile(fn)
    before = {e.dxf.handle for e in msp}
    xref.load_modelspace(src, doc, conflict_policy=xref.ConflictPolicy.KEEP)
    dy = -row * ROW_DY
    for e in msp:
        if e.dxf.handle not in before:
            try: e.translate(0, dy, 0)
            except Exception as ex: print("  無法平移：", e.dxftype(), ex)
    for j in range(n):
        if special: name = "00_COVER"
        else: name = f"{k_toc + 1:02d}_{TOC[k_toc][0]}"; k_toc += 1
        sheets.append((name, j * SHEET_DX, dy))
    print(f"{row:02d} {os.path.basename(fn)}：{n} 張")
assert k_toc == len(TOC), (k_toc, len(TOC))
for d_ in doc.objects.query("IMAGEDEF"): d_.dxf.filename = os.path.join(OUT, os.path.basename(d_.dxf.filename))   # 底圖用絕對路徑（主控台出圖才載得到）
for name, x0, y0 in sheets:
    lay = doc.layouts.new(name)
    lay.page_setup(size=(420, 297), margins=(0, 0, 0, 0), units="mm", offset=(0, 0), rotation=0, scale=(1, 1),
                   name="ISO_full_bleed_A3", device="DWG To PDF.pc3")
    lay.dxf.current_style_sheet = CTB
    L_ = lay.dxf_layout.dxf
    L_.plot_layout_flags = (L_.plot_layout_flags | 4 | 16); L_.standard_scale_type = 0      # 置中＋佈滿圖紙
for nm in [l.name for l in doc.layouts if l.name != "Model" and l.name not in [s[0] for s in sheets]]:
    doc.layouts.delete(nm)
base = f"{PRE}{dd.stamp}_A3_設計圖冊_CAD整合_{dd.ver('cad_set')}_TWD97_GENIE"
out = os.path.join(OUT, base + ".dxf")
if os.path.exists(out): raise SystemExit(f"{out} 已存在，不覆蓋")
doc.saveas(out)
dd.write_json("cad_set_layouts.json", [list(s_) for s_ in sheets])
print("配置：", len(sheets), [s[0] for s in sheets]); print("DXF：", out)

# ---------- .dsd（PUBLISH 清單，cp950）與 .scr（建視埠、另存 DWG） ----------
dwg = os.path.join(OUT, base + ".dwg"); pdf = os.path.join(OUT, base + "_發布.pdf"); dsd = os.path.join(OUT, base + ".dsd")
s = ["[DWF6Version]", "Ver=1", "[DWF6MinorVersion]", "MinorVer=1"]
for nm, _, _ in sheets:
    s += [f"[DWF6Sheet:{base}-{nm}]", f"DWG={dwg}", f"Layout={nm}", "Setup=", f"OriginalSheetPath={dwg}", "Has Plot Port=0", "Has3DDWF=0"]
s += ["[Target]", "Type=6", f"DWF={pdf}", f"OUT={OUT}\\", "PWD=",
      "[PdfOptions]", "IncludeHyperlinks=TRUE", "CreateBookmarks=TRUE", "CaptureFontsInDrawing=TRUE", "ConvertTextToGeometry=FALSE",
      "VectorResolution=1200", "RasterResolution=400",
      "[AutoCAD Block Data]", "IncludeLayer=TRUE", "PromptForDwfName=FALSE", "PromptForPwd=FALSE", "NoOfCopies=1", "PlotStampOn=FALSE",
      "ViewFile=FALSE", "JobID=0", "SelectionSetName=", "AcadProfile=", "CategoryName=", "LogFilePath=", "IncludeSheetSetData=FALSE", "SheetSetName=",
      "[SheetSet Properties]", "IsSheetSet=FALSE", "IsHomogeneous=FALSE", "SheetSet Name=", "NoOfCopies=1", "PlotStampOn=FALSE", "ViewFile=FALSE",
      "JobID=0", "SelectionSetName=", "AcadProfile=", "CategoryName=", "LogFilePath=", "IncludeSheetSetData=FALSE", "SheetSetName=",
      "PromptForDwfName=FALSE", "PromptForPwd=FALSE", "RepublishingMarkups=FALSE", "PublishSheetSetMetadata=FALSE", "PublishSheetMetadata=FALSE", "3DDWFOptions=0 0"]
open(dsd, "w", encoding="cp950", newline="\r\n").write("\n".join(s) + "\n"); print("DSD：", dsd)
# .scr 一律用純英數暫存路徑（accoreconsole 讀中文路徑會失敗；短檔名 ADMINI~1 也不要用）：%TEMP%/ditch_cadset
TMPD = os.path.join(os.path.realpath(os.environ.get("TEMP", r"C:\Temp")), "ditch_cadset"); os.makedirs(TMPD, exist_ok=True)
if not TMPD.isascii(): raise SystemExit(f"暫存路徑含非英數字：{TMPD}")
tmp_dxf = os.path.join(TMPD, "cadset.dxf"); tmp_dwg = os.path.join(TMPD, "cadset.dwg")
cmd = ["FILEDIA", "0", "CMDECHO", "0", "-LAYER", "M", "VPORT", "C", "8", "", "P", "N", "", ""]
for nm, x0, y0 in sheets:
    cmd += ["-LAYOUT", "S", nm, "PSPACE", "ZOOM", "W", "-10,-10", "430,307", "-VPORTS", "0,0", "420,297", "ZOOM", "W", "-10,-10", "430,307",
            "MSPACE", "ZOOM", "C", f"{x0 + 210:.3f},{y0 + 148.5:.3f}", "297", "PSPACE"]
cmd += ["-LAYOUT", "S", sheets[0][0], "-LAYER", "S", "0", "", "_.SAVEAS", "2018", tmp_dwg, "_.QUIT", "_Y"]
scr = dd.work("cadset_vp.scr")
open(scr, "w", encoding="ascii", newline="\r\n").write("\n".join(cmd) + "\n"); print("SCR：", scr)
if "--dwg" in sys.argv:
    import shutil
    acad = dd.arg("--acad", r"C:\Program Files\Autodesk\AutoCAD 2022\accoreconsole.exe")
    shutil.copyfile(out, tmp_dxf)
    if os.path.exists(tmp_dwg): os.remove(tmp_dwg)
    subprocess.run([acad, "/i", tmp_dxf, "/s", scr], capture_output=True, timeout=900)
    if not os.path.exists(tmp_dwg): raise SystemExit("accoreconsole 沒有產出 DWG；請改用 AutoCAD 開 DXF 後執行 .scr")
    shutil.move(tmp_dwg, dwg); print("DWG：", dwg)
