"""案件條件表 xlsx → ditch_config.json。

用法：python intake_to_config.py <條件表.xlsx> <ditch_config.json 輸出> [--base <既有設定檔>] [--data-dir <輸入檔根目錄>] [--out-dir <交付資料夾>]
- 讀「條件表」工作表的「填寫值」欄，依「設定鍵」欄寫入設定檔（點號路徑；「a / b」為一格兩鍵，程式拆值）。
- 讀「側溝與集水井」工作表（略過備註含「東山街範例」的範例列）→ design.ditches[]、design.wells[]。
- 讀「停點確認」工作表：「確認結果」有填的停點寫入 stops_confirmed。
- --base：先載入既有設定檔（例如 templates/ditch_config.P33.json 的版面鍵、版次），再用條件表的值覆蓋。
- 印出：必填沒填（或填了解析不出數值）的項目，以及各項卡住哪個★停點；有缺漏時回傳碼 2，設定檔仍會寫出（缺項不填）。
"""
import sys, os, re, json
from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")
STOPS = {0: "開始前（基本資料）", 1: "★1 建地形", 2: "★2 定線", 3: "★3 EG 或 SG", 4: "★4 標準圖與擋土型式", 5: "★5 既有構造物拆除", 6: "★6 單價與費率", 7: "★7 工期"}
STOP_KEY = {1: "terrain", 2: "alignment", 3: "ground", 4: "standards", 5: "demolish", 6: "prices", 7: "schedule"}


def stop_of(key):
    k = key.split(" / ")[0]
    if k in ("case_name", "file_prefix") or k.startswith("title_block") or k in ("budget.site",): return 0
    if k == "src_dxf" or k.startswith("layers"): return 1
    if k.startswith("alignment"): return 2
    if k in ("design.ground",) or k.startswith("sg."): return 3
    if k.startswith("design") or k.startswith("standards") or k.startswith("temp_shoring") or k.startswith("traffic"): return 4
    if k.startswith("demolish"): return 5
    if k.startswith("budget") or k.startswith("qty"): return 6
    if k.startswith("schedule"): return 7
    return 0


def setp(cfg, path, v):
    cur = cfg; ks = path.split(".")
    for k in ks[:-1]: cur = cur.setdefault(k, {})
    cur[ks[-1]] = v


NUM = r"-?\d+(?:,\d{3})*(?:\.\d+)?"
def nums(s): return [float(x.replace(",", "")) for x in re.findall(NUM, str(s))]
def split2(s): return [x.strip() for x in re.split(r"[／/]", str(s), maxsplit=1)] + [""]
def split_list(s): return [x.strip() for x in re.split(r"[、,，;；\n]", str(s)) if x.strip()]
def pct(s):
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", str(s))
    if m: return round(float(m.group(1)) / 100, 6)
    n = nums(s); return n[0] if n and n[0] < 1 else None


RATE_KW = [("側溝", "ditch"), ("集水井", "well"), ("拆除", "demolish"), ("打除", "demolish"), ("樁", "pile"), ("擋土", "pile"),
           ("AC", "ac"), ("路面", "ac"), ("準備", "prep"), ("清理", "cleanup")]


def convert(key, val, cfg, warn):
    """把一格填寫值轉成設定值寫入 cfg；回傳 False 表示必填但解析不出可用值"""
    s = str(val).strip()
    if key == "layers.contour_minor / contour_major":
        a, b = split2(s)[:2]
        none = lambda x: "" if (not x or x.startswith("（") or "無" in x) else x
        setp(cfg, "layers.contour_minor", none(a)); setp(cfg, "layers.contour_major", none(b)); return True
    if key == "layers.features": setp(cfg, key, split_list(s.replace("…", ""))); return True
    if key == "layers.spot_insert_layer":
        m = re.search(r"圖層\s*(\S+?)\s*的", s); setp(cfg, key, m.group(1) if m else s); return True
    if key == "sg.pad_dxf / sg.corner_z":
        pad = re.split(r"[（(]", s)[0].strip(); setp(cfg, "sg.pad_dxf", pad)
        z = nums(s[len(pad):])
        if len(z) >= 4: setp(cfg, "sg.corner_z", dict(zip(("NW", "NE", "SW", "SE"), z[:4])))
        else: warn.append(f"sg.corner_z：四角高程只讀到 {len(z)} 個，請在設定檔補")
        return True
    if key == "alignment.centerline":
        z = nums(s)
        if len(z) >= 4: setp(cfg, key, [[z[0], z[1]], [z[2], z[3]]])
        else: setp(cfg, "alignment.centerline_layer", s)
        return True
    if key == "alignment.downstream":
        setp(cfg, key, "start"); m = re.match(r"([東西南北]+)", s)
        if m: setp(cfg, "alignment.downstream_dir", m.group(1))
        return True
    if key == "alignment.bank_left_layer / bank_right_layer":
        a = split_list(s); setp(cfg, "alignment.bank_left_layer", a[0]); setp(cfg, "alignment.bank_right_layer", a[1] if len(a) > 1 else ""); return True
    if key == "design.ground": setp(cfg, key, s.upper()[:2]); return s.upper()[:2] in ("EG", "SG")
    if key == "sg.draw_eg_line": setp(cfg, key, s.startswith("是")); return True
    if key == "temp_shoring.type / pile_l / pile_sp":
        setp(cfg, "temp_shoring.type", re.split(r"\s|L\s*=", s)[0])
        m = re.search(r"L\s*=\s*([\d.]+)", s); n = re.search(r"@\s*([\d.]+)", s)
        if m: setp(cfg, "temp_shoring.pile_l", float(m.group(1)))
        if n: setp(cfg, "temp_shoring.pile_sp", float(n.group(1)))
        if "，" in s: setp(cfg, "temp_shoring.note", s.split("，", 1)[1])
        return bool(m and n)
    if key == "traffic.phases / guardrail_side":
        a = re.split(r"[，,]", s, maxsplit=1); setp(cfg, "traffic.phases", a[0]); setp(cfg, "traffic.guardrail_side", a[1] if len(a) > 1 else ""); return True
    if key == "demolish[]": setp(cfg, "demolish_note", s); return True
    if key in ("standards.import[]",): setp(cfg, "standards.import", split_list(s)); return True
    if key == "budget.price_sources[]": setp(cfg, "budget.price_sources", [x.strip() for x in re.split(r">|＞", s) if x.strip()]); return True
    if key.startswith("budget.rates."):
        r = pct(s); setp(cfg, "budget.rate_notes." + key.split(".")[-1], s)
        if r is None: return False
        setp(cfg, key, r); return True
    if key == "budget.design_fee / supervision_fee":
        z = nums(s)
        if z: setp(cfg, "budget.design_fee", int(z[0]))
        if len(z) > 1: setp(cfg, "budget.supervision_fee", int(z[1]))
        return True
    if key == "schedule.days":
        z = nums(s)
        if z: setp(cfg, key, int(z[0]))
        return bool(z)
    if key == "schedule.rates":
        d = {}
        for part in split_list(s):
            z = nums(part)
            if not z: continue
            for kw, k in RATE_KW:
                if kw in part: d[k] = z[0]; break
        if d: setp(cfg, key, d)
        else: warn.append(f"schedule.rates：「{s}」沒有可用數值，工期改用預設每日施工量（【假設】）")
        return True
    if key == "standards.rc_check": setp(cfg, key, s.startswith("是")); return True
    if key == "plot.ctb": setp(cfg, key, "A3-圖筆(全彩).ctb" if "全彩" in s else "A3-圖筆(黑白).ctb"); return True
    if key in ("plot.plan_scale", "plot.xs_scale"):
        z = nums(s.replace("1/", "")); setp(cfg, key, int(z[0]) if z else None); return bool(z)
    if key == "plot.profile_scale":
        z = [int(x) for x in nums(s.replace("1/", ""))]; setp(cfg, key, z[:2]); return len(z) >= 2
    if key in ("design.t_cover", "design.t_wall", "design.t_slab", "design.t_bed", "design.sump", "design.well_wall", "design.road_tol", "alignment.spacing",
               "temp_shoring.offset_out", "temp_shoring.offset_in"):
        z = nums(s)
        if z: setp(cfg, key, z[0])
        return bool(z)
    setp(cfg, key, s); return True


def read_items(ws, cfg, missing):
    head = [c.value for c in ws[2]]; ix = {h: i for i, h in enumerate(head)}
    ditches, wells = [], []
    for row in ws.iter_rows(min_row=3, values_only=True):
        if not row or row[0] in (None, ""): continue
        if "範例" in str(row[ix["備註"]] or ""): continue
        no, side, kind = str(row[0]).strip(), str(row[1] or "").strip(), str(row[2] or "").strip()
        sk = re.match(r"[A-Za-z]+", side); sk = sk.group(0).upper() if sk else side[:1]
        lr = "right" if "右" in side else "left"
        f = lambda c: (nums(row[ix[c]]) or [None])[0]
        if kind == "側溝":
            d = dict(id=no, side=sk, lr=lr, name=f"{sk} 側", start=f("起點樁號 (m)"), end=f("終點樁號 (m)"), W=f("內寬 W (m)"), H=f("內高 H (m)"))
            if d["W"] is None or d["H"] is None: missing.append(("design.ditches[]", f"{no} 內寬／內高", 4))
            ditches.append(d)
        elif kind == "集水井":
            st, en = f("起點樁號 (m)"), f("終點樁號 (m)")
            wells.append(dict(id=no, side=sk, end="start" if (st or 0) == 0 else "end", station=st, inner=f("集水井內徑 (m)")))   # 起點樁號 0＝側溝起點（下游），其餘＝終點
    if not ditches: missing.append(("design.ditches[]", "側溝明細（至少一條）", 4))
    else: setp(cfg, "design.ditches", ditches)
    if wells: setp(cfg, "design.wells", wells)
    # 側溝定線圖層：條件表給的左右道路邊線
    for d in ditches:
        lay = cfg.get("alignment", {}).get("bank_left_layer" if d["lr"] == "left" else "bank_right_layer")
        if lay and "line_layer" not in d: d["line_layer"] = lay


def main():
    a = sys.argv[1:]
    if len(a) < 2: raise SystemExit(__doc__)
    xlsx, out = a[0], a[1]
    opt = lambda k: a[a.index(k) + 1] if k in a else None
    cfg = json.load(open(opt("--base"), encoding="utf-8-sig")) if opt("--base") else {}
    for k in ("design", ):
        if k in cfg:   # 側溝與集水井以條件表為準
            cfg[k].pop("ditches", None); cfg[k].pop("wells", None)
    if opt("--data-dir"): cfg["data_dir"] = opt("--data-dir")
    if opt("--out-dir"): cfg["out_dir"] = opt("--out-dir")
    wb = load_workbook(xlsx, data_only=True)
    ws = wb["條件表"]; head = [c.value for c in ws[2]]; ix = {h: i for i, h in enumerate(head)}
    missing, warn, n_in = [], [], 0
    for row in ws.iter_rows(min_row=3, values_only=True):
        key = row[ix["設定鍵"]] if len(row) > ix["設定鍵"] else None
        if not key: continue
        val, req, name = row[ix["填寫值"]], row[ix["必填"]] == "必填", row[ix["欄位"]]
        if val is None or str(val).strip() == "":
            if req: missing.append((key, name, stop_of(key)))
            continue
        n_in += 1
        ok = convert(key, val, cfg, warn)
        if not ok and req: missing.append((key, f"{name}（填了「{val}」但解析不出可用值）", stop_of(key)))
    read_items(wb["側溝與集水井"], cfg, missing)
    if "停點確認" in wb.sheetnames:
        conf = [STOP_KEY.get(int(r[0])) for r in wb["停點確認"].iter_rows(min_row=3, values_only=True)
                if r and r[0] and str(r[0]).isdigit() and r[4] not in (None, "")]
        cfg["stops_confirmed"] = sorted(set(cfg.get("stops_confirmed", []) if not opt("--base") else []) | set(c for c in conf if c))
    cfg.setdefault("case_code", re.match(r"[A-Za-z]*\d*", cfg.get("case_name", "")).group(0) if cfg.get("case_name") else "")
    json.dump(cfg, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"已讀條件 {n_in} 項、側溝 {len(cfg.get('design', {}).get('ditches', []))} 條、集水井 {len(cfg.get('design', {}).get('wells', []))} 座 → {out}")
    for w in warn: print("  注意：", w)
    if missing:
        print(f"必填缺漏 {len(missing)} 項（Claude 停下來問，不自行假設）：")
        for st in sorted(set(m[2] for m in missing)):
            print(f"  卡住 {STOPS[st]}：")
            for k, nm, s_ in missing:
                if s_ == st: print(f"    - {nm}（{k}）")
        sys.exit(2)
    print("必填項目齊全。")


if __name__ == "__main__":
    main()
