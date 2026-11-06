---
name: machine-handoff
description: 換電腦接續同一案（桃園 llpc-237 ↔ 臺中 llpc-48 ↔ 其他）：送件機檢查 git 未提交與未推送分支、打包「Claude 工作包」（記憶、案件程式與中間資料、最新版交付成果、說明檔、manifest SHA256），上傳 NAS 後比對；收件機比對 manifest、複製案件程式、改 case_config 路徑與檔名前綴、檢查 Python／AutoCAD／Excel／字型／git／gh 環境。遇到「換電腦、換機、交接、工作包、接續、打包、還原、到臺中做、回桃園做、manifest」時使用。
---

# 換電腦交接（Claude 工作包）

規則引用倉庫 CLAUDE.md，不重抄：「工作方式規則 三、版次與檔案」（版次、`Get-Date`、找檔順序先本機 `輸出` 再 NAS）、「五、多對話協作」（換電腦前推送分支、交接包附說明與路徑對照）、「六、轉檔」最後一條（Python 依機器、`PYTHONIOENCODING`、`-I`）。
機器專屬規則在各機全域 CLAUDE.md 同步標記之外：NAS 路徑、臺中檔名前綴「(臺中48)」。

## 檔案
| 檔案 | 用途 |
|---|---|
| `scripts/pack_handoff.ps1` | 送件機：git 檢查 → 打包 → 說明骨架 → manifest；`-UploadPackage` 上傳 NAS 並在 NAS 端重算比對 |
| `scripts/restore_handoff.ps1` | 收件機：比對 manifest → 複製案件程式 → 改 `case_config.json` → 記憶提示 → 環境檢查 → sync-rules 提醒 |
| `templates/handoff_readme.template.md` | `00_說明_先讀這份.md` 骨架；`{{…}}` 由腳本填，【待填】由 Claude 填 |

兩支都是 PowerShell 5.1（UTF-8 含 BOM），用 `powershell -ExecutionPolicy Bypass -File …` 執行。輸出含中文，Claude 讀結果時用腳本寫的 UTF-8 報告檔，或自己 `*> 檔案` 再讀，不直接看主控台。

## 工作包結構
資料夾名 `（機器）yyyyMMdd_HHmm_案名_Claude工作包`，時間取 `Get-Date`。機器標籤依 `$env:COMPUTERNAME`：LLPC-237 →「（桃園）」、LLPC-48 →「(臺中48)」，其他用電腦名；可用 `-MachineLabel` 指定。

| 項目 | 內容 |
|---|---|
| `00_說明_先讀這份.md` | 資料夾對照表（含原位置）、已完成成果與產生程式、已定案條件、待決事項、下一步、git 狀態、收件機還原步驟 |
| `01_對話紀錄` | 只在 `-IncludeConversation` 時建立；`-ConversationPath` 給匯出 zip，沒給就放提示檔，請使用者從桌面版匯出後放入 |
| `02_記憶` | `MEMORY.md` 索引＋本案相關 md（`-MemoryFiles` 指定檔名，或 `-MemoryKeywords` 比對檔名與內容） |
| `03_案件程式與中間資料` | `-CaseDir` 全部複製，排除 `__pycache__`、`.git`、`OLD`、`_作廢`、`暫存`、`tmp`、`*_bak_*`、`*.pyc`、`*.bak`、`~$*`、大於 `-MaxFileMB`（預設 100） |
| `04_交付成果` | `-DeliverableDir` 每組取最新（同資料夾、去掉前綴與時間與 `_v版次` 後同名為一組；先比版次，再比存檔時間）；`OLD`、`_作廢` 不收 |
| `05_…` 起 | `-ExtraDirs` 每個資料夾一格，例如標準圖轉檔 |
| `handoff_info.json` | 原路徑、記憶清單、各倉庫分支與未推送數，給還原腳本讀 |
| `manifest.csv` | 相對路徑、大小、SHA256（不含自己） |

打包報告（排除清單、選中的交付成果）寫在工作包外面：`<工作包名>_打包報告.txt`。

## 步驟（送件機）
1. 讀本案記憶，決定 `-MemoryFiles`（本案 md、相關工作規則 md）；確認案件程式夾、交付成果夾。
2. 打包到本機暫存（不要直接打包到 NAS）：
   ```
   powershell -ExecutionPolicy Bypass -File <SKILL>\scripts\pack_handoff.ps1 `
     -CaseName 東山街排水 -CaseDir 'D:\Claude_工作區\共用\地形出圖\cases\P33_新社東山' `
     -DeliverableDir 'D:\Claude_工作區\輸出\P33_新社東山' -OutputDir 'D:\Claude_工作區\輸出\交接包' `
     -MemoryFiles p33-xinshe-dongshan-ditch.md,mbmgi-repo-setup.md -ExtraDirs 'D:\Claude_工作區\暫存\標準圖DXF' `
     -Repos 'D:\Claude_工作區\mbmgi' -IncludeConversation
   ```
3. git 檢查（`-Repos`，預設 mbmgi）：每個 worktree 的未提交檔，以及每個本地分支「不在任何遠端」的提交數（`git rev-list <分支> --not --remotes`）。有任何一項就**停下（結束代碼 2）並列出**，請使用者決定：提交推送後重跑，或確認不需要再加 `-AllowUnpushed`（會寫進說明檔）。腳本不自動提交。推送卡住先 `gh auth setup-git`。
   - Claude 子代理的工作樹（`.claude/worktrees/agent-*`，分支 `worktree-agent-*`）有未提交變更也會列出，代表還有對話在改；等那些對話提交推送，或由使用者確認可略過。`.claude/worktrees` 資料夾本身不算未提交。
4. Claude 依案件記憶填 `00_說明_先讀這份.md` 的【待填】：已完成成果（檔名、產生程式、版次）、已定案條件（附確認日期）、待決事項、下一步；有 `05_…` 的話補內容欄。數值附出處，不確定標【待確認】。
5. 上傳並比對（說明檔還有【待填】會拒絕；目的地已存在不覆蓋）：
   ```
   powershell -ExecutionPolicy Bypass -File <SKILL>\scripts\pack_handoff.ps1 -UploadPackage '<本機工作包>' -NasDest '<NAS 案件 01_收資料>'
   ```
   會重算 manifest、robocopy 到 NAS、在 NAS 端逐檔重算 SHA256；不符時結束代碼 3。
6. 回報使用者：NAS 路徑（收件機要用的寫法）、檔數與大小、git 狀態。

## 步驟（收件機）
1. 先用收件機的 NAS 寫法找工作包（見下方「踩過的雷」）；工作包只讀。
2. 還原：
   ```
   powershell -ExecutionPolicy Bypass -File <SKILL>\scripts\restore_handoff.ps1 `
     -PackageDir '\\192.168.1.164\C2storagecjec\...\（桃園）20261105_2120_東山街排水_Claude工作包' `
     -CaseDir 'D:\Claude_工作區\共用\地形出圖\cases\P33_新社東山' -OutDir 'D:\Claude_工作區\輸出\P33_新社東山'
   ```
   - manifest 不符：結束代碼 3，停下回報。
   - `-CaseDir` 已有檔案：結束代碼 4，不覆蓋，請使用者決定（換資料夾，或舊的移到 `OLD`）。
   - `case_config.json`：原案件路徑 → `-CaseDir`；原 `out_dir` 開頭的路徑（含 `preview_dir`）→ `-OutDir`；`file_prefix` → 本機前綴（或 `-FilePrefix`）。原檔另存 `case_config_還原前.json`，改了什麼列在報告。其他 `.py`、`.json`、`.scr`、`.ps1`、`.bat` 寫死的送件機路徑只列出，由 Claude 確認後再改。
   - `-CheckOnly`：只比對與檢查環境，不複製。
3. 記憶：報告列出每個記憶檔在本機的狀態（沒有／相同／不同）。本案 md 複製到本機記憶資料夾；`MEMORY.md` 只合併本案條目，不整份覆蓋。
4. 環境：報告列 [有]／[缺] 與安裝指令。**不自動安裝、不自動設定 git 身分**；要裝要設先問使用者（下載軟體屬需同意的動作）。
   - Python（排除 `WindowsApps` 商店空殼）與套件（預設 numpy、ezdxf、matplotlib、pypdf、Pillow、openpyxl，可用 `-PyPackages` 改）
   - AutoCAD `accoreconsole.exe`、Excel COM、GENIE／GENISO 字型
   - git 全域作者身分、gh 登入、送件機分支是否已在 origin
5. 要更新規則與 SKILL 才跑 `sync-rules.ps1`；先提醒使用者它會切到 main、覆蓋全域 CLAUDE.md 標記區、複製全部 SKILL，跑完要重開 Claude Code。
6. 接續工作：新檔名用本機前綴，內容有變就升版次。

## 踩過的雷（2026-11-05 P33 桃園 → 臺中實測）
- 臺中 llpc-48 不能用 `\\NAS` 名稱；`C2storagecjec` 也要用 IP：`\\192.168.1.164\C2storagecjec\`（CJ001 是 `\\192.168.1.164\CJ001\`）。桃園 llpc-237 用 `\\NAS\C2storagecjec\`。說明檔要寫收件機那台的寫法。
- 中文路徑、檔名的輸出直接看主控台會亂碼：先 `Out-File -Encoding utf8` 存檔再讀；兩支腳本都另寫 UTF-8 報告。
- 送件機本地分支 `feat/ditch-design-drawings` 未提交、未推送，臺中拿不到程式。打包前的 git 檢查就是為了擋這個。
- 2026-11-06 臺中 → 桃園打包：照本檔範例用 `powershell -File … -MemoryFiles a.md,b.md`，逗號清單被當成一個檔名，記憶只收到 `MEMORY.md`（輸出有「記憶資料夾找不到」）。`-File` 不會把逗號解析成陣列；腳本已改成自己拆逗號，`-File`、`-Command` 兩種呼叫都可以。這個錯是因為寫 SKILL 時沒有照範例原文實跑。
- 同一次實跑又抓到兩個：
  - 輸出路徑用 8.3 短檔名（例 `C:\Users\ADMINI~1\...`，Claude 暫存區常見）時，`Resolve-Path` 保留短名、`Get-ChildItem` 回長名，`Substring` 切錯，manifest 相對路徑全錯，還原時 117 個檔都報缺。已改用 `Resolve-Full`（`GetLongPathName` 展開）。
  - 已合併、遠端分支已刪的本地分支，還原時被誤報「送件機未推送」；現在提交都已在遠端（`unpushed` = 0）的分支不列。
- 臺中原本只有商店空殼 python，要用 `winget install -e --id Python.Python.3.12 --scope user` 再 pip 裝套件（使用者同意後才裝）。
- 舊說明檔寫「一律 `python -I`」：`-I` 會把腳本所在資料夾移出 `sys.path`，產生器 `import` 同資料夾模組（例如 `p33_sheet`）就 `ModuleNotFoundError`。產生器不加 `-I`；讀外來檔（NAS、下載）的程式才加。
- 收件機沒有 git 作者身分，commit 失敗。單次用 `git -c user.name=… -c user.email=… commit`，不改全域設定；要設全域先問。
- push 卡住通常在等 GitHub 登入：gh 已登入時先 `gh auth setup-git` 再推。
- `case_config.json` 的 `file_prefix` 是送件機的（例「（桃園）」），沒改的話臺中出圖檔名會錯；還原腳本會改。
- 舊工作包把 `__pycache__`、同版次不同存檔時間的舊檔都打包進去（交付成果頂層 44 個 DXF、PDF，實際要用的只有 4 種圖的最新版）；現在排除並每組取最新。
- NAS 原檔只讀：工作包上傳到新資料夾，目的地已存在就停；收件機從 NAS 複製到本機再改，不在 NAS 上改。

## 【待確認】
- GENIE 字型的實際檔名：臺中機只找到 `GENISO.ttf`、`GENISO.shx`、`geniso12.shx`，沒有 `GENIE*`；腳本以檔名開頭比對，可能誤報缺字型。
- 機器標籤：工作包沿用 P33 舊包的「（桃園）」；倉庫規則的對話標題前綴是「(桃園237)」「(臺中48)」「(台南01)」，工作包要不要統一改用同一套；台南及其他機器目前用「（電腦名）」。
- 交付成果分組：檔名中段改過（例如 `平面配置圖_v1.5` → `平面配置圖_1-500_v1.6`）會被當成兩組都收；要不要只收最新一組，由 Claude 看打包報告後決定。
- 對話匯出無法由腳本自動產生，需使用者從桌面版手動匯出。
