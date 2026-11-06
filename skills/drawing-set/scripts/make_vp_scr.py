"""產生 AutoCAD 指令檔：開整合 DXF 後在每個配置建視埠（1:1，視埠圖層 VPORT 不列印），另存 DWG；可選接著 PUBLISH。
用法：python make_vp_scr.py <dwg輸出> <scr輸出> [dsd 檔（有則接著發布）]"""
import sys, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
dwg, scr = sys.argv[1:3]; dsd = sys.argv[3] if len(sys.argv) > 3 else None
L = json.load(open(os.path.join(HERE, "cad_set_layouts.json"), encoding="utf-8"))
cmd = ["FILEDIA", "0", "CMDECHO", "0", "-LAYER", "M", "VPORT", "C", "8", "", "P", "N", "", ""]   # 視埠圖層 VPORT（不列印），設為目前圖層
for nm, x0, y0 in L:
    cmd += ["-LAYOUT", "S", nm, "PSPACE", "ZOOM", "W", "-10,-10", "430,307", "-VPORTS", "0,0", "420,297", "ZOOM", "W", "-10,-10", "430,307", "MSPACE", "ZOOM", "C", f"{x0 + 210:.3f},{y0 + 148.5:.3f}", "297", "PSPACE"]
cmd += ["-LAYOUT", "S", L[0][0], "-LAYER", "S", "0", "", "_.SAVEAS", "2018", dwg]
if dsd: cmd += ["BACKGROUNDPLOT", "0", "-PUBLISH", dsd]
cmd += ["_.QUIT", "_Y"]
with open(scr, "w", encoding="ascii", newline="\r\n") as f: f.write("\n".join(cmd) + "\n")
print(scr, len(L))
