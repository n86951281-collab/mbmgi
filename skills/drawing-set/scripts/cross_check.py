"""跨圖數值一致性檢查：讀多張產生器 DXF 的文字（TEXT、MTEXT、MULTILEADER），依設定檔比對同一數值在各圖是否一致。

用法：
    python -I cross_check.py <設定.json> [DXF ...] [--xlsx 數量表.xlsx] [--report 報告.txt]
    - DXF 沒給時用設定檔的 "dxf"（可用萬用字元，相對路徑以設定檔所在資料夾為準）。
    - 讀外來檔（輸出資料夾、NAS），一律加 -I；-I 會忽略 PYTHONIOENCODING，本程式自己把輸出設成 UTF-8。
    - 回傳碼：0＝全部一致；1＝有不一致或找不到；2＝設定錯誤。

圖號判定：產生器 DXF 每張圖在模型空間橫向並排（間距 sheet_pitch，預設 450 mm），
每張的圖號取圖標欄圖號格（sheet_no_box，紙面 mm，預設 392,10,410,21）內的文字。

設定檔格式見 templates/cross_check.example.json：
    groups[]：name（項目名）、expect（可省略，應有的值）、items[]
    items[]：
      {"sheet": "S-03", "pattern": "開挖寬\\s*(\\d+)"}                 圖號可用萬用字元（"S-*"、"*"）
      {"sheet": "S-01", "pattern": "外壁外\\s*(\\d+)、路外側\\s*(\\d+)", "expr": "150+g1+g2"}
      {"xlsx": "數量表.xlsx", "ws": "工作表", "cell": "E12", "expr": "g1*100"}   讀快取值，xlsx 要先用 Excel 重算存檔
      {"xlsx": "數量表.xlsx", "ws": "參數", "cell": "B11", "pattern": "(混凝土|水泥砂漿)"}  文字儲存格用 pattern 擷取
    pattern 的擷取群組依序為 g1、g2…；沒有 expr 時，值＝各群組以「×」連接。
    expr 只能用 g1…、數字、＋－×÷、括號、逗號（多值）；數值四捨五入到 ndigits（預設 3）位再比。
    "required": false 時，該項找不到不算錯（預設找不到就算錯，避免標註改字後默默漏比）。
"""
import sys, os, re, json, glob, ast, fnmatch, operator, argparse

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

# ---------- 讀 DXF ----------
_FMT = re.compile(r"\\[ACcFfHhQTWp][^;\\]*;|\\[LlOoKk]|[{}]")
def plain(s):
    """去掉 MTEXT 格式碼（\\W0.5; \\H…; {} 等），\\P 換成換行"""
    s = s.replace("\\P", "\n").replace("\\~", " ")
    return _FMT.sub("", s).replace("%%c", "Ø").replace("%%d", "°").replace("%%p", "±")

def dxf_texts(path, pitch=450.0):
    import ezdxf
    doc = ezdxf.readfile(path); out = []
    def walk(ents):
        for e in ents:
            t = e.dxftype()
            try:
                if t == "TEXT": s, p = e.dxf.text, e.dxf.insert
                elif t == "MTEXT": s, p = e.text, e.dxf.insert
                elif t == "MULTILEADER":
                    c = e.context.mtext
                    if c is None: continue
                    s, p = c.default_content, c.insert
                elif t == "INSERT":
                    for a in e.attribs: out.append((plain(a.dxf.text), a.dxf.insert.x, a.dxf.insert.y))
                    continue
                elif t == "DIMENSION":
                    s = e.dxf.get("text", "")
                    if s in ("", "<>"): continue
                    p = e.dxf.get("text_midpoint", e.dxf.defpoint)
                else: continue
            except Exception: continue
            out.append((plain(s), p.x, p.y))
    walk(doc.modelspace()); return out

def by_sheet(texts, pitch, nobox):
    """依 x 分張 → {圖號: [文字…]}；找不到圖號的張用「#序號」"""
    sheets = {}
    for s, x, y in texts: sheets.setdefault(int(x // pitch), []).append((s, x - (x // pitch) * pitch, y))
    res = {}
    x0, y0, x1, y1 = nobox
    for k, lst in sorted(sheets.items()):
        no = [s.strip() for s, x, y in lst if x0 <= x <= x1 and y0 <= y <= y1 and s.strip() and s.strip() != "圖號"]
        key = no[0] if no else f"#{k}"
        res.setdefault(key, []).extend(s for s, _, _ in lst)
    return res

# ---------- 讀 xlsx ----------
def xlsx_value(path, ws, cell):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sh = wb[ws] if ws else wb.worksheets[0]
    v = sh[cell].value; wb.close(); return v

# ---------- 安全的算式 ----------
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}
def calc(expr, g):
    def ev(n):
        if isinstance(n, ast.Expression): return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
        if isinstance(n, ast.Name) and re.fullmatch(r"g\d+", n.id): return g[int(n.id[1:]) - 1]
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS: return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS: return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Tuple): return tuple(ev(e) for e in n.elts)
        raise ValueError(f"算式不支援：{ast.dump(n)}")
    return ev(ast.parse(expr, mode="eval"))

def num(s):
    try: return float(str(s).replace(",", ""))
    except ValueError: return s

def norm(v, nd):
    if isinstance(v, tuple): return "×".join(norm(x, nd) for x in v)
    if isinstance(v, (int, float)): return f"{round(float(v), nd):g}"
    return str(v).strip()

# ---------- 主程式 ----------
def run(cfg, dxfs, base, xlsx_override=None):
    pitch = cfg.get("sheet_pitch", 450.0); nobox = cfg.get("sheet_no_box", (392, 10, 410, 21)); nd = cfg.get("ndigits", 3)
    excl = cfg.get("exclude", [])
    paths = []
    for d in dxfs:
        d = d if os.path.isabs(d) else os.path.join(base, d)
        paths += sorted(glob.glob(d)) if any(c in d for c in "*?[") else [d]
    paths = [p for p in paths if not any(e in os.path.basename(p) for e in excl)]
    sheets = {}                                                      # 圖號 → [(文字, 檔名)]
    for p in paths:
        for no, lst in by_sheet(dxf_texts(p, pitch), pitch, nobox).items():
            sheets.setdefault(no, []).extend((s, os.path.basename(p)) for s in lst)
    lines = [f"讀入 {len(paths)} 個 DXF、{len(sheets)} 張圖：{'、'.join(sorted(sheets))}"]
    bad = 0
    for G in cfg["groups"]:
        found = []                                                   # (值, 來源, 原文)
        missing = []
        for it in G["items"]:
            req = it.get("required", True)
            if "xlsx" in it:
                xp = xlsx_override or it["xlsx"]; xp = xp if os.path.isabs(xp) else os.path.join(base, xp)
                try: v = xlsx_value(xp, it.get("ws"), it["cell"])
                except Exception as e: v = None; lines.append(f"   ！讀 {xp} 失敗：{e}")
                if v is None:
                    if req: missing.append(f"{os.path.basename(xp)}!{it['cell']}（空白或未重算）")
                    continue
                if "pattern" in it:                                  # 儲存格是文字時，用 pattern 擷取
                    m = re.search(it["pattern"], str(v))
                    if not m:
                        if req: missing.append(f"{os.path.basename(xp)}!{it['cell']}「{it['pattern']}」")
                        continue
                    g = tuple(num(x) for x in m.groups()) or (m.group(0),)
                else: g = (num(v),)
                val = calc(it["expr"], g) if "expr" in it else (g if len(g) > 1 else g[0])
                found.append((norm(val, nd), f"{os.path.basename(xp)}!{it.get('ws') or ''}!{it['cell']}", str(v))); continue
            pat = re.compile(it["pattern"]); hit = 0
            for no in sorted(sheets):
                if not fnmatch.fnmatchcase(no, it.get("sheet", "*")): continue
                for s, fn in sheets[no]:
                    for m in pat.finditer(s):
                        g = tuple(num(x) for x in m.groups()) or (m.group(0),)
                        val = calc(it["expr"], g) if "expr" in it else (g if len(g) > 1 else g[0])
                        found.append((norm(val, nd), no, s.replace("\n", "／")[:60])); hit += 1
            if not hit and req: missing.append(f"{it.get('sheet', '*')}「{it['pattern']}」")
        vals = sorted({v for v, _, _ in found})
        ok = len(vals) <= 1 and not missing and (G.get("expect") is None or vals == [norm(num(G["expect"]), nd)])
        bad += not ok
        lines.append(f"{'○' if ok else '×'} {G['name']}：{'、'.join(vals) or '（無）'}" + (f"（應為 {G['expect']}）" if G.get("expect") is not None else ""))
        if not ok or os.environ.get("CC_VERBOSE"):
            for v, src, s in found: lines.append(f"     {v:>12s}  {src}：{s}")
            for m in missing: lines.append(f"     找不到：{m}")
    lines.append(f"[跨圖檢查] {len(cfg['groups'])} 組，不一致或缺項 {bad} 組")
    return bad, lines

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("config"); ap.add_argument("dxf", nargs="*")
    ap.add_argument("--xlsx", help="取代設定檔各 xlsx 項的檔案路徑"); ap.add_argument("--report")
    a = ap.parse_args()
    try: cfg = json.load(open(a.config, encoding="utf-8"))
    except Exception as e: print("設定檔錯誤：", e); sys.exit(2)
    base = os.path.dirname(os.path.abspath(a.config))
    bad, lines = run(cfg, a.dxf or cfg.get("dxf", []), base, a.xlsx)
    print("\n".join(lines))
    if a.report: open(a.report, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
