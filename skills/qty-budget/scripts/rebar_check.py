"""P33 箱涵式側溝（W×H＝110×100 cm）配筋檢核表：B20 標準圖配筋（適用 W≦100）用於本案 W=110 之檢核。
輸出 xlsx（保留公式）；PDF 由 Excel 開啟重算後匯出（rebar_check_pdf.ps1）。
依據：
- 內政部「混凝土結構設計規範」（強度設計法）：U＝1.2D＋1.6L＋1.6H；φ 撓曲 0.90、剪力 0.75；Vc＝0.53√fc'·b·d；ρmin 版 0.0018。
- 交通部「公路橋梁設計規範」：HS20-44 後輪重 7.26 t；衝擊 I＝15.24／(L＋38)≦0.30；主筋垂直車行之版，分布寬 E＝1.22＋0.06S（m）；
  依規範設計彎矩之版，視為剪力及握裹足夠（AASHTO 3.24.4 同）——本表仍列剪力供參。
- 側向土壓：靜止土壓 K0、土壤單位重 γ、交通超載等值土高 0.6 m（AASHTO 3.20.3）。
用法：python rebar_check.py --case <案件資料夾> [--param design_param_v1.json] --stamp YYYYMMDD_HHMM
（--case 省略時用本檔所在資料夾；--param 為斷面尺寸 json（W、H、t_wall、t_slab、t_cover…），相對於案件資料夾）
參考實作：材料、土壓、載重假設是 P33 的（多項【待確認】），新案依地質與規範改。
"""
import sys, os, json, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.page import PageMargins

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
CASE = os.path.abspath(arg("--case", HERE))
CFG = json.load(open(os.path.join(CASE, "case_config.json"), encoding="utf-8-sig"))
stamp = arg("--stamp", datetime.datetime.now().strftime("%Y%m%d_%H%M"))
P = json.load(open(os.path.join(CASE, arg("--param", "design_param_v1.json")), encoding="utf-8-sig"))

# (項次, 項目, 符號, 公式或數值（{符號} 代入）, 單位, 說明／出處)；項次 "#" 開頭為中標題
R = [
 ("#1", "材料與斷面（假設條件標【待確認】）"),
 ("1.1", "蓋板混凝土強度", "fcc", 280, "kgf/cm²", "B20 附註 1：預鑄溝蓋板 f'c≧280"),
 ("1.2", "溝體混凝土強度", "fcb", 210, "kgf/cm²", "B20 剖面圖：210 kgf/cm² 混凝土"),
 ("1.3", "鋼筋降伏強度（D16、D19）", "fyL", 4200, "kgf/cm²", "SD420W【待確認】B20 未註明"),
 ("1.4", "鋼筋降伏強度（D10、D13）", "fyS", 2800, "kgf/cm²", "SD280W【待確認】B20 未註明"),
 ("1.5", "D13 單根面積", "A13", 1.267, "cm²", "CNS 560"),
 ("1.6", "D16 單根面積", "A16", 1.986, "cm²", "CNS 560"),
 ("1.7", "D19 單根面積", "A19", 2.865, "cm²", "CNS 560"),
 ("1.8", "渠寬（淨）", "W", P["W"] * 100, "cm", "本案設計（design_param_v1.json）"),
 ("1.9", "渠高（淨）", "H", P["H"] * 100, "cm", "本案設計"),
 ("1.10", "側牆厚", "tw", P["t_wall"] * 100, "cm", "本案設計"),
 ("1.11", "底版厚", "ts", P["t_slab"] * 100, "cm", "本案設計"),
 ("1.12", "預鑄溝蓋板厚", "tc", P["t_cover"] * 100, "cm", "B20：t=23"),
 ("1.13", "蓋板單塊寬（沿溝向）", "bp", 100, "cm", "B20：每塊 100 cm"),
 ("1.14", "鋼筋混凝土單位重", "gc", 2.4, "t/m³", "一般值"),
 ("1.15", "土壤單位重", "gs", 1.9, "t/m³", "【待確認】無地質資料"),
 ("1.16", "靜止土壓係數", "K0", 0.5, "－", "【待確認】無地質資料"),
 ("1.17", "交通超載等值土高", "hs", 0.6, "m", "AASHTO 3.20.3（2 ft）"),
 ("1.18", "HS20-44 後輪重", "Pw", 7.26, "t", "公路橋梁設計規範"),
 ("#2", "乙種預鑄溝蓋板（全斷面，主筋 ⑩ D16）"),
 ("2.1", "計算跨徑（支承中心距 W＋tw）", "Lc", "=({W}+{tw})/100", "m", "簡支"),
 ("2.2", "衝擊係數", "Ii", "=MIN(15.24/({Lc}+38),0.3)", "－", "公路橋梁設計規範"),
 ("2.3", "分布寬 E＝1.22＋0.06S", "Ew", "=1.22+0.06*{Lc}", "m", "大於單塊寬 1.0 m，輪重全由單塊承受"),
 ("2.4", "靜載重（蓋板＋AC 5 cm）", "wD", "={tc}/100*{gc}+0.05*2.3", "t/m²", ""),
 ("2.5", "靜載重彎矩（單塊）", "MD", "={wD}*{bp}/100*{Lc}^2/8", "t·m", "wL²/8"),
 ("2.6", "活載重彎矩（輪重置跨中，單塊）", "ML", "={Pw}*(1+{Ii})*{Lc}/4", "t·m", "PL/4"),
 ("2.7", "設計彎矩 Mu", "Mu2", "=1.2*{MD}+1.6*{ML}", "t·m", "1.2D＋1.6(L＋I)"),
 ("2.8", "底層主筋 ⑩ D16 支數（單塊）", "n10", 7, "支", "B20 乙種鋼筋表 ⑩ 14 支（上下層各 7）"),
 ("2.9", "主筋面積 As", "As2", "={n10}*{A16}", "cm²", ""),
 ("2.10", "有效深度 d＝tc−3−1.6/2", "d2", "={tc}-3-1.6/2", "cm", "保護層 3 cm（B20 附註 3）"),
 ("2.11", "應力塊深 a", "a2", "={As2}*{fyL}/(0.85*{fcc}*{bp})", "cm", ""),
 ("2.12", "設計彎矩強度 φMn", "phiM2", "=0.9*{As2}*{fyL}*({d2}-{a2}/2)/100000", "t·m", "φ＝0.90"),
 ("2.13", "彎矩檢核 Mu／φMn", "r2", "={Mu2}/{phiM2}", "－", "≦1.0 OK"),
 ("2.14", "設計剪力 Vu（輪重距支承 d）", "Vu2", "=1.2*{wD}*{bp}/100*{Lc}/2+1.6*{Pw}*(1+{Ii})*(1-{d2}/100/{Lc})", "t", ""),
 ("2.15", "混凝土剪力強度 φVc", "phiV2", "=0.75*0.53*SQRT({fcc})*{bp}*{d2}/1000", "t", "φ＝0.75"),
 ("2.16", "箍筋 ⑧ D13 U 形 @15，每斷面取 2 組 Av", "Av2", "=4*{A13}", "cm²", "B20 乙種鋼筋表 ⑧ 30 支 @15；保守取 2 組"),
 ("2.17", "φ(Vc＋Vs)", "phiVs2", "=0.75*(0.53*SQRT({fcc})*{bp}*{d2}+{Av2}*{fyS}*{d2}/15)/1000", "t", "Vs＝Av·fy·d／s"),
 ("2.18", "剪力檢核 Vu／φ(Vc＋Vs)", "rv2", "={Vu2}/{phiVs2}", "－", "≦1.0 OK（依規範彎矩設計之版亦可免檢剪力）"),
 ("#3", "甲種預鑄溝蓋板（格柵開口 73 cm，開口段由兩側肋承受）"),
 ("3.1", "開口段兩側肋合計寬 b＝bp−73", "b3", "={bp}-73", "cm", "B20 甲種詳圖：開口 73×63"),
 ("3.2", "設計彎矩 Mu（同乙種，輪重經格柵傳至肋）", "Mu3", "={Mu2}", "t·m", "保守取同值"),
 ("3.3", "底層主筋 ① D19 支數（兩肋）", "n1", 4, "支", "B20 甲種鋼筋表 ① 8 支（上下層各 4）"),
 ("3.4", "主筋面積 As", "As3", "={n1}*{A19}", "cm²", ""),
 ("3.5", "有效深度 d＝tc−3−1.9/2", "d3", "={tc}-3-1.9/2", "cm", ""),
 ("3.6", "應力塊深 a", "a3", "={As3}*{fyL}/(0.85*{fcc}*{b3})", "cm", ""),
 ("3.7", "設計彎矩強度 φMn", "phiM3", "=0.9*{As3}*{fyL}*({d3}-{a3}/2)/100000", "t·m", ""),
 ("3.8", "彎矩檢核 Mu／φMn", "r3", "={Mu3}/{phiM3}", "－", "≦1.0 OK"),
 ("3.9", "肋剪力 Vu（輪重全量經肋傳至支承）", "Vu3", "=1.6*{Pw}*(1+{Ii})", "t", "保守"),
 ("3.10", "箍筋 ④ D13 U 形 @7.5，兩肋 Av", "Av3", "=4*{A13}", "cm²", "B20 甲種鋼筋表 ④ 22 支 @7.5"),
 ("3.11", "φ(Vc＋Vs)", "phiV3", "=0.75*(0.53*SQRT({fcc})*{b3}*{d3}+{Av3}*{fyS}*{d3}/7.5)/1000", "t", "Vs＝Av·fy·d／s"),
 ("3.12", "剪力檢核 Vu／φ(Vc＋Vs)", "rv3", "={Vu3}/{phiV3}", "－", "≦1.0 OK"),
 ("#4", "側牆（懸臂，外側主筋 A D16 @15）"),
 ("4.1", "牆頂深度（蓋板厚）", "z1", "={tc}/100", "m", "路面起算"),
 ("4.2", "牆底深度（底版頂）", "z2", "=({tc}+{H})/100", "m", ""),
 ("4.3", "懸臂長 h＝z2−z1", "hw", "={z2}-{z1}", "m", ""),
 ("4.4", "土壓彎矩（梯形分布）", "ME", "={K0}*{gs}*({z1}*{hw}^2/2+{hw}^3/6)", "t·m/m", "∫K0γz(z2−z)dz"),
 ("4.5", "超載彎矩", "MS", "={K0}*{gs}*{hs}*{hw}^2/2", "t·m/m", ""),
 ("4.6", "設計彎矩 Mu", "Mu4", "=1.6*({ME}+{MS})", "t·m/m", "1.6H＋1.6L"),
 ("4.7", "主筋面積 As（D16 @15）", "As4", "={A16}*100/15", "cm²/m", "S-01 鋼筋 A"),
 ("4.8", "有效深度 d＝tw−5−1.6/2", "d4", "={tw}-5-1.6/2", "cm", "接土面保護層 5 cm"),
 ("4.9", "應力塊深 a", "a4", "={As4}*{fyL}/(0.85*{fcb}*100)", "cm", ""),
 ("4.10", "設計彎矩強度 φMn", "phiM4", "=0.9*{As4}*{fyL}*({d4}-{a4}/2)/100000", "t·m/m", ""),
 ("4.11", "彎矩檢核 Mu／φMn", "r4", "={Mu4}/{phiM4}", "－", "≦1.0 OK"),
 ("4.12", "設計剪力 Vu", "Vu4", "=1.6*{K0}*{gs}*(({z1}+{z2})/2*{hw}+{hs}*{hw})", "t/m", ""),
 ("4.13", "φVc", "phiV4", "=0.75*0.53*SQRT({fcb})*100*{d4}/1000", "t/m", ""),
 ("4.14", "剪力檢核 Vu／φVc", "rv4", "={Vu4}/{phiV4}", "－", "≦1.0 OK"),
 ("#5", "底版（地反力上推，內側上層筋 B D13 @15）"),
 ("5.1", "底版寬 B＝W＋2tw", "Bb", "=({W}+2*{tw})/100", "m", ""),
 ("5.2", "兩牆中心距", "Lb", "=({W}+{tw})/100", "m", ""),
 ("5.3", "輪重沿溝向分布長（蓋板寬＋45° 擴散至底版）", "Ld", "={bp}/100+({tc}+{H})/100", "m", "單側擴散，保守"),
 ("5.4", "靜載重（蓋板、AC、兩側牆、緣石）", "WD5", "={wD}*{Bb}+2*{tw}/100*{H}/100*{gc}+0.2*0.15*{gc}", "t/m", "底版自重直接平衡，不計"),
 ("5.5", "活載重", "WL5", "={Pw}*(1+{Ii})/{Ld}", "t/m", ""),
 ("5.6", "設計總載重 Wu", "Wu5", "=1.2*{WD5}+1.6*{WL5}", "t/m", ""),
 ("5.7", "跨中彎矩 Mu＝Wu(L/4−B/8)", "Mu5", "={Wu5}*({Lb}/4-{Bb}/8)", "t·m/m", "均布地反力、兩牆線載重"),
 ("5.8", "主筋面積 As（D13 @15）", "As5", "={A13}*100/15", "cm²/m", "S-01 鋼筋 B 底版段"),
 ("5.9", "有效深度 d＝ts−4−1.3/2", "d5", "={ts}-4-1.3/2", "cm", ""),
 ("5.10", "應力塊深 a", "a5", "={As5}*{fyS}/(0.85*{fcb}*100)", "cm", ""),
 ("5.11", "設計彎矩強度 φMn", "phiM5", "=0.9*{As5}*{fyS}*({d5}-{a5}/2)/100000", "t·m/m", ""),
 ("5.12", "彎矩檢核 Mu／φMn", "r5", "={Mu5}/{phiM5}", "－", "≦1.0 OK"),
 ("5.13", "牆根剪力 Vu", "Vu5", "={Wu5}/2-{Wu5}/{Bb}*({Bb}-{Lb})/2", "t/m", ""),
 ("5.14", "φVc", "phiV5", "=0.75*0.53*SQRT({fcb})*100*{d5}/1000", "t/m", ""),
 ("5.15", "剪力檢核 Vu／φVc", "rv5", "={Vu5}/{phiV5}", "－", "≦1.0 OK"),
 ("5.16", "最少鋼筋 0.0018·b·h", "Amin5", "=0.0018*100*{ts}", "cm²/m", "As≧Amin"),
 ("#6", "集水井井壁（水平框架，E／F D13 @15）"),
 ("6.1", "井內寬", "Wi", P["well_in"] * 100, "cm", "本案設計"),
 ("6.2", "井壁中心距", "Lw", "=({Wi}+{tw})/100", "m", ""),
 ("6.3", "最大深度（路面至井底版底）", "zw", 1.6, "m", "井深約 1.37＋底版 0.2【待確認】"),
 ("6.4", "側壓 p＝K0γ(z＋hs)", "pw", "={K0}*{gs}*({zw}+{hs})", "t/m²", ""),
 ("6.5", "角隅彎矩 Mu＝1.6pL²/12", "Mu6", "=1.6*{pw}*{Lw}^2/12", "t·m/m", "四邊框架，角隅固接"),
 ("6.6", "主筋面積 As（D13 @15）", "As6", "={A13}*100/15", "cm²/m", "S-01 鋼筋 E、F"),
 ("6.7", "有效深度 d＝tw−5−1.3/2", "d6", "={tw}-5-1.3/2", "cm", ""),
 ("6.8", "設計彎矩強度 φMn", "phiM6", "=0.9*{As6}*{fyS}*({d6}-{As6}*{fyS}/(0.85*{fcb}*100)/2)/100000", "t·m/m", ""),
 ("6.9", "彎矩檢核 Mu／φMn", "r6", "={Mu6}/{phiM6}", "－", "≦1.0 OK"),
 ("6.10", "剪力 Vu＝1.6pL/2", "Vu6", "=1.6*{pw}*{Lw}/2", "t/m", ""),
 ("6.11", "φVc", "phiV6", "=0.75*0.53*SQRT({fcb})*100*{d6}/1000", "t/m", ""),
 ("6.12", "剪力檢核 Vu／φVc", "rv6", "={Vu6}/{phiV6}", "－", "≦1.0 OK"),
 ("#7", "縱向配力筋（溫度及收縮鋼筋，沿溝向；新增鋼筋 E D13 @25 內外兩層）"),
 ("7.1", "側牆水平鋼筋最小比 ρh", "rhw", 0.0025, "－", "混凝土結構設計規範 牆之最少水平鋼筋（D13、fy＜4200 取 0.0025）"),
 ("7.2", "側牆最少水平鋼筋 Ah,min＝ρh·b·tw", "Ahw", "={rhw}*100*{tw}", "cm²/m", "每公尺牆高"),
 ("7.3", "配置 E：D13 @25 內外兩層", "Asw7", "=2*{A13}*100/25", "cm²/m", "內外層各 D13 @25"),
 ("7.4", "側牆檢核 Ah,min／As", "r7w", "={Ahw}/{Asw7}", "－", "≦1.0 OK"),
 ("7.5", "側牆間距上限 min(3tw, 45)", "smw", "=MIN(3*{tw},45)", "cm", "採 25 cm ≦ 上限 OK"),
 ("7.6", "底版溫度及收縮鋼筋比 ρt", "rts", 0.0020, "－", "混凝土結構設計規範 版之溫度鋼筋（fy 2800 取 0.0020）"),
 ("7.7", "底版最少溫度鋼筋 At,min＝ρt·b·ts", "Ats", "={rts}*100*{ts}", "cm²/m", "每公尺版寬"),
 ("7.8", "配置 E：D13 @25 上下兩層", "Ass7", "=2*{A13}*100/25", "cm²/m", "上下層各 D13 @25"),
 ("7.9", "底版檢核 At,min／As", "r7s", "={Ats}/{Ass7}", "－", "≦1.0 OK"),
 ("7.10", "底版間距上限 min(5ts, 45)", "sms", "=MIN(5*{ts},45)", "cm", "採 25 cm ≦ 上限 OK"),
 ("7.11", "外層 A 筋路徑長 2(H＋10)＋(W＋30)", "Po", "=2*({H}+10)+({W}+30)", "cm", "S-01 鋼筋 A 形狀 L=360"),
 ("7.12", "內層 B 筋路徑長 2H＋(W＋10)", "Pi", "=2*{H}+({W}+10)", "cm", "S-01 鋼筋 B 形狀 L=320"),
 ("7.13", "每斷面縱向筋支數＝(Po÷25 取整＋1)＋(Pi÷25 取整＋1)", "nE", "=ROUNDUP({Po}/25,0)+1+ROUNDUP({Pi}/25,0)+1", "支", ""),
 ("7.14", "搭接增量係數（12 m 定尺，搭接 40db＝52 cm）", "kL", "=1+0.52/12", "－", "規範受拉搭接長度【待確認】"),
 ("7.15", "縱向筋 E 每公尺重量＝nE×0.994×kL", "wE", "={nE}*0.994*{kL}", "kg/m", "回饋 S-01 每公尺數量表、數量計算書"),
]
CHECKS = [("乙種預鑄溝蓋板 彎矩", "r2"), ("乙種預鑄溝蓋板 剪力", "rv2"), ("甲種預鑄溝蓋板 彎矩", "r3"), ("甲種預鑄溝蓋板 剪力", "rv3"),
          ("側牆 彎矩", "r4"), ("側牆 剪力", "rv4"), ("底版 彎矩", "r5"), ("底版 剪力", "rv5"), ("集水井井壁 彎矩", "r6"), ("集水井井壁 剪力", "rv6"),
          ("側牆 縱向配力筋（最少水平鋼筋）", "r7w"), ("底版 縱向配力筋（溫度及收縮鋼筋）", "r7s")]

wb = Workbook(); ws = wb.active; ws.title = "配筋檢核"
HF = PatternFill("solid", fgColor="3E5C76"); SF = PatternFill("solid", fgColor="D8DFE6"); thin = Side(style="thin", color="1F2D3A")
BD = Border(left=thin, right=thin, top=thin, bottom=thin); DK = "1F2D3A"
ws.append(["項次", "項目", "符號", "數值", "單位", "說明／出處"])
for c in ws[1]: c.font = Font(name="微軟正黑體", size=25, bold=True, color="FFFFFF"); c.fill = HF; c.alignment = Alignment(horizontal="center", vertical="center"); c.border = BD
ws.row_dimensions[1].height = 42
cell = {}
for r in R:
    if r[0].startswith("#"):
        ws.append(["", r[1]]); rr = ws.max_row; ws.merge_cells(start_row=rr, start_column=2, end_row=rr, end_column=6)
        for c in ws[rr]: c.fill = SF; c.border = BD
        ws.cell(rr, 2).font = Font(name="微軟正黑體", size=20, bold=True, color=DK); ws.row_dimensions[rr].height = 34; continue
    no, item, sym, val, unit, note = r
    ws.append([no, item, sym, None, unit, note]); rr = ws.max_row; cell[sym] = f"D{rr}"
    if isinstance(val, str):
        f = val
        for k in sorted(cell, key=len, reverse=True): f = f.replace("{" + k + "}", cell[k])
        assert "{" not in f, (sym, f); ws.cell(rr, 4, f)
    else: ws.cell(rr, 4, val)
    for j in range(1, 7):
        c = ws.cell(rr, j); c.font = Font(name="微軟正黑體", size=14, color=DK); c.border = BD
        c.alignment = Alignment(horizontal="center" if j in (1, 3, 5) else ("right" if j == 4 else "left"), vertical="center", wrap_text=True)
    ws.cell(rr, 4).number_format = "0.0000" if sym in ("rhw", "rts") else ("0.000" if sym == "kL" else "0.00")
    ws.row_dimensions[rr].height = 30 if len(note) < 30 and len(item) < 26 else 48
# 結論表
ws.append([]); ws.append(["", "檢核結論"]); rr = ws.max_row; ws.merge_cells(start_row=rr, start_column=2, end_row=rr, end_column=6)
for c in ws[rr]: c.fill = SF; c.border = BD
ws.cell(rr, 2).font = Font(name="微軟正黑體", size=20, bold=True, color=DK); ws.row_dimensions[rr].height = 34
for k, (nm, sym) in enumerate(CHECKS, 1):
    ws.append([f"8.{k}", nm, sym, f"={cell[sym]}", "－", f'=IF({cell[sym]}<=1,"OK（使用率 "&TEXT({cell[sym]},"0%")&"）","NG，需加筋")'])
    rr = ws.max_row
    for j in range(1, 7):
        c = ws.cell(rr, j); c.font = Font(name="微軟正黑體", size=14, color=DK); c.border = BD
        c.alignment = Alignment(horizontal="center" if j in (1, 3, 5) else ("right" if j == 4 else "left"), vertical="center")
    ws.cell(rr, 4).number_format = "0.00"; ws.row_dimensions[rr].height = 30
for col, w in zip("ABCDEF", (10, 46, 10, 14, 11, 52)): ws.column_dimensions[col].width = w
ws.freeze_panes = "B2"
ws.print_title_rows = "1:1"; ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.orientation = "landscape"
ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.8, bottom=0.8)
ws.oddHeader.center.text = f"{CFG['title_block']['project']}　箱涵式側溝配筋檢核"; ws.oddHeader.center.size = 12
ws.oddFooter.center.text = "辰璟工程技術顧問有限公司　第 &P 頁／共 &N 頁"; ws.oddFooter.center.size = 12
out = os.path.join(CFG["out_dir"], f"{CFG['file_prefix']}{stamp}_箱涵式側溝配筋檢核表_W110_v1.2.xlsx")
if os.path.exists(out): sys.exit(f"{out} 已存在，不覆蓋")
wb.save(out); print(out)
