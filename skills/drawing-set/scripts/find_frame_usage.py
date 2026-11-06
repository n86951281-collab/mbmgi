"""改共用元件（圖框、圖標欄、簽名欄、字寬、自動檢查）前，列出案件資料夾每支產生器用的是共用版還是自己的版本。

用法：python find_frame_usage.py <案件資料夾> [--term 關鍵字 ...]
    - 預設略過 *_bak_*.py 備份檔。
    - 「自有」欄有東西的檔案，改共用元件時要一起改（P33 的 P-01 plan_view.py 用自己的 frame，工程名稱超框、簽名欄都漏改過）。
    - --term 另外搜尋字串（例如新加的簽名欄人名、圖標欄字寬 0.55），列出出現位置，改完再跑一次確認每支都有。
"""
import sys, os, re, glob, argparse

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

OWN = {                                                                  # 自己定義的共用元件
    "圖框": re.compile(r"^\s*def\s+(frame|title_block|tb_\w*|draw_frame)\s*\("),
    "檢查": re.compile(r"^\s*def\s+(check\w*)\s*\("),
    "字寬": re.compile(r"^\s*(def\s+(tw|tbox|text_w\w*)\s*\(|(CJK_W|ASC_W)\s*,?.*=)"),
    "存檔": re.compile(r"^\s*def\s+save\s*\("),
}
SHARED = re.compile(r"from\s+p33_sheet\s+import\s+(.+)|import\s+p33_sheet")
HARD = re.compile(r"工程名稱：|設計：|繪圖：|主管：|校核：|\"圖號\"|圖標欄")       # 寫死的圖標欄字串

def scan(folder, terms):
    rows = []
    for p in sorted(glob.glob(os.path.join(folder, "*.py"))):
        if "_bak" in os.path.basename(p): continue
        src = open(p, encoding="utf-8", errors="replace").read().splitlines()
        own = {k: [i + 1 for i, l in enumerate(src) if r.search(l)] for k, r in OWN.items()}
        imp = [m.group(1) or "p33_sheet" for l in src for m in [SHARED.search(l)] if m]
        hard = [i + 1 for i, l in enumerate(src) if HARD.search(l) and not l.lstrip().startswith("#")]
        uses_frame = any(re.search(r"\bframe\s*\(", l) for l in src)
        hits = {t: [i + 1 for i, l in enumerate(src) if t in l] for t in terms}
        rows.append((os.path.basename(p), imp, own, hard, uses_frame, hits))
    return rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("folder"); ap.add_argument("--term", action="append", default=[])
    a = ap.parse_args()
    rows = scan(a.folder, a.term); warn = 0
    for fn, imp, own, hard, uses_frame, hits in rows:
        mine = {k: v for k, v in own.items() if v}
        if not (imp or mine or hard or any(hits.values())): continue
        tag = "共用本體" if fn == "p33_sheet.py" else "自有" if mine else ("共用" if imp else "—")
        print(f"[{tag}] {fn}")
        if imp: print(f"    import p33_sheet：{'；'.join(s.strip() for s in imp)}")
        for k, v in mine.items():
            print(f"    {'定義' if fn == 'p33_sheet.py' else '自有'}{k}：第 {', '.join(map(str, v))} 行"); warn += fn != "p33_sheet.py"
        if hard and fn != "p33_sheet.py": print(f"    寫死圖標欄字串：第 {', '.join(map(str, hard[:12]))}{' …' if len(hard) > 12 else ''} 行")
        for t, v in hits.items(): print(f"    「{t}」：{'第 ' + ', '.join(map(str, v)) + ' 行' if v else '沒有'}")
    print(f"\n共 {len(rows)} 支，產生器自有共用元件 {warn} 處；改 p33_sheet.py 的圖框、字寬、檢查時，這些都要一起改或改成呼叫共用版")

if __name__ == "__main__": main()
