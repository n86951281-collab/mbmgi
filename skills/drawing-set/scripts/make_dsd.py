"""產生 AutoCAD PUBLISH 用 .dsd（多頁 PDF，依配置順序連續列印）。用法：python make_dsd.py <dwg> <pdf輸出> <dsd輸出> [編碼]"""
import sys, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
dwg, pdf, dsd = sys.argv[1:4]; enc = sys.argv[4] if len(sys.argv) > 4 else "cp950"
L = [r[0] for r in json.load(open(os.path.join(HERE, "cad_set_layouts.json"), encoding="utf-8"))]
s = ["[DWF6Version]", "Ver=1", "[DWF6MinorVersion]", "MinorVer=1"]
base = os.path.splitext(os.path.basename(dwg))[0]
for nm in L:
    s += [f"[DWF6Sheet:{base}-{nm}]", f"DWG={dwg}", f"Layout={nm}", "Setup=", f"OriginalSheetPath={dwg}", "Has Plot Port=0", "Has3DDWF=0"]
s += ["[Target]", "Type=6", f"DWF={pdf}", f"OUT={os.path.dirname(pdf)}\\", "PWD=",
      "[PdfOptions]", "IncludeHyperlinks=TRUE", "CreateBookmarks=TRUE", "CaptureFontsInDrawing=TRUE", "ConvertTextToGeometry=FALSE",
      "VectorResolution=1200", "RasterResolution=400",
      "[AutoCAD Block Data]", "IncludeLayer=TRUE", "PromptForDwfName=FALSE", "PromptForPwd=FALSE", "NoOfCopies=1", "PlotStampOn=FALSE",
      "ViewFile=FALSE", "JobID=0", "SelectionSetName=", "AcadProfile=", "CategoryName=", "LogFilePath=", "IncludeSheetSetData=FALSE", "SheetSetName=",
      "[SheetSet Properties]", "IsSheetSet=FALSE", "IsHomogeneous=FALSE", "SheetSet Name=", "NoOfCopies=1", "PlotStampOn=FALSE", "ViewFile=FALSE",
      "JobID=0", "SelectionSetName=", "AcadProfile=", "CategoryName=", "LogFilePath=", "IncludeSheetSetData=FALSE", "SheetSetName=",
      "PromptForDwfName=FALSE", "PromptForPwd=FALSE", "RepublishingMarkups=FALSE", "PublishSheetSetMetadata=FALSE", "PublishSheetMetadata=FALSE", "3DDWFOptions=0 0"]
open(dsd, "w", encoding=enc, newline="\r\n").write("\n".join(s) + "\n"); print(dsd, len(L), "張")
