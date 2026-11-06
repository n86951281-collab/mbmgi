---
name: drawing-set
description: 設計圖冊組圖與出圖：A3 圖紙元件（圖框、多重引線、自動檢查）、引用他機關標準圖 CAD（B20、A18 等）改本公司線型字型、封面、PDF 合併加書籤、整合成一個 DWG（每張一個配置、視埠 1:1）並用 PUBLISH 連續背景列印。遇到「設計圖冊、封面、圖目錄、標準圖引用、多重引線、合併圖冊、配置、視埠、發布、批次列印、PUBLISH、DSD」時使用。
---

# 設計圖冊組圖與出圖

版面與標註規則以全域規則 CLAUDE.md「四、CAD 與 DXF 圖面 > 設計圖冊版面與標註規則 v2」為準，本 SKILL 只講程式與步驟。
`scripts/` 是 P33 東山街案的參考實作，用到案件資料夾的 `case_config.json`、`toc_v2.json`、`src/`。新案複製到案件資料夾後，再改檔名、圖紙清單。

## 環境
- Python 3.12：numpy、ezdxf（1.4 以上，要有 `ezdxf.xref`）、matplotlib、pypdf、Pillow。執行前先設 `PYTHONIOENCODING=utf-8`。
- 產生器 import 同資料夾模組，所以不用 `-I`。讀外來檔（下載、NAS）的程式才用 `-I`。
- AutoCAD 2022 `accoreconsole.exe`：做 DWG 與 DXF 互轉、建視埠、PUBLISH 測試。指令檔一律用純英數路徑，長檔名用 `[IO.Path]::GetFullPath` 展開，不要用 `ADMINI~1` 這種短檔名。

## 模組
| 檔案 | 用途 |
|---|---|
| `p33_sheet.py` | A3 圖紙：圖框與圖標欄、`text`、`mleader`（DXF 寫 MULTILEADER）、`fill`、`image`；`check()` 檢查文字重疊、壓線、出界、引線壓字；`save()` 輸出 DXF、套圖筆的 PDF、PNG |
| `b20_import.py` | 引用他機關標準圖：依範圍框取原圖圖元，展開 DIMENSION、LEADER、INSERT，轉成 Sheet 圖元。改用本公司圖層、ByLayer、GENIE、14 pt 以上；詳圖號圓圈隨字放大；字放大後自動避讓（沿法向至多 6 mm、沿字向至多 14 mm） |
| `cover_sheet.py` | 封面（不列入圖目錄張次） |
| `merge_set.py` | 依 `PARTS`（檔名、頁數）合併 PDF，加書籤；頁數要和圖目錄張數一致 |
| `build_cad_set.py` | 各產生器 DXF 用 `xref.load_modelspace` 合成一個檔，每檔一列（間距 400 mm），每張圖一個 A3 配置，並設定頁面 |
| `make_vp_scr.py` | 產生 AutoCAD 指令檔：每個配置建視埠（VPORT 層不出圖）、ZOOM 到該張中心、高 297 mm（1:1），再另存 DWG |
| `make_dsd.py` | 產生 PUBLISH 用 `.dsd`（多頁 PDF，cp950 編碼，可含中文路徑） |

## 步驟
1. 各圖產生器出 DXF、PDF、PNG，`check()` 全部 0 才往下。
2. 引用標準圖：
   - 把原檔 DWG 轉成 DXF：複製到暫存區，用 accoreconsole 跑 `DXFOUT`；NAS 原檔只讀。
   - 先畫整張預覽圖看各詳圖位置，在 `REGIONS` 填範圍框（原圖紙面 mm）。
   - 用 `place(sh, 區名, ox, oy, k)` 放上圖紙。k 選整數比例（原 A1 比例 ÷ k），例如 A1 1:20 用 k＝0.8，得 1:25。
   - 看 PNG：圓圈內字、壓線、字擠在一起時，改比例或版面，不得縮字。
3. 合併 PDF：`python merge_set.py --stamp …`。
4. CAD 整合（全冊一個 DWG）：
   ```
   python build_cad_set.py --stamp …                     # → …_CAD整合_v1.0_….dxf
   python make_vp_scr.py <暫存>\final.dwg <暫存>\final.scr
   accoreconsole.exe /i <暫存>\final.dxf /s <暫存>\final.scr   # 建視埠並另存 DWG（暫存區路徑要純英數）
   ```
   - 把 DWG 複製到輸出資料夾，改成正式檔名。
   - 產生發布清單：`python make_dsd.py <輸出DWG> <輸出PDF> <輸出DSD>`。
   - 驗證：用 accoreconsole 開輸出 DWG 跑 `-PUBLISH <dsd>`，確認頁數與紙張（420×297）。
5. 交付：DWG、DSD、發布 PDF、合併 PDF。使用者在 AutoCAD 開 DWG → PUBLISH → 載入 DSD（或「載入所有圖紙」）→ 勾背景發布 → 發布。

## 踩過的雷（2026-11-06 實測）
- ezdxf `page_setup(scale=1)` 會被當成「標準比例第 1 號」（1/128"=1'），要寫 `scale=(1, 1)`。
- 置中與佈滿：`page_setup` 之後再設 `dxf_layout.dxf.plot_layout_flags |= 4 | 16`（4＝置中、16＝使用標準比例），以及 `standard_scale_type = 0`（佈滿圖紙）。用無邊界 A3 發布時跟 1:1 看起來一樣，換成有邊界的印表機才看得出差別。
- `page_setup` 的 `name` 只給 `ISO_full_bleed_A3`，程式會自動補「_(420.00_x_297.00_MM)」；給全名會重複一段。
- ezdxf 建的 VIEWPORT 在主控台出圖時不顯示模型內容，所以改由 AutoCAD 指令檔 `-VPORTS 0,0 420,297` 建視埠。
- 建視埠前要先在圖紙空間 `ZOOM W -10,-10 430,307`，不然 `MSPACE` 會回「沒有作用中的模型空間視埠」。
- accoreconsole 不印點陣影像（Google 底圖），PUBLISH 測試頁看不到底圖是正常的；AutoCAD 視窗版才會印。IMAGEDEF 用絕對路徑，PNG 跟著 DWG 一起交。
- GENIE 實際字寬：中文約 1.20h、半形約 0.66h（再乘寬度係數），比舊估算（1.0h、0.6h）寬約 20%。`p33_sheet.tw()` 已改用 `CJK_W`、`ASC_W` 實測值，自動檢查才準；圖標欄工程名稱用寬度係數 0.55。
- MLEADER：`build(insert=…)` 的插入點是文字塊頂端，不是中心，要用「中心＋(行數−1)×行距＋字高的一半」換算。AutoCAD 多行行距約 1.8h（`ML_HL`），行距係數或精確行距設了不會變小。連字線用 `HorizontalConnection.middle_of_text`，接在文字中間。
- 用 PUBLISH 測試頁核對 CAD 實際排版，不要只看程式預覽。程式預覽是依估算字寬縮放的，跟 CAD 不一定一樣。
- 指令檔、DSD 的配置名用純英數。DSD 用 cp950 編碼時中文路徑可正常發布。
- 圖說 DXF 已存在時程式不覆蓋，重出要換存檔時間。
