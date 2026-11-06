# -*- coding: utf-8 -*-
"""產生「排水設計 案件條件」網頁表單（單一 HTML 檔，離線可用，公司內網或 NAS 直接開）。

用法：python make_intake_html.py <輸出.html>

- 欄位名稱、說明、必填、沒填時、東山街範例，一律取自 make_intake_xlsx.py 的 ROWS（與 Excel 條件表同一份定義）。
- 本檔只補「用什麼元件填」（WIDGETS）與步驟分組（STEPS）；ROWS 有任何設定鍵沒有元件，產生時直接報錯，兩邊不會分歧。
- 組合欄位（例如擋土「型式＋L＋@」）由 fmt 組成和 Excel 範例同格式的字串，intake_to_config.py 不用另寫解析。
- 表單送出＝下載 JSON（{"form": "ditch-intake", "fields": {設定鍵: 值}, "items": [...]}），交給 intake_to_config.py 轉設定檔。
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_intake_xlsx import ROWS, ITEMS_HEAD  # noqa: E402

FORM_VERSION = "1.1"   # 1.1：可發布為 claude.ai 網頁（送出給 Claude、存檔、複製），深色模式、手機版

# 元件：text / path / num / select / textarea / combo（parts＋fmt）/ centerline（圖層或座標二選一）
# combo 的 fmt：{名稱} 代入；[ … ] 內的佔位都有值才輸出該段
W = {
    "case_name": dict(t="text", ph="例：P34_某某路側溝"),
    "title_block.project": dict(t="text"),
    "title_block.agency": dict(t="select", opts=["臺中市政府水利局", "臺中市政府建設局", "桃園市政府水務局", "桃園市政府工務局"], other=True),
    "title_block.agency_en": dict(t="text"),
    "title_block.designer": dict(t="text", default="辰璟工程技術顧問有限公司"),
    "budget.plan_name": dict(t="text"),
    "budget.project_no": dict(t="text"),
    "budget.account": dict(t="text"),
    "budget.site": dict(t="text"),
    "title_block.date_roc": dict(t="text", default="@roc_month"),
    "file_prefix": dict(t="select", opts=["(臺中48)", "（桃園）", "(台南01)"], other=True),

    "design.ground": dict(t="select", opts=["EG", "SG"], labels=["EG：原地形（沒有整地）", "SG：整地後地形（有整地圖）"]),
    "src_dxf": dict(t="path", ph="NAS 路徑或案件資料夾內的相對路徑"),
    "layers.spot_insert_layer": dict(t="text", ph="例：0"),
    "layers.contour_minor / contour_major": dict(t="combo", parts=[("minor", "首曲線圖層", "text"), ("major", "計曲線圖層", "text")],
                                                 fmt="{minor} / {major}", allow_empty=True, ex={}),
    "layers.features": dict(t="textarea", ph="一行一個圖層，或用頓號分隔"),
    "sg.pad_dxf / sg.corner_z": dict(t="combo", when=("design.ground", "SG"),
                                     parts=[("pad", "整地圖路徑", "path"), ("nw", "西北角 EL", "num"), ("ne", "東北角 EL", "num"),
                                            ("sw", "西南角 EL", "num"), ("se", "東南角 EL", "num")],
                                     fmt="{pad}（四角 {nw} / {ne} / {sw} / {se}）",
                                     ex=dict(pad="src/sg_pad.dwg", nw=476.99, ne=477.00, sw=477.88, se=477.80)),
    "sg.draw_eg_line": dict(t="select", opts=["否", "是"], when=("design.ground", "SG")),
    "design.road_tol": dict(t="num", min=0.05, max=1, step=0.05, unit="m"),
    "cadastre.pdf": dict(t="path"),
    "cadastre.control_points": dict(t="textarea", ph="點名 E N，一行一點（至少 2 點）"),
    "design.sketch": dict(t="path"),

    "alignment.centerline": dict(t="centerline", ex=dict(e1=229269.988, n1=2678883.406, e2=229268.603, n2=2678767.941)),
    "alignment.downstream": dict(t="select", opts=["北端（下游）", "南端（下游）", "東端（下游）", "西端（下游）"]),
    "alignment.bank_left_layer / bank_right_layer": dict(t="combo", parts=[("l", "左側（A）道路邊線圖層", "text"), ("r", "右側（B）道路邊線圖層", "text")],
                                                          fmt="{l}、{r}", ex=dict(l="左側道路邊線A", r="右側道路邊線B")),
    "alignment.spacing": dict(t="num", min=5, max=50, step=5, unit="m", default=20),

    "design.ditch_type": dict(t="select", opts=["箱涵式側溝（甲乙種預鑄溝蓋板）", "U 型溝", "矩形明溝"], other=True),
    "design.top_rule": dict(t="select", opts=["蓋板頂貼設計地面，每 1 m 逐點", "指定縱坡", "指定底高"], other=True),
    "design.t_cover": dict(t="num", min=0.1, max=0.5, step=0.01, unit="m"),
    "design.t_wall": dict(t="num", min=0.1, max=0.5, step=0.01, unit="m"),
    "design.t_slab": dict(t="num", min=0.1, max=0.5, step=0.01, unit="m"),
    "design.t_bed": dict(t="num", min=0.05, max=0.3, step=0.01, unit="m"),
    "design.sump": dict(t="num", min=0, max=1, step=0.05, unit="m", default=0.3),
    "design.well_wall": dict(t="num", min=0.1, max=0.5, step=0.01, unit="m"),
    "design.outlet": dict(t="text"),
    "design.fc": dict(t="text"),
    "design.rebar_grade": dict(t="text"),

    "standards.ditch": dict(t="select", opts=["依 B20 改尺寸（臺北市工務局箱涵式側溝）", "引用他機關標準圖（備註寫圖號）", "自繪"], other=True),
    "standards.import[]": dict(t="text", ph="例：B20、A18（臺北市工務局）"),
    "standards.guardrail": dict(t="select", opts=["A18 鋼管護欄（臨時）", "不設"], other=True),
    "standards.rc_check": dict(t="select", opts=["是", "否"]),
    "temp_shoring.type / pile_l / pile_sp": dict(t="combo", parts=[("type", "型式", "select:鋼軌樁|鋼板樁|斜坡開挖"), ("l", "樁長 L (m)", "num"),
                                                                   ("sp", "間距 @ (m)", "num"), ("note", "補充", "text")],
                                                 fmt="{type}[ L={l} m @{sp} m][，{note}]",
                                                 ex=dict(type="鋼軌樁", l=3, sp=1.0, note="路外側鐵板兼外模")),
    "temp_shoring.offset_out": dict(t="num", min=0, max=1, step=0.05, unit="m", default=0.10),
    "temp_shoring.offset_in": dict(t="num", min=0, max=1, step=0.05, unit="m", default=0.30),
    "demolish[]": dict(t="textarea", ph="逐項：構造物、範圍、拆或不拆"),
    "traffic.phases / guardrail_side": dict(t="combo", parts=[("ph", "施工階段", "select:一階段|A、B 兩階段|三階段以上"),
                                                              ("side", "臨時護欄設置", "select:臨時鋼管護欄設路內側＋兩端|臨時鋼管護欄設兩側|不設護欄")],
                                            fmt="{ph}，{side}", ex=dict(ph="A、B 兩階段", side="臨時鋼管護欄設路內側＋兩端")),

    "budget.template_xls": dict(t="path"),
    "qty.template_xlsx": dict(t="path"),
    "budget.price_sources[]": dict(t="text", ph="用 > 分隔，優先的在前"),
    "budget.rates.profit": dict(t="combo", parts=[("v", "費率 (%)", "num"), ("note", "計算基礎", "text")], fmt="{v}%[{note}]",
                                ex=dict(v=8, note="×(壹.一+壹.二)")),
    "budget.rates.qc": dict(t="combo", parts=[("v", "費率 (%)", "num"), ("note", "備註", "text")], fmt="{v}%[（{note}）]",
                            ex=dict(v=2, note="分段級距【待確認】")),
    "budget.rates.mgmt": dict(t="combo", parts=[("v", "500 萬元以下部分費率 (%)", "num"), ("note", "備註", "text")], fmt="{v}%[（{note}）]",
                              ex=dict(v=3, note="分段級距【待確認】")),
    "budget.rates.air": dict(t="combo", parts=[("v", "費率 (%)", "num")], fmt="{v}%", ex=dict(v=0.35)),
    "budget.design_fee / supervision_fee": dict(t="combo", parts=[("d", "委外設計費 (元)", "num"), ("s", "委外監造費 (元)", "num")],
                                                fmt="[{d}][／{s}]", allow_empty=True, ex=dict(d=312182, s=312181)),

    "schedule.days": dict(t="num", min=1, max=1500, step=1, unit="日曆天"),
    "schedule.rates": dict(t="combo", allow_empty=True,
                           parts=[("ditch", "側溝 (m/日)", "num"), ("well", "集水井 (日/座)", "num"), ("demo", "打除 (m/日)", "num"),
                                  ("pile", "擋土樁 (支/日)", "num"), ("ac", "AC 鋪面 (m²/日)", "num"), ("prep", "準備 (日)", "num"), ("clean", "清理 (日)", "num")],
                           fmt="[側溝 {ditch} m/日、][集水井 {well} 日/座、][打除 {demo} m/日、][擋土樁 {pile} 支/日、][AC {ac} m²/日、][準備 {prep} 日、][清理 {clean} 日]",
                           ex={}),
    "schedule.calendar": dict(t="select", opts=["日曆天，不另折減", "工作天（扣週休與國定假日）"]),
    "plot.ctb": dict(t="select", opts=["黑白", "全彩（有航照或 Google 底圖）"]),
    "plot.plan_scale": dict(t="select", opts=["1/500", "1/200", "1/250", "1/1000"]),
    "plot.profile_scale": dict(t="select", opts=["1/500／1/50", "1/500／1/100", "1/1000／1/100", "1/200／1/50"]),
    "plot.xs_scale": dict(t="select", opts=["1/100", "1/50", "1/200"]),
}

STEPS = [
    ("基本資料", ["case_name", "title_block.project", "title_block.agency", "title_block.agency_en", "title_block.designer", "budget.site",
                "budget.plan_name", "budget.project_no", "budget.account", "title_block.date_roc", "file_prefix"]),
    ("地面與輸入檔案", ["design.ground", "src_dxf", "layers.spot_insert_layer", "layers.contour_minor / contour_major", "layers.features",
                    "sg.pad_dxf / sg.corner_z", "sg.draw_eg_line", "design.road_tol", "cadastre.pdf", "cadastre.control_points", "design.sketch"]),
    ("定線", ["alignment.centerline", "alignment.downstream", "alignment.bank_left_layer / bank_right_layer", "alignment.spacing"]),
    ("構造物", ["design.ditch_type", "design.top_rule", "design.t_cover", "design.t_wall", "design.t_slab", "design.t_bed", "design.sump",
              "design.well_wall", "design.outlet", "design.fc", "design.rebar_grade"]),
    ("側溝與集水井", ["@items"]),
    ("標準圖與施工", ["standards.ditch", "standards.import[]", "standards.guardrail", "standards.rc_check", "temp_shoring.type / pile_l / pile_sp",
                  "temp_shoring.offset_out", "temp_shoring.offset_in", "demolish[]", "traffic.phases / guardrail_side"]),
    ("預算", ["budget.template_xls", "qty.template_xlsx", "budget.price_sources[]", "budget.rates.profit", "budget.rates.qc", "budget.rates.mgmt",
            "budget.rates.air", "budget.design_fee / supervision_fee"]),
    ("工期與出圖", ["schedule.days", "schedule.rates", "schedule.calendar", "plot.ctb", "plot.plan_scale", "plot.profile_scale", "plot.xs_scale"]),
    ("檢查與送出", ["@review"]),
]

# 側溝與集水井範例（東山街）：與 make_intake_xlsx.ITEMS_EX 相同
ITEMS_EXAMPLE = [
    {"種類": "側溝", "編號": "#A", "側別": "A（左）", "起點樁號 (m)": 0, "終點樁號 (m)": 111.53, "內寬 W (m)": 1.10, "內高 H (m)": 1.00},
    {"種類": "側溝", "編號": "#B", "側別": "B（右）", "起點樁號 (m)": 0, "終點樁號 (m)": 110.48, "內寬 W (m)": 1.10, "內高 H (m)": 1.00},
    {"種類": "集水井", "編號": "#AC1", "側別": "A（左）", "起點樁號 (m)": 0, "集水井內徑 (m)": 1.50},
    {"種類": "集水井", "編號": "#BC1", "側別": "B（右）", "起點樁號 (m)": 0, "集水井內徑 (m)": 1.50},
]


def build_spec():
    rows = {r[4]: r for r in ROWS if r[1] is not None}
    keys_in_steps = [k for _, ks in STEPS for k in ks if not k.startswith("@")]
    miss_w = [k for k in rows if k not in W]
    miss_s = [k for k in rows if k not in keys_in_steps]
    extra = [k for k in keys_in_steps if k not in rows]
    if miss_w or miss_s or extra:
        raise SystemExit(f"欄位定義不一致：沒有元件 {miss_w}；沒排進步驟 {miss_s}；ROWS 沒有 {extra}")
    fields = {}
    for k, (cat, name, desc, ex, key, req, miss) in rows.items():
        fields[k] = dict(W[k], key=k, name=name, desc=desc, ex=W[k].get("ex", ex), exText=ex, req=(req == "必填"), miss=miss)
    return dict(version=FORM_VERSION, steps=[dict(title=t, keys=ks) for t, ks in STEPS], fields=fields,
                itemsHead=ITEMS_HEAD, itemsExample=ITEMS_EXAMPLE)


HEAD_FULL = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
"""
HEAD_ARTIFACT = ""   # 發布為 claude.ai 網頁時：外殼由平台包，頁面從 <title> 開始

HTML = r"""<title>排水設計案件條件</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* 版面：頂部色帶＋可橫捲步驟列＋單欄卡片＋底部固定按鈕列；灰藍單色系 */
:root{--blue:#3E5C76;--on-blue:#FFFFFF;--dark:#1F2D3A;--muted:#55606B;--line:#D8DFE6;--bg:#F4F6F8;--card:#FFFFFF;--in:#FFF8E1;--inline:#9AA7B4;--err:#B3261E;--ok:#2E6B3F;--th:#3E5C76}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--blue:#7FA3C2;--on-blue:#0F1A24;--dark:#E3E9EF;--muted:#A9B4BF;--line:#33414E;--bg:#121A21;--card:#1B252E;--in:#26303A;--inline:#55636F;--err:#F2B8B5;--ok:#9BD3A8;--th:#2E465A;color-scheme:dark}}
:root[data-theme="dark"]{--blue:#7FA3C2;--on-blue:#0F1A24;--dark:#E3E9EF;--muted:#A9B4BF;--line:#33414E;--bg:#121A21;--card:#1B252E;--in:#26303A;--inline:#55636F;--err:#F2B8B5;--ok:#9BD3A8;--th:#2E465A;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--dark);font:16px/1.6 "Microsoft JhengHei","微軟正黑體","PingFang TC","Noto Sans TC",sans-serif}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
header{background:var(--blue);color:var(--on-blue);padding-block:14px;display:flex;flex-wrap:wrap;gap:4px 20px;align-items:baseline}
header h1{font-size:22px;margin:0;font-weight:700;text-wrap:balance}
header .sub{opacity:.9;font-size:14px}
nav{display:flex;gap:6px;padding-block:10px;background:var(--card);border-bottom:1px solid var(--line);overflow-x:auto;white-space:nowrap}
nav button{flex:none;border:1px solid var(--line);background:var(--card);color:var(--dark);border-radius:16px;padding:4px 12px;font:inherit;font-size:14px;cursor:pointer}
nav button.cur{background:var(--blue);color:var(--on-blue);border-color:var(--blue)}
nav button.bad{border-color:var(--err);color:var(--err)}
nav button.cur.bad{color:var(--on-blue)}
main{max-width:980px;margin:0 auto;padding-block:20px calc(130px + env(safe-area-inset-bottom,0px))}
h2{font-size:20px;margin:0 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin-bottom:12px;min-width:0}
.card.hide{display:none}
.lab{font-weight:700;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.req{font-size:13px;font-weight:400;color:var(--on-blue);background:var(--blue);border-radius:4px;padding:0 6px}
.opt{font-size:13px;font-weight:400;color:var(--blue);border:1px solid var(--blue);border-radius:4px;padding:0 6px}
.desc{font-size:14px;color:var(--muted);margin:2px 0 8px}
.ex{font-size:14px;color:var(--muted);margin-top:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.ex button{font:inherit;font-size:13px;border:1px solid var(--blue);color:var(--blue);background:var(--card);border-radius:4px;padding:0 8px;cursor:pointer}
input,select,textarea{font:inherit;width:100%;padding:8px 10px;border:1px solid var(--inline);border-radius:6px;background:var(--in);color:var(--dark);min-width:0}
textarea{min-height:76px}
:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.row>div{min-width:0}
.row label{font-size:14px;color:var(--muted);display:block}
.unit{font-size:14px;color:var(--muted)}
.msg{font-size:14px;color:var(--err);margin-top:6px}
.note{font-size:14px;color:var(--ok);margin-top:6px}
.card.err{border-color:var(--err)}
.miss{font-size:14px;color:var(--muted);margin-top:4px}
footer{position:fixed;z-index:5;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding-top:10px;padding-bottom:calc(10px + env(safe-area-inset-bottom,0px));display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.btn{font:inherit;padding:8px 18px;border-radius:6px;border:1px solid var(--blue);background:var(--card);color:var(--blue);cursor:pointer}
.btn.pri{background:var(--blue);color:var(--on-blue)}
.btn[disabled]{opacity:.45;cursor:default}
.tbl{overflow-x:auto;min-width:0}
table{border-collapse:collapse;width:100%;font-size:15px;font-variant-numeric:tabular-nums}
th,td{border:1px solid var(--line);padding:6px;text-align:center;vertical-align:middle}
th{background:var(--th);color:#FFFFFF;font-weight:700}
td input,td select{padding:4px 6px;min-width:70px}
.sum td{text-align:left;overflow-wrap:anywhere}
main,header,nav,footer{max-width:100%}
.sum td.k{width:32%;font-weight:700}
.bad{color:var(--err)}
.good{color:var(--ok)}
.tools{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 14px}
#jsonbox{width:100%;min-height:160px;font-family:Consolas,monospace;font-size:13px}
@media (max-width:600px){header h1{font-size:19px}main{padding-top:14px}}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
<header class="gut"><h1>排水設計 案件條件</h1><span class="sub">辰璟工程技術顧問有限公司｜表單 v__VER__｜一步一步填，最後送出或存檔交給 Claude</span></header>
<nav id="nav" class="gut"></nav>
<main id="main" class="gut"></main>
<footer class="gut"><button class="btn" id="prev">上一步</button><button class="btn pri" id="next">下一步</button></footer>
<script>
const SPEC = __SPEC__;
const LS = "ditch-intake-draft-v" + SPEC.version;
let S = {fields: {}, parts: {}, items: []}, cur = 0;
try { const d = JSON.parse(localStorage.getItem(LS) || "null"); if (d && d.fields) S = Object.assign(S, d); } catch (e) {}
const save = () => { try { localStorage.setItem(LS, JSON.stringify(S)); } catch (e) {} };
const $ = (t, a = {}, ...kids) => { const e = document.createElement(t); for (const [k, v] of Object.entries(a)) { if (k === "on") for (const [ev, f] of Object.entries(v)) e.addEventListener(ev, f); else if (k in e && k !== "list") e[k] = v; else e.setAttribute(k, v); } for (const c of kids.flat()) if (c != null) e.append(c); return e; };
const rocMonth = () => { const d = new Date(); return (d.getFullYear() - 1911) + "年" + (d.getMonth() + 1) + "月"; };

function fmtCombo(f, p) {
  // [ … ] 內佔位都有值才輸出；其餘 {x} 直接代入
  const fill = s => s.replace(/\{(\w+)\}/g, (_, k) => (p[k] ?? "") === "" ? "" : String(p[k]));
  const hasAll = s => [...s.matchAll(/\{(\w+)\}/g)].every(m => (p[m[1]] ?? "") !== "");
  let out = f.fmt.replace(/\[([^\]]*)\]/g, (_, s) => hasAll(s) ? fill(s) : "");
  out = fill(out).replace(/、$/, "").trim();
  const any = Object.values(p).some(v => v !== "" && v != null);
  if (!any) return "";
  if (f.key === "layers.contour_minor / contour_major") { const a = p.minor || "（無）", b = p.major || "（無）"; return (p.minor || p.major) ? a + " / " + b : ""; }
  if (f.key.startsWith("temp_shoring") && p.type === "斜坡開挖") return "斜坡開挖" + (p.note ? "，" + p.note : "");
  return out;
}
function centerlineVal(p) {
  if (p.mode === "layer") return p.layer || "";
  const k = ["e1", "n1", "e2", "n2"]; if (k.some(x => (p[x] ?? "") === "")) return "";
  return `E${p.e1} N${p.n1} → E${p.e2} N${p.n2}`;
}
function visible(f) { return !f.when || S.fields[f.when[0]] === f.when[1]; }
function check(f) {
  const v = S.fields[f.key] ?? "";
  if (!visible(f)) return "";
  if (f.req && v === "") return "必填";
  if (f.t === "num" && v !== "") { const n = Number(v); if (isNaN(n)) return "要填數字"; if (f.min != null && n < f.min) return `不能小於 ${f.min}`; if (f.max != null && n > f.max) return `不能大於 ${f.max}`; }
  if (f.t === "combo") {
    const p = S.parts[f.key] || {};
    for (const [n, lab, t] of f.parts) if (t === "num" && (p[n] ?? "") !== "" && isNaN(Number(p[n]))) return `「${lab}」要填數字`;
    if (f.key.startsWith("temp_shoring") && p.type && p.type !== "斜坡開挖" && (!p.l || !p.sp)) return "樁長與間距都要填";
    if (f.key.startsWith("sg.pad") && visible(f) && ["pad", "nw", "ne", "sw", "se"].some(x => (p[x] ?? "") === "")) return "選了 SG：整地圖與四角高程都要填";
  }
  if (f.t === "centerline" && v === "" && f.req) return "填圖層，或填兩端點的 E、N";
  return "";
}
function itemErrs() {
  const e = [];
  if (!S.items.some(r => r["種類"] === "側溝")) e.push("至少要一條側溝");
  S.items.forEach((r, i) => {
    const n = r["編號"] || `第 ${i + 1} 列`;
    if (!r["編號"]) e.push(`第 ${i + 1} 列沒有編號`);
    if (r["種類"] === "側溝") for (const c of ["起點樁號 (m)", "終點樁號 (m)", "內寬 W (m)", "內高 H (m)"]) if ((r[c] ?? "") === "" || isNaN(Number(r[c]))) e.push(`${n}：${c} 要填數字`);
    if (r["種類"] === "集水井") for (const c of ["起點樁號 (m)", "集水井內徑 (m)"]) if ((r[c] ?? "") === "" || isNaN(Number(r[c]))) e.push(`${n}：${c} 要填數字`);
    const W = Number(r["內寬 W (m)"]); if (r["種類"] === "側溝" && W && (W < 0.3 || W > 3)) e.push(`${n}：內寬 ${W} m 不在 0.3～3 m`);
  });
  return e;
}
function stepErrs(i) {
  const st = SPEC.steps[i]; let n = 0;
  for (const k of st.keys) { if (k === "@items") n += itemErrs().length; else if (!k.startsWith("@") && check(SPEC.fields[k])) n++; }
  return n;
}
function setField(f, v) { S.fields[f.key] = v; save(); }
function setPart(f, n, v) {
  S.parts[f.key] = S.parts[f.key] || {}; S.parts[f.key][n] = v;
  S.fields[f.key] = f.t === "centerline" ? centerlineVal(S.parts[f.key]) : fmtCombo(f, S.parts[f.key]); save();
}
function applyExample(f) {
  if (f.t === "combo" || f.t === "centerline") {
    const ex = f.ex || {}; if (!Object.keys(ex).length) return;
    S.parts[f.key] = Object.assign({}, f.t === "centerline" ? {mode: "coord"} : {}, Object.fromEntries(Object.entries(ex).map(([k, v]) => [k, String(v)])));
    S.fields[f.key] = f.t === "centerline" ? centerlineVal(S.parts[f.key]) : fmtCombo(f, S.parts[f.key]);
  } else {
    let v = String(f.ex);
    if (f.t === "num") { const m = v.match(/-?\d+(\.\d+)?/); v = m ? m[0] : ""; }
    if (f.t === "select" && !f.opts.includes(v)) { const hit = f.opts.find(o => o.startsWith(v) || v.startsWith(o.split("（")[0])); if (hit) v = hit; }
    S.fields[f.key] = v;
  }
  save();
}
function fieldCard(f) {
  const card = $("div", {className: "card" + (visible(f) ? "" : " hide"), id: "c-" + f.key});
  card.append($("div", {className: "lab"}, f.name, $("span", {className: f.req ? "req" : "opt"}, f.req ? "必填" : "選填")));
  if (f.desc) card.append($("div", {className: "desc"}, f.desc));
  const v = S.fields[f.key] ?? "";
  const onv = e => { setField(f, e.target.value); refresh(f); };
  if (f.t === "select") {
    // 「其他」：不用 prompt（發布的網頁不顯示對話框），改在下拉下方直接輸入
    S.other = S.other || {};
    const isOther = S.other[f.key] || (v !== "" && !f.opts.includes(v));
    const s = $("select", {id: "f-" + f.key, on: {change: e => { if (e.target.value === "@other") { S.other[f.key] = true; setField(f, ""); } else { S.other[f.key] = false; setField(f, e.target.value); } render(); }}});
    s.append($("option", {value: ""}, "（請選擇）"));
    f.opts.forEach((o, i) => s.append($("option", {value: o}, (f.labels && f.labels[i]) || o)));
    if (f.other || isOther) s.append($("option", {value: "@other"}, "其他（自行輸入）"));
    s.value = isOther ? "@other" : v; card.append(s);
    if (isOther) card.append($("input", {type: "text", id: "o-" + f.key, value: v, placeholder: "請輸入", style: "margin-top:8px", on: {input: onv}}));
  } else if (f.t === "textarea") card.append($("textarea", {value: v, placeholder: f.ph || "", on: {input: onv}}));
  else if (f.t === "num") card.append($("div", {style: "display:flex;gap:10px;align-items:center;max-width:360px"}, $("input", {type: "text", inputMode: "decimal", value: v, placeholder: f.min != null ? `${f.min}～${f.max}` : "", on: {input: onv}}), f.unit ? $("span", {className: "unit", style: "white-space:nowrap"}, f.unit) : null));
  else if (f.t === "combo") {
    const p = S.parts[f.key] || {}; const row = $("div", {className: "row"});
    for (const [n, lab, t] of f.parts) {
      let inp;
      if (t.startsWith("select:")) { inp = $("select", {on: {change: e => { setPart(f, n, e.target.value); render(); }}}); inp.append($("option", {value: ""}, "（請選擇）")); t.slice(7).split("|").forEach(o => inp.append($("option", {value: o}, o))); inp.value = p[n] ?? ""; }
      else inp = $("input", {type: "text", inputMode: t === "num" ? "decimal" : "text", value: p[n] ?? "", on: {input: e => { setPart(f, n, e.target.value); refresh(f); }}});
      row.append($("div", {}, $("label", {}, lab), inp));
    }
    card.append(row);
  } else if (f.t === "centerline") {
    const p = S.parts[f.key] || {mode: "coord"};
    const sel = $("select", {on: {change: e => { setPart(f, "mode", e.target.value); render(); }}}, $("option", {value: "coord"}, "給兩端點 TWD97 座標"), $("option", {value: "layer"}, "給 DXF 圖層名稱"));
    sel.value = p.mode || "coord"; card.append(sel);
    const row = $("div", {className: "row", style: "margin-top:8px"});
    if ((p.mode || "coord") === "layer") row.append($("div", {}, $("label", {}, "中心線圖層"), $("input", {type: "text", value: p.layer ?? "", on: {input: e => { setPart(f, "layer", e.target.value); refresh(f); }}})));
    else for (const [n, lab] of [["e1", "起點 E"], ["n1", "起點 N"], ["e2", "終點 E"], ["n2", "終點 N"]]) row.append($("div", {}, $("label", {}, lab), $("input", {type: "text", inputMode: "decimal", value: p[n] ?? "", on: {input: e => { setPart(f, n, e.target.value); refresh(f); }}})));
    card.append(row);
  } else card.append($("input", {type: "text", value: v, placeholder: f.ph || "", on: {input: onv}}));
  card.append($("div", {className: "ex"}, "東山街範例：" + f.exText, $("button", {type: "button", on: {click: () => { applyExample(f); render(); }}}, "帶入")));
  card.append($("div", {className: "miss"}, "沒填時：" + f.miss));
  card.append($("div", {className: "msg"}));
  return card;
}
function refresh(f) {
  const c = document.getElementById("c-" + f.key); if (!c) return;
  const m = check(f); c.querySelector(".msg").textContent = m; c.classList.toggle("err", !!m); nav();
}
function itemsView() {
  const box = $("div");
  const cols = ["種類", "編號", "側別", "起點樁號 (m)", "終點樁號 (m)", "內寬 W (m)", "內高 H (m)", "集水井內徑 (m)", "備註"];
  const autoNo = kind => { const side = "A"; const pre = kind === "側溝" ? "#" : "#" + side + "C"; let i = 1; const used = new Set(S.items.map(r => r["編號"])); if (kind === "側溝") { for (const c of "ABCDEFGH") if (!used.has("#" + c)) return "#" + c; } while (used.has(pre + i)) i++; return pre + i; };
  box.append($("div", {className: "desc"}, "每條側溝、每座集水井各一列。編號：側溝 #A、#B；集水井「側別＋C＋序號」，由下游起（#AC1、#BC1）。集水井樁號填 0 代表在側溝起點（下游端）。"));
  box.append($("div", {className: "tools"},
    $("button", {className: "btn", on: {click: () => { S.items.push({"種類": "側溝", "編號": autoNo("側溝"), "側別": "A（左）"}); save(); render(); }}}, "＋ 新增側溝"),
    $("button", {className: "btn", on: {click: () => { S.items.push({"種類": "集水井", "編號": autoNo("集水井"), "側別": "A（左）"}); save(); render(); }}}, "＋ 新增集水井"),
    twoStep("帶入東山街範例", S.items.length ? "再按一次：取代目前明細" : null, () => { S.items = JSON.parse(JSON.stringify(SPEC.itemsExample)); save(); render(); })));
  const t = $("table"); t.append($("tr", {}, cols.map(c => $("th", {}, c)), $("th", {}, "")));
  S.items.forEach((r, i) => {
    const tr = $("tr");
    for (const c of cols) {
      const off = (r["種類"] === "側溝" && c === "集水井內徑 (m)") || (r["種類"] === "集水井" && ["終點樁號 (m)", "內寬 W (m)", "內高 H (m)"].includes(c));
      let inp;
      if (c === "種類") inp = $("span", {}, r[c]);
      else if (c === "側別") { inp = $("select", {on: {change: e => { r[c] = e.target.value; save(); }}}, ["A（左）", "B（右）"].map(o => $("option", {value: o}, o))); inp.value = r[c] || "A（左）"; }
      else if (off) inp = $("span", {className: "unit"}, "－");
      else inp = $("input", {type: "text", value: r[c] ?? "", inputMode: c.includes("(m)") ? "decimal" : "text", on: {input: e => { r[c] = e.target.value; save(); errBox(); nav(); }}});
      tr.append($("td", {}, inp));
    }
    tr.append($("td", {}, $("button", {className: "btn", on: {click: () => { S.items.splice(i, 1); save(); render(); }}}, "刪除")));
    t.append(tr);
  });
  box.append($("div", {className: "tbl"}, t));
  const eb = $("div", {className: "msg", id: "itemerr"}); box.append(eb);
  return box;
}
function errBox() { const e = document.getElementById("itemerr"); if (e) e.textContent = itemErrs().join("；"); }
function payload() {
  const fields = {}; for (const [k, f] of Object.entries(SPEC.fields)) { const v = S.fields[k] ?? ""; if (v !== "" && visible(f)) fields[k] = v; }
  const items = S.items.map(r => { const o = {}; for (const h of SPEC.itemsHead) if ((r[h] ?? "") !== "") o[h] = String(r[h]); return o; });
  return {form: "ditch-intake", version: SPEC.version, saved_at: new Date().toISOString(), fields, items};
}
// 兩段式確認：發布的網頁不顯示 confirm()，改成按鈕第一次變「再按一次…」，4 秒內再按才執行
function twoStep(label, again, action, cls = "btn") {
  const b = $("button", {className: cls, type: "button"}, label); let armed = false, t = 0;
  b.addEventListener("click", () => {
    if (!again || armed) { clearTimeout(t); action(); return; }
    armed = true; b.textContent = again; t = setTimeout(() => { armed = false; b.textContent = label; }, 4000);
  });
  return b;
}
// 能力：發布在 claude.ai 時才有（db＝送出給 Claude、downloads＝存檔）；本機或 NAS 開啟時為 null，改用瀏覽器下載
const CAP = {};
const use = n => (window.claude && window.claude.use) ? window.claude.use(n).catch(() => null) : Promise.resolve(null);
Promise.all([use("db"), use("downloads"), use("user")]).then(([db, dl, user]) => { CAP.db = db; CAP.dl = dl; CAP.user = user; CAP.ready = true; if (cur === SPEC.steps.length - 1) render(); });
async function saveFile(name, text, msgEl) {
  if (CAP.dl) {
    try { await CAP.dl.save({filename: name, data: text}); msgEl.className = "note"; msgEl.textContent = "已存檔：" + name; }
    catch (e) { msgEl.className = "msg"; msgEl.textContent = e && e.code === "declined" ? "已取消存檔。" : "這裡不能存檔，請改用「複製內容」貼給 Claude。"; }
    return;
  }
  if (window.claude && window.claude.use) { msgEl.className = "msg"; msgEl.textContent = "這裡不能存檔，請改用「送出給 Claude」或「複製內容」。"; return; }
  const a = $("a", {href: URL.createObjectURL(new Blob([text], {type: "application/json"})), download: name}); document.body.append(a); a.click(); a.remove();
  msgEl.className = "note"; msgEl.textContent = "已下載：" + name + "（在瀏覽器的下載資料夾）";
}
async function submitDb(p, msgEl, btn) {
  btn.disabled = true; msgEl.className = "note"; msgEl.textContent = "送出中…";
  try {
    const by = CAP.user && CAP.user.id ? await CAP.user.id().catch(() => "") : "";
    const id = "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const miss = Object.values(SPEC.fields).filter(f => check(f)).length + itemErrs().length;
    await CAP.db.collection("intakes").doc(id).set({case_name: p.fields.case_name || "未命名", saved_at: p.saved_at, missing: miss, by: by || "", version: p.version, json: JSON.stringify(p)});
    msgEl.textContent = `已送出（編號 ${id}）。跟 Claude 說「${p.fields.case_name || "這案"}條件送出了」即可。`;
  } catch (e) { msgEl.className = "msg"; msgEl.textContent = "送出失敗：" + (e && e.code === "not_granted" ? "沒有寫入權限，請改用存檔或複製。" : (e && e.message) || "請稍後再試，或改用存檔／複製。"); }
  btn.disabled = false;
}
function stamp() { const d = new Date(), z = n => String(n).padStart(2, "0"); return `${d.getFullYear()}${z(d.getMonth() + 1)}${z(d.getDate())}_${z(d.getHours())}${z(d.getMinutes())}`; }
function reviewView() {
  const box = $("div"); let total = 0;
  const t = $("table", {className: "sum"});
  SPEC.steps.forEach((st, i) => {
    if (st.keys[0] === "@review") return;
    t.append($("tr", {}, $("th", {colSpan: 3, style: "text-align:left"}, `${i + 1}. ${st.title}`)));
    if (st.keys[0] === "@items") { const e = itemErrs(); total += e.length; t.append($("tr", {}, $("td", {className: "k"}, "明細"), $("td", {}, `側溝 ${S.items.filter(r => r["種類"] === "側溝").length} 條、集水井 ${S.items.filter(r => r["種類"] === "集水井").length} 座`), $("td", {className: e.length ? "bad" : "good"}, e.length ? e.join("；") : "OK"))); return; }
    for (const k of st.keys) { const f = SPEC.fields[k]; if (!visible(f)) continue; const m = check(f); if (m) total++;
      t.append($("tr", {}, $("td", {className: "k"}, f.name), $("td", {}, S.fields[k] || "（空白）"), $("td", {className: m ? "bad" : "good"}, m || (S.fields[k] ? "OK" : "選填，" + f.miss)))); }
  });
  const msg = $("div", {className: "note", id: "outmsg"});
  const fname = () => `${S.fields.file_prefix || ""}${stamp()}_${S.fields.case_name || "未命名"}_案件條件.json`;
  const tools = $("div", {className: "tools"});
  if (CAP.db) { const b = $("button", {className: "btn pri", type: "button", id: "b-submit"}, "送出給 Claude"); b.onclick = () => submitDb(payload(), msg, b); tools.append(b); }
  tools.append($("button", {className: CAP.db ? "btn" : "btn pri", type: "button", id: "b-save", on: {click: () => saveFile(fname(), JSON.stringify(payload(), null, 1), msg)}}, "存檔（JSON）"));
  tools.append($("button", {className: "btn", type: "button", id: "b-copy", on: {click: () => { const txt = JSON.stringify(payload());
    const show = () => { const ta = document.getElementById("jsonbox") || $("textarea", {id: "jsonbox", readOnly: true}); ta.value = txt; if (!ta.isConnected) msg.after(ta); ta.focus(); ta.select(); msg.className = "note"; msg.textContent = "已選取下方內容，請手動複製後貼給 Claude。"; };
    try { navigator.clipboard.writeText(txt).then(() => { msg.className = "note"; msg.textContent = "已複製，直接貼給 Claude 即可。"; }, show); } catch (e) { show(); } }}}, "複製內容"));
  const pick = $("input", {type: "file", accept: ".json,application/json", id: "f-open", hidden: true, on: {change: async e => { try { const p = JSON.parse(await e.target.files[0].text()); if (p.form !== "ditch-intake") throw 0; S.fields = p.fields || {}; S.items = p.items || []; S.parts = {}; S.other = {}; save(); cur = 0; render(); } catch (x) { msg.className = "msg"; msg.textContent = "這個檔案不是案件條件設定檔。"; } }}});
  tools.append(pick, $("button", {className: "btn", type: "button", on: {click: () => pick.click()}}, "開啟舊的設定檔"));
  tools.append(twoStep("全部清空", "再按一次：清空所有欄位", () => { S = {fields: {}, parts: {}, items: [], other: {}}; save(); cur = 0; render(); }));
  tools.append(twoStep("全部帶入東山街範例（測試）", "再按一次：覆蓋目前內容", () => { for (const f of Object.values(SPEC.fields)) applyExample(f); S.items = JSON.parse(JSON.stringify(SPEC.itemsExample)); save(); render(); }));
  box.append($("div", {className: "card"}, total ? $("div", {className: "bad"}, `還有 ${total} 項要補（紅字）。可以先送出或存檔，補齊後再交；Claude 收到有缺漏的條件會停下來問。`) : $("div", {className: "good"}, "必填都填好了。"),
    tools, msg,
    $("div", {className: "desc"}, CAP.db ? "「送出給 Claude」：存到這個網頁的線上資料，Claude 可以直接讀。也可以存檔後放進案件資料夾（例如 NAS 的 01_收資料）。草稿會自動存在這個瀏覽器裡。"
      : "存檔後放進案件資料夾（例如 NAS 的 01_收資料），跟 Claude 說「XX 案條件填好了，在某某資料夾」。草稿會自動存在這個瀏覽器裡。")));
  box.append($("div", {className: "tbl"}, t));
  return box;
}
function nav() {
  const n = document.getElementById("nav"); n.innerHTML = "";
  SPEC.steps.forEach((st, i) => { const bad = st.keys[0] !== "@review" && stepErrs(i) > 0; n.append($("button", {className: (i === cur ? "cur" : "") + (bad ? " bad" : ""), on: {click: () => { cur = i; render(); }}}, `${i + 1}. ${st.title}`)); });
  document.getElementById("prev").disabled = cur === 0;
  document.getElementById("next").textContent = cur === SPEC.steps.length - 2 ? "檢查與送出" : "下一步";
  document.getElementById("next").style.visibility = cur === SPEC.steps.length - 1 ? "hidden" : "visible";
}
function render() {
  for (const f of Object.values(SPEC.fields)) if ((S.fields[f.key] ?? "") === "" && f.default != null && !(S.touched || {})[f.key]) { S.fields[f.key] = f.default === "@roc_month" ? rocMonth() : String(f.default); }
  const m = document.getElementById("main"); m.innerHTML = "";
  const st = SPEC.steps[cur]; m.append($("h2", {}, `${cur + 1}／${SPEC.steps.length}　${st.title}`));
  for (const k of st.keys) {
    if (k === "@items") m.append(itemsView());
    else if (k === "@review") m.append(reviewView());
    else { const f = SPEC.fields[k]; const c = fieldCard(f); m.append(c); }
  }
  for (const k of st.keys) if (!k.startsWith("@")) refresh(SPEC.fields[k]);
  errBox(); nav(); window.scrollTo(0, 0); save();
}
document.getElementById("prev").onclick = () => { if (cur > 0) { cur--; render(); } };
document.getElementById("next").onclick = () => { if (cur < SPEC.steps.length - 1) { cur++; render(); } };
render();
</script>
"""


def main(out, artifact=False):
    spec = build_spec()
    body = HTML.replace("__SPEC__", json.dumps(spec, ensure_ascii=False)).replace("__VER__", FORM_VERSION)
    html = (HEAD_ARTIFACT + body) if artifact else (HEAD_FULL + body + "</html>\n")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已產生：{out}（{len(spec['fields'])} 個欄位、{len(spec['steps'])} 步{'，claude.ai 網頁版' if artifact else ''}）")


if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    main(sys.argv[1], artifact="--artifact" in sys.argv)
