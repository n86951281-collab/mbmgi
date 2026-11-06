"""設計橫斷面（ditch-design，由 P33 cross_sections 一般化）：A3 橫式 1/100，每張 6 刀。

- 斷面樁號以道路中心線 0K+000 為準（垂直中心線），自有設施樁位起切：集水井、各側交接面、每 alignment.spacing（20 m）；
  每刀畫各側新設構造物與面積（挖、填、混凝土、墊層）。
- 臨時擋土：temp_shoring（樁長 pile_l、間距 pile_sp；路外側樁心距外壁 offset_out、路內側 offset_in）；
  集水井段路外側樁打在既有側溝外緣線上，井往路內側移 plan_base.WELL_SHIFT。
- 既有側溝示意位置以 252 斜線表示（依測量圖既有側溝邊線與溝名尺寸），施工前拆除。
- 版面：CL 在框上、樁號在框下置中加底線、面積各側一列在樁號下靠右（P33 使用者 CAD 手調 v1.4__V2）。
地面：design.ground（SG 用 sg.tin_npz，EG 用 tin_npz）；挖填面積以所選地面計。
用法：python cross_sections.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
輸出：A3 設計橫斷面 DXF＋PDF＋PNG；work_dir/section_areas.csv（數量計算書讀）。
限制：引線版面照 P33 兩側側溝（第一條在左、最後一條在右）；單側或三條以上側溝要調整版面。
"""
import sys, os, json, csv, math, re, datetime
import numpy as np
import matplotlib.tri as mtri
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
import p33_sheet as S
from p33_sheet import Sheet, frame, check, save, tw, tbox, PT
import plan_base as B

S = dd.sheet_module()
CFG = B.CFG; P_ = B.P_; stamp = dd.stamp
OUT = dd.OUT; PREV = os.path.join(OUT, "05_橫斷面"); KEYS = B.KEYS
HALF = 9.0; SC = 10.0
OUTER = B.OUTER; EXC = B.EXC_HALF; WEXC = B.WELL_EXC_HALF; HW = B.HALF_W
TC, TS, TB, TWL = P_["t_cover"], P_["t_slab"], P_["t_bed"], P_["t_wall"]

ds = np.load(dd.src(CFG["sg"]["tin_npz"] if dd.USE_SG else CFG["tin_npz"]))
Gsg = mtri.LinearTriInterpolator(mtri.Triangulation(ds["points"][:, 0], ds["points"][:, 1], ds["triangles"]), ds["points"][:, 2])
def z_at(xy): xy = np.atleast_2d(xy); return np.ma.filled(Gsg(xy[:, 0], xy[:, 1]), np.nan)
DP = {}
for key in KEYS:
    r = list(csv.DictReader(open(dd.work(f"design_profile_{key}.csv"), encoding="utf-8-sig")))
    DP[key] = {k: np.array([float(x[k]) for x in r]) for k in ("樁距m", "溝頂高m", "溝底高m", "開挖底高m")}

# 既有側溝：測量圖既有側溝線段＋溝名（WxH）
EX_SEG = [(a, b) for P, lay in B.FEATS if lay == "既有側溝" for a, b in zip(P[:-1], P[1:])]
EX_LAB = []
for p, t in B.MLAB:
    m_ = re.search(r"(\d+)\s*[Xx×]\s*(\d+)", t)
    if m_: EX_LAB.append((p, int(m_.group(1)) / 100, int(m_.group(2)) / 100, t))
def existing(pc, n):
    """斷面線 pc + x·n 與既有側溝線交點 → [(x1, x2, H, 名稱)]"""
    xs = []
    for a, b in EX_SEG:
        d = b - a; M = np.column_stack([n, -d])
        if abs(np.linalg.det(M)) < 1e-9: continue
        x, t = np.linalg.solve(M, a - pc)
        if 0 <= t <= 1 and -HALF <= x <= HALF: xs.append(x)
    xs = sorted(xs); out = []; i = 0
    while i < len(xs) - 1:
        g = xs[i + 1] - xs[i]
        if 0.3 <= g <= 1.4:
            mid = pc + n * (xs[i] + xs[i + 1]) / 2
            xm = (xs[i] + xs[i + 1]) / 2
            same = [r for r in EX_LAB if abs((r[0] - B.C0) @ B.nv - xm) < 2.0]   # 同一條溝線上的溝名（橫距差 < 2 m）
            lab = min(same, key=lambda r: np.hypot(*(r[0] - mid))) if same else None
            H = lab[2] if lab and np.hypot(*(lab[0] - mid)) < 200 else 0.8
            out.append((xs[i], xs[i + 1], H, lab[3] if lab and np.hypot(*(lab[0] - mid)) < 200 else "既有側溝")); i += 2
        else: i += 1
    return out

sta = dd.sta0

# ---------------- 斷面樁號：以道路中心線 0K+000 為準，自有設施處起切（使用者 2026-11-06）----------------
GEO = {}
for key in KEYS:
    P, side = B.SIDES[key]; L = float(np.hypot(*(P[1] - P[0]))); u = (P[1] - P[0]) / L
    c0 = float((P[0] - B.C0) @ B.tv); c1 = float((P[1] - B.C0) @ B.tv); k_ = (c1 - c0) / L     # 側溝樁距 → 中心線樁距
    GEO[key] = dict(P=P, side=side, L=L, u=u, c0=c0, c1=c1, k=k_)
def c_of(key, s): g = GEO[key]; return g["c0"] + g["k"] * s
SP = float(CFG["alignment"].get("spacing", 20.0))
wells0 = [c_of(k, 0.0) for k in KEYS]; wells1 = [c_of(k, GEO[k]["L"]) for k in KEYS]
juncs0 = sorted((c_of(k, HW), k) for k in KEYS); juncs1 = sorted((c_of(k, GEO[k]["L"] - HW), k) for k in KEYS)
CUTS = [(round(float(np.mean(wells0)), 2), f"集水井 {B.well_names(0)}")] + [(round(c + 0.02, 2), f"{k} 側交接面") for c, k in juncs0]
CUTS += [(float(v), "") for v in np.arange(SP, min(c for c, _ in juncs1) - 1.0, SP) if v > max(c for c, _ in juncs0) + 1.0]
CUTS += [(round(c - 0.02, 2), f"{k} 側交接面") for c, k in juncs1] + [(round(float(np.mean(wells1)), 2), f"集水井 {B.well_names(1)}")]

def side_at(key, pc):
    """斷面（過中心線點 pc、方向 nv）與該側溝中心線交點：側溝樁距 s、橫距 xo、類別"""
    g = GEO[key]; M = np.column_stack([g["u"], -B.nv]); s, xo = np.linalg.solve(M, pc - g["P"][0])
    if -HW <= s <= HW or g["L"] - HW <= s <= g["L"] + HW: kind = "well"
    elif HW < s < g["L"] - HW: kind = "junc" if min(abs(s - HW), abs(s - (g["L"] - HW))) < 0.1 else "ditch"
    else: kind = None
    return float(s), float(xo), kind

secs = []
for st, note in CUTS:
    pc = B.C0 + B.tv * st
    xs_ = np.arange(-HALF, HALF + 1e-9, 0.1); gz = z_at(pc[None, :] + xs_[:, None] * B.nv[None, :])
    rec = dict(st=st, note=note, x=xs_, gz=gz, ex=existing(pc, B.nv), side={})
    for key in KEYS:
        s, xo, kind = side_at(key, pc); g = GEO[key]; D = DP[key]
        if kind is None: rec["side"][key] = None; continue
        sc = min(max(s, 0.0), g["L"])
        top = float(np.interp(sc, D["樁距m"], D["溝頂高m"])); bot = float(np.interp(sc, D["樁距m"], D["溝底高m"]))
        fl = bot - P_["sump"] if kind == "well" else bot; exc = fl - TS - TB
        e_in, e_out = B.exc_offsets(key, kind == "well")
        xl, xr = (xo - e_out, xo + e_in) if g["side"] < 0 else (xo - e_in, xo + e_out)       # 東為正；A 路外在西
        xx = np.linspace(xl, xr, 43); road = z_at(pc[None, :] + xx[:, None] * B.nv[None, :])
        xc_ = xo - g["side"] * B.WELL_SHIFT if kind == "well" else xo                         # 結構中心（集水井往路內移）
        ow = HW if kind == "well" else OUTER
        rd_side = np.r_[road[xx <= xc_ - ow], road[xx >= xc_ + ow]] if kind == "well" else np.r_[road[xx <= xo - ow], road[xx >= xo + ow]]
        rec["side"][key] = dict(s=s, xo=xo, xc=xc_, kind=kind, side=g["side"], top=top, bot=bot, fl=fl, exc=exc, xl=xl, xr=xr,
                                road=float(np.interp(xc_, xx, road)), cut=float(np.trapezoid(road - exc, xx)),
                                fill=float((B.WORK_GAP + B.GAP_OUT) * (np.mean(rd_side) - TC - exc)) if len(rd_side) else 0.0,
                                conc=(2 * TWL * (top - bot) + (P_["W"] + 2 * TWL) * TS) if kind != "well" else (2 * TWL * (top - fl) + 2 * HW * TS),
                                bed=2 * ow * TB)
    secs.append(rec)
print("斷面樁號：", [(c, n) for c, n in CUTS])

# ---------------- 出圖 ----------------
LAYERS = {
    "圖框": (7, None, "#000000", 0.50), "圖標欄": (7, None, "#000000", 0.35), "資料帶": (7, None, "#000000", 0.25),
    "格線": (254, "DOT", "#CCCCCC", 0.212), "SG地面線": (7, None, "#000000", 0.35), "斷面中心線": (22, "DASHDOT", "#000000", 0.18),
    "設計側溝": (7, None, "#000000", 0.50), "溝蓋板": (7, None, "#000000", 0.35), "墊層": (7, None, "#000000", 0.25),
    "開挖線": (253, "DASHED", "#7A7A7A", 0.30), "鋼軌樁": (7, None, "#000000", 0.60), "鐵板": (7, "DASHED", "#000000", 0.25),
    "既有側溝": (252, None, "#666666", 0.20), "隱藏線": (7, "DASHED", "#000000", 0.18),
    "標註": (7, None, "#000000", 0.18), "文字": (7, None, "#000000", 0.0),
}
KN = {"well": "集水井", "junc": "交接面", "ditch": "側溝"}
PER = 6; NC = 2; CW_ = 200.0; RH_ = 84.0
NSH = math.ceil((len(secs) + 1) / PER); sheets = []                   # 末格放說明
for pi in range(NSH):
    sh = Sheet(f"設計橫斷面圖({pi+1}/{NSH})"); frame(sh, sh.name, ["H=1/100", "V=1/100"], f"X-{pi+1:02d}"); sheets.append(sh)
    for k, R in enumerate(secs[pi * PER:(pi + 1) * PER]):
        col, row = k % NC, k // NC
        x0 = 10.0 + col * CW_; y0 = 287.0 - (row + 1) * RH_
        xc = x0 + 106.0; bx0, bx1 = xc - HALF * SC, xc + HALF * SC
        g0 = np.nanmean([v["road"] for v in R["side"].values() if v])
        base = math.floor((g0 - 3.0 - 0.2) * 2) / 2; top_z = base + 4.5          # 框底在地面下約 3.2 m，鋼軌樁 L=3 m 全長可見
        yb = y0 + 32.0; yt = yb + (top_z - base) * SC
        X = lambda x: xc + x * SC; Y = lambda z: yb + (min(max(z, base), top_z) - base) * SC
        sh.rect(bx0, yb, bx1 - bx0, yt - yb, "資料帶")
        for z in np.arange(math.ceil(base), top_z, 1.0):
            if base < z < top_z: sh.line(bx0, Y(z), bx1, Y(z), "格線", "DOT")
            sh.text(bx0 - 1.5, Y(z), f"{z:.0f}", "right", PT)
        # 2026-11-06 使用者 V2：框內不畫豎格線
        for x in (-8, -4, 4, 8): sh.text(X(x), yb - 6.0, ("左" if x < 0 else "右") + f"{abs(x)}", "center", PT)
        sh.text(X(0), yt + 4.5, "CL", "center", PT)
        sh.line(X(0), yb, X(0), yt, "斷面中心線", "DASHDOT")
        ok = ~np.isnan(R["gz"])
        if ok.any(): sh.poly(np.column_stack([X(R["x"][ok]), [Y(z) for z in R["gz"][ok]]]), "SG地面線")
        for x1, x2, H, nm in R["ex"]:                                     # 既有側溝（拆除）：252 斜線
            zt = float(np.interp((x1 + x2) / 2, R["x"][ok], R["gz"][ok])); zb_ = zt - H
            X1, X2, Yt, Yb = X(x1), X(x2), Y(zt), Y(zb_)
            sh.poly([(X1, Yt), (X1, Yb), (X2, Yb), (X2, Yt)], "既有側溝")
            c = X1 - (Yt - Yb)
            while c < X2:
                xa, xb = max(X1, c), min(X2, c + (Yt - Yb))
                if xa < xb: sh.line(xa, Yb + (xa - c), xb, Yb + (xb - c), "既有側溝")
                c += 1.2
        lines_ = []
        for key in KEYS:
            v = R["side"][key]
            if v is None: lines_.append(f"{key}側：無新設構造物"); continue
            c = v["xc"]; tp, bt, fl, ex = v["top"], v["bot"], v["fl"], v["exc"]
            o = HW if v["kind"] == "well" else OUTER; w = (P_["well_in"] if v["kind"] == "well" else P_["W"]) / 2
            sh.poly([(X(c - o), Y(tp)), (X(c - o), Y(fl - TS)), (X(c + o), Y(fl - TS)), (X(c + o), Y(tp)),
                     (X(c + w), Y(tp)), (X(c + w), Y(fl)), (X(c - w), Y(fl)), (X(c - w), Y(tp)), (X(c - o), Y(tp))], "設計側溝")
            if v["kind"] != "well":
                for sg in (-1, 1): sh.poly([(X(c + sg * w), Y(bt + 0.2)), (X(c + sg * (w - 0.2)), Y(bt))], "設計側溝")
            sh.rect(X(c - o), Y(ex), 2 * o * SC, TB * SC, "墊層")
            sh.rect(X(c - o), Y(tp), 2 * o * SC, TC * SC, "溝蓋板")
            xo_c = c + v["side"] * (o - 0.1); sh.rect(X(xo_c - 0.1), Y(tp + TC), 2.0, 1.5, "溝蓋板")      # 場鑄緣石（路外側）
            if v["kind"] == "junc":
                cw_ = c - v["side"] * B.WELL_SHIFT
                sh.poly([(X(cw_ - HW), Y(tp)), (X(cw_ - HW), Y(fl - P_["sump"] - TS)), (X(cw_ + HW), Y(fl - P_["sump"] - TS)), (X(cw_ + HW), Y(tp))], "隱藏線", "DASHED")
            for xp, sg in ((v["xl"], -1), (v["xr"], 1)):                   # 鋼軌樁＋背插鐵板（路外側貼外壁 10 cm）
                gp = float(np.interp(xp, R["x"][ok], R["gz"][ok]))
                sh.line(X(xp), Y(gp + 0.1), X(xp), Y(gp - B.PILE_L + 0.1), "鋼軌樁")
                sh.line(X(xp - sg * 0.05), Y(gp), X(xp - sg * 0.05), Y(ex), "鐵板", "DASHED")
            sh.poly([(X(v["xl"]), Y(ex)), (X(v["xr"]), Y(ex))], "開挖線", "DASHED")
            # 渠底高併入多重引線（使用者 V2）
            lines_.append(f"{key}側（{KN[v['kind']]}）：挖 {v['cut']:.2f}　填 {v['fill']:.2f}　混凝土 {v['conc']:.2f}　墊層 {v['bed']:.2f} m²")
        va, vb = R["side"].get(KEYS[0]), (R["side"].get(KEYS[-1]) if len(KEYS) > 1 else None)
        if va:                                                           # A 側（左）：既有側溝打除＋新設側溝式箱涵
            ca, oa = va["xc"], (HW if va["kind"] == "well" else OUTER); wa = (P_["well_in"] if va["kind"] == "well" else P_["W"]) / 2
            tx = X(ca - oa) - 6.5
            xw0 = (tx - 40.0 - xc) / SC; xw1 = (tx - xc) / SC                # 文字所在橫距範圍：取其中最高地面，字放在地面線下
            sel = (R["x"][ok] >= xw0) & (R["x"][ok] <= xw1)
            g_ = R["gz"][ok][sel] if sel.any() else np.array([float(np.interp(ca - oa - 1.0, R["x"][ok], R["gz"][ok]))])
            yg = Y(float(np.min(g_))) - 3.2                               # 地面線下的字塊：取範圍內最低地面
            gmax = Y(float(np.max(g_)))                                   # 地面線上的字：取範圍內最高地面
            exA = [r for r in R["ex"] if (r[0] + r[1]) / 2 < 0]
            if exA:
                x1, x2, H, nm = max(exA, key=lambda r: r[1]); zt = float(np.interp((x1 + x2) / 2, R["x"][ok], R["gz"][ok]))
                gtop = gmax
                if yt - gtop >= PT + 3.0: ty = (gtop + yt) / 2            # 地面線上方空白放得下就放上方（2026-11-06：CAD 行距 1.8h，下方留給三行字塊）
                else: ty = yg - PT / 2; yg = ty - PT / 2 - 2.6
                sh.mleader((X(x1 + 0.12), Y(zt - 0.3)), tx, ty, ["既有側溝打除"], -1)
            if va["kind"] == "well":
                dim = f"集水井W×H={P_['well_in']:.2f}×{va['top'] - TC - va['fl']:.2f}(m)"
            else:
                dim = f"W×H={P_['W']:.2f}×{P_['H']:.2f}(m)"
            hl = PT * S.ML_HL; ty = yg - PT / 2 - hl
            sh.mleader((X(ca - wa), Y(va["fl"])), tx, ty, ["新設側溝式箱涵", dim, f"渠底EL+{va['fl']:.2f}"], -1)
        if vb:                                                           # B 側（右）：臨時擋土鋼軌樁
            xp = vb["xr"]; ex_ = vb["exc"]; wb = (P_["well_in"] if vb["kind"] == "well" else P_["W"]) / 2
            ygb = Y(float(np.interp(xp + 1.0, R["x"][ok], R["gz"][ok]))) - 3.2 - PT / 2
            sh.mleader((X(vb["xc"] + wb), Y(vb["fl"])), X(xp) + 9.0, ygb, [f"渠底EL+{vb['fl']:.2f}"], 1)
            typ = max(Y(ex_ - 0.5) - 3.5, yb + PT * S.ML_HL / 2 + PT / 2 + 2.5)          # 不壓框底
            sh.mleader((X(xp), min(Y(ex_ - 0.5), typ + 3.5)), X(xp) + 9.0, typ, ["臨時擋土", f"鋼軌樁L={B.PILE_L:.0f}@{B.PILE_SP:.0f}m"], 1)
        lab = sta(R["st"]) + (f"（{R['note']}）" if R["note"] else "")
        ws = tw(lab, PT)
        sh.text(xc, yb - 7.2, lab, "center", PT)
        sh.line(xc - ws / 2 - 0.5, yb - 10.4, xc + ws / 2 + 0.5, yb - 10.4, "標註")
        exn = "、".join(sorted(set(r[3] for r in R["ex"]))) or "無"
        for j, t in enumerate(lines_ + [f"既有側溝：{exn}（施工前拆除）"]): sh.text(xc + 88.0, yb - 13.0 - 5.6 * j, t, "right", PT)
    if pi == NSH - 1:                                                    # 末格：說明
        k = len(secs) - pi * PER; col, row = k % NC, k // NC
        x0 = 10.0 + col * CW_ + 8; ytop = 287.0 - row * RH_ - 10
        _dn = CFG["alignment"].get("downstream_dir", "")
        _lr = "、".join(("左側 " if d.get("lr", "left") == "left" else "右側 ") + d["side"] + ("（" + d["dir"] + "）" if d.get("dir") else "") for d in dd.DITCHES)
        for j, t in enumerate(["說明：", "1. 斷面樁號為道路中心線樁號（0K+000 起算），", f"　 自有設施之樁位開始標示；面向下游{'（' + _dn + '）' if _dn else ''}，",
                               f"　 {_lr}。", f"2. 比例 H＝V＝1/100；高程 m；面積 m²（挖方以 {dd.GROUND} 計）。",
                               "3. 斜線為既有側溝示意位置，施工前拆除。", f"4. {dd.SHO.get('type', '鋼軌樁')} L={B.PILE_L:g} m @{B.PILE_SP:.1f} m 背插鐵板；",
                               f"　 路外側樁心距外壁 {B.GAP_OUT*100:.0f} cm（鐵板兼外模），路內側 {B.WORK_GAP*100:.0f} cm；",
                               "　 集水井段路外側樁打在既有側溝外緣線上。"]):
            sh.text(x0, ytop - 7.6 * j, t, "left", PT)

for sh in sheets: check(sh, ("設計側溝", "溝蓋板", "開挖線", "SG地面線", "鋼軌樁", "資料帶", "既有側溝", "隱藏線"))
base = f"{dd.PRE}{stamp}_A3_設計橫斷面圖_{dd.ver('cross_sections')}_{dd.GROUND}_TWD97_GENIE"
dxf, pdf, pngs = save(sheets, LAYERS, OUT, PREV, base)
with open(dd.work("section_areas.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["中心線樁號", "說明", "側", "側溝樁距m", "類別", f"{dd.GND}m", "溝頂高m", "溝底(井底)高m", "開挖底高m", "挖方m2", "回填m2", "溝體混凝土m2", "墊層m2"])
    for R in secs:
        for key in KEYS:
            v = R["side"][key]
            if v: w.writerow([sta(R["st"]), R["note"], key, round(v["s"], 2), KN[v["kind"]], round(v["road"], 3), round(v["top"], 3), round(v["fl"], 3), round(v["exc"], 3),
                              round(v["cut"], 2), round(v["fill"], 2), round(v["conc"], 2), round(v["bed"], 2)])
        print(sta(R["st"]), R["note"], {k: (KN[v["kind"]], round(v["s"], 2), round(v["cut"], 2)) if v else None for k, v in R["side"].items()})
print("DXF：", dxf); print("PDF：", pdf); [print("PNG：", p) for p in pngs]
