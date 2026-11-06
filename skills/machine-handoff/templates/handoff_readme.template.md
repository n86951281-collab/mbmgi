# {{CASE_NAME}}｜Claude 工作包

- 打包時間：{{PACKED_AT}}（{{MACHINE}}）
- 工作包：`{{PACKAGE_NAME}}`
- 用途：換到另一台電腦接續本案。收件機先讀本檔，再跑 `restore_handoff.ps1`（SKILL `machine-handoff`）。
- 檔案完整性：`manifest.csv`（相對路徑、大小、SHA256）；`handoff_info.json` 給還原腳本讀。

## 一、資料夾內容

| 資料夾 | 內容 | 原位置（送件機） |
|---|---|---|
{{FOLDER_TABLE}}

## 二、已完成（最新版）

【待填】由 Claude 依案件記憶填：成果、檔名（交付成果資料夾內）、產生程式、版次。

| 成果 | 檔名 | 產生程式 |
|---|---|---|
| 【待填】 | | |

本包內的交付成果（每組依版次、存檔時間取最新）：

{{DELIVERABLES}}

## 三、已定案的條件

【待填】使用者已確認的尺寸、坡度、定線、標準圖型號等，附確認日期。

## 四、待決事項（要問使用者或業主）

【待填】逐項列出，附相關樁號、檔名、版次。

## 五、下一步

【待填】

## 六、git 與倉庫

{{REPOS}}

{{GIT_STATUS}}

## 七、收件機還原步驟

1. NAS 路徑：桃園 llpc-237 用 `\\NAS\C2storagecjec\`；臺中 llpc-48 不能用 `\\NAS` 名稱，改用 IP `\\192.168.1.164\C2storagecjec\`。工作包在 NAS 上只讀，不在原地修改。
2. 在 mbmgi 倉庫拉最新 main，取得 SKILL `machine-handoff`。
3. 執行還原（先比對 manifest，再複製案件程式，並檢查環境）：
   ```
   powershell -ExecutionPolicy Bypass -File <mbmgi>\skills\machine-handoff\scripts\restore_handoff.ps1 `
       -PackageDir '<本工作包路徑>' -CaseDir '<本機案件資料夾>'
   ```
   原案件資料夾：`{{CASE_DIR}}`（工作包內為「{{CASE_FOLDER}}」）。路徑不同時，腳本會改 `case_config.json` 的輸出路徑與檔名前綴，並列出改了什麼。
4. 依還原報告補裝缺少的環境（Python 與套件、AutoCAD、GENIE 字型、git 作者身分、gh 登入）；腳本只列指令，不自動安裝，安裝前先問使用者。
5. 記憶：把「記憶」資料夾的本案 md 複製到收件機 Claude 記憶資料夾（送件機為 `{{MEMORY_DIR}}`），MEMORY.md 用合併的，不要整份覆蓋；或開對話時直接叫 Claude 讀本檔與記憶檔。
6. 需要更新全域規則時，在 mbmgi 倉庫跑 `sync-rules.ps1`（會切到 main、覆蓋全域 CLAUDE.md 標記區、複製 SKILL；倉庫有未提交變更會停下）。
