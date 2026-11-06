"""平面及縱斷面圖 PP（ditch-design，由 P33 plan_profile 一般化）：每條側溝一張 A3 橫式，上平面 1/500、下縱斷面 H1/500 V1/50。
資料帶由上而下：坡度、挖深、地面高、溝頂高、溝底高、樁號、單距；縱斷面框自資料欄起；流向箭頭與渠底平行。
右欄：指北、比例、圖例、控制點及集水井座標表（井中心）。
輸入：work_dir/design_profile_<側別>.csv（design_profiles.py）、plan_base 幾何。
用法：python plan_profile.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
"""
import sys, os, csv, math, datetime
import numpy as np
import ezdxf
from ezdxf.enums import TextEntityAlignment as TA
from ezdxf.render import mleader
from ezdxf.math import Vec2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
S = dd.sheet_module()
from p33_sheet import frame, tw, PT, TXT, WF, W_, H_
import plan_base as B

CFG = B.CFG; P_ = B.P_; stamp = dd.stamp
OUT = dd.OUT; PRE = dd.PRE; PREV = os.path.join(OUT, "03_設計縱斷面")
base = f"{PRE}{stamp}_A3_平面及縱斷面圖_{'_'.join(k + '0K' for k in B.KEYS)}_{dd.ver('plan_profile')}_{dd.GROUND}_TWD97_GENIE"
GL = "SG 整地後地面" if dd.USE_SG else "原地面（路面）"
HS, VS = 500.0, 50.0; XM = 1000 / HS; YM = 1000 / VS
LAYERS = {
    "圖框": (7, None, "#000000", 0.50), "圖標欄": (7, None, "#000000", 0.35), "資料帶": (7, None, "#000000", 0.25),
    "格線": (254, "DOT", "#CCCCCC", 0.212), "主格線": (253, "DASHED", "#A3A3A3", 0.212),
    "地物": (253, None, "#A3A3A3", 0.15), "SF地物": (253, None, "#B5B5B5", 0.12), "既有側溝": (252, None, "#666666", 0.25),
    "中心線1": (22, "CENTER", "#000000", 0.18), "設計側溝": (7, None, "#000000", 0.60),
    "路面線": (252, None, "#666666", 0.30), "設計溝頂線": (7, None, "#000000", 0.60), "設計溝底線": (7, None, "#000000", 0.60),
    "開挖線": (253, "DASHED", "#7A7A7A", 0.25), "集水井": (7, None, "#000000", 0.45), "RCP": (7, "DASHED", "#000000", 0.35),
    "鋼軌樁": (7, None, "#000000", 0.30), "標註": (7, None, "#000000", 0.18), "表格": (7, None, "#000000", 0.25), "文字": (7, None, "#000000", 0.0),
}
PLAN_BG = ("地物", "SF地物", "既有側溝")

class Sheet(S.Sheet):
    def __init__(self, name): super().__init__(name); self.mls = []
    def mleader(self, tgt, tx, ty, lines, side):
        """多重引線（DXF 寫 MLEADER）；預覽另存 mltext／mlpoly／mlfill"""
        self.mls.append((tuple(tgt), (tx, ty), list(lines), side)); n = len(lines); hl = PT * S.ML_HL
        for j, t in enumerate(lines):
            self.items.append(("mltext", (tx, ty + (n - 1) / 2 * hl - j * hl), t, "left" if side > 0 else "right", PT, 0, self.wf))
        dog = np.array([tx - side * 5.0, ty]); land = np.array([tx - side * 1.0, ty]); T = np.array(tgt, float)
        self.items.append(("mlpoly", np.array([T, dog, land]), "標註", None))
        u = (dog - T) / np.hypot(*(dog - T)); nn = np.array([-u[1], u[0]])
        self.items.append(("mlfill", np.array([T, T + u * 2.5 + nn * 0.7, T + u * 2.5 - nn * 0.7]), "標註", None))
    def arrow(self, x0, y0, x1, y1, layer="標註"):
        self.line(x0, y0, x1, y1, layer); u = np.array([x1 - x0, y1 - y0]); u /= np.hypot(*u); n = np.array([-u[1], u[0]])
        self.items.append(("mlfill", np.array([(x1, y1), (x1, y1) - u * 3.0 + n * 0.9, (x1, y1) - u * 3.0 - n * 0.9]), layer, None))

def tbox(it):
    _, (x, y), s, ha, h, rot, wf = it; w = tw(s, h, wf)
    if rot == 0:
        x0 = x if ha == "left" else x - w / 2 if ha == "center" else x - w; return (x0, y - h / 2, x0 + w, y + h / 2)
    y0 = y if ha == "left" else y - w / 2 if ha == "center" else y - w; return (x - h / 2, y0, x + h / 2, y0 + w)
def sta(s, pre):
    if abs(s - round(s)) < 1e-6: k = int(round(s)); return f"{pre}{k//1000}K+{k%1000:03d}"
    return f"{pre}{int(s)//1000}K+{s%1000:06.2f}"

def load(key):
    rows = list(csv.DictReader(open(dd.work(f"design_profile_{key}.csv"), encoding="utf-8-sig")))
    g = lambda c: np.array([float(r[c]) for r in rows])
    s = g("樁距m"); D = dict(key=key, s=s, L=float(s[-1]), road=g(f"{dd.GND}m"), top=g("溝頂高m"), bot=g("溝底高m"), exc=g("開挖底高m"), dig=g("挖深m"))
    D["wf"] = {0.0: D["bot"][0] - P_["sump"], D["L"]: D["bot"][-1] - P_["sump"]}
    return D

ROWS = ["坡度(%)", "挖深(m)", f"{dd.GND}(m)", "溝頂高(m)", "溝底高(m)", "樁號", "單距(m)"]   # 2026-11-06 使用者：單距與樁號對調
RH = {"坡度(%)": 9.0, "單距(m)": 9.0, "樁號": 18.0}
TCW = 30.0; BX0 = 20.0; DX0 = BX0 + TCW; RX = 324.0          # 右欄起點
PV = (BX0, 214.0, 318.0, 284.0); PVY = 247.0                 # 平面視窗、中心線紙面 y
sheets = []
SP = float(CFG["alignment"].get("spacing", 20.0))
for no, key in enumerate(B.KEYS, 1):
    D = load(key); L, s = D["L"], D["s"]
    sh = Sheet(f"{key}0K 平面及縱斷面圖"); frame(sh, sh.name, ["H=1/500", "V=1/50"], f"PP-{no:02d}"); sheets.append(sh)
    X0 = DX0 + 22.0; xs = lambda v: X0 + v * XM; BX1 = xs(L) + 22.0
    at = lambda v, arr: float(np.interp(v, s, arr))
    # ================= 平面 1/500 =================
    Pk, side = B.SIDES[key]
    T = B.make_T(Pk[0], X0, PVY + float((Pk[0] - B.C0) @ B.nv) * XM, XM)
    V = (PV[0], PV[1], BX1, PV[3])
    for P, lay in B.FEATS:
        for q in B.clip(T(P), V): sh.poly(q, lay)
    for q in B.clip(T(np.array([B.CLn[0] - B.tv * 30, B.CLn[1] + B.tv * 30])), V): sh.poly(q, "中心線1")
    for k2 in B.KEYS:
        polys, Lk, u, n = B.ditch_polys(k2)
        for P, lay in polys:
            for q in B.clip(T(P), V): sh.poly(q, "設計側溝" if lay == "設計側溝" else "集水井")
        for Ln in B.pile_lines(k2):
            for q in B.clip(T(Ln), V): sh.poly(q, "鋼軌樁")
    u = (Pk[1] - Pk[0]) / L; outw = B.nv * side
    sts = sorted(set([float(v) for v in np.arange(0, L, SP)] + [L]))
    for v in sts:                                                # 本側樁號：溝外側短線＋直書樁號
        q0 = T((Pk[0] + u * v + outw * (B.OUTER + 0.4))[None, :])[0]
        sh.line(q0[0], q0[1], q0[0], q0[1] + side * 2.5, "標註")
        sh.text(q0[0], q0[1] + side * 3.5, sta(v, key), "left" if side > 0 else "right", PT, 90)
    for sc, nm in ((0.0, B.WELL_ID[(key, 0)]), (L, B.WELL_ID[(key, 1)])):          # 集水井編號
        c = T((Pk[0] + u * sc + outw * (B.WELL_EXC_HALF + 0.3))[None, :])[0]       # 路外側、井的上下游外
        sh.text(c[0] + (-3.0 if sc == 0 else 3.0), c[1] + side * 2.5, nm, "right" if sc == 0 else "left", PT)
    # （2026-11-06 側溝內移後道路內側無空間：側溝名稱改由縱斷面多重引線標示，流向見縱斷面與圖例）
    placed = [tbox(it) for it in sh.items if it[0] == "text"]
    dsegs = [(a, c) for it in sh.items if it[0] == "poly" and it[2] in ("設計側溝", "集水井", "中心線1", "標註", "鋼軌樁") for a, c in zip(it[1][:-1], it[1][1:])]
    def on_line(b):
        return any(b[0] - 0.8 < x < b[2] + 0.8 and b[1] - 0.8 < y < b[3] + 0.8 for a, c in dsegs for x, y in (a + (c - a) * t for t in np.linspace(0, 1, 60)))
    for p, t in B.MLAB:                                          # 既有溝名稱（避開已放文字、設計線、中心線）
        q = T(p[None, :])[0]
        if not (V[0] + 5 < q[0] < V[2] - 5 and V[1] + 3 < q[1] < V[3] - 3): continue
        for dx, dy in ((0, 0), (0, 4), (0, -4), (-8, 0), (8, 0), (0, 8), (0, -8), (-8, 4), (-8, -4), (0, 12), (0, -12)):
            it = ("text", (q[0] + dx, q[1] + dy), t, "center", PT, 0, WF); b = tbox(it)
            if not any(b[0] < r[2] and r[0] < b[2] and b[1] < r[3] and r[1] < b[3] for r in placed) and V[1] < b[1] and b[3] < V[3] and not on_line(b):
                sh.items.append(it); placed.append(b); break
    # ================= 縱斷面 =================
    y = 34.0; rowy = {}
    for nm in reversed(ROWS):
        h = RH.get(nm, 13.0); rowy[nm] = (y, h); y += h
    PY0 = y
    zlo = min(min(D["wf"].values()) - P_["t_slab"], D["exc"].min()) - 0.2; zhi = np.nanmax(D["road"]) + 0.2
    BASE = math.floor(zlo * 2) / 2; TOP = math.ceil(zhi * 2) / 2
    ys = lambda z: PY0 + (z - BASE) * YM; PY1 = ys(TOP)
    sh.rect(DX0, PY0, BX1 - DX0, PY1 - PY0, "資料帶")                 # 使用者 V2：縱斷面框自資料欄起（不含列名欄）
    z = BASE
    while z <= TOP + 1e-9:
        if BASE < z < TOP:
            sh.line(DX0, ys(z), BX1, ys(z), "主格線" if abs(z - round(z)) < 1e-9 else "格線", "DASHED" if abs(z - round(z)) < 1e-9 else "DOT")
            if abs(z - round(z)) < 1e-9: sh.text(DX0 - 2, ys(z), f"{z:.0f}", "right", PT)
        z += 0.5
    for nm in ROWS:
        y0, h = rowy[nm]; sh.rect(BX0, y0, TCW, h, "資料帶"); sh.rect(DX0, y0, BX1 - DX0, h, "資料帶")
        sh.text(BX0 + TCW / 2, y0 + h / 2, nm, "center", PT)
    sh.text(BX0 + TCW / 2, (PY0 + PY1) / 2, "高程(m)", "center", PT, 90)
    sh.poly(np.column_stack([xs(s), ys(D["road"])]), "路面線")
    sh.poly(np.column_stack([xs(s), ys(D["top"])]), "設計溝頂線")
    sh.poly(np.column_stack([xs(s), ys(D["bot"])]), "設計溝底線")
    sh.poly(np.column_stack([xs(s), ys(D["exc"])]), "開挖線", "DASHED")
    half = P_["well_in"] / 2
    for sc, sd in ((0.0, -1), (L, 1)):
        fl = D["wf"][sc]; rd = at(sc, D["road"])
        xi0, xi1 = xs(sc - half), xs(sc + half); xo0, xo1 = xs(sc - half - P_["well_wall"]), xs(sc + half + P_["well_wall"])
        sh.poly([(xi0, ys(rd - P_["t_cover"])), (xi0, ys(fl)), (xi1, ys(fl)), (xi1, ys(rd - P_["t_cover"]))], "集水井")
        sh.poly([(xo0, ys(rd)), (xo0, ys(fl - P_["t_slab"])), (xo1, ys(fl - P_["t_slab"])), (xo1, ys(rd)), (xo0, ys(rd))], "集水井")
        sh.line(xo0, ys(rd - P_["t_cover"]), xo1, ys(rd - P_["t_cover"]), "集水井")
        inv = fl + P_["sump"]; xe = xo1 if sd > 0 else xo0
        sh.line(xe, ys(inv), xe + sd * 12.0, ys(inv), "RCP", "DASHED")
    xst = [xs(v) for v in sts]
    for v, x in zip(sts, xst):
        sh.line(x, PY0, x, ys(at(v, D["exc"])), "格線", "DOT")
        for nm, arr in (("挖深(m)", D["dig"]), (f"{dd.GND}(m)", D["road"]), ("溝頂高(m)", D["top"]), ("溝底高(m)", D["bot"])):
            y0, h = rowy[nm]; sh.text(x - 0.7, y0 + h / 2, f"{at(v, arr):.2f}", "center", PT, 90)
        y0, h = rowy["樁號"]; sh.text(x - 0.7, y0 + h / 2, sta(v, key), "center", PT, 90)
    for a, b, xa, xb in zip(sts[:-1], sts[1:], xst[:-1], xst[1:]):
        y0, h = rowy["坡度(%)"]; sh.text((xa + xb) / 2, y0 + h / 2, f"{(at(b, D['bot']) - at(a, D['bot'])) / (b - a) * 100:.2f}", "center", PT)
        y0, h = rowy["單距(m)"]; sh.text((xa + xb) / 2, y0 + h / 2, f"{b-a:.2f}", "center", PT)
    for sc, sd in ((0.0, 1), (L, -1)):                           # 多重引線：集水井
        fl = D["wf"][sc]; rd = at(sc, D["road"]); x = xs(sc); hw = (rd - P_["t_cover"] - fl) * 100
        nm = B.WELL_ID[(key, 0 if sc == 0 else 1)]
        sh.mleader((x, ys((rd + fl) / 2)), x + sd * 9.0, PY1 + 8.0,
                   [f"新設側溝式箱涵集水井 {nm} W×H＝{P_['well_in']*100:.0f}×{hw:.0f} cm（內徑）", f"井底 EL.{fl:.2f}／RCP 管底 EL.{fl+P_['sump']:.2f}"], sd)
    st_ = 0.28 * L; zt = at(st_, D["top"]); zb = at(st_, D["bot"]); zr = at(st_, D["road"])
    sh.mleader((xs(st_), ys((zt + zb) / 2)), xs(st_) + 14.0, ys(zr) + 13.0,
               [f"新設側溝式箱涵 #{key} W×H＝{P_['W']*100:.0f}×{P_['H']*100:.0f} cm（含溝蓋板 t={P_['t_cover']*100:.0f} cm）"], 1)
    s1, s2 = 0.60 * L, 0.80 * L; off = 5.0                          # 流向箭頭與渠底平行（渠底上方 5 mm，往 0K+000）
    sh.arrow(xs(s2), ys(at(s2, D["bot"])) + off, xs(s1), ys(at(s1, D["bot"])) + off)
    sh.text(xs((s1 + s2) / 2), ys(at((s1 + s2) / 2, D["bot"])) + off + 5.0, "流向", "center", PT)
    # ================= 右欄 =================
    nvec = np.array([np.array([0, 1]) @ B.tv, np.array([0, 1]) @ B.nv]); nvec /= np.hypot(*nvec)
    cN = np.array([RX + 12.0, 262.0]); tip = cN + nvec * 7; tail = cN - nvec * 7; pn = np.array([-nvec[1], nvec[0]])
    sh.line(*tail, *tip, "標註"); sh.items.append(("mlfill", np.array([tip, tip - nvec * 3.5 + pn * 1.4, tip - nvec * 3.5 - pn * 1.4]), "標註", None))
    sh.text(*(tip + nvec * 4.5), "N", "center", PT)
    sh.text(RX + 28.0, 270.0, "平面圖", "left", TXT); sh.text(RX + 28.0, 260.0, "S＝1/500", "left", PT)
    sh.text(RX, 232.0, "縱斷面圖", "left", TXT); sh.text(RX, 222.0, "縱 1/50、橫 1/500", "left", PT)
    sh.text(RX, 213.0, "（單位除註明外為公尺）", "left", PT)
    yl = 200.0; sh.text(RX, yl, "圖　例", "left", TXT); yl -= 10.0
    for lay, lt, lab in (("路面線", None, GL), ("設計溝頂線", None, "設計溝頂／溝底"), ("開挖線", "DASHED", "開挖底"),
                         ("RCP", "DASHED", "RCP 管底"), ("集水井", None, "集水井"), ("鋼軌樁", None, "臨時鋼軌樁（平面）"), ("中心線1", "CENTER", "道路中心線")):
        sh.line(RX, yl, RX + 12, yl, lay, lt); sh.text(RX + 15.0, yl, lab, "left", PT); yl -= 8.0
    yl -= 2.0; sh.arrow(RX + 12.0, yl, RX, yl); sh.text(RX + 15.0, yl, "流向", "left", PT)
    # 控制點及放樣座標表
    _ra = CFG["alignment"].get("plan_range", [-30.0, B.Lc + 30.0])
    rows = [(nm, p) for nm, p in B.CPTS if _ra[0] <= (p[:2] - B.C0) @ B.tv <= _ra[1] and abs((p[:2] - B.C0) @ B.nv) < 20]

    rows = sorted(rows, key=lambda r: r[0])
    for sc, nm in ((0.0, B.WELL_ID[(key, 0)]), (L, B.WELL_ID[(key, 1)])):
        c = B.well_center(key, sc); rows.append((f"{nm} 井中心", np.array([c[0], c[1], D["wf"][sc]])))
    cw = [22.0, 22.0, 23.0, 13.0]; cx = [RX - 4.0]
    for w_ in cw: cx.append(cx[-1] + w_)
    rh = 7.4; yt = 108.0
    sh.text(RX - 4.0, yt + 6.5, "控制點及集水井座標表", "left", PT)
    hdr = ("點名", "X(E)", "Y(N)", "高程")
    tab = [hdr] + [(nm, f"{p[0]:.3f}", f"{p[1]:.3f}", f"{p[2]:.2f}") for nm, p in rows]
    for k, r in enumerate(tab):
        yy = yt - rh * (k + 0.5)
        for j, v in enumerate(r): sh.text((cx[j] + cx[j + 1]) / 2, yy, v, "center", PT)
        sh.line(cx[0], yt - rh * (k + 1), cx[-1], yt - rh * (k + 1), "表格")
    sh.line(cx[0], yt, cx[-1], yt, "表格")
    for xx in cx: sh.line(xx, yt, xx, yt - rh * len(tab), "表格")
    sh.text(RX - 4.0, yt - rh * len(tab) - 6.0, "井中心高程為井底高程。", "left", PT)
    print(f"{key}：L={L:.2f}，高程框 {BASE}～{TOP}，縱斷面頂 {PY1:.1f} mm；座標表 {len(rows)} 列（底 {yt - rh*len(tab):.1f} mm）")

# ---------- 檢查 ----------
def check(sh):
    segs = np.array([(a[0], a[1], b[0], b[1]) for it in sh.items if it[0] in ("poly", "mlpoly") and it[2] not in ("資料帶", "圖框", "圖標欄", "格線", "主格線") + PLAN_BG
                     for a, b in zip(it[1][:-1], it[1][1:])])
    TT = [tbox(it) for it in sh.items if it[0] in ("text", "mltext")]
    def hit(r):
        x0, y0, x1, y1 = r
        for sx0, sy0, sx1, sy1 in segs:
            for t in np.linspace(0, 1, 40):
                px, py = sx0 + (sx1 - sx0) * t, sy0 + (sy1 - sy0) * t
                if x0 < px < x1 and y0 < py < y1: return True
        return False
    bad = [it[2] for it in sh.items if it[0] in ("text", "mltext") and hit(tbox(it))]
    over = sum(1 for i in range(len(TT)) for j in range(i + 1, len(TT)) if TT[i][0] < TT[j][2] and TT[j][0] < TT[i][2] and TT[i][1] < TT[j][3] and TT[j][1] < TT[i][3])
    out = sum(1 for r in TT if r[0] < 10 or r[2] > 410 or r[1] < 10 or r[3] > 287)
    print(f"[檢查] {sh.name}：文字壓線 {len(bad)}{bad[:6] if bad else ''}、文字重疊 {over}、出界 {out}（平面底圖地物線不計）")
for sh in sheets: check(sh)

# ---------- DXF ----------
doc = ezdxf.new("R2018", setup=True); doc.header["$LTSCALE"] = 5
if "GENIE" not in doc.styles: doc.styles.add("GENIE", font="GENISO.shx").dxf.bigfont = "GENIE.shx"
for nm, (aci, lt, *_r) in LAYERS.items(): doc.layers.add(nm, color=aci, linetype=lt or "CONTINUOUS")
m = doc.modelspace()
for k, sh in enumerate(sheets):
    ox = k * 450.0
    for it in sh.items:
        if it[0] in ("mltext", "mlpoly"): continue
        if it[0] == "mlfill":
            if any(np.allclose(it[1][0], ml[0]) for ml in sh.mls): continue        # 多重引線箭頭由 MLEADER 畫
            m.add_solid([(p[0] + ox, p[1]) for p in (it[1][0], it[1][1], it[1][2])], dxfattribs={"layer": it[2]}); continue
        if it[0] == "poly":
            at_ = {"layer": it[2]}
            if it[3] and it[3] != LAYERS[it[2]][1]: at_["linetype"] = it[3]
            m.add_lwpolyline([(p[0] + ox, p[1]) for p in it[1]], dxfattribs=at_)
        else:
            _, (x, y), s_, ha, h, rot, wf = it
            t = m.add_text(s_, height=h, rotation=rot, dxfattribs={"layer": "文字", "style": "GENIE", "width": wf})
            t.set_placement((x + ox, y), align={"left": TA.MIDDLE_LEFT, "center": TA.MIDDLE_CENTER, "right": TA.MIDDLE_RIGHT}[ha])
    for tgt, (tx, ty), lines, side in sh.mls:
        ml = m.add_multileader_mtext("Standard", dxfattribs={"layer": "標註"})
        ml.set_content("\\P".join(f"\\W{WF};{t}" for t in lines), char_height=PT, style="GENIE",
                       alignment=mleader.TextAlignment.left if side > 0 else mleader.TextAlignment.right)
        ml.set_arrow_properties(size=2.5); ml.set_connection_properties(landing_gap=1.0, dogleg_length=4.0)
        ml.set_connection_types(left=mleader.HorizontalConnection.middle_of_text, right=mleader.HorizontalConnection.middle_of_text)
        ml.add_leader_line(mleader.ConnectionSide.left if side > 0 else mleader.ConnectionSide.right, [Vec2(tgt[0] + ox, tgt[1])])
        ml.build(insert=Vec2(tx + ox, ty + ((len(lines) - 1) * PT * S.ML_HL + PT) / 2))   # insert＝文字塊頂端
dxf_path = os.path.join(OUT, base + ".dxf")
if os.path.exists(dxf_path): sys.exit(f"{dxf_path} 已存在，不覆蓋")
doc.saveas(dxf_path)

# ---------- PDF + PNG ----------
fp = FontProperties(fname=r"C:\Windows\Fonts\msjhl.ttc")
pdf_path = os.path.join(OUT, base + ".pdf")
with PdfPages(pdf_path) as pdf:
    for k, sh in enumerate(sheets):
        fig = plt.figure(figsize=(W_ / 25.4, H_ / 25.4)); ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, W_); ax.set_ylim(0, H_); ax.set_aspect("equal"); ax.axis("off")
        for it in sh.items:
            if it[0] == "mlfill": ax.fill(it[1][:, 0], it[1][:, 1], color="#000000", lw=0); continue
            if it[0] in ("poly", "mlpoly"):
                aci, lt0, col, lw = LAYERS[it[2]]; lt = it[3] or lt0
                ax.plot(it[1][:, 0], it[1][:, 1], color=col, lw=lw * 72 / 25.4, ls=S.LS.get(lt, "-"), solid_capstyle="butt"); continue
            _, (x, y), s_, ha, h, rot, wf = it
            tp = TextPath((0, 0), s_, size=h, prop=fp); w = tw(s_, h, wf); sx = w / max(tp.get_extents().x1, 1e-6)
            a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
            ax.add_patch(PathPatch(Affine2D().scale(sx, 1).translate(a0, -h * 0.40).rotate_deg(rot).translate(x, y).transform_path(tp), color="#000000", lw=0))
        pdf.savefig(fig); png = os.path.join(PREV, f"{base}_p{k+1}.png"); fig.savefig(png, dpi=200); plt.close(fig); print("PNG：", png)
print("DXF：", dxf_path); print("PDF：", pdf_path)
