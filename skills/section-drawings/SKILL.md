---
name: section-drawings
description: 由測量圖 DXF 建原始地形 TIN、定線、切縱橫斷面，產出 A3 平面總圖、縱斷面圖、橫斷面圖（DXF＋PDF＋PNG，樣板 v4.0）。遇到「測量圖、建地形、TIN、等高線、高程點、中心線、定線、樁號、縱斷面、橫斷面、平縱橫斷面圖說、出圖」時使用。
---

# 平縱橫斷面出圖產生器

本 SKILL 負責全域規則「平縱橫斷面至挖填方、混凝土量作業流程」的前四個階段：收資料、建地形、定線、切原地形縱橫斷面並出圖。
設計斷面、挖填方、混凝土量（階段五以後）尚未做成程式，照全域規則逐步做。
圖層、線型、圖筆、字級以全域規則「出圖設定表（樣板 v4.0）」為準；程式已照該表寫好，不要自行改動。

## 環境

- Python 需有 numpy、ezdxf、matplotlib。一律用 `python -I` 執行，並先設 `$env:PYTHONIOENCODING='utf-8'`。
- 程式在本 SKILL 的 `scripts/`；圖筆 CTB 在 `assets/plot-styles/`（由 `sync-rules.ps1` 從 mbmgi 倉庫複製）。
- 預覽字型：微軟正黑體 Light（`C:\Windows\Fonts\msjhl.ttc`）、GENISO（`C:\Windows\Fonts\GENISO.ttf`）；這台沒有就在設定檔 `fonts` 指定。

## 步驟

### 1. 收資料，建案件設定檔
1. 每個案件開一個資料夾（例：`D:\Claude_工作區\共用\地形出圖\cases\<案名>\`），從 `templates/case_config.example.json` 複製成 `case_config.json`。**案件設定檔與中間資料只放本機，不放進 mbmgi 倉庫（公開）。**
2. 用 ezdxf 列出測量圖的圖層、各圖層圖元數、有無 Z 值，回報使用者，並請使用者確認：
   - 首曲線、計曲線圖層（`layers.contour_minor`／`contour_major`）。
   - 高程點 INSERT 所在圖層（`layers.spot_insert_layer`，插入點 Z 需大於 0）。
   - 地物圖層（`layers.features`，不帶 Z，只畫在平面圖上）。
   - 圖例表所在圖層與範圍（`legend.layer`、`legend.box`，世界座標 x0, y0, x1, y1）。

### 2. 建地形 ★停點
```
python -I scripts/build_terrain.py <case_config.json>
```
- 等高線沿線每 `terrain.densify_step`（預設 2 m）加密取點，加上高程點建 TIN；邊長超過 `terrain.max_edge`（預設 40 m）的三角形當作測量範圍外刪除。
- 同時用「只有等高線的 TIN」比對高程點，抽驗結果寫在 `<tin>_qa.txt`（RMSE、MAE、最大誤差、誤差最大 5 點）。把抽驗結果回報使用者；容許誤差尚未定案，不要自己判定合不合格。
- 預覽：
```
python -I scripts/terrain_views.py <case_config.json>
```
  輸出四個正向＋四個斜角的立體圖，等高線畫進地表顏色裡（背面自然遮住），測量範圍外不畫。`terrain.view_grid_step` 預設 0.25 m（中心線1 案約 2 分鐘跑完 8 張）；改 0.1 m 鋸齒較少，但同一案超過 12 分鐘仍跑不完一張，不建議。把 PNG 給使用者確認後才往下。

### 3. 定線 ★停點
- 使用者給定線時，請使用者把中心線、右岸線、左岸線（面向下游）分別放在設定檔 `alignment` 指定的圖層，另存 DXF。
- 使用者沒給定線時，依全域規則用兩岸線中點畫中心線，畫好請使用者確認，再存成上述格式。
```
python -I scripts/make_alignment.py <case_config.json>
```
- 0K+000 在下游：程式比較中心線兩端的 TIN 高程，自動把低的一端當起點；要強制指定時設 `alignment.downstream` 為 `"start"` 或 `"end"`。
- 斷面每 `alignment.spacing`（20 m）一刀，起終點加刀；新舊結構交接面等加刀位置寫在 `alignment.extra_stations`。
- 岸線可以是多段，程式會自動接起來；接完會檢查左右岸是否放反。
- 回報全長、斷面刀數與樁號範圍，等使用者確認。

### 4. 出圖
1. 填設定檔 `plan`：
   - `center_world`：平面圖中心的世界座標（通常取定線範圍的中點）。
   - `ticks_e`、`ticks_n`：圖廓邊的 TWD97 座標刻度（每 50 m，取落在圖廓內的整數）。
   - `frame`、`center_paper` 一般不用改（1/1000、圖廓 170×237 mm）。定線範圍超過 170 m × 237 m 時，1/1000 放不下，回報使用者決定分幅。
2. `profile.split_at`：縱斷面分張樁號，每張約 120 m（例：全長 228.9 m → `[120]`）。
3. 執行：
```
python -I scripts/section_drawings.py <case_config.json>
```
4. 看執行紀錄的「[檢查]」：每張圖的文字壓線、文字重疊、出界都要是 0 處；不是 0 就調整位置參數或回報使用者。「樁號未能避開」也要處理。
5. 輸出（檔名開頭都是 `file_prefix` 加存檔時間）：
   - `out_dir`：`…_A3_縱橫斷面圖說_<version>_TWD97_GENIE.dxf`（所有圖紙橫向並排，每張間隔 450 mm）、同名 PDF（套圖筆）。
   - `preview_dir`：每張圖一份 PNG，給手機檢視。
6. 要 DWG 時，用 AutoCAD 的 `accoreconsole.exe` 跑腳本 `FILEDIA 0` → `_.SAVEAS 2018 <路徑>` → `_.QUIT _Y`，路徑要純英文。

## 使用者在 CAD 手調後

使用者回傳 DWG：轉 DXF（`accoreconsole.exe` 跑 `DXFOUT`），和這次輸出的 DXF 逐圖元比對，把差異寫回 `scripts/section_drawings.py` 或樣板，開 PR 更新 mbmgi，並升版號。

## 已知限制

- 設計線、挖填方面積、混凝土量還沒做：橫斷面上的「挖：— m²　填：— m²」是預留位置；縱斷面圖例的「計畫溪床線（待設計）」亦同。
- 切線用前後各 1 m 求差分。2026-11-01 中心線1 案當時的算法沒有保留，用這支程式重算會有 0～1.9 度的差異；該案沿用原本的 `alignment.npz`，不要重算。
- 中間檔（`tin_npz`、`alignment_npz`）與出圖 DXF 已存在時程式會停下來，不覆蓋；重算請在設定檔改檔名加版次。
- 立體預覽在陡坎、測量範圍邊緣會有格網鋸齒，是預覽用格網的解析度限制，不影響 TIN 與斷面（斷面直接由 TIN 取高程）。
