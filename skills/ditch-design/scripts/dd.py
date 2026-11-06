"""ditch-design 共用模組：讀案件設定檔 ditch_config.json，提供路徑、版次、設計參數、圖標欄。

各產生器第一行 `import dd`，用法一律：
    python <產生器>.py --config <ditch_config.json> [--stamp YYYYMMDD_HHMM]
（也可設環境變數 DITCH_CONFIG 指定設定檔）

設定檔路徑規則：
- data_dir：輸入檔（測量圖、TIN、定線、標準圖 DXF、地籍 DXF、底圖）的根目錄，相對路徑都以它為準；只讀不寫。
- out_dir：交付檔（DXF、PDF、xlsx）。
- work_dir：中間資料（設計縱斷面 csv、斷面積 csv、數量 json、工期 json、圖目錄 json、配置清單 json）。
  預設 out_dir\\_work；不會寫進 data_dir（舊案資料夾保持唯讀）。
"""
import sys, os, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(os.path.dirname(HERE))
DS_SCRIPTS = os.path.join(SKILLS, "drawing-set", "scripts")        # 共用圖紙元件 p33_sheet、b20_import
for _p in (DS_SCRIPTS, HERE):                                       # 本資料夾優先（plan_base 用本 SKILL 版）
    if _p in sys.path: sys.path.remove(_p)
    sys.path.insert(0, _p)
sys.stdout.reconfigure(encoding="utf-8")


def arg(k, d=None):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d


CFG_PATH = arg("--config") or os.environ.get("DITCH_CONFIG")
if not CFG_PATH:
    raise SystemExit("缺設定檔：請加 --config <ditch_config.json>（或設環境變數 DITCH_CONFIG）")
CFG_PATH = os.path.abspath(CFG_PATH)
os.environ["DITCH_CONFIG"] = CFG_PATH                               # 子程序沿用
CFG = json.load(open(CFG_PATH, encoding="utf-8-sig"))

DATA = CFG.get("data_dir") or os.path.dirname(CFG_PATH)
OUT = CFG["out_dir"]
WORK = CFG.get("work_dir") or os.path.join(OUT, "_work")
PRE = CFG.get("file_prefix", "")
CODE = CFG.get("case_code", "")
stamp = arg("--stamp") or datetime.datetime.now().strftime("%Y%m%d_%H%M")
os.makedirs(OUT, exist_ok=True); os.makedirs(WORK, exist_ok=True)


def src(p):
    """輸入檔路徑：相對 data_dir"""
    return p if os.path.isabs(p) else os.path.join(DATA, p)


def work(name):
    """中間資料路徑（work_dir）"""
    return os.path.join(WORK, name)


def ver(key, default="v1.0"):
    return CFG.get("versions", {}).get(key, default)


def get(path, default=None):
    """以點號取設定值，例：get("budget.rates.profit")"""
    cur = CFG
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur: return default
        cur = cur[k]
    return cur


# ---------------- 設計參數（唯一來源：design.*；側溝斷面取 ditches[0]，集水井內徑取 wells[0]） ----------------
DES = CFG["design"]
DITCHES = DES["ditches"]
WELLS = DES.get("wells", [])
GROUND = DES.get("ground", "EG").upper()
USE_SG = GROUND == "SG"
if len({(d["W"], d["H"]) for d in DITCHES}) > 1:
    raise SystemExit("目前各側溝斷面須相同（W、H）；不同斷面尚未支援，見 SKILL.md 限制")
P_ = dict(t_cover=DES["t_cover"], H=DITCHES[0]["H"], W=DITCHES[0]["W"], t_wall=DES["t_wall"], t_slab=DES["t_slab"],
          t_bed=DES["t_bed"], sump=DES.get("sump", 0.30), well_in=(WELLS[0]["inner"] if WELLS else DES.get("well_in", 1.5)),
          well_wall=DES["well_wall"], road_tol=DES.get("road_tol", 0.25))
GND = "SG地面高" if USE_SG else "路面高"                              # 設計縱斷面 csv 的地面欄名

# 側溝：key（A、B…）→ 設定（line_layer、side：-1＝中心線左／路外在 -nv，+1＝右）
SIDE_KEYS = [d["side"] for d in DITCHES]
DITCH = {d["side"]: d for d in DITCHES}
# 集水井編號：(側別, 0＝起點／1＝終點) → 編號
WELL_ID = {(w["side"], 0 if w.get("end", "start") == "start" else 1): w["id"] for w in WELLS}

# ---------------- 臨時擋土 ----------------
SHO = CFG.get("temp_shoring", {})
PILE_L = float(SHO.get("pile_l", 3.0)); PILE_SP = float(SHO.get("pile_sp", 1.0))
GAP_OUT = float(SHO.get("offset_out", 0.10)); WORK_GAP = float(SHO.get("offset_in", 0.30))

# ---------------- 圖標欄 ----------------
TBC = CFG["title_block"]
TB = dict(agency=TBC["agency"], agency_en=TBC.get("agency_en", ""), project=TBC["project"],
          designer=TBC.get("designer", "辰璟工程技術顧問有限公司"), designer_en=TBC.get("designer_en", "Chen-Jing Engineering Co.,Ltd"),
          design=TBC.get("design", ""), draft=TBC.get("draft", ""), manager=TBC.get("manager", ""), check=TBC.get("check", ""))
COMPANY = TB["designer"]


def sheet_module():
    """drawing-set 的 p33_sheet（圖框、檢查、輸出），圖標欄換成本案"""
    import p33_sheet as S
    S.TB.update(TB)
    return S


def sta0(v):
    """道路中心線樁號 0K+xxx"""
    return f"0K+{v:06.2f}" if abs(v - round(v)) > 1e-6 else f"0K+{int(round(v)):03d}"


def read_json(name, default=None):
    p = work(name)
    if not os.path.exists(p):
        if default is not None: return default
        raise SystemExit(f"缺中間資料 {p}：請先跑前一步（run_all.py 依序執行）")
    return json.load(open(p, encoding="utf-8-sig"))


def write_json(name, obj):
    json.dump(obj, open(work(name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return work(name)
