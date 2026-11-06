---
name: drawing-set
description: 設計圖冊組圖與出圖：A3 圖紙元件（圖框、多重引線、自動檢查）、引用他機關標準圖 CAD（B20、A18 等）改本公司線型字型、封面、PDF 合併加書籤、整合成一個 DWG（每張一個配置、視埠 1:1）並用 PUBLISH 連續背景列印。自動檢查含框格溢出、引線交叉、跨圖數值一致。遇到「設計圖冊、封面、圖目錄、標準圖引用、多重引線、合併圖冊、配置、視埠、發布、批次列印、PUBLISH、DSD、自動檢查、跨圖一致」時使用。
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
| `p33_sheet.py` | A3 圖紙：圖框與圖標欄、`text`、`mleader`（DXF 寫 MULTILEADER）、`fill`、`image`、`box`（登記框格）；`check()` 自動檢查（見步驟 1）；`save()` 輸出 DXF、套圖筆的 PDF、PNG |
| `cross_check.py` | 跨圖數值一致性：讀多張產生器 DXF 的文字（TEXT、MTEXT、MULTILEADER），依設定檔比對同一數值在各圖、數量表 xlsx 是否一致。設定檔範例 `templates/cross_check.example.json` |
| `find_frame_usage.py` | 改共用元件前，列出案件資料夾每支產生器用共用版還是自有的圖框、檢查、字寬函式 |
| `b20_import.py` | 引用他機關標準圖：依範圍框取原圖圖元，展開 DIMENSION、LEADER、INSERT，轉成 Sheet 圖元。改用本公司圖層、ByLayer、GENIE、14 pt 以上；詳圖號圓圈隨字放大；字放大後自動避讓（沿法向至多 6 mm、沿字向至多 14 mm） |
| `cover_sheet.py` | 封面（不列入圖目錄張次） |
| `merge_set.py` | 依 `PARTS`（檔名、頁數）合併 PDF，加書籤；頁數要和圖目錄張數一致 |
| `build_cad_set.py` | 各產生器 DXF 用 `xref.load_modelspace` 合成一個檔，每檔一列（間距 400 mm），每張圖一個 A3 配置，並設定頁面 |
| `make_vp_scr.py` | 產生 AutoCAD 指令檔：每個配置建視埠（VPORT 層不出圖）、ZOOM 到該張中心、高 297 mm（1:1），再另存 DWG |
| `make_dsd.py` | 產生 PUBLISH 用 `.dsd`（多頁 PDF，cp950 編碼，可含中文路徑） |

## 步驟
1. 各圖產生器出 DXF、PDF、PNG，`check()` 全部 0 才往下（「字距線過近」是警告，逐筆看過即可）。檢查項目（規則見全域 CLAUDE.md「設計圖冊版面與標註規則 v2」的自動檢查五項）：
   | 項目 | 抓什麼 | P33 漏抓實例 |
   |---|---|---|
   | 文字重疊、文字壓線、出界、引線壓字 | 原有四項；壓線只查 `design_layers` | — |
   | 框格溢出 | 文字估算外框超出所屬框格；非圖標欄文字伸進圖標欄 | 圖標欄工程名稱超框；G-02 一般說明第五節掉到圖標欄底下 |
   | 引線交叉 | MLEADER 引線兩兩交叉；連字線穿過其他文字 | S-01 集水井兩條引線交叉 |
   | 其他線壓字 | 所有圖層的線穿過字框，或平行貼在字頂、字底（`touch`×字高內） | S-04 殘留舊短線貼在「開挖施工區」字頂 |
   | 字級不足 | 字高小於 14 pt（4.94 mm） | — |
   | 字距線過近（警告） | 字框外 `near_ratio`×字高內有線，例如尺寸字貼尺寸線 | — |
   - 框格：`frame()` 自動登記圖標欄各格。說明欄、表格欄要自己登記：`b = sh.box(x0, y0, x1, y1, "一般說明")`；文字一路往下排、插入點可能掉出框外時，排完再 `sh.own(b, i0)` 指定成員（`i0`＝開始排之前的 `len(sh.items)`）。
   - 自己畫圖框的產生器（P33 的 `plan_view.py`），畫完圖標欄要呼叫 `register_title_block(sh, i0)`，否則圖標欄不受檢查。
   - 關閉單項：`check(sh, L, near_line=False)`；參數 `boxes`、`leader_cross`、`any_line`、`min_size`、`near_line`、`touch`、`near_ratio`、`ignore_layers`、`near_ignore`。
   - 回傳值仍可解包成 `(重疊, 壓線＋引線壓字, 出界)`；全部項目看 `.detail`，是否全過看 `.ok`。逐筆列出：設 `P33_DEBUG=1`。
1-1. 跨圖一致性：全冊 DXF 出齊後（數量表有改時一起）跑
   ```
   python -I cross_check.py <案件>\cross_check.json [DXF ...] [--xlsx 數量計算書.xlsx] --report <暫存>\cross_check.txt
   ```
   - 設定檔每組列「圖號＋正則」，例如 S-01 開挖線算出的寬度、S-03「開挖寬」、數量表參數儲存格，應一致的數值放 `expect`。
   - 不一致或找不到就回傳碼 1，列出各圖的值與原文。改標註文字後 pattern 對不上也會報「找不到」，不會默默漏比。
   - xlsx 讀的是快取值，先用 Excel COM 重算存檔再跑。
1-2. 改共用元件（圖框、圖標欄、簽名欄、字寬、檢查）時，先列出所有產生器再改，改完再跑一次確認每支都改到：
   ```
   python find_frame_usage.py <案件資料夾> --term 陳俊廷
   ```
   或直接 grep：`grep -nE "def (frame|check|tw|tbox)\b|CJK_W|工程名稱：|設計：" <案件資料夾>/*.py`（略過 `_bak_` 備份檔）。標「自有」的檔案要一起改。P33 的 P-01（`plan_view.py`）用自己的圖框函式，工程名稱字寬、簽名欄人名兩次都漏改；`design_profiles.py`、`plan_profile.py` 也有自己的圖框或檢查。
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
- 自動檢查全 0 不代表沒問題（11/06 P33 由使用者或數量對話人工抓到，已補成檢查項目）：
  - 圖標欄文字原本不在檢查範圍（中心在 y＜32 的字一律跳過），工程名稱超框、G-02 說明溢到圖標欄都沒抓到 → 框格溢出。
  - 壓線只查指定的設計圖層；S-04 殘留短線剛好落在字框頂邊（y 相等），只看框內部也抓不到 → 其他線壓字（含平行貼邊）。
  - 跨圖數值不一致（S-01 開挖寬 190、S-03 寫 210；S-01 加腋引線寫水泥砂漿、數量表算混凝土）單張檢查抓不到 → `cross_check.py`。
  - 交通錐和護欄立柱局部重疊是圖形對圖形，目前檢查只管文字，仍要看 PNG。
- 新檢查第一次跑 P33 v3.4 標準圖時，「其他線壓字」在 S-01-1 報 19 處，多半是引用 B20 的尺寸字貼著尺寸線（字框底邊距線不到 0.15 mm），要逐筆判斷是否移字。
- 用 `python -I` 時 `PYTHONIOENCODING` 不生效；`cross_check.py`、`find_frame_usage.py` 已在程式裡把輸出改成 UTF-8。
