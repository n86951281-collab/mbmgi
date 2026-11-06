"""圖冊前頁 2 張（ditch-design，由 P33 front_sheets 一般化；A3 橫式）。
  G-01 工程位置圖及圖目錄：左 Google 地圖底圖（front.map_png，標工程範圍、起終點、集水井 TWD97 座標），右圖目錄。
  G-02 一般說明：條文讀 front.notes_file（templates/ 或 data_dir 下的 json；{END}、{LA}… 由本程式代入）。
底圖：front.map_png（Edge 無頭模式擷取 Google 地圖嵌入頁），front.map 給中心經緯度 lat0／lon0、zoom、倍率 dpr、
      嵌入框中心在視窗的 CSS 座標 cx／cy、裁切範圍 crop（原圖像素）。
圖目錄：依 design.ditches（PP 張數）、橫斷面刀數（plan_base.section_cuts，每張 6 刀）、standards.sheets 組成，存 work_dir/toc.json。
用法：python front_sheets.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
"""
import sys, os, json, math, datetime
import numpy as np
import ezdxf
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dd
S = dd.sheet_module()
from p33_sheet import Sheet, frame, tw, PT, TXT
import twd97
import plan_base as B

CFG = dd.CFG; P_ = dd.P_; stamp = dd.stamp
OUT = dd.OUT; PRE = dd.PRE; PREV = os.path.join(OUT, "00_前頁")
base = f"{PRE}{stamp}_A3_工程位置圖及一般說明_{dd.ver('front')}_TWD97_GENIE"
LAYERS = {"圖框": (7, None, "#000000", 0.50), "圖標欄": (7, None, "#000000", 0.35), "表格": (7, None, "#000000", 0.25),
          "工程範圍": (7, None, "#000000", 0.50), "工程範圍填線": (7, None, "#000000", 0.25), "標註": (7, None, "#000000", 0.25),
          "文字": (7, None, "#000000", 0.0)}

CL = B.CLn
LEN = {k: float(np.hypot(*(B.SIDES[k][0][1] - B.SIDES[k][0][0]))) for k in B.KEYS}
LA = LEN[B.KEYS[0]]; LB = LEN[B.KEYS[-1]]; LC = float(np.hypot(*(CL[1] - CL[0])))
END = f"0K+{LC:06.2f}"

# ======================= G-01 工程位置圖及圖目錄 =======================
sh1 = Sheet("工程位置圖及圖目錄"); frame(sh1, sh1.name, ["NTS"], "G-01")
sh1.wf = 0.7; sh1.text(210.0, 274.0, CFG["title_block"]["project"], "center", 10.6); sh1.wf = S.WF

# --- 底圖：裁切並換算世界座標 → 紙面 ---
SRC = dd.src(CFG["front"]["map_png"])
_m = CFG["front"]["map"]
LAT0, LON0, Z, DPR, CX, CY = _m["lat0"], _m["lon0"], _m["zoom"], _m["dpr"], _m["cx"], _m["cy"]
CROP = tuple(_m["crop"])                                                  # 原圖像素
MX0, MW = 18.0, 204.0; MH = MW * (CROP[3] - CROP[1]) / (CROP[2] - CROP[0]); MY1 = 244.0; MY0 = MY1 - MH
img = Image.open(SRC).convert("RGB").crop(CROP)
map_png = os.path.join(OUT, f"{PRE}{stamp}_工程位置圖底圖_Google_z{Z}.png"); img.save(map_png)
SC = 256 * 2 ** Z / (2 * math.pi)
def merc(lat): return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
def W2P(p):
    lat, lon = twd97.to_latlon(*p)
    px = (CX + math.radians(lon - LON0) * SC) * DPR - CROP[0]; py = (CY - (merc(lat) - merc(LAT0)) * SC) * DPR - CROP[1]
    return np.array([MX0 + px * MW / (CROP[2] - CROP[0]), MY1 - py * MW / (CROP[2] - CROP[0])])
sh1.image(map_png, (MX0, MY0, MX0 + MW, MY1)); sh1.rect(MX0, MY0, MW, MH, "表格")

# --- 工程範圍：中心線兩側各 8 m 框＋45° 填線 ---
tv = (CL[1] - CL[0]) / LC; nv = np.array([-tv[1], tv[0]]); HW = 8.0
QP = np.array([W2P(q) for q in (CL[0] - nv * HW, CL[0] + nv * HW, CL[1] + nv * HW, CL[1] - nv * HW)])
sh1.poly(np.vstack([QP, QP[:1]]), "工程範圍")
lo, hi = QP.min(axis=0), QP.max(axis=0); hh = hi[1] - lo[1]
for c in np.arange(lo[0] - hh, hi[0], 1.2):
    t0 = max(0.0, (lo[0] - c) / hh); t1 = min(1.0, (hi[0] - c) / hh)
    if t1 > t0: sh1.line(c + t0 * hh, lo[1] + t0 * hh, c + t1 * hh, lo[1] + t1 * hh, "工程範圍填線")
# --- 標註：多重引線（使用者 2026-11-06：同平面圖，箭頭＋水平連字線），四個點標 TWD97 座標 ---
pN = W2P(CL[0]); pS = W2P(CL[1]); pM = (pN + pS) / 2
def xy(p): return f"E={p[0]:.3f}　N={p[1]:.3f}"
WID = B.WELL_ID
sh1.mleader(tuple(pN), pN[0] + 34.0, pN[1] + 34.0, ["工程起點 0K+000"], 1)
sh1.mleader(tuple(pS), pS[0] + 34.0, pS[1] - 34.0, [f"工程終點 {END}"], 1)
for key in reversed(B.KEYS):
    P, sd = B.SIDES[key]
    L_ = float(np.hypot(*(P[1] - P[0])))
    for j, (w_, dy) in enumerate(((P[0], 15.0), (P[1], -15.0))):
        q = W2P(w_); lab = f"{key}0K+{(0.0 if j == 0 else L_):06.2f}".replace("+000.00", "+000") + (f"（{WID[(key, j)]}）" if (key, j) in WID else "")
        sh1.mleader(tuple(q), q[0] + sd * 30.0, q[1] + dy, [lab, xy(w_)], sd)
sh1.mleader(tuple(pM + np.array([-1.7, 0])), pM[0] - 34.0, pM[1], ["新設側溝式箱涵", f"W×H＝{P_['W']*100:.0f}×{P_['H']*100:.0f} cm"], -1)
sh1.text(MX0, MY0 - 31.0, "座標系統：TWD97（TM2，m）。", "left", PT)
cN = np.array([MX0 + MW - 14.0, MY1 - 24.0])                              # 指北針
sh1.poly([cN + (0, -9), cN + (0, 9)], "標註"); sh1.poly([cN + (-3.5, 3.5), cN + (0, 9), cN + (3.5, 3.5)], "標註")
sh1.text(cN[0], cN[1] + 14.0, "N", "center", PT)
sh1.text(MX0 + MW / 2, MY0 - 9.0, "工程位置圖", "center", TXT)
w0 = tw("工程位置圖", TXT)
for dy in (14.5, 15.7): sh1.line(MX0 + MW / 2 - w0 / 2 - 2, MY0 - dy, MX0 + MW / 2 + w0 / 2 + 2, MY0 - dy, "標註")
sh1.text(MX0, MY0 - 24.0, "底圖：Google 地圖（©Google），僅示工程位置。", "left", PT)

# --- 圖目錄 ---
STD = [tuple(x) for x in CFG["standards"]["sheets"]]                     # standards.sheets：[圖號, 圖名, 比例]
NX = math.ceil((len(B.section_cuts()) + 1) / 6)                           # 橫斷面張數（每張 6 刀，末格放說明；同 cross_sections.py）
TOC = [("G-01", "工程位置圖及圖目錄", "NTS"), ("G-02", "一般說明", "NTS")] + \
      ([("L-01", "地籍套繪圖", "1/500")] if CFG.get("cadastre", {}).get("dxf") else []) + \
      [("P-01", "新設側溝平面配置圖", "1/500")] + \
      [(f"PP-{i:02d}", f"{k}0K 平面及縱斷面圖", "H1/500 V1/50") for i, k in enumerate(B.KEYS, 1)] + \
      [(f"X-{i:02d}", f"設計橫斷面圖（{i}/{NX}）", "1/100") for i in range(1, NX + 1)] + STD
dd.write_json("toc.json", TOC)

cols = [232.0, 252.0, 270.0, 358.0, 404.0]; RH_ = 9.4; ytop = 244.0
sh1.text(cols[0], ytop + 8.0, "設計圖目錄", "left", TXT)
rows = [("張次", "圖號", "圖　　名", "比例")] + [(f"{k+1:02d}/{len(TOC):02d}", no, nm, sc) for k, (no, nm, sc) in enumerate(TOC)]
ybot = ytop - RH_ * len(rows)
for k, r in enumerate(rows):
    y = ytop - RH_ * (k + 0.5)
    for j, v in enumerate(r):
        if j == 2 and k > 0: sh1.text(cols[2] + 2.0, y, v, "left", PT)
        else: sh1.text((cols[j] + cols[j + 1]) / 2, y, v, "center", PT)
    sh1.line(cols[0], ytop - RH_ * (k + 1), cols[-1], ytop - RH_ * (k + 1), "表格")
sh1.line(cols[0], ytop, cols[-1], ytop, "表格")
for x in cols: sh1.line(x, ytop, x, ybot, "表格")

# ======================= G-02 一般說明 =======================
sh2 = Sheet("一般說明"); frame(sh2, sh2.name, ["NTS"], "G-02")
def _notes_path(fn):
    for d in (os.path.join(os.path.dirname(dd.HERE), "templates"), dd.DATA):
        if os.path.exists(os.path.join(d, fn)): return os.path.join(d, fn)
    return dd.src(fn)
_V = dict(END=END, LA=LA, LB=LB, W_cm=P_["W"] * 100, H_cm=P_["H"] * 100, well_cm=P_["well_in"] * 100, n_wells=len(dd.WELLS),
          well_ids="、".join(w["id"] for w in dd.WELLS), pile_type=dd.SHO.get("type", "鋼軌樁"), pile_l=dd.PILE_L, pile_sp=dd.PILE_SP)
NOTES = [(k, t.format(**_V)) for k, t in json.load(open(_notes_path(CFG["front"]["notes_file"]), encoding="utf-8-sig"))["notes"]]
COLX = (18.0, 216.0); CW = 186.0; LH = 6.6; TOP = 278.0; BOT = 38.0; y = TOP; col = 0   # 2026-11-06：行距 6.6（1.33 倍字高），兩欄放得下
def wrap(s, width):
    """依寬度換行；不在英數字（含小數點、＝、=）中間斷行"""
    out, cur = [], ""
    keep = lambda c: c.isascii() and (c.isalnum() or c in ".=＝+-×") or c in "＝×"
    for ch in s:
        if tw(cur + ch, PT) > width:
            k = len(cur)
            while k > 0 and keep(cur[k - 1]) and keep(ch if k == len(cur) else cur[k]): k -= 1
            if k == 0: k = len(cur)
            out.append(cur[:k]); cur = cur[k:] + ch
        else: cur += ch
    return out + ([cur] if cur else [])
for i_, (kind, t) in enumerate(NOTES):
    ind = 0.0 if kind == "H" else tw("10.", PT) + 1.5
    lines = [t] if kind == "H" else wrap(t, CW - ind)
    need = len(lines) * LH + 3.0
    if kind == "H" and i_ + 1 < len(NOTES):                          # 節標題與下一條同欄，不落單
        need += len(wrap(NOTES[i_ + 1][1], CW - tw("10.", PT) - 1.5)) * LH
    if y - need < BOT:
        if col == 0: col = 1; y = TOP
        else: raise SystemExit("一般說明超過兩欄，請精簡條文或改 A3 多頁")
    if kind == "H": y -= 1.5
    x = COLX[col]
    for k, s in enumerate(lines):
        if kind != "H" and k == 0: sh2.text(x, y, f"{kind}.", "left", PT)
        sh2.text(x + ind, y, s, "left", PT); y -= LH
    if kind == "H": y -= 1.5

assert y > BOT - 1.0, f"一般說明出界 y={y}"
# ======================= 輸出 =======================
for sh in (sh1, sh2): S.check(sh, ("工程範圍", "標註", "表格"))
dxf, pdf, pngs = S.save([sh1, sh2], LAYERS, OUT, PREV, base)
print("DXF：", dxf); print("PDF：", pdf); print("PNG：", pngs); print("底圖：", map_png)
