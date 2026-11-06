---
name: ditch-design
description: 道路側溝排水設計一條龍：案件條件表（xlsx）轉設定檔 ditch_config.json，依★停點逐步自動出圖（設計縱斷面、平面配置 P-01、平面及縱斷面 PP、橫斷面 X、地籍套繪 L-01、工程位置及一般說明 G、標準圖 S、封面、合併圖冊、CAD 整合 DWG）、數量計算書、工程數量計算表、配筋檢核表、工期推算、PCCES 預算書，並可對已核定成果做整批回歸比對。遇到「排水設計、側溝、箱涵、箱涵式側溝、集水井、案件條件表、條件表轉設定檔、自動出圖、一鍵出圖、數量、預算、工期、重跑驗證、回歸比對」時使用。
---

# 道路側溝排水設計（ditch-design）

把 P33 東山街案（臺中市新社區東山街與協興街路口排水改善工程）的一次性產生器一般化：**所有案件值只放在一份設定檔 `ditch_config.json`**，產生器讀設定檔，不再寫死 P33 常數。
版面、字型、字級、圖層、檢查一律照全域規則 CLAUDE.md（「設計圖冊版面與標註規則 v2」「三、Excel 試算表」「工作方式規則」），程式與 P33 定案成果同一套，**這是重構不是改版面**。

上游、共用的 SKILL：
- 建地形、定線、SG 整地面：`section-drawings`（本 SKILL 從「TIN 與定線已確認」開始）。
- 圖紙元件 `p33_sheet.py`（圖框、多重引線、自動檢查、輸出）、引用標準圖 `b20_import.py`：`drawing-set/scripts`（`dd.py` 自動加到 import 路徑，不另複製）。
- Excel 重算、匯出 PDF、掃 `###`：`qty-budget/scripts/quantity_calc_pdf.ps1`、`xlsx_preview.ps1`。
- 地籍謄本套繪：`cadastre-overlay`（產出地籍 DXF 後，本 SKILL 只負責出 L-01）。
- 配筋檢核原理與規範：`rc-section-check`。

## 環境
- 臺中 llpc-48：Python 3.12（numpy、ezdxf 1.4 以上、matplotlib、openpyxl、pypdf、Pillow、shapely）；執行前設 `$env:PYTHONIOENCODING='utf-8'`。
- 產生器會 import 同資料夾模組（`dd`、`plan_base`）與 drawing-set 的 `p33_sheet`，**不要加 `-I`**。
- Excel（COM）：`--pdf` 時重算、匯出 PDF。AutoCAD 2022 `accoreconsole.exe`：`--dwg` 時產整合 DWG（沒有也能跑，只少 DWG）。
- 下列範例指令都在本 SKILL 資料夾（`skills\ditch-design`）用 PowerShell 執行。

## 設定檔 ditch_config.json
- 範例（P33 重跑）：`templates/ditch_config.P33.json`。主要鍵：
  | 鍵 | 內容 |
  |---|---|
  | `data_dir` | 輸入檔根目錄（測量圖、TIN、定線、標準圖、地籍、底圖），相對路徑以此為準；**只讀** |
  | `out_dir`／`work_dir` | 交付檔／中間資料（設計縱斷面 csv、斷面積 csv、qty_table.json、schedule.json、toc.json）；不寫回 data_dir |
  | `file_prefix`、`case_code`、`versions.*` | 檔名前綴（臺中機一律 `(臺中48)`）、案號、各圖版次（內容有變就升版） |
  | `title_block.*` | 工程名稱、主辦機關（中英）、設計單位、簽名欄（設計、繪圖、主管、校核） |
  | `src_dxf`、`sf_dxf`、`tin_npz`、`layers.*`、`legend.*` | 測量圖、SF 地物、EG TIN、圖層、圖例表範圍 |
  | `alignment.*` | 定線 DXF、中心線圖層或兩端點、0K+000 方向、斷面間距、平面圖樁距範圍 |
  | `design.*` | 設計地面 EG／SG、蓋板／壁／底版／墊層厚、沉砂深、井壁厚、`ditches[]`（側別、左右、定線圖層、W、H）、`wells[]`（編號、側別、起點或終點、內徑）；**設計參數唯一來源** |
  | `sg.*` | SG TIN、四角高程 |
  | `temp_shoring.*` | 擋土型式、樁長、樁距、路外側／路內側距離 |
  | `demolish[]` | 既有構造物（側別、名稱、尺寸、拆或不拆） |
  | `standards.*` | 溝體標準圖、配筋檢核、引用 B20／A18 DXF、標準圖張次 `sheets` |
  | `cadastre.*`、`front.*` | 地籍 DXF 與圖塊；G-01 底圖與經緯度、G-02 說明條文檔 |
  | `qty.*`、`budget.*` | 數量工項檔、預算單價檔、費率、單價來源、表頭資料 |
  | `schedule.*` | 工期（日曆天）或每日施工量、旗手人數與工作天 |
  | `stops_confirmed` | 已確認的★停點 |
- 案件資料檔（每案一份，放 `templates/` 或 `data_dir`）：
  | 檔案 | 內容 |
  |---|---|
  | `general_notes.<案>.json` | G-02 一般說明條文（可用 `{END}`、`{LA}`、`{W_cm}`、`{n_wells}`、`{pile_l}`… 代入） |
  | `qty_items.<案>.json` | 數量計算書參數、工項、算式文字、假設表；參數值 `"auto"` 由程式依定線與斷面積算 |
  | `qty_table.<案>.py` | 工程數量計算表工項（`big`／`item`／`sub`／`total`／`single` 呼叫，exec 執行） |
  | `unit_prices.<案>.json` | 單價依據、單價分析、預算詳細表工項、計畫說明書文字 |

## 步驟

### 1. 收條件表，轉設定檔
1. 給使用者空白條件表（`templates/排水設計_案件條件表_v1.0.xlsx`；改欄位時改 `templates/make_intake_xlsx.py` 再重產）：
   ```powershell
   $env:PYTHONIOENCODING='utf-8'
   python templates/make_intake_xlsx.py $env:TEMP\排水設計_案件條件表_v1.0.xlsx
   ```
2. 收回後轉設定檔；`--base` 帶入版面鍵（版次、圖例表範圍、G-01 底圖參數等條件表沒有的鍵）：
   ```powershell
   python scripts/intake_to_config.py templates/排水設計_案件條件表_v1.0.xlsx $env:TEMP\ditch_config_空白.json
   ```
   必填沒填（或填了解析不出數值）會列出缺漏項與**卡住哪個★停點**，回傳碼 2。缺漏逐項問使用者，不自行假設。
3. 示範／測試：把條件表的「東山街範例」抄進填寫值再轉（P33 範例只有 2 座井的示範列，正式重跑用 `ditch_config.P33.json`）：
   ```powershell
   python scripts/intake_fill_example.py templates/排水設計_案件條件表_v1.0.xlsx $env:TEMP\條件表_P33範例.xlsx
   python scripts/intake_to_config.py $env:TEMP\條件表_P33範例.xlsx $env:TEMP\ditch_config_P33範例.json --base templates/ditch_config.P33.json
   ```
4. 轉完補條件表沒有的鍵：`data_dir`、`out_dir`、`demolish[]` 明細（側別、尺寸）、`design.ditches[].line_layer`、`legend.box`、`front.map`、各案件資料檔檔名。

### 2. 一鍵執行（遇★停點就停）
```powershell
python scripts/run_all.py --config templates/ditch_config.P33.json --list
python scripts/run_all.py --config templates/ditch_config.P33.json --stamp (Get-Date -Format yyyyMMdd_HHmm) --pdf --dwg
```
- 存檔時間一律 `Get-Date` 取得；全部步驟用同一個 stamp（merge_set、build_cad_set 依 stamp 找各圖）。
- 停點沒確認時印出要確認的內容（TIN 抽驗、定線、EG/SG 與四角高程、標準圖與擋土、拆除清單、單價與費率、工期）並回傳 3。使用者確認後寫進 `stops_confirmed`，或加 `--confirmed`：
  ```powershell
  python scripts/run_all.py --config templates/ditch_config.P33.json --stamp (Get-Date -Format yyyyMMdd_HHmm) --confirmed terrain,alignment,ground --until profiles
  ```
- `--until`／`--from` 只跑一段；單一產生器也可直接跑：`python scripts/<產生器>.py --config <設定檔> --stamp <stamp>`。

| ★停點 | 擋在哪一步之前 | 回報內容 |
|---|---|---|
| terrain 建地形 | profiles | TIN 路徑、`*_qa.txt` 抽驗（RMSE、最大誤差）；8 視角預覽在 section-drawings 做 |
| alignment 定線 | profiles | 定線 DXF、中心線、各側溝定線圖層、0K+000 方向 |
| ground EG／SG | profiles | 設計地面；SG 時 TIN 與四角高程 |
| standards 標準圖與擋土 | sections | 溝體標準圖、配筋檢核、斷面尺寸、擋土樁長／間距／路外路內距離 |
| demolish 拆除 | plan | `demolish[]` 逐項拆或不拆 |
| schedule 工期 | schedule | 工期或每日施工量（預設值標【假設】） |
| prices 單價與費率 | budget | 單價來源順序、單價檔、費率、委外設計監造費 |

### 3. 交付前檢查
- 每張圖的 `[檢查]` 列：文字重疊、文字壓線、出界、引線壓字、框格溢出、字級不足要 0；「其他線壓字」「引線交叉」「字距線過近」逐筆看 PNG（P33 定案版本身就有，數字不得比基準多）。
- xlsx：`--pdf` 已重算並掃 `###`（Overflow/error cells 要 0），再用 `qty-budget/scripts/xlsx_preview.ps1` 逐張看。
- CAD：用 AutoCAD 開整合 DWG 執行 PUBLISH 載入 `.dsd` 出 PDF 目視（程式預覽字寬與 CAD 不同）。沒看過的項目回報時明講。
- 三層數量勾稽：數量計算書 ↔ 工程數量計算表（`work_dir/qty_table.json`）↔ 預算詳細表。

### 4. 回歸比對（改程式後、或重跑舊案）
```powershell
python scripts/regress_run.py --config templates/ditch_config.P33.json --stamp <重跑的 stamp> --baseline "D:\Claude_工作區\輸出\P33_新社東山\(印報告)" --cross-check ..\drawing-set\templates\cross_check.example.json
```
- 依檔名配對（去掉前綴與存檔時間）：DXF 比各圖層圖元數、全部文字、幾何（容差 0.01 mm）；xlsx 比逐格公式與重算值（兩邊都要先經 COM 重算）；預算另列發包工程費、總價、詳細表每列金額；跨圖一致性用 drawing-set `cross_check.py` 兩邊各跑一次。
- 單檔：`python scripts/regress_dxf.py <基準.dxf> <重跑.dxf>`、`python scripts/regress_xlsx.py <基準.xlsx> <重跑.xlsx>`。

## 模組
| 檔案 | 用途 | 讀 | 寫 |
|---|---|---|---|
| `dd.py` | 共用：讀設定檔、路徑（data／out／work）、版次、設計參數 `P_`、側溝與集水井編號、擋土參數、圖標欄（套進 p33_sheet） | 設定檔 | － |
| `intake_to_config.py` | 條件表 → 設定檔，列缺漏與卡住的★停點（回傳碼 2） | 條件表 xlsx | ditch_config.json |
| `intake_fill_example.py` | 測試用：範例欄抄進填寫值 | 條件表 xlsx | xlsx |
| `run_all.py` | 依序執行、★停點、`--until`／`--from`／`--pdf`／`--dwg` | 設定檔 | 全部 |
| `design_profiles.py` | 設計縱斷面（溝頂、溝底、開挖底、挖深；SG 貼地或 EG 直線縱坡）＋檢核用縱斷面圖 | TIN、SG TIN、測量圖高程點 | `design_profile_<側>.csv`、`design_param.json` |
| `plan_base.py` | 平面共用：定線、地物、SF、既有溝名、新設側溝與井、擋土樁列、斷面切線樁號 | 測量圖、SF、定線 | － |
| `cross_sections.py` | X 設計橫斷面（每張 6 刀）＋斷面積 | design_profile、SG/EG TIN | X DXF/PDF/PNG、`section_areas.csv` |
| `plan_view.py` | P-01 平面配置（1/500；`--scale 200` 分兩張） | plan_base | P-01 |
| `plan_profile.py` | PP 平面及縱斷面（每條側溝一張） | design_profile、plan_base | PP |
| `cadastral_sheet.py` | L-01 地籍套繪（`cadastre.dxf` 沒給就略過） | 地籍 DXF | L-01 |
| `front_sheets.py` | G-01 工程位置圖及圖目錄、G-02 一般說明 | 底圖 PNG、說明條文檔 | G、`toc.json` |
| `cover_sheet.py` | 封面 | － | 封面 |
| `standard_drawings.py` | S-01～S-06 標準圖（引用 B20、A18） | B20／A18 DXF | S |
| `rebar_check.py` | 配筋檢核表（`standards.rc_check` 為 true 才跑） | 設定檔 design | xlsx |
| `quantity_calc.py` | 數量計算書（參數、土石方、集水井、工程數量、假設） | `section_areas.csv`、qty_items | xlsx |
| `qty_table.py` | 工程數量計算表（A4 直式，照公司範本） | qty_table 工項檔 | xlsx、`qty_table.json` |
| `schedule.py` | 工期推算與連動（旗手工數、職安人月） | `qty_table.json` | xlsx、`schedule.json` |
| `budget_pcces.py` | PCCES 預算書（封面、計畫說明書、總表、詳細表、單價分析、單價依據、參數、假設） | unit_prices、`qty_table.json`、`schedule.json` | xlsx |
| `merge_set.py` | 封面＋各圖 PDF 合併、書籤，頁數對圖目錄 | 各圖 PDF、`toc.json` | 圖冊 PDF |
| `build_cad_set.py` | 各圖 DXF 合一（每張一配置）、`.dsd`、建視埠 `.scr`；`--dwg` 跑 accoreconsole | 各圖 DXF | 整合 DXF／DWG／DSD |
| `regress_run.py`、`regress_dxf.py`、`regress_xlsx.py` | 回歸比對 | 基準、重跑 | 報表（主控台） |
| `twd97.py` | TWD97 ↔ 經緯度（G-01 底圖定位） | － | － |

## P33 重跑驗證（2026-11-06，stamp 20261106_2343）
輸出：`D:\Claude_工作區\輸出\排水設計自動化\P33重跑驗證\`；基準：`D:\Claude_工作區\輸出\P33_新社東山\(印報告)\`。
- 7 份 DXF 與 CAD 整合 DXF：各圖層圖元數、全部文字一致；幾何最大偏差 0.005 mm（SF 填線、B20 填線端點的浮點差；P33 原產生器自己重跑也一樣）。
- 數量計算書 911 格、工程數量計算表 402 格：公式與重算值全同。
- 預算書：發包工程費 8,645,314、總價 9,503,175、詳細表 57 列金額全同；另有 22 格文字差異（基準 xlsx 交付後在 Excel 手改過：封面版面、表頭【待補】留白、部分【待確認】字樣），與 P33 原產生器輸出逐格相同。
- 配筋檢核表：1 格出處文字改為「本案設計（設定檔 design）」（原寫 design_param_v1.json，設計參數已改唯一來源）。
- 自動檢查計數與 P33 原產生器（同一版 p33_sheet）逐張相同；跨圖一致性 cross_check 兩邊都是「7 組、1 組不一致」（基準本來就有）。

## 踩過的雷
- 舊案資料夾只讀：P33 產生器把 `design_profile_*.csv`、`section_areas_v3.csv`、`qty_table_v2.0.json`、`toc_v2.json`、`design_param_v1.json` 寫回程式所在資料夾；一般化後一律寫 `work_dir`。
- 設計參數原本兩份（`design_param_v1.json` 與 design_profiles.py 的 PARAM 寫死），改成只讀設定檔 `design.*`；`design_param.json` 只是紀錄。
- 填線（HATCH 展開線）每次重跑端點差 0.001～0.005 mm，DXF 雜湊比對會誤判；回歸比對要用容差、同結構最近配對，不能排序後逐筆比。
- 預算書基準 xlsx 交付後有在 Excel 手改，產生器重跑不會重現手改；比對前先確認基準是不是程式原樣輸出。
- accoreconsole 指令檔裡的路徑要純英數，也不要用 `ADMINI~1` 短檔名；`build_cad_set.py` 一律在 `%TEMP%\ditch_cadset` 轉檔再搬回。
- 子程序（run_all 呼叫產生器、PowerShell 呼叫 Excel）主控台中文會亂碼，只影響畫面；結果看檔案或 `work_dir` 的 `.values.txt`。
- `json.dump` 改設定檔會把整份重排版；手改設定檔用編輯器，程式只讀不寫。

## 限制與【待確認】
- 幾何：側溝為直線（定線 DXF 各側一條兩點線）、每條側溝兩端各一座集水井、所有側溝同一斷面（W、H）；彎道、中途集水井、變斷面尚未支援。
- 橫斷面、PP 的引線版面照 P33「兩側側溝（左 A、右 B）」寫；單側或三條以上側溝要調整版面並重跑檢查。
- 標準圖 S-01～S-06 的圖面、鋼筋表、交維階段、告示牌是 P33 箱涵式側溝（B20 改 W110）專用，只參數化尺寸、擋土、引用檔與圖標；U 型溝、明溝等其他型式要另寫圖面。
- 數量計算書、工程數量計算表、預算書的**工項與算式文字**是案件資料檔（`qty_items`、`qty_table`、`unit_prices`），新案要依新設計逐項改寫；只有 `auto` 參數（側溝長、溝身淨長、拆除長、井數、井尺寸、樁距樁長）與表頭、費率、工期連動是自動的。工程數量計算表算式數字尚未由數量計算書自動產生【待確認是否要做】。
- 配筋檢核表的材料、土壓、載重假設與 B20 鋼筋配置是 P33 的（多項【待確認】）。
- 工期預設每日施工量（側溝 6 m/日、集水井 4 日/座、打除 30 m/日、擋土樁 40 支/日、AC 150 m²/日、準備 7 日、清理 5 日）是經驗值【假設】，未經使用者確認；各工項依序施工未考慮平行作業。旗手工作天沒給時取工期×2/3【假設】。
- 預算基準 v2.5 的 22 格手改（封面版面、表頭【待補】留白、部分【待確認】字樣）要不要寫回 `unit_prices.P33.json`／產生器【待確認】。
- 法規、規範條號沿用 P33 條文，依記憶引用者仍標【待確認】，交付前要核對原文。
