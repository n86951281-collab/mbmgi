"""P33 共用圖紙元件：A3 圖框／圖標欄、文字寬度、輸出 DXF／PDF／PNG、自動檢查。單位＝紙面 mm。"""
import os, math
import numpy as np
import ezdxf
from ezdxf.render import mleader as _mlr
from ezdxf.math import Vec2 as _V2
from ezdxf.enums import TextEntityAlignment as TA
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D

W_, H_ = 420.0, 297.0
TXT = 7.06; PT = 4.94; TBT = 4.94; WF = 0.5; TB_WF = 0.7
TB = dict(agency="臺中市政府水利局", agency_en="Taichung Water Resources Bureau",
          project="臺中市新社區東山街與協興街路口排水改善工程",
          designer="辰璟工程技術顧問有限公司", designer_en="Chen-Jing Engineering Co.,Ltd")
LS = {"DOT": (0, (1, 3)), "DASHED": (0, (6, 3)), "DOT2": (0, (1, 1.5)), "CENTER": (0, (12, 3, 3, 3)), "DASHDOT": (0, (8, 2, 1, 2))}

def tw(s, h=TXT, wf=WF): return wf * sum(h if ord(ch) > 255 else 0.6 * h for ch in s)

class Sheet:
    def __init__(self, name): self.items = []; self.name = name; self.wf = WF
    def poly(self, pts, layer, lt=None): self.items.append(("poly", np.asarray(pts, float), layer, lt))
    def line(self, x1, y1, x2, y2, layer, lt=None): self.poly([(x1, y1), (x2, y2)], layer, lt)
    def rect(self, x, y, w, h, layer): self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], layer)
    def fill(self, pts, layer): self.items.append(("fill", np.asarray(pts, float), layer))   # 實心填滿（箭頭、實心填充）
    def image(self, path, box): self.items.append(("image", path, tuple(box)))   # 點陣底圖：box＝紙面 (x0, y0, x1, y1)
    def mleader(self, tgt, tx, ty, lines, side, h=PT):
        """多重引線（DXF 寫 MLEADER，文字 14 pt）。side=+1 文字在引線右側、-1 在左側；(tx, ty)＝文字近引線端中點。
        預覽：mltext（列入文字檢查）／mlpoly（引線）／mlfill（箭頭）"""
        n = len(lines); hl = h * 1.5; T = np.array(tgt, float); i0 = len(self.items)
        for j, t in enumerate(lines):
            self.items.append(("mltext", (tx, ty + (n - 1) / 2 * hl - j * hl), t, "left" if side > 0 else "right", h, 0, self.wf))
        dog = np.array([tx - side * 5.0, ty]); land = np.array([tx - side * 1.0, ty])
        self.items.append(("mlpoly", np.array([T, dog, land]), "標註", None, i0))
        u = (dog - T) / np.hypot(*(dog - T)); nn = np.array([-u[1], u[0]])
        self.items.append(("mlfill", np.array([T, T + u * 2.5 + nn * 0.7, T + u * 2.5 - nn * 0.7]), "標註", None))
        self.items.append(("mlmeta", tuple(T), (tx, ty), list(lines), side, h))
    def text(self, x, y, s, ha="left", h=TXT, rot=0):
        if s.strip(): self.items.append(("text", (x, y), s, ha, h, rot, self.wf))   # 空字串不加（TextPath 無法處理）

def tbox(it):
    _, (x, y), s, ha, h, rot, wf = it; w = tw(s, h, wf); th = math.radians(rot)
    a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
    P = [(x + u * math.cos(th) - v * math.sin(th), y + u * math.sin(th) + v * math.cos(th)) for u in (a0, a0 + w) for v in (-h / 2, h / 2)]
    return (min(p[0] for p in P), min(p[1] for p in P), max(p[0] for p in P), max(p[1] for p in P))

def frame(sh, name, scales, no):
    sh.rect(0, 0, W_, H_, "圖框"); sh.rect(10, 10, 400, 277, "圖框"); sh.rect(10, 10, 400, 22, "圖標欄")
    for x in (86, 188, 226, 298, 392): sh.line(x, 10, x, 32, "圖標欄")
    for x0, x1 in ((86, 188), (226, 298), (392, 410)): sh.line(x0, 21, x1, 21, "圖標欄")
    sh.line(262, 10, 262, 32, "圖標欄")
    yc = (14.94, 20.88, 26.82); sh.wf = TB_WF
    sh.text(48, yc[2], "主辦機關", "center", TBT); sh.text(48, yc[1], TB["agency"], "center", TBT); sh.text(48, yc[0], TB["agency_en"], "center", TBT)
    sh.text(89.5, 26.5, "工程名稱：" + TB["project"], "left", TBT); sh.text(89.5, 15.5, "圖　名：" + name, "left", TBT)
    sh.text(207, yc[2], "比例尺", "center", TBT)
    if len(scales) == 1: sh.text(207, yc[1], scales[0], "center", TBT)
    else: sh.text(207, yc[1], scales[0], "center", TBT); sh.text(207, yc[0], scales[1], "center", TBT)
    sh.text(229.5, 26.5, "設計：", "left", TBT); sh.text(265.5, 26.5, "主管：", "left", TBT)
    sh.text(229.5, 15.5, "繪圖：", "left", TBT); sh.text(265.5, 15.5, "校核：", "left", TBT)
    sh.text(345, yc[2], "設計單位", "center", TBT); sh.text(345, yc[1], TB["designer"], "center", TBT); sh.text(345, yc[0], TB["designer_en"], "center", TBT)
    sh.text(401, 26.5, "圖號", "center", TBT); sh.text(401, 15.5, no, "center", TBT); sh.wf = WF

def check(sh, design_layers):
    """文字重疊、文字壓設計線、出界（圖標欄文字不計出界）"""
    TT = [it for it in sh.items if it[0] in ("text", "mltext")]
    T_ = [tbox(it) for it in TT]
    lead = 0
    for k, it in enumerate(sh.items):
        if it[0] != "mlpoly": continue
        own = {id(x) for x in sh.items[it[4]:k]}
        for q, r in zip(TT, T_):
            if id(q) in own: continue
            a, b = it[1][0], it[1][1]
            if any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 40)):
                lead += 1
                if os.environ.get("P33_DEBUG"): print("   引線壓字：", q[2])
    over = sum(1 for i in range(len(T_)) for j in range(i + 1, len(T_)) if T_[i][0] < T_[j][2] and T_[j][0] < T_[i][2] and T_[i][1] < T_[j][3] and T_[j][1] < T_[i][3])
    outb = sum(1 for r in T_ if (r[1] + r[3]) / 2 > 32 and (r[0] < 10 or r[2] > 410 or r[1] < 32 or r[3] > 287))
    segs = [(a, b) for it in sh.items if it[0] == "poly" and it[2] in design_layers for a, b in zip(it[1][:-1], it[1][1:])]
    press = sum(1 for r in T_ if any(any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 30)) for a, b in segs))
    if os.environ.get("P33_DEBUG"):
        for i in range(len(T_)):
            r = T_[i]
            if (r[1] + r[3]) / 2 > 32 and (r[0] < 10 or r[2] > 410 or r[1] < 32 or r[3] > 287): print("   出界：", TT[i][2], [round(v, 1) for v in r])
            for j in range(i + 1, len(T_)):
                q = T_[j]
                if r[0] < q[2] and q[0] < r[2] and r[1] < q[3] and q[1] < r[3]: print("   重疊：", TT[i][2], "／", TT[j][2])
            if any(any(r[0] < a[0] + (b[0] - a[0]) * t < r[2] and r[1] < a[1] + (b[1] - a[1]) * t < r[3] for t in np.linspace(0, 1, 30)) for a, b in segs): print("   壓線：", TT[i][2], [round(v, 1) for v in r])
    print(f"[檢查] {sh.name}：文字重疊 {over}、文字壓線 {press}、出界 {outb}、引線壓字 {lead}")
    return over, press + lead, outb

def save(sheets, layers, out_dir, prev_dir, base):
    """layers: 名稱 → (ACI, 線型, 預覽色, 預覽線寬mm)。DXF 各張橫向並排、間隔 450 mm。"""
    os.makedirs(prev_dir, exist_ok=True)
    doc = ezdxf.new("R2018", setup=True); doc.header["$LTSCALE"] = 5
    doc.styles.add("GENIE", font="GENISO.shx").dxf.bigfont = "GENIE.shx"
    for nm, (aci, lt, *_r) in layers.items(): doc.layers.add(nm, color=aci, linetype=lt or "CONTINUOUS")
    if "標註" not in doc.layers: doc.layers.add("標註", color=7)
    m = doc.modelspace()
    for k, sh in enumerate(sheets):
        ox = k * 450.0
        for it in sh.items:
            if it[0] in ("mltext", "mlpoly", "mlfill"): continue
            if it[0] == "fill":
                hh = m.add_hatch(dxfattribs={"layer": it[2]}); hh.paths.add_polyline_path([(p[0] + ox, p[1]) for p in it[1]], is_closed=True); continue
            if it[0] == "mlmeta":
                _, tgt, (tx, ty), lines, side, h = it
                ml = m.add_multileader_mtext("Standard", dxfattribs={"layer": "標註"})
                ml.set_content("\\P".join(f"\\W{WF};{t}" for t in lines), char_height=h, style="GENIE",
                               alignment=_mlr.TextAlignment.left if side > 0 else _mlr.TextAlignment.right)
                ml.set_arrow_properties(size=2.5); ml.set_connection_properties(landing_gap=1.0, dogleg_length=4.0)
                ml.add_leader_line(_mlr.ConnectionSide.left if side > 0 else _mlr.ConnectionSide.right, [_V2(tgt[0] + ox, tgt[1])])
                ml.build(insert=_V2(tx + ox, ty)); continue
            if it[0] == "image":                                # DXF 以 IMAGE 參照同資料夾的 PNG
                from PIL import Image as _Im
                _, pth, (x0, y0, x1, y1) = it; wpx, hpx = _Im.open(pth).size
                if "底圖" not in doc.layers: doc.layers.add("底圖", color=7)
                idef = doc.add_image_def(filename=os.path.basename(pth), size_in_pixel=(wpx, hpx))
                m.add_image(idef, insert=(x0 + ox, y0), size_in_units=(x1 - x0, y1 - y0), dxfattribs={"layer": "底圖"})
                continue
            if it[0] == "poly":
                at = {"layer": it[2]}
                if it[3] and it[3] != layers[it[2]][1]: at["linetype"] = it[3]
                if (it[3] or layers[it[2]][1]) == "DOT2": at["ltscale"] = 0.1      # 樣板 v4.0：原始地面線 DOT2 個別比例 0.1
                m.add_lwpolyline([(p[0] + ox, p[1]) for p in it[1]], dxfattribs=at)
            else:
                _, (x, y), s, ha, h, rot, wf = it
                t = m.add_text(s, height=h, rotation=rot, dxfattribs={"layer": "文字", "style": "GENIE", "width": wf})
                t.set_placement((x + ox, y), align={"left": TA.MIDDLE_LEFT, "center": TA.MIDDLE_CENTER, "right": TA.MIDDLE_RIGHT}[ha])
    dxf_path = os.path.join(out_dir, base + ".dxf")
    if os.path.exists(dxf_path): raise SystemExit(f"{dxf_path} 已存在，不覆蓋")
    doc.saveas(dxf_path)
    fp = FontProperties(fname=r"C:\Windows\Fonts\msjhl.ttc")
    pdf_path = os.path.join(out_dir, base + ".pdf"); pngs = []
    with PdfPages(pdf_path) as pdf:
        for k, sh in enumerate(sheets):
            fig = plt.figure(figsize=(W_ / 25.4, H_ / 25.4)); ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, W_); ax.set_ylim(0, H_); ax.set_aspect("equal"); ax.axis("off")
            for it in sh.items:
                if it[0] == "image":
                    _, pth, (x0, y0, x1, y1) = it
                    ax.imshow(plt.imread(pth), extent=(x0, x1, y0, y1), zorder=0, interpolation="lanczos"); continue
                if it[0] == "mlmeta": continue
                if it[0] == "fill": ax.fill(it[1][:, 0], it[1][:, 1], color=layers.get(it[2], (0, 0, "#000000"))[2], lw=0); continue
                if it[0] == "mlfill": ax.fill(it[1][:, 0], it[1][:, 1], color="#000000", lw=0); continue
                if it[0] == "mlpoly": ax.plot(it[1][:, 0], it[1][:, 1], color="#000000", lw=0.18 * 72 / 25.4); continue
                if it[0] == "poly":
                    aci, lt0, col, lw = layers[it[2]]; lt = it[3] or lt0
                    ax.plot(it[1][:, 0], it[1][:, 1], color=col, lw=lw * 72 / 25.4, ls=LS.get(lt, "-"), solid_capstyle="butt")
                else:
                    _, (x, y), s, ha, h, rot, wf = it
                    tp = TextPath((0, 0), s, size=h, prop=fp); w = tw(s, h, wf); sx = w / max(tp.get_extents().x1, 1e-6)
                    a0 = 0 if ha == "left" else -w / 2 if ha == "center" else -w
                    ax.add_patch(PathPatch(Affine2D().scale(sx, 1).translate(a0, -h * 0.40).rotate_deg(rot).translate(x, y).transform_path(tp), color="#000000", lw=0))
            ax.set_xlim(0, W_); ax.set_ylim(0, H_)
            pdf.savefig(fig); png = os.path.join(prev_dir, f"{base}_p{k+1}.png"); fig.savefig(png, dpi=200); plt.close(fig); pngs.append(png)
    return dxf_path, pdf_path, pngs
