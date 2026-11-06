"""回歸比對：兩份 DXF 的各圖層圖元數、全部文字（TEXT、MTEXT、MULTILEADER）、幾何指紋。

用法：python regress_dxf.py <基準.dxf> <重跑.dxf>
輸出：圖層圖元數差異、文字多出／缺少清單、幾何指紋（座標取 0.001 mm）是否一致；完全一致時回傳碼 0，否則 1。
"""
import sys, collections, hashlib
import ezdxf

sys.stdout.reconfigure(encoding="utf-8")


def texts(e):
    t = e.dxftype()
    if t == "TEXT": return [e.dxf.text]
    if t == "MTEXT": return [e.plain_text()]
    if t in ("MULTILEADER", "MLEADER"):
        try: return [e.context.mtext.default_content]
        except Exception: return []
    return []


def geom(e):
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE": return tuple((float(round(x, 3)), float(round(y, 3))) for x, y in e.get_points("xy"))
        if t in ("TEXT",): return (round(e.dxf.insert.x, 3), round(e.dxf.insert.y, 3), round(e.dxf.height, 3), e.dxf.text)
        if t == "SOLID": return tuple((round(v.x, 3), round(v.y, 3)) for v in e.vertices())
        if t == "HATCH": return tuple((float(round(v[0], 3)), float(round(v[1], 3))) for p in e.paths for v in getattr(p, "vertices", []))
        if t == "INSERT": return (e.dxf.name, round(e.dxf.insert.x, 3), round(e.dxf.insert.y, 3))
    except Exception: pass
    return t


def load(p):
    doc = ezdxf.readfile(p); m = doc.modelspace()
    cnt = collections.Counter((e.dxf.layer, e.dxftype()) for e in m)
    tx = collections.Counter(s for e in m for s in texts(e))
    g = sorted(repr((e.dxf.layer, e.dxftype(), geom(e))) for e in m)
    return cnt, tx, hashlib.sha1("\n".join(g).encode("utf-8")).hexdigest(), len(list(m)), g


def compare(a, b, quiet=False):
    ca, ta, ha, na, ga = load(a); cb, tb, hb, nb, gb = load(b)
    diff_cnt = {k: (ca.get(k, 0), cb.get(k, 0)) for k in set(ca) | set(cb) if ca.get(k, 0) != cb.get(k, 0)}
    miss = ta - tb; extra = tb - ta
    if not quiet:
        print(f"圖元總數 基準 {na}／重跑 {nb}；文字 {sum(ta.values())}／{sum(tb.values())}；幾何指紋 {'一致' if ha == hb else '不同'}")
        for k, (x, y) in sorted(diff_cnt.items()): print(f"  圖層 {k[0]} {k[1]}：{x} → {y}")
        for s, n in miss.items(): print(f"  缺少文字 ×{n}：{s}")
        for s, n in extra.items(): print(f"  多出文字 ×{n}：{s}")
    tol_ok, dmax = True, 0.0; bad_layers = collections.Counter()
    if ha != hb:                                   # 指紋不同時改用容差比對：同圖層同類圖元座標排序後逐筆比，最大偏差 ≦ TOL 視為一致
        sa, sb = set(ga), set(gb); oa, ob = sorted(sa - sb), sorted(sb - sa)
        if len(oa) != len(ob): tol_ok = False
        else:
            import re
            num = lambda x: [float(v) for v in re.findall(r"-?\d+\.\d+|-?\d+", x)]
            sig = lambda x: re.sub(r"[-\d.]+", "#", x)
            pool = {}
            for y in ob: pool.setdefault(sig(y), []).append(num(y))
            for x in oa:                               # 同圖層同結構中找最接近的一筆配對（排序配對會被微小偏差打亂）
                cand = pool.get(sig(x), []); fx = num(x)
                if not cand: tol_ok = False; dmax = float("inf"); break
                j = min(range(len(cand)), key=lambda i: max(abs(p - q) for p, q in zip(fx, cand[i])))
                dmax = max(dmax, max(abs(p - q) for p, q in zip(fx, cand[j]))); cand.pop(j)
            if dmax > TOL: tol_ok = False
        bad_layers = collections.Counter(ast_layer(x) for x in oa)
        if not quiet:
            print(f"  不同圖元所在圖層：{dict(bad_layers)}")
            print(f"  幾何指紋不同：只在基準 {len(oa)} 筆、只在重跑 {len(ob)} 筆；逐筆最大偏差 {dmax:.4f}（容差 {TOL}）→ {'視為一致' if tol_ok else '不一致'}")
            if not tol_ok:
                for x in oa[:5]: print("    基準：", x[:160])
                for x in ob[:5]: print("    重跑：", x[:160])
    return dict(n=(na, nb), text=(sum(ta.values()), sum(tb.values())), layer_diff=len(diff_cnt), text_missing=sum(miss.values()),
                text_extra=sum(extra.values()), geom_same=ha == hb or tol_ok, geom_dmax=dmax, geom_layers=dict(bad_layers))


def ast_layer(x):
    return x.split("'")[1] if "'" in x else "?"


TOL = 0.01   # 圖面 mm；P33 原產生器自己重跑兩次，SF 填線端點就差 0.001（浮點），不算差異


if __name__ == "__main__":
    r = compare(sys.argv[1], sys.argv[2])
    sys.exit(0 if (r["layer_diff"] == 0 and r["text_missing"] == 0 and r["text_extra"] == 0 and r["geom_same"]) else 1)
