"""兩版 DXF 逐圖層、逐圖元比對（產生器原版 vs 使用者 CAD 手改的 V2）。

用法：
  python -I dxf_diff.py <基準.dxf> <V2.dxf> <輸出資料夾> [選項]

選項：
  --tol 0.01           座標容差（圖面單位）；在容差內視為沒動
  --move-max 100       「移動」配對的最大距離（圖面單位），超過就當刪除＋新增
  --layers A,B*        只比這些圖層（逗號分隔，可用萬用字元 * ?）
  --ignore-layers X,Y  排除這些圖層
  --space model        model（預設）／paper／all（含各配置）
  --explode            INSERT 展開成圖元再比（預設把圖塊參考當一個圖元比）
  --upm 10             圖面單位／實際公尺（例：橫斷面 1/100、單位 mm → 10），有給就換算實長偏差
  --upm-y 20           垂直方向另給（縱斷面 V 比例不同時），預設同 --upm
  --window x0,y0,x1,y1 只輸出這個範圍的預覽圖（比對仍是全圖）
  --prefix diff        輸出檔名前綴

輸出（UTF-8）：
  <prefix>.csv          差異清單（utf-8-sig，Excel 直接開不亂碼）
  <prefix>_summary.txt  摘要：各類筆數、逐圖層統計、圖層表差異、共同位移群組、文字與字高改變
  <prefix>.png          全圖差異預覽：灰＝未變、紅＝刪除（移動前位置為紅虛線）、綠＝新增或移動後、藍＝原位改屬性、橙＝形狀改變
  <prefix>_zoom.png     放大到有差異的範圍

差異類別：
  刪除、新增、移動、圖層改變、文字改變、字高改變、屬性改變（顏色、線型、線寬）、形狀改變（同圖層折線點數或線形不同）
  同一筆可能同時有多種（例：「移動＋字高改變」）。
"""
import argparse
import csv
import fnmatch
import math
import os
import sys
from collections import Counter, defaultdict

import numpy as np
import ezdxf
from ezdxf import disassemble
from ezdxf.tools.text import plain_mtext

TEXT_TYPES = {"TEXT", "ATTRIB", "MTEXT", "MULTILEADER", "MLEADER"}
LINEAR_TYPES = {"LINE", "LWPOLYLINE", "POLYLINE", "SPLINE", "HATCH", "SOLID", "ELLIPSE", "ARC", "CIRCLE"}


# ---------------------------------------------------------------- 讀檔
def read_doc(path):
    try:
        return ezdxf.readfile(path)
    except ezdxf.DXFStructureError:
        from ezdxf import recover
        doc, auditor = recover.readfile(path)
        print(f"[警告] {os.path.basename(path)} 結構有誤，已用 recover 讀入（{len(auditor.errors)} 個錯誤）")
        return doc


def xy(v):
    return (float(v[0]), float(v[1]))


def prim_vertices(e, tol):
    try:
        p = disassemble.make_primitive(e, max_flattening_distance=max(tol, 0.01))
        return [xy(v) for v in p.vertices()]
    except Exception:
        return []


def mleader_info(e):
    """回傳 (文字, 字高, 文字插入點, 引線折線清單)。"""
    text, h, ins, lines = "", None, None, []
    ctx = getattr(e, "context", None)
    if ctx is None:
        return text, h, ins, lines
    mt = getattr(ctx, "mtext", None)
    if mt is not None:
        try:
            text = plain_mtext(mt.default_content or "", split=False)
        except Exception:
            text = mt.default_content or ""
        ins = xy(mt.insert)
    h = getattr(ctx, "char_height", None)
    for ld in getattr(ctx, "leaders", []) or []:
        for ll in getattr(ld, "lines", []) or []:
            vs = [xy(v) for v in ll.vertices]
            if getattr(ld, "last_leader_point", None) is not None:
                vs.append(xy(ld.last_leader_point))
            if vs:
                lines.append(vs)
    return text, h, ins, lines


def entity_record(e, space, tol):
    t = e.dxftype()
    d = e.dxf
    r = dict(type=t, space=space, layer=d.get("layer", "0"), handle=d.get("handle", ""),
             text="", h=None, extra=(), closed=False,
             attrs=(d.get("color", 256), d.get("linetype", "BYLAYER").upper(), d.get("lineweight", -1)),
             rot=0.0, plot=[], plot_text=None)
    pts = []
    if t in ("TEXT", "ATTRIB"):
        r["text"] = d.get("text", "")
        r["h"] = d.get("height", None)
        r["rot"] = d.get("rotation", 0.0)
        use_align = (d.get("halign", 0) or d.get("valign", 0)) and d.hasattr("align_point")
        pts = [xy(d.align_point if use_align else d.insert)]
        r["plot_text"] = (pts[0], r["text"], r["h"] or 1.0, r["rot"])
    elif t == "MTEXT":
        r["text"] = e.plain_text()
        r["h"] = d.get("char_height", None)
        r["rot"] = d.get("rotation", 0.0)
        pts = [xy(d.insert)]
        r["plot_text"] = (pts[0], r["text"].split("\n")[0], r["h"] or 1.0, r["rot"])
    elif t in ("MULTILEADER", "MLEADER"):
        text, h, ins, lines = mleader_info(e)
        r["text"], r["h"] = text, h
        pts = ([ins] if ins else []) + [p for ln in lines for p in ln]
        r["plot"] = lines
        if ins:
            r["plot_text"] = (ins, text.split("\n")[0], h or 1.0, 0.0)
    elif t == "INSERT":
        r["text"] = d.get("name", "")
        att = [a.dxf.text for a in getattr(e, "attribs", [])]
        if att:
            r["text"] += " | " + " | ".join(att)
        pts = [xy(d.insert)]
        r["extra"] = (d.get("xscale", 1.0), d.get("yscale", 1.0), d.get("rotation", 0.0))
        r["plot"] = [[(x, y) for x, y in _bbox_ring(e)]] if _bbox_ring(e) else []
    elif t == "DIMENSION":
        r["text"] = d.get("text", "")
        try:
            r["text"] += f" [{e.get_measurement():.4f}]" if not isinstance(e.get_measurement(), tuple) else ""
        except Exception:
            pass
        for k in ("defpoint", "defpoint2", "defpoint3", "text_midpoint"):
            if d.hasattr(k):
                pts.append(xy(d.get(k)))
        r["plot"] = [pts[:3]] if len(pts) >= 2 else []
    elif t == "LINE":
        pts = [xy(d.start), xy(d.end)]
        if pts[1] < pts[0]:
            pts.reverse()
        r["plot"] = [pts]
    elif t == "LWPOLYLINE":
        pts = [xy(p) for p in e.get_points("xy")]
        r["closed"] = bool(e.closed)
        r["extra"] = tuple(round(b, 6) for b in (p[4] for p in e.get_points("xyseb"))) if any(
            p[4] for p in e.get_points("xyseb")) else ()
        if not r["closed"] and len(pts) > 1 and pts[-1] < pts[0]:
            pts.reverse()
        r["plot"] = [prim_vertices(e, tol) or pts]
    elif t == "POLYLINE":
        pts = [xy(v.dxf.location) for v in e.vertices]
        r["closed"] = bool(e.is_closed)
        if not r["closed"] and len(pts) > 1 and pts[-1] < pts[0]:
            pts.reverse()
        r["plot"] = [prim_vertices(e, tol) or pts]
    elif t == "CIRCLE":
        pts = [xy(d.center)]
        r["extra"] = (d.radius,)
        r["plot"] = [prim_vertices(e, tol)]
    elif t == "ARC":
        pts = [xy(d.center), xy(e.start_point), xy(e.end_point)]
        r["extra"] = (d.radius,)
        r["plot"] = [prim_vertices(e, tol)]
    elif t == "POINT":
        pts = [xy(d.location)]
        r["plot"] = [[pts[0], pts[0]]]
    else:
        vs = prim_vertices(e, tol)
        pts = vs
        if t == "HATCH":
            r["text"] = d.get("pattern_name", "")
        r["plot"] = [vs] if vs else []
    if not pts:
        return None
    r["pts"] = np.asarray(pts, dtype=float)
    return r


def _bbox_ring(e):
    try:
        from ezdxf import bbox
        b = bbox.extents([e], fast=True)
        if not b.has_data:
            return None
        (x0, y0), (x1, y1) = xy(b.extmin), xy(b.extmax)
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    except Exception:
        return None


def collect(doc, args):
    inc = [p.strip() for p in args.layers.split(",")] if args.layers else None
    exc = [p.strip() for p in args.ignore_layers.split(",")] if args.ignore_layers else []

    def keep(layer):
        if inc and not any(fnmatch.fnmatchcase(layer, p) for p in inc):
            return False
        return not any(fnmatch.fnmatchcase(layer, p) for p in exc)

    spaces = []
    if args.space in ("model", "all"):
        spaces.append(("Model", doc.modelspace()))
    if args.space in ("paper", "all"):
        spaces += [(lo.name, lo) for lo in doc.layouts if lo.name != "Model"]
    recs = []

    def walk(ents, space, depth=0):
        for e in ents:
            if args.explode and e.dxftype() == "INSERT" and depth < 8:
                try:
                    walk(list(e.virtual_entities()), space, depth + 1)
                    continue
                except Exception:
                    pass
            lay = e.dxf.get("layer", "0")
            if not keep(lay):
                continue
            r = entity_record(e, space, args.tol)
            if r is not None:
                recs.append(r)

    for name, sp in spaces:
        walk(sp, name)
    return recs


# ---------------------------------------------------------------- 配對
def pts_dist(a, b):
    if a.shape != b.shape:
        return math.inf
    return float(np.max(np.abs(a - b))) if len(a) else 0.0


def extra_eq(a, b, tol):
    if len(a) != len(b):
        return False
    return all(abs(x - y) <= max(tol, 1e-9) for x, y in zip(a, b))


def h_eq(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def greedy(A, B, idxA, idxB, key, radius, score):
    """在 idxA、idxB（未配對）之間依 key 分組、以第一點為錨點做格網鄰近查詢，score 回傳 None 表示不接受。"""
    cell = max(radius, 1e-9)
    grid = defaultdict(list)
    for j in idxB:
        r = B[j]
        p = r["pts"][0]
        grid[(key(r), int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell)))].append(j)
    cand = []
    for i in idxA:
        r = A[i]
        p = r["pts"][0]
        k = key(r)
        cx, cy = int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((k, cx + dx, cy + dy), ()):
                    s = score(r, B[j])
                    if s is not None:
                        cand.append((s, i, j))
    cand.sort(key=lambda c: c[0])
    ua, ub, pairs = set(), set(), []
    for s, i, j in cand:
        if i in ua or j in ub:
            continue
        ua.add(i)
        ub.add(j)
        pairs.append((i, j))
    return pairs


def poly_dev(a, b):
    """兩條折線的偏差：回傳 (a 的點到 b 線的最大距離, b 的點到 a 線的最大距離)。
    地面線只被截短時，V2→基準 很小、基準→V2 很大；真的改高程時兩者都大。"""
    def p2l(P, L):
        if len(L) == 1:
            return np.hypot(*(P - L[0]).T)
        S0, S1 = L[:-1], L[1:]
        d = S1 - S0
        ll = np.maximum((d ** 2).sum(1), 1e-18)
        t = np.clip(((P[:, None, :] - S0[None]) * d[None]).sum(2) / ll[None], 0, 1)
        proj = S0[None] + t[..., None] * d[None]
        return np.sqrt(((P[:, None, :] - proj) ** 2).sum(2)).min(1)
    return float(p2l(a, b).max()), float(p2l(b, a).max())


def bbox_of(p):
    return p.min(0), p.max(0)


def span_overlap(a, b):
    """沿兩線外框較長的方向，比較投影範圍的重疊比（交集／聯集）。地面線改高程、整條上移都還算同一條線。"""
    (a0, a1), (b0, b1) = bbox_of(a), bbox_of(b)
    k = int(np.argmax(np.maximum(a1 - a0, b1 - b0)))
    inter = min(a1[k], b1[k]) - max(a0[k], b0[k])
    union = max(a1[k], b1[k]) - min(a0[k], b0[k])
    return float(inter / union) if union > 0 and inter > 0 else 0.0


def compare(A, B, args):
    tol, mv = args.tol, args.move_max
    ia, ib = set(range(len(A))), set(range(len(B)))
    out = []  # (類別清單, i or None, j or None, 說明, 偏差)

    def take(pairs):
        for i, j in pairs:
            ia.discard(i)
            ib.discard(j)

    # 1 完全相同
    p1 = greedy(A, B, ia, ib, lambda r: (r["space"], r["type"], r["layer"], r["text"], len(r["pts"])), tol,
                lambda a, b: (d if (d := pts_dist(a["pts"], b["pts"])) <= tol and h_eq(a["h"], b["h"], tol)
                              and a["attrs"] == b["attrs"] and extra_eq(a["extra"], b["extra"], tol) else None))
    take(p1)
    n_same = len(p1)

    def attr_cats(a, b):
        c = []
        if a["layer"] != b["layer"]:
            c.append("圖層改變")
        if a["text"] != b["text"]:
            c.append("文字改變")
        if not h_eq(a["h"], b["h"], tol):
            c.append("字高改變")
        if a["attrs"] != b["attrs"]:
            c.append("屬性改變")
        return c

    # 2 原位改屬性（幾何相同）
    p2 = greedy(A, B, ia, ib, lambda r: (r["space"], r["type"], len(r["pts"])), tol,
                lambda a, b: (d if (d := pts_dist(a["pts"], b["pts"])) <= tol
                              and extra_eq(a["extra"], b["extra"], tol) else None))
    for i, j in p2:
        out.append((attr_cats(A[i], B[j]) or ["屬性改變"], i, j, "", 0.0))
    take(p2)

    # 3 移動（形狀相同、平移；文字與圖塊名要相同）
    def mv_score(a, b):
        if a["text"] != b["text"] or not extra_eq(a["extra"], b["extra"], tol):
            return None
        sa, sb = a["pts"] - a["pts"][0], b["pts"] - b["pts"][0]
        if pts_dist(sa, sb) > tol:
            return None
        d = float(np.hypot(*(b["pts"][0] - a["pts"][0])))
        return d + (0 if a["layer"] == b["layer"] else mv * 0.01) if d <= mv else None
    k3 = lambda r: (r["space"], r["type"], len(r["pts"]))
    p3 = greedy(A, B, ia, ib, k3, mv, mv_score)
    # 重複圖元（格線、刻度）容易配到最近的「別條」：先找主要位移量，再優先配符合主要位移量的組合重配一次
    q = max(tol * 2, 1e-6)
    dom = []
    vc = Counter()
    for i, j in p3:
        d = B[j]["pts"][0] - A[i]["pts"][0]
        vc[(round(d[0] / q), round(d[1] / q))] += 1
    vsum = defaultdict(lambda: np.zeros(2))
    for i, j in p3:
        d = B[j]["pts"][0] - A[i]["pts"][0]
        vsum[(round(d[0] / q), round(d[1] / q))] += d
    dom = [vsum[k] / n for k, n in vc.most_common(5) if n >= 3]
    if dom:
        def mv_score2(a, b):
            s = mv_score(a, b)
            if s is None:
                return None
            d = b["pts"][0] - a["pts"][0]
            hit = min(float(np.hypot(*(d - v))) for v in dom)
            return s * 1e-6 if hit <= q * 2 else s + mv
        p3 = greedy(A, B, ia, ib, k3, mv, mv_score2)
    for i, j in p3:
        out.append((["移動"] + attr_cats(A[i], B[j]), i, j, "", 0.0))
    take(p3)

    # 3b 同內容文字搬得比較遠（超過移動上限，例如面積說明從框左上移到樁號下方）：內容相同就配，不限距離
    p3b = greedy(A, B, ia, ib, lambda r: (r["space"], r["type"], r["text"]) if r["text"] else (id(r),), 1e12,
                 lambda a, b: (float(np.hypot(*(b["pts"][0] - a["pts"][0])))
                               if a["type"] in TEXT_TYPES and a["text"] and a["text"] == b["text"] else None))
    for i, j in p3b:
        out.append((["移動"] + attr_cats(A[i], B[j]), i, j, "超過移動上限，依文字內容相同配對", 0.0))
    take(p3b)

    # 4 文字內容改＋小幅移動（同圖層、同類，距離 ≤ max(2 倍字高, 10 倍容差)）
    def tx_score(a, b):
        if a["type"] not in TEXT_TYPES or a["layer"] != b["layer"]:
            return None
        lim = max(2 * (a["h"] or 0), 10 * tol)
        d = float(np.hypot(*(b["pts"][0] - a["pts"][0])))
        return d if d <= lim else None
    lim_r = max([2 * (r["h"] or 0) for r in A if r["type"] in TEXT_TYPES] + [10 * tol])
    p4 = greedy(A, B, ia, ib, lambda r: (r["space"], r["type"]), lim_r, tx_score)
    for i, j in p4:
        c = attr_cats(A[i], B[j])
        if float(np.hypot(*(B[j]["pts"][0] - A[i]["pts"][0]))) > tol:
            c = ["移動"] + c
        out.append((c, i, j, "", 0.0))
    take(p4)

    # 5 形狀改變（同類同圖層的線，外框重疊）
    def sh_score(a, b):
        if a["type"] not in LINEAR_TYPES or a["layer"] != b["layer"]:
            return None
        ca, cb = a["pts"].mean(0), b["pts"].mean(0)
        if float(np.hypot(*(cb - ca))) > mv:
            return None
        u = span_overlap(a["pts"], b["pts"])
        if u < args.min_iou:
            return None
        # 形心位移接近主要位移量（整框一起搬）的優先
        off = min(float(np.hypot(*(cb - ca - v))) for v in dom + [np.zeros(2)])
        return (1 - u) + off / mv
    p5 = greedy(A, B, ia, ib, lambda r: (r["space"], r["type"]), mv, sh_score)
    for i, j in p5:
        pa, pb = A[i]["pts"], B[j]["pts"]
        ab, ba = poly_dev(pa, pb)
        cc = pb.mean(0) - pa.mean(0)
        note = f"點數 {len(pa)}→{len(pb)}，形心位移 ({cc[0]:+.3f},{cc[1]:+.3f})"
        if dom:
            ab2, ba2, v2 = min(((*poly_dev(pa + v, pb), v) for v in dom), key=lambda t: max(t[0], t[1]))
            if max(ab2, ba2) < 0.5 * max(ab, ba):   # 明顯變小才當作「跟著整框搬」
                ab, ba = ab2, ba2
                note += f"；已扣除共同位移 ({v2[0]:+.3f},{v2[1]:+.3f})"
        note += f"；V2→基準 {ba:.3f}、基準→V2 {ab:.3f}"
        if ba <= tol < ab:
            note += "（V2 只是截短或刪點，線形沒改）"
        dev = max(ab, ba)
        if dev <= tol:
            note += "，線形在容差內"
        out.append((["形狀改變"] + [k for k in attr_cats(A[i], B[j]) if k != "圖層改變"], i, j, note, dev))
    take(p5)

    for i in sorted(ia):
        out.append((["刪除"], i, None, "", None))
    for j in sorted(ib):
        out.append((["新增"], None, j, "", None))
    return n_same, out


# ---------------------------------------------------------------- 輸出
def fmt(v, n=3):
    return "" if v is None else f"{v:.{n}f}"


def layer_table_diff(da, db):
    def info(doc):
        return {l.dxf.name: (l.dxf.get("color", 7), l.dxf.get("linetype", "Continuous").upper(), l.dxf.get("lineweight", -3))
                for l in doc.layers}
    a, b = info(da), info(db)
    lines = []
    for n in sorted(set(b) - set(a)):
        lines.append(f"  新增圖層：{n}  顏色 {b[n][0]}  線型 {b[n][1]}")
    for n in sorted(set(a) - set(b)):
        lines.append(f"  刪除圖層：{n}")
    for n in sorted(set(a) & set(b)):
        if a[n] != b[n]:
            lines.append(f"  圖層設定改變：{n}  (顏色,線型,線寬) {a[n]} → {b[n]}")
    return lines


def write_outputs(A, B, n_same, out, args, da, db):
    os.makedirs(args.outdir, exist_ok=True)
    pre = os.path.join(args.outdir, args.prefix)
    upm_x = args.upm
    upm_y = args.upm_y or args.upm
    rows = []
    for cats, i, j, note, dev in out:
        a = A[i] if i is not None else None
        b = B[j] if j is not None else None
        pa = a["pts"][0] if a is not None else None
        pb = b["pts"][0] if b is not None else None
        dx = dy = dist = None
        if pa is not None and pb is not None:
            dx, dy = float(pb[0] - pa[0]), float(pb[1] - pa[1])
            dist = math.hypot(dx, dy)
        rows.append({
            "類別": "＋".join(cats),
            "圖元": (a or b)["type"],
            "空間": (a or b)["space"],
            "圖層_基準": a["layer"] if a else "",
            "圖層_V2": b["layer"] if b else "",
            "文字_基準": a["text"] if a else "",
            "文字_V2": b["text"] if b else "",
            "字高_基準": fmt(a["h"]) if a else "",
            "字高_V2": fmt(b["h"]) if b else "",
            "X_基準": fmt(pa[0]) if pa is not None else "", "Y_基準": fmt(pa[1]) if pa is not None else "",
            "X_V2": fmt(pb[0]) if pb is not None else "", "Y_V2": fmt(pb[1]) if pb is not None else "",
            "dX": fmt(dx), "dY": fmt(dy), "距離": fmt(dist),
            "dX_實長m": fmt(dx / upm_x) if (dx is not None and upm_x) else "",
            "dY_實長m": fmt(dy / upm_y) if (dy is not None and upm_y) else "",
            "線形偏差": fmt(dev) if dev else "",
            "線形偏差_實長m": fmt(dev / upm_y) if (dev and upm_y) else "",
            "點數_基準": len(a["pts"]) if a else "", "點數_V2": len(b["pts"]) if b else "",
            "handle_基準": a["handle"] if a else "", "handle_V2": b["handle"] if b else "",
            "說明": note,
        })
    with open(pre + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["類別"])
        w.writeheader()
        w.writerows(rows)

    # ---- 摘要
    S = []
    S.append(f"基準：{args.base}")
    S.append(f"V2  ：{args.v2}")
    S.append(f"容差 {args.tol}、移動上限 {args.move_max}、空間 {args.space}"
             + (f"、圖層篩選 {args.layers}" if args.layers else "")
             + (f"、排除 {args.ignore_layers}" if args.ignore_layers else "")
             + (f"、圖面單位/m＝{upm_x}" + (f"（垂直 {upm_y}）" if args.upm_y else "") if upm_x else ""))
    S.append("")
    S.append(f"圖元數：基準 {len(A)}、V2 {len(B)}；完全相同 {n_same}；有差異 {len(out)} 筆")
    cat_cnt = Counter()
    for cats, *_ in out:
        for c in cats:
            cat_cnt[c] += 1
    S.append("各類筆數（一筆可屬多類）：" + "、".join(f"{k} {v}" for k, v in cat_cnt.most_common()))
    S.append("")
    S.append("圖元類型數量（基準 → V2）：")
    ca, cb = Counter(r["type"] for r in A), Counter(r["type"] for r in B)
    for t in sorted(set(ca) | set(cb)):
        mark = "" if ca[t] == cb[t] else "  ←"
        S.append(f"  {t:<12} {ca[t]:>6} → {cb[t]:<6}{mark}")
    S.append("")
    S.append("逐圖層差異（圖層：類別 筆數）：")
    per = defaultdict(Counter)
    for (cats, i, j, *_), row in zip(out, rows):
        lay = row["圖層_V2"] or row["圖層_基準"]
        for c in cats:
            per[lay][c] += 1
    for lay in sorted(per, key=lambda k: -sum(per[k].values())):
        S.append(f"  {lay}：" + "、".join(f"{k} {v}" for k, v in per[lay].most_common()))
    lt = layer_table_diff(da, db)
    S.append("")
    S.append("圖層表差異：" + ("無" if not lt else ""))
    S += lt

    # 共同位移群組
    q = max(args.tol * 2, 1e-6)
    grp = defaultdict(list)
    for (cats, i, j, *_), row in zip(out, rows):
        if "移動" in cats:
            dx, dy = float(row["dX"]), float(row["dY"])
            grp[(round(dx / q), round(dy / q))].append((dx, dy, row["圖層_V2"], row["文字_V2"]))
    S.append("")
    S.append("共同位移群組（同一位移量一起動的圖元，通常代表一條版面規則）：")
    if not grp:
        S.append("  無")
    for k, g in sorted(grp.items(), key=lambda kv: -len(kv[1]))[:args.max_groups]:
        dx = np.mean([x[0] for x in g])
        dy = np.mean([x[1] for x in g])
        lays = Counter(x[2] for x in g).most_common(4)
        real = ""
        if upm_x:
            real = f"（實長 dX {dx / upm_x:+.3f} m、dY {dy / upm_y:+.3f} m）"
        txt = [x[3] for x in g if x[3]][:3]
        S.append(f"  {len(g):>4} 筆  dX {dx:+.3f}  dY {dy:+.3f}{real}  圖層 "
                 + "、".join(f"{n}×{c}" for n, c in lays) + (f"  例：{' / '.join(txt)}" if txt else ""))

    def listing(title, cond, fmt_row, limit=60):
        sel = [r for (cats, *_), r in zip(out, rows) if cond(cats)]
        S.append("")
        S.append(f"{title}（{len(sel)} 筆）：" + ("無" if not sel else ""))
        for r in sel[:limit]:
            S.append("  " + fmt_row(r))
        if len(sel) > limit:
            S.append(f"  …其餘 {len(sel) - limit} 筆見 csv")

    listing("文字改變", lambda c: "文字改變" in c,
            lambda r: f"[{r['圖層_V2']}] 「{r['文字_基準']}」→「{r['文字_V2']}」 @({r['X_V2']},{r['Y_V2']})")
    listing("字高改變", lambda c: "字高改變" in c,
            lambda r: f"[{r['圖層_V2']}] {r['字高_基準']}→{r['字高_V2']} 「{r['文字_V2']}」")
    listing("圖層改變", lambda c: "圖層改變" in c,
            lambda r: f"{r['圖元']} {r['圖層_基準']}→{r['圖層_V2']} 「{r['文字_V2']}」")
    listing("形狀改變", lambda c: "形狀改變" in c,
            lambda r: f"[{r['圖層_V2']}] {r['圖元']} {r['說明']} 最大偏差 {r['線形偏差']}"
                      + (f"（實長 {r['線形偏差_實長m']} m）" if r["線形偏差_實長m"] else ""))
    listing("新增", lambda c: c == ["新增"],
            lambda r: f"[{r['圖層_V2']}] {r['圖元']} 「{r['文字_V2']}」 @({r['X_V2']},{r['Y_V2']})")
    listing("刪除", lambda c: c == ["刪除"],
            lambda r: f"[{r['圖層_基準']}] {r['圖元']} 「{r['文字_基準']}」 @({r['X_基準']},{r['Y_基準']})")
    with open(pre + "_summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(S) + "\n")

    plot(A, B, out, args, pre)
    return rows, S


# ---------------------------------------------------------------- 預覽圖
def plot(A, B, out, args, pre):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.collections import LineCollection
    fams = {f.name for f in font_manager.fontManager.ttflist}
    for fam in ("Microsoft JhengHei", "Noto Sans TC", "Noto Sans CJK TC", "MingLiU", "SimHei"):
        if fam in fams:
            plt.rcParams["font.family"] = fam
            break
    plt.rcParams["axes.unicode_minus"] = False

    changedA, changedB = {}, {}
    for cats, i, j, *_ in out:
        if i is not None:
            changedA[i] = cats
        if j is not None:
            changedB[j] = cats

    def color_of(cats, side):
        if cats == ["刪除"]:
            return "#D62728", "-", 1.0
        if cats == ["新增"]:
            return "#2CA02C", "-", 1.0
        if "移動" in cats:
            return ("#D62728", "--", 0.6) if side == "A" else ("#2CA02C", "-", 1.0)
        if "形狀改變" in cats:
            return ("#D62728", "--", 0.6) if side == "A" else ("#FF7F0E", "-", 1.0)
        return (None, None, None) if side == "A" else ("#1F77B4", "-", 1.0)

    def all_xy(recs):
        return np.vstack([r["pts"] for r in recs]) if recs else np.zeros((0, 2))

    def extent(points, pad_ratio=0.03):
        if not len(points):
            return None
        lo, hi = points.min(0), points.max(0)
        pad = max((hi - lo).max() * pad_ratio, args.tol * 10, 1e-6)
        return lo - pad, hi + pad

    full = extent(np.vstack([all_xy(A), all_xy(B)]))
    chg = extent(np.vstack([all_xy([A[i] for i in changedA]), all_xy([B[j] for j in changedB])]), 0.08) \
        if (changedA or changedB) else None
    views = []
    if args.window:
        x0, y0, x1, y1 = [float(v) for v in args.window.split(",")]
        views.append((pre + ".png", (np.array([x0, y0]), np.array([x1, y1]))))
    else:
        views.append((pre + ".png", full))
        if chg is not None:
            views.append((pre + "_zoom.png", chg))

    for path, ext in views:
        if ext is None:
            continue
        lo, hi = ext
        w, h = hi - lo
        aspect = h / w if w > 0 else 1
        fw = 16.0
        fh = min(max(fw * aspect, 4), 40)
        fig = plt.figure(figsize=(fw, fh), dpi=args.dpi)
        ax = fig.add_axes([0.01, 0.04, 0.98, 0.94])
        ax.set_xlim(lo[0], hi[0])
        ax.set_ylim(lo[1], hi[1])
        ax.set_aspect("equal", adjustable="box")
        ax.set_xticks([])
        ax.set_yticks([])
        fig.canvas.draw()
        bb = ax.get_window_extent()
        xl = ax.get_xlim()
        ppu = bb.width / (xl[1] - xl[0]) * 72.0 / fig.dpi  # 每圖面單位多少 pt

        def draw(recs, idxs, colfun, z):
            segs = defaultdict(list)
            for k in idxs:
                r = recs[k]
                c, ls, lw = colfun(k)
                if c is None:
                    continue
                for pl in r["plot"]:
                    if len(pl) >= 2:
                        segs[(c, ls, lw)].append(np.asarray(pl))
                if r["plot_text"]:
                    (px, py), s, hh, rot = r["plot_text"]
                    fs = hh * ppu / 0.75
                    if fs >= 0.6 and s:
                        ax.text(px, py, s, fontsize=fs, color=c, rotation=rot, ha="left", va="baseline",
                                zorder=z + 1, clip_on=True)
                elif not r["plot"]:
                    ax.plot(*r["pts"][0], marker="o", ms=2, color=c, zorder=z)
            for (c, ls, lw), sg in segs.items():
                ax.add_collection(LineCollection(sg, colors=c, linestyles=ls, linewidths=lw, zorder=z))

        same_b = [j for j in range(len(B)) if j not in changedB]
        draw(B, same_b, lambda k: ("#BBBBBB", "-", 0.4), 1)
        draw(A, list(changedA), lambda k: color_of(changedA[k], "A"), 3)
        draw(B, list(changedB), lambda k: color_of(changedB[k], "B"), 5)
        # 移動箭頭
        for cats, i, j, *_ in out:
            if "移動" in cats and i is not None and j is not None:
                p, q = A[i]["pts"][0], B[j]["pts"][0]
                ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="->", color="#9467BD", lw=0.6), zorder=6)
        from matplotlib.lines import Line2D
        leg = [Line2D([], [], color="#BBBBBB", label="未變"),
               Line2D([], [], color="#D62728", label="刪除"),
               Line2D([], [], color="#D62728", ls="--", label="移動前／改形前"),
               Line2D([], [], color="#2CA02C", label="新增／移動後"),
               Line2D([], [], color="#FF7F0E", label="形狀改變後"),
               Line2D([], [], color="#1F77B4", label="原位改屬性（圖層、文字、字高）")]
        ax.legend(handles=leg, loc="lower center", bbox_to_anchor=(0.5, -0.045), ncol=6, fontsize=9, frameon=False)
        fig.savefig(path, dpi=args.dpi)
        plt.close(fig)


# ---------------------------------------------------------------- 主程式
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="兩版 DXF 逐圖元比對")
    ap.add_argument("base")
    ap.add_argument("v2")
    ap.add_argument("outdir")
    ap.add_argument("--tol", type=float, default=0.01)
    ap.add_argument("--move-max", type=float, default=100.0)
    ap.add_argument("--min-iou", type=float, default=0.3, help="形狀改變配對的外框重疊比下限")
    ap.add_argument("--layers", default="")
    ap.add_argument("--ignore-layers", default="")
    ap.add_argument("--space", default="model", choices=["model", "paper", "all"])
    ap.add_argument("--explode", action="store_true")
    ap.add_argument("--upm", type=float, default=None)
    ap.add_argument("--upm-y", type=float, default=None)
    ap.add_argument("--window", default="")
    ap.add_argument("--prefix", default="diff")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--max-groups", type=int, default=20)
    args = ap.parse_args()

    da, db = read_doc(args.base), read_doc(args.v2)
    A, B = collect(da, args), collect(db, args)
    n_same, out = compare(A, B, args)
    rows, S = write_outputs(A, B, n_same, out, args, da, db)
    print("\n".join(S[:40]))
    print(f"\n輸出：{os.path.join(args.outdir, args.prefix)}.csv／_summary.txt／.png")


if __name__ == "__main__":
    main()
