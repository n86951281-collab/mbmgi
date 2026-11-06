"""整批回歸比對：重跑輸出資料夾 vs 已核定交付資料夾（例如 P33 的 (印報告)）。

用法：python regress_run.py --config <ditch_config.json> --stamp <重跑 stamp> --baseline <交付資料夾> [--cross-check <cross_check 設定.json>]
- 依檔名（去掉「前綴＋存檔時間_」）配對：各圖 DXF、CAD 整合 DXF、數量計算書、工程數量計算表、預算書、配筋檢核表。
- DXF：regress_dxf（各圖層圖元數、全部文字、幾何容差 0.01 mm）；xlsx：regress_xlsx（逐格公式與 Excel 重算值，兩邊都要先經 COM 重算存檔）。
- 預算書另列發包工程費、總價、詳細表金額列數與不同列。
- --cross-check：drawing-set 的跨圖一致性設定，基準與重跑各跑一次（重跑時把設定中的基準路徑換成重跑檔）比不一致筆數。
"""
import sys, os, re, glob, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
import regress_dxf, regress_xlsx
from openpyxl import load_workbook

BASE = dd.arg("--baseline")
if not BASE: raise SystemExit("請給 --baseline <交付資料夾>")
key = lambda p: re.sub(r"^.*?\d{8}_\d{4}_", "", os.path.basename(p))
base_files = {key(p): p for p in glob.glob(os.path.join(BASE, "**", "*.*"), recursive=True)}
run_files = {key(p): p for p in glob.glob(os.path.join(dd.OUT, glob.escape(f"{dd.PRE}{dd.stamp}_") + "*.*"))}
rows = []
for k in sorted(set(base_files) & set(run_files)):
    b, r = base_files[k], run_files[k]
    if k.endswith(".dxf"):
        print(f"\n## {k}"); x = regress_dxf.compare(b, r)
        ok = x["layer_diff"] == 0 and x["text_missing"] == 0 and x["text_extra"] == 0 and x["geom_same"]
        rows.append((k, f"圖元 {x['n'][0]}、文字 {x['text'][0]}", f"圖元 {x['n'][1]}、文字 {x['text'][1]}",
                     "一致" if ok else f"圖層差 {x['layer_diff']}、缺字 {x['text_missing']}、多字 {x['text_extra']}、幾何{'同' if x['geom_same'] else '異'}（{x['geom_layers']}，最大 {x['geom_dmax']:.3f} mm）"))
    elif k.endswith(".xlsx"):
        print(f"\n## {k}"); x = regress_xlsx.compare(b, r, show=30)
        rows.append((k, f"{x['cells'][0]} 格", f"{x['cells'][1]} 格", "一致" if x["sheets_same"] and not x["formula_diff"] and not x["value_diff"]
                     else f"工作表順序{'同' if x['sheets_same'] else '異'}、公式差 {x['formula_diff']}、值差 {x['value_diff']}"))
        if "預算書" in k:
            def tot(p):
                wb = load_workbook(p, data_only=True); t = wb["預算總表"]; d = wb["預算詳細表"]
                T = {t.cell(i, 2).value: t.cell(i, 6).value for i in range(9, 23)}
                amt = {d.cell(i, 1).value: d.cell(i, 6).value for i in range(9, d.max_row + 1) if isinstance(d.cell(i, 6).value, (int, float))}
                return T, amt
            (tb, ab), (tr, ar) = tot(b), tot(r)
            bad = [n for n in set(ab) | set(ar) if ab.get(n) != ar.get(n)]
            rows.append(("預算 發包工程費", f"{tb['發包工程費']:,}", f"{tr['發包工程費']:,}", "一致" if tb['發包工程費'] == tr['發包工程費'] else "不同"))
            rows.append(("預算 總價", f"{tb['總價(總計)']:,}", f"{tr['總價(總計)']:,}", "一致" if tb['總價(總計)'] == tr['總價(總計)'] else "不同"))
            rows.append(("預算 詳細表金額列", f"{len(ab)} 列", f"{len(ar)} 列", "全部一致" if not bad else f"不同 {len(bad)} 列：{bad[:8]}"))
miss = sorted(k for k in base_files if k.endswith((".dxf", ".xlsx")) and k not in run_files)
cc = dd.arg("--cross-check")
if cc:
    def run_cc(cfgp):
        r = subprocess.run([sys.executable, "-I", os.path.join(dd.SKILLS, "drawing-set", "scripts", "cross_check.py"), cfgp], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode, [l for l in r.stdout.splitlines() if l.strip()][-1:] if r.stdout else []
    c = json.load(open(cc, encoding="utf-8-sig"))
    rb = run_cc(cc)
    c2 = json.loads(json.dumps(c, ensure_ascii=False))
    c2["dxf"] = [os.path.join(dd.OUT, glob.escape(f"{dd.PRE}{dd.stamp}_") + "*.dxf")]
    def swap(o):
        if isinstance(o, dict): return {k: (run_files.get(key(v), v) if k == "xlsx" else swap(v)) for k, v in o.items()}
        if isinstance(o, list): return [swap(v) for v in o]
        return o
    c2 = swap(c2)
    tmp = dd.work("cross_check_rerun.json"); json.dump(c2, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rr = run_cc(tmp)
    rows.append(("跨圖一致性 cross_check", f"回傳碼 {rb[0]} {rb[1]}", f"回傳碼 {rr[0]} {rr[1]}", "一致" if rb[0] == rr[0] else "不同"))
print("\n| 項目 | 基準 | 重跑 | 差異 |\n|---|---|---|---|")
for r in rows: print("| " + " | ".join(str(x) for x in r) + " |")
if miss: print("基準有、重跑沒有：", miss)
