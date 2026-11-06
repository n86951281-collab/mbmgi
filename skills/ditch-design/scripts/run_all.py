"""排水設計一鍵流程：依序執行各產生器，遇到★停點且未確認時停下，列出要使用者確認的內容。

用法：python run_all.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM] [--confirmed <停點,停點…>] [--until <步驟>] [--from <步驟>] [--pdf] [--dwg] [--list]
- 停點（★）：terrain 建地形、alignment 定線、ground EG/SG、standards 標準圖與擋土型式、demolish 既有構造物拆除、prices 單價與費率、schedule 工期。
  已確認的停點寫在設定檔 stops_confirmed，或用 --confirmed 逗號分隔帶入（例：--confirmed terrain,alignment,ground）。
- --until／--from：只跑到／從某步驟（步驟名見 --list）。
- --pdf：xlsx 用 Excel COM 重算、存檔、匯出 PDF 並掃 ###（qty-budget/scripts/quantity_calc_pdf.ps1）。
- --dwg：build_cad_set 另用 accoreconsole 產 DWG（需 AutoCAD）。
全部步驟用同一個 --stamp（存檔時間；請用 Get-Date 取得，不要自己推算）。
回傳碼：0 完成；3 停在未確認的★停點；其他＝某步驟失敗。
"""
import sys, os, subprocess, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd

HERE = dd.HERE; CFG = dd.CFG
STOP_TEXT = {
    "terrain": "★1 建地形：TIN（tin_npz）與抽驗結果（*_qa.txt：RMSE、最大誤差）、8 視角預覽已給使用者看過（SKILL section-drawings 步驟 2／2-B）",
    "alignment": "★2 定線：道路中心線、各側溝定線圖層、0K+000 在下游、全長與樁號範圍",
    "ground": "★3 設計地面 EG 或 SG（SG 時四角高程逐角確認）",
    "standards": "★4 標準圖與臨時擋土型式：溝體標準圖、是否超出適用範圍（配筋檢核）、擋土樁長與間距、路外／路內距離",
    "demolish": "★5 既有構造物拆除：逐項拆或不拆（demolish[]）",
    "prices": "★6 單價與費率：單價來源、【假設】項目、品管／利潤／空污／工程管理費率、委外設計監造費",
    "schedule": "★7 工期：日曆天數或每日施工量（schedule.rates，預設值為【假設】）",
}
# (步驟名, 程式, 執行前要確認的停點, 條件)
STEPS = [
    ("profiles", "design_profiles.py", ["terrain", "alignment", "ground"], None),
    ("sections", "cross_sections.py", ["standards"], None),
    ("plan", "plan_view.py", ["demolish"], None),
    ("plan_profile", "plan_profile.py", [], None),
    ("cadastral", "cadastral_sheet.py", [], lambda: bool(CFG.get("cadastre", {}).get("dxf"))),
    ("standards", "standard_drawings.py", [], None),
    ("rebar", "rebar_check.py", [], lambda: bool(CFG.get("standards", {}).get("rc_check"))),
    ("front", "front_sheets.py", [], None),
    ("cover", "cover_sheet.py", [], None),
    ("quantity", "quantity_calc.py", [], None),
    ("qty_table", "qty_table.py", [], None),
    ("schedule", "schedule.py", ["schedule"], None),
    ("budget", "budget_pcces.py", ["prices"], None),
    ("merge", "merge_set.py", [], None),
    ("cad_set", "build_cad_set.py", [], None),
]


def detail(stop):
    """停點回報內容（從設定檔與中間資料取）"""
    g = dd.get
    if stop == "terrain":
        qa = glob.glob(dd.src(os.path.splitext(g("tin_npz", ""))[0] + "_qa.txt"))
        return [f"TIN：{dd.src(g('tin_npz', '?'))}"] + ([open(qa[0], encoding="utf-8", errors="replace").read().strip()] if qa else ["（找不到抽驗檔 *_qa.txt）"])
    if stop == "alignment":
        return [f"定線 DXF：{g('alignment.dxf')}；中心線 {g('alignment.centerline_layer', '中心線1')}；0K+000 在 {g('alignment.downstream')}（{g('alignment.downstream_dir', '')}）",
                "側溝：" + "；".join(f"{d['id']} {d.get('line_layer', '?')}（{d.get('lr')}）" for d in dd.DITCHES)]
    if stop == "ground":
        return [f"設計地面：{dd.GROUND}" + (f"；SG TIN {g('sg.tin_npz')}；四角 {g('sg.corner_z')}" if dd.USE_SG else "")]
    if stop == "standards":
        return [f"溝體標準圖：{g('standards.ditch')}；配筋檢核：{g('standards.rc_check')}",
                f"斷面：W×H＝{dd.P_['W']}×{dd.P_['H']} m、蓋板 {dd.P_['t_cover']}、壁 {dd.P_['t_wall']}、底版 {dd.P_['t_slab']}、墊層 {dd.P_['t_bed']}",
                f"臨時擋土：{dd.SHO.get('type')} L={dd.PILE_L} m @{dd.PILE_SP} m；路外 {dd.GAP_OUT} m、路內 {dd.WORK_GAP} m"]
    if stop == "demolish":
        return [f"{r.get('name')} {r.get('size', '')}：{'拆' if r.get('demolish', True) else '不拆'}" for r in CFG.get("demolish", [])] or ["（demolish[] 空白）"]
    if stop == "prices":
        return [f"單價來源：{' > '.join(g('budget.price_sources', []))}；單價檔 {g('budget.unit_prices_file')}", f"費率：{g('budget.rates')}",
                f"委外設計 {g('budget.design_fee')}、監造 {g('budget.supervision_fee')}"]
    if stop == "schedule":
        return [f"工期：{g('schedule.days') or '未指定（依每日施工量推算）'}；每日施工量：{g('schedule.rates') or '預設值【假設】'}"]
    return []


def main():
    conf = set(CFG.get("stops_confirmed", []))
    for x in (dd.arg("--confirmed") or "").split(","):
        if x.strip(): conf.add(x.strip())
    names = [s[0] for s in STEPS]
    if "--list" in sys.argv:
        for n, p, st, _ in STEPS: print(f"{n:13s} {p:22s} 停點：{','.join(st) or '－'}")
        return 0
    until, frm = dd.arg("--until"), dd.arg("--from")
    for x in (until, frm):
        if x and x not in names: raise SystemExit(f"沒有步驟 {x}；可用：{', '.join(names)}")
    i0 = names.index(frm) if frm else 0; i1 = names.index(until) if until else len(STEPS) - 1
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    base = ["--config", dd.CFG_PATH, "--stamp", dd.stamp]
    print(f"設定檔：{dd.CFG_PATH}\nstamp：{dd.stamp}\n輸出：{dd.OUT}\n中間資料：{dd.WORK}")
    for n, prog, stops, cond in STEPS[i0:i1 + 1]:
        need = [s for s in stops if s not in conf]
        if need:
            print(f"\n=== 停在步驟「{n}」之前：下列★停點尚未確認 ===")
            for s in need:
                print(STOP_TEXT[s])
                for line in detail(s): print("   ", line)
            print(f"\n使用者確認後，把停點加進設定檔 stops_confirmed，或重跑加 --confirmed {','.join(need)}")
            return 3
        if cond and not cond(): print(f"\n--- {n}：略過（設定檔未啟用）"); continue
        args = base + (["--pdf"] if n == "schedule" and "--pdf" in sys.argv else []) + (["--dwg"] if n == "cad_set" and "--dwg" in sys.argv else [])
        print(f"\n--- {n}：{prog}", flush=True)
        r = subprocess.run([sys.executable, os.path.join(HERE, prog)] + args, env=env)
        if r.returncode: print(f"步驟 {n} 失敗（回傳碼 {r.returncode}）"); return r.returncode
    if "--pdf" in sys.argv:
        ps1 = os.path.join(dd.SKILLS, "qty-budget", "scripts", "quantity_calc_pdf.ps1")
        for x in sorted(glob.glob(os.path.join(dd.OUT, glob.escape(f"{dd.PRE}{dd.stamp}_") + "*.xlsx"))):
            if "工期推算" in x: continue                                     # schedule.py --pdf 已做
            print("\n--- pdf：", os.path.basename(x), flush=True)
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, "-xlsx", x, "-dumpdir", dd.WORK], check=True)
    print("\n完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
