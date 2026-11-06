---
name: cadastre-overlay
description: 地籍圖謄本 PDF 定位套繪到測量圖 DWG：解密讀出謄本向量地籍線與地號（不描圖），用標示比例尺＋單點做初值，再用兩個以上 TWD97 控制點做相似轉換（比例、旋轉、平移），建地籍線、地號兩個新圖層（地號避讓、窄長條地加引線），用 accoreconsole 併入測量圖另存新檔，逐圖層比對原圖物件數。遇到「地籍圖、謄本、地籍線、地號、套繪、地籍套繪、控制點、定位、相似轉換、殘差」時使用。
---

# 地籍圖謄本定位套繪

規則以倉庫 CLAUDE.md 為準，本 SKILL 只講程式與步驟：
- 字型、ByLayer、DXF 命名：「四、CAD 與 DXF 圖面」。
- 地籍線 252 灰色虛線、畫面內每塊地號都要標：「設計圖冊版面與標註規則 v2 > 地籍套繪圖（L-01）」。
- 至少兩個控制點、回報殘差、併入後比對原圖層物件數：「工作方式規則 > 四、驗證」。

`scripts/` 是 P33 東山街案的參考實作，已把案件相關的值移到設定檔。新案把 `templates/overlay_config.example.json` 複製到案件資料夾，改名 `overlay_config.json`，逐項改成本案的值。

## 環境
- Python 3.12：numpy、ezdxf（1.4 以上）、matplotlib。執行前先設 `PYTHONIOENCODING=utf-8`。
- 程式會 import 同資料夾的 `common.py`，所以不加 `-I`。謄本 PDF、測量圖要先複製到本機暫存區再讀，NAS 原檔只讀。
- AutoCAD 2022 `accoreconsole.exe`：DWG 轉 DXF、把地籍 DXF 併入 DWG。指令檔由 `make_scr.py` 產生，路徑要純英數的完整長路徑。

## 模組
| 檔案 | 用途 |
|---|---|
| `common.py` | 讀設定檔、PDF pt 轉 TWD97（`xf`）、讀測量圖線段 |
| `pdf_dump.py` | 解密（Standard V1/R2、40-bit RC4、空白使用者密碼）並傾印所有物件與串流到 dump 資料夾 |
| `pdf_parse.py` | 自動找各頁內容串流與字型 ToUnicode，解析路徑（紙面 pt）與文字 → `parsed.json`、`texts.txt` |
| `pdf_preview.py` | 各頁畫成 PNG，並統計線條樣式（找地籍線的顏色、線寬） |
| `dxf_inspect.py` | 測量圖各圖層、圖元數、範圍、文字樣式（UTF-8 輸出） |
| `reg2.py` | `init`：標示比例尺＋單點初值；`fit`：控制點最小二乘相似轉換，各頁分別算，輸出殘差表 csv |
| `probe.py` | 在控制點處拉探測線，量地籍線交點座標，用來得到控制點的套繪量得座標與檢核線殘差 |
| `overlay.py` | 用定位參數直接畫測量圖＋地籍線檢查圖（不必先建 DXF） |
| `build_cadastre_dxf.py` | 建地籍 DXF：地籍線、地號兩圖層；地號避讓、引線；段名 |
| `make_scr.py` | 產生 accoreconsole 指令檔：`dxfout`（DWG 轉 DXF）、`merge`（分解插入地籍 DXF，另存新 DWG、DXF） |
| `verify_merged.py` | 原圖每個「圖層＋圖元種類」物件數比對，PASS／FAIL |
| `preview_merged.py` | 合併檔預覽 PNG、PDF（全區＋分段），自動檢查壓線、文字互疊、引線壓字 |
| `register.py`（選用） | 地籍線對測量圖邊線的距離場格點搜尋（固定比例），沒有控制點時當粗配準或交叉檢核 |
| `pdf_zoom.py`（選用） | 放大 PDF 一小塊，`--vertices` 印出地籍角點 pt 座標（找 `init.pref`） |
| `survey_plot.py`（選用） | 測量圖某段依圖層上色，找可對照的道路邊線、側溝 |

## 步驟
以下 `<w>` 是案件工作資料夾，`<a>` 是純英數暫存資料夾（例如 `C:\Users\Administrator\AppData\Local\Temp\cadx`），`cfg` 是 `<w>\overlay_config.json`。

1. 收資料：
   - 謄本 PDF（中華地政或各地政事務所電子謄本，使用者自行申請下載）。
   - 測量圖 DWG：複製到 `<a>\survey.dwg`，轉 DXF 後用 `dxf_inspect.py` 看圖層與範圍、確認是 TWD97：
     ```
     python make_scr.py dxfout <a>\survey.dxf <a>\toDxf.scr
     accoreconsole.exe /i <a>\survey.dwg /s <a>\toDxf.scr /l zh-TW
     python dxf_inspect.py <a>\survey.dxf <w>\survey_layers.txt
     ```
   - 控制點：請使用者在國土圖資等網頁標記並截圖，給 TWD97 座標（E、N），至少 2 點，分佈在工區兩端（例如起點路口、設計終點）。截圖要能看到比例尺，用來量標記點到附近地籍線的距離（px/m）。
2. 讀謄本：
   ```
   python pdf_dump.py <謄本.pdf> <w>\dump
   python pdf_parse.py <w>\dump cfg
   python pdf_preview.py <w>\dump cfg
   ```
   - 謄本通常是向量檔、40-bit RC4 權限加密（不用密碼），直接讀出原始線條與文字，不描圖。不是 V1/R2 時 `pdf_dump` 會停止。
   - 一頁一個段別（p1、p2…）。看 `texts.txt`：字高 ≥ 6 pt 的是標題、土地坐落（段名、地號清單）、比例尺標示（例「比例尺：1/3000」「原比例尺：1/500」）；小於 6 pt 的才是圖上地號。段名填 `pdf.pages`，比例尺分母填 `pdf.scale_denominator`。
   - 看 `pdf_preview` 的線條統計，找地籍線的顏色（P33：灰 0.9412、線寬 0.1）填 `cadastral_stroke_rgb`；看預覽圖找地圖框，填 `map_clip_pt`。
3. 定位：
   - 初值：用 `pdf_zoom.py --vertices` 找北端控制點旁一個地籍角點的 pt 座標當 `init.pref`；在網頁截圖上量出該角點的 TWD97 當 `init.wref`，各頁各一組。
     ```
     python reg2.py init cfg <w>\reg_init.json
     python build_cadastre_dxf.py <w>\dump <w>\reg_init.json <a>\cadastre.dxf cfg
     ```
   - 第二點以後：在每個控制點用 `probe.py <a>\cadastre.dxf <N> <E西> <E東>` 量地籍線位置，和截圖量到的位置比，得到該控制點在目前套繪中的 `observed` 座標（第一點本身當初值，`observed` = `twd97`）。
   - 相似轉換（各頁分別算，`pages` 省略時套到所有頁）：
     ```
     python reg2.py fit cfg <w>\reg_init.json <w>\reg_fit.json <w>\定位殘差.csv
     python build_cadastre_dxf.py <w>\dump <w>\reg_fit.json <a>\cadastre.dxf cfg
     ```
   - 驗證：重跑 `probe.py`，在每個控制點量多條南北向、東西向地籍線，和截圖比，把檢核線殘差補進殘差表。2 點時相似轉換剛好有解，控制點本身殘差恆為 0，只有檢核線殘差有意義；3 點以上才有控制點殘差。
   - `overlay.py` 放大看控制點附近，地籍道路界線與測量圖道路邊線、側溝外緣是否大致平行吻合。
   - P33 實測：標示 1/3000，實際大 0.9%（約 1/3027）、旋轉 −0.13°；只用單點時南端（約 116 m 外）偏北約 1.05 m、偏東約 0.26 m。兩點修正後北端 ≤ 0.05 m、南端南北向線 ≤ 0.12 m、東西向路界 ≤ 0.2 m。
4. 建 DXF（`build_cadastre_dxf.py`）：
   - 兩個新圖層，名稱、顏色、線型、字型取 `output`（ByLayer、GENISO＋GENIE、寬度係數 0.5）；地號字高 2.5 m（1/500 約 14 pt），段名 5 m。
   - 地號避讓：先保留謄本原位置；壓線或互疊的，在自己地塊內就近找不壓線、不互疊的位置（可轉 90°）；放不下的窄長條地拉引線，沿 `road_axis_e` 道路的一律往路外側標。印出 `label_outcome`（moved、leader、unresolved）。
5. 併入 DWG（原檔不動，另存新檔）：
   ```
   python make_scr.py merge <a>\cadastre.dxf <a>\merged.dwg <a>\merged.dxf <a>\merge.scr
   accoreconsole.exe /i <a>\survey.dwg /s <a>\merge.scr /l zh-TW
   python verify_merged.py <a>\survey.dxf <a>\merged.dxf <w>\verify.txt cfg
   python preview_merged.py <a>\merged.dxf <w>\預覽.png <w>\預覽.pdf <w>\overlap.txt cfg
   ```
   - `verify.txt` 第一行要 PASS：原圖每個圖層、圖元種類的物件數都不變，只多地籍線、地號兩層；殘留圖塊參照 0（`-INSERT "*路徑"` 會分解插入）。
   - `overlap.txt` 的問題數要 0；再看預覽 PDF 的北、中、南段，確認地號在自己地塊內。
6. 交付（檔名依 CLAUDE.md DXF 命名規則，加存檔時間與版次）：
   - 合併 DWG、DXF；預覽 PDF（A3 橫式，全區＋分段）、PNG；定位參數 json（`reg_fit.json`）；定位殘差表（控制點＋檢核線）。
   - 回報：控制點與殘差、比例與旋轉修正量、各頁地籍線與地號數、自動檢查結果、沒在 CAD 目視的項目。
   - 註明：控制點都在工區內，工區內可信；工區外越遠誤差越大，只當參考。地籍線只是謄本圖解位置，實地界址以複丈鑑界為準。
7. 要出地籍套繪圖（L-01）時，接 `drawing-set` 的圖紙產生器，用本流程的定位參數（P33 是案件資料夾的 `cadastral_sheet.py`）。

## 踩過的雷（2026-11-05 P33 實測）
- 本機（臺中 llpc-48）有 GENISO，沒有 GENIE 中文大字體：樣式照規則設 GENISO＋GENIE，缺字型的電腦上中文段名會用替代字型顯示，地號是數字不受影響。交付時講明。
- accoreconsole 指令檔路徑含中文時，寫進 `.scr` 會變成「?」，轉檔失敗。一律複製到純英數資料夾，用完整長路徑（不要用 `ADMINI~1`），`make_scr.py` 會擋。
- `dxf_inspect` 等輸出由程式自己寫 UTF-8 檔，不用 PowerShell 重導向（會變亂碼）。accoreconsole 的 log 是 UTF-16，讀時要轉碼。
- 謄本文字：段名、地號清單、比例尺、核發機關都是大字（≥ 6 pt），地號是小字。只取小字當地號，段名另外由設定檔放；不要把「土地坐落」那行當地號。
- 浮水印（地政事務所名稱）在表單 XObject 裡，`pdf_parse` 只列出，不寫入圖面。
- 謄本標示比例尺只是約略值（P33 差 0.9%），只用一個控制點時比例、旋轉都檢查不出來，工區另一端會偏 1 m 左右。
- 自動配準（`register.py`）拿地籍線去貼現況邊線，結果被房屋、側溝拉偏（P33 旋轉 −0.36°、+0.14°，兩頁不一致），只能當參考，不能取代控制點。
- 建 DXF 時同一頁內重複的邊（相鄰地塊共用邊）以座標去重；兩頁都有的段界線不跨頁去重，各留一份，兩頁定位正確時會重疊在一起，可順便當接邊檢查。地圖框外的線與地號不取。
- 2 點相似轉換的控制點殘差恆為 0，不能拿來當驗證結果回報，一定要另外量檢核線。

## 【待確認】
- 地號圖層顏色號：CLAUDE.md 只規定地籍線 252 灰色虛線，範例設定暫用 7；P33 v1.1 交付時兩層都用 6、實線（當時還沒有 L-01 規則）。
- 地籍線 DASHED 在 TWD97 公尺單位下的線型比例（LTSCALE、個別比例），要在 CAD 出圖確認虛線看得出來。
- 檢核線殘差的容許值（P33 南端 0.2 m 算通過，沒有明文規定）。
- `pdf_parse` 自動找頁面只在 P33 謄本（臺中市東勢地政事務所電子謄本）驗證過；其他地政事務所、R3 以上加密的 PDF 尚未實測。
