# restore_handoff.ps1
# 收件機：還原「Claude 工作包」。PowerShell 5.1 相容。
# 只讀工作包（NAS 原檔不動）；不自動安裝任何軟體、不改 git 設定、不跑 sync-rules.ps1。
#
# 動作：
#   1. 比對 manifest.csv（大小、SHA256）
#   2. 把案件程式與中間資料複製到本機 -CaseDir（目的地已有檔案就停下）
#   3. 路徑或機器不同時，改 case_config.json 的絕對路徑與 file_prefix，列出改了什麼；
#      其他 .py/.json 內寫死的送件機路徑只列出，不改
#   4. 提示記憶要放哪裡（不複製）
#   5. 檢查環境：Python 與套件、accoreconsole、Excel、GENIE 字型、git 作者身分、gh 登入、倉庫分支是否在遠端
#   6. 提醒 sync-rules.ps1 的作用（不執行）
#
# 例：
#   .\restore_handoff.ps1 -PackageDir '\\192.168.1.164\C2storagecjec\...\（桃園）20261105_2120_東山街排水_Claude工作包' `
#       -CaseDir 'D:\Claude_工作區\共用\地形出圖\cases\P33_新社東山' -OutDir 'D:\Claude_工作區\輸出\P33_新社東山'
#
# 結束代碼：0 完成（環境缺項列在報告）；3 manifest 不符；4 目的地已有檔案；1 其他錯誤。

param(
    [Parameter(Mandatory = $true)] [string]$PackageDir,
    [Parameter(Mandatory = $true)] [string]$CaseDir,
    [string]$OutDir,                    # 本機交付成果資料夾；給了就把 case_config 裡原 out_dir 開頭的路徑換成這個
    [string]$FilePrefix,                # 新檔名前綴；不給就依本機機器名
    [string]$MemoryDir = (Join-Path $env:USERPROFILE '.claude\projects\D--Claude----\memory'),
    [string]$RepoDir = 'D:\Claude_工作區\mbmgi',
    [string[]]$PyPackages = @('numpy', 'ezdxf', 'matplotlib', 'pypdf', 'PIL', 'openpyxl'),
    [string]$ReportPath,
    [switch]$SkipVerify,
    [switch]$CheckOnly                  # 只比對與檢查環境，不複製
)

$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'
$utf8NoBom = New-Object Text.UTF8Encoding($false)
$log = New-Object System.Collections.Generic.List[string]
function Log([string]$s) { $log.Add($s); Write-Host $s }
function Save-Report {
    if (-not $ReportPath) {
        $base = if (Test-Path 'D:\Claude_工作區\暫存') { 'D:\Claude_工作區\暫存' } else { $env:TEMP }
        $ReportPath = Join-Path $base ("{0}還原檢查_{1}.txt" -f $script:Prefix, (Get-Date).ToString('yyyyMMdd_HHmm'))
    }
    [IO.File]::WriteAllText($ReportPath, ($log -join "`r`n"), $utf8NoBom)
    Write-Host ''
    Write-Host "還原報告（UTF-8）：$ReportPath"
}

switch ($env:COMPUTERNAME.ToUpper()) {
    'LLPC-237' { $autoPrefix = '（桃園）' }
    'LLPC-48'  { $autoPrefix = '(臺中48)' }
    default    { $autoPrefix = "（$($env:COMPUTERNAME)）" }
}
$script:Prefix = if ($FilePrefix) { $FilePrefix } else { $autoPrefix }

if (-not (Test-Path -LiteralPath $PackageDir)) {
    throw "找不到工作包：$PackageDir`n臺中機不能用 \\NAS 名稱，請改用 IP，例如 \\192.168.1.164\C2storagecjec\..."
}
$pkg  = (Resolve-Path -LiteralPath $PackageDir).ProviderPath.TrimEnd('\')
$info = Get-Content -LiteralPath (Join-Path $pkg 'handoff_info.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Log "工作包：$pkg"
Log "案名：$($info.case_name)　送件機：$($info.machine_label) $($info.machine)　打包：$($info.packed_at)"
Log "本機：$($env:COMPUTERNAME)　新檔名前綴：$script:Prefix"
Log ''

# 1. manifest
if (-not $SkipVerify) {
    $rows = Import-Csv -LiteralPath (Join-Path $pkg 'manifest.csv') -Encoding UTF8
    $bad = @()
    foreach ($r in $rows) {
        $p = Join-Path $pkg $r.RelativePath
        if (-not (Test-Path -LiteralPath $p)) { $bad += "缺檔：$($r.RelativePath)"; continue }
        if ([int64]$r.Size -ne (Get-Item -LiteralPath $p).Length) { $bad += "大小不符：$($r.RelativePath)"; continue }
        if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne $r.SHA256) { $bad += "SHA256 不符：$($r.RelativePath)" }
    }
    if ($bad.Count -gt 0) {
        Log "【停止】manifest 比對不符 $($bad.Count) 項："
        $bad | ForEach-Object { Log "  $_" }
        Save-Report; exit 3
    }
    Log "1. manifest 比對：$($rows.Count) 個檔，大小與 SHA256 全部相符。"
} else { Log '1. manifest 比對：已略過（-SkipVerify）。' }

# 2. 複製案件程式
$srcCase = Join-Path $pkg $info.case_folder
$CaseDir = [IO.Path]::GetFullPath($CaseDir).TrimEnd('\')
$oldCase = ([string]$info.case_dir).TrimEnd('\')
if ($CheckOnly) {
    Log '2. 複製案件程式：已略過（-CheckOnly）。'
} else {
    if ((Test-Path -LiteralPath $CaseDir) -and @(Get-ChildItem -LiteralPath $CaseDir -Force).Count -gt 0) {
        Log "【停止】本機案件資料夾已有檔案：$CaseDir"
        Log '  不覆蓋。請使用者決定：改用新資料夾，或先把舊資料夾移到 OLD 再重跑。'
        Save-Report; exit 4
    }
    New-Item -ItemType Directory -Force $CaseDir | Out-Null
    & robocopy $srcCase $CaseDir /E /COPY:DAT /R:2 /W:5 /NP /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy 失敗，代碼 $LASTEXITCODE" }
    $n = @(Get-ChildItem -LiteralPath $CaseDir -Recurse -File).Count
    Log "2. 已複製案件程式與中間資料 $n 個檔 → $CaseDir"
}

# 3. case_config.json
$workDir = if ($CheckOnly) { $srcCase } else { $CaseDir }
$cfgPath = Join-Path $workDir 'case_config.json'
$jsonEsc = { param($s) $s.Replace('\', '\\') }
if (Test-Path -LiteralPath $cfgPath) {
    $raw = Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8
    $cfg = $raw | ConvertFrom-Json
    $changes = @()
    $new = $raw
    # 3a. 原案件資料夾 → 本機案件資料夾
    if ($oldCase -and $oldCase -ne $CaseDir -and $new.Contains((& $jsonEsc $oldCase))) {
        $new = $new.Replace((& $jsonEsc $oldCase), (& $jsonEsc $CaseDir)); $changes += "案件路徑 $oldCase → $CaseDir"
    }
    # 3b. out_dir 開頭的路徑 → -OutDir
    if ($OutDir -and $cfg.out_dir) {
        $oldOut = ([string]$cfg.out_dir).TrimEnd('\'); $newOut = [IO.Path]::GetFullPath($OutDir).TrimEnd('\')
        if ($oldOut -ne $newOut) { $new = $new.Replace((& $jsonEsc $oldOut), (& $jsonEsc $newOut)); $changes += "輸出路徑 $oldOut → $newOut（含 preview_dir 等同開頭的路徑）" }
    }
    # 3c. 檔名前綴
    if ($null -ne $cfg.file_prefix -and $cfg.file_prefix -ne $script:Prefix) {
        $new = [regex]::Replace($new, '("file_prefix"\s*:\s*")[^"]*(")', { param($m) $m.Groups[1].Value + $script:Prefix + $m.Groups[2].Value })
        $changes += "file_prefix「$($cfg.file_prefix)」→「$script:Prefix」"
    }
    if ($changes.Count -gt 0 -and -not $CheckOnly) {
        $null = $new | ConvertFrom-Json   # 確認仍是合法 JSON
        Copy-Item -LiteralPath $cfgPath -Destination (Join-Path $CaseDir 'case_config_還原前.json')
        [IO.File]::WriteAllText($cfgPath, $new, $utf8NoBom)
        Log '3. 已改 case_config.json（原檔另存 case_config_還原前.json）：'
    } elseif ($changes.Count -gt 0) { Log '3. case_config.json 需要改（-CheckOnly 未改）：' }
    else { Log '3. case_config.json：路徑與前綴不用改。' }
    $changes | ForEach-Object { Log "   - $_" }
    # 仍指向不存在位置的絕對路徑
    $after = if ($CheckOnly) { $raw } else { $new }
    foreach ($m in [regex]::Matches($after, '"(?<k>[^"]+)"\s*:\s*"(?<v>(?:[A-Za-z]:|\\\\\\\\)[^"]*)"')) {
        $v = $m.Groups['v'].Value.Replace('\\', '\')
        if (-not (Test-Path -LiteralPath $v)) { Log "   【注意】$($m.Groups['k'].Value) 指向本機不存在的路徑：$v（輸出資料夾第一次出圖時建立即可）" }
    }
} else { Log '3. 沒有 case_config.json，略過。' }
# 其他檔案寫死的送件機路徑：只列出
$hits = @()
$pats = @($oldCase, [string]$info.deliverable_dir) | Where-Object { $_ } | ForEach-Object { $_.TrimEnd('\') }
foreach ($f in Get-ChildItem -LiteralPath $workDir -Recurse -File -Include *.py, *.json, *.scr, *.ps1, *.bat | Where-Object { $_.Name -notlike 'case_config*' }) {
    $t = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8
    if ($null -eq $t) { continue }
    foreach ($p in $pats) {
        if ($t.Contains($p) -or $t.Contains($p.Replace('\', '\\')) -or $t.Contains($p.Replace('\', '/'))) { $hits += "$($f.Name)：含 $p"; break }
    }
}
if ($hits.Count -gt 0) { Log '   程式內寫死送件機路徑（未改，請確認）：'; $hits | ForEach-Object { Log "   - $_" } }
Log ''

# 4. 記憶
$memSrc = Get-ChildItem -LiteralPath $pkg -Directory | Where-Object { $_.Name -like '*記憶' } | Select-Object -First 1
Log "4. 記憶：本機 Claude 記憶資料夾 $MemoryDir"
if ($memSrc) {
    foreach ($m in Get-ChildItem -LiteralPath $memSrc.FullName -File) {
        $dst = Join-Path $MemoryDir $m.Name
        $state = if (-not (Test-Path -LiteralPath $dst)) { '本機沒有，可直接複製' }
                 elseif ((Get-FileHash -LiteralPath $dst).Hash -eq (Get-FileHash -LiteralPath $m.FullName).Hash) { '本機已相同' }
                 else { '本機已有不同內容，請合併，不要直接覆蓋' }
        if ($m.Name -eq 'MEMORY.md') { $state = '索引檔：只把本案條目合併進本機 MEMORY.md，不要整份覆蓋' }
        Log "   - $($m.Name)：$state"
    }
    Log '   腳本不複製記憶；由 Claude 依上表處理，或開對話時直接讀工作包的說明檔與記憶檔。'
}
Log ''

# 5. 環境
Log '5. 環境檢查（缺的項目只列安裝指令，不自動安裝；安裝要先問使用者）：'
$missing = @()
# Python：排除 WindowsApps 商店空殼
$py = $null
$cands = @()
$cands += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object FullName
$cands += Get-ChildItem 'C:\Program Files\Python3*\python.exe' -ErrorAction SilentlyContinue | ForEach-Object FullName
$cands += @(Get-Command python -All -ErrorAction SilentlyContinue | ForEach-Object Source)
foreach ($c in $cands) {
    if ($c -like '*\WindowsApps\*') { continue }
    try { $v = & $c -c 'import sys;print(sys.version.split()[0])' 2>$null; if ($LASTEXITCODE -eq 0 -and $v) { $py = $c; break } } catch {}
}
if ($py) {
    Log "   [有] Python $v：$py"
    $code = "import importlib.util as u;print(','.join(m for m in '$($PyPackages -join ',')'.split(',') if u.find_spec(m) is None))"
    $lack = (& $py -I -c $code 2>$null)
    if ($lack) {
        $pipNames = ($lack -split ',' | ForEach-Object { if ($_ -eq 'PIL') { 'Pillow' } else { $_ } }) -join ' '
        Log "   [缺] Python 套件：$lack"
        $missing += "`"$py`" -m pip install --user $pipNames"
    } else { Log "   [有] Python 套件：$($PyPackages -join '、')" }
} else {
    Log '   [缺] Python（只有商店空殼或沒有）'
    $missing += 'winget install -e --id Python.Python.3.12 --scope user'
    $missing += "（裝好後）python -m pip install --user $((($PyPackages | ForEach-Object { if ($_ -eq 'PIL') { 'Pillow' } else { $_ } }) -join ' '))"
}
# accoreconsole
$acc = Get-ChildItem 'C:\Program Files\Autodesk\AutoCAD*\accoreconsole.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
if ($acc) { Log "   [有] accoreconsole：$($acc.FullName)" } else { Log '   [缺] AutoCAD accoreconsole（DWG↔DXF、PUBLISH 要用；沒有就請使用者在有 AutoCAD 的機器轉檔）'; $missing += '安裝 AutoCAD（公司授權，請使用者處理）' }
# Excel
if (Test-Path 'Registry::HKEY_CLASSES_ROOT\Excel.Application') { Log '   [有] Excel（COM 可用）' } else { Log '   [缺] Excel（COM 重算、轉 PDF 要用）'; $missing += '安裝 Microsoft Excel（公司授權，請使用者處理）' }
# GENIE 字型
$fontDirs = @("$env:WINDIR\Fonts", "$env:LOCALAPPDATA\Microsoft\Windows\Fonts") + @(Get-ChildItem 'C:\Program Files\Autodesk\AutoCAD*\Fonts' -Directory -ErrorAction SilentlyContinue | ForEach-Object FullName)
# 字型檔名【待確認】：本 SKILL 以檔名開頭比對（GENIE*、GENISO*，含 .ttf/.shx）
foreach ($fn in @('GENIE', 'GENISO')) {
    $hit = @(foreach ($d in $fontDirs) { Get-ChildItem -LiteralPath $d -Filter "$fn*" -ErrorAction SilentlyContinue | Where-Object { $fn -ne 'GENIE' -or $_.Name -notlike 'GENISO*' } })
    if ($hit.Count -gt 0) { Log "   [有] $fn 字型：$(($hit | ForEach-Object FullName | Select-Object -Unique) -join '、')" }
    else { Log "   [缺] $fn 字型（CAD 出圖用；檔名比對 $fn*，實際檔名【待確認】）"; $missing += "從送件機複製 $fn 字型檔到 AutoCAD Fonts 或 Windows 字型資料夾（請使用者處理）" }
}
# git
$gitName = (git config --global user.name 2>$null); $gitMail = (git config --global user.email 2>$null)
if ($gitName -and $gitMail) { Log "   [有] git 作者身分：$gitName <$gitMail>" }
else {
    Log '   [缺] git 作者身分（commit 會失敗）。單次提交可用 git -c user.name=... -c user.email=... commit'
    $missing += 'git config --global user.name "<名稱>"; git config --global user.email "<信箱>"（要先問使用者，不自行設定）'
}
# gh
if (Get-Command gh -ErrorAction SilentlyContinue) {
    & gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Log '   [有] gh 已登入（push 卡住時先跑 gh auth setup-git）' } else { Log '   [缺] gh 未登入'; $missing += 'gh auth login；gh auth setup-git' }
} else { Log '   [缺] GitHub CLI'; $missing += 'winget install -e --id GitHub.cli' }
# 倉庫分支
if (Test-Path -LiteralPath (Join-Path $RepoDir '.git')) {
    foreach ($r in @($info.repos)) {
        foreach ($b in @($r.branches)) {
            if ($b.branch -in @('main', 'master') -or $b.branch -like 'worktree-*') { continue }
            $remote = git -C $RepoDir ls-remote --heads origin $b.branch 2>$null
            if ($remote) { Log "   [有] 遠端分支 $($b.branch)" } else { Log "   [缺] 遠端沒有分支 $($b.branch)（送件機未推送，這台拿不到）" }
        }
    }
} else { Log "   【注意】找不到 mbmgi 倉庫：$RepoDir（先 gh repo clone）" }
foreach ($g in @($info.git_issues)) { if ($g) { Log "   【送件機打包時】$g" } }
if ($missing.Count -gt 0) { Log ''; Log '   安裝或設定指令（請使用者同意後再執行）：'; $missing | ForEach-Object { Log "   - $_" } }
Log ''

# 6. sync-rules 提醒
Log '6. 要更新全域規則與 SKILL 時，在 mbmgi 倉庫跑 .\sync-rules.ps1。執行前注意：'
Log '   - 會切到 main 並 fast-forward；倉庫有未提交變更會停下。'
Log '   - 只覆蓋全域 CLAUDE.md 的 RULES:BEGIN～END 區段（存 .bak），機器專屬規則（NAS 路徑、檔名前綴）不動。'
Log '   - 會把 skills\ 全部複製到 ~/.claude/skills；跑完要重開 Claude Code。'
Log ''
Log '執行程式提醒：設 PYTHONIOENCODING=utf-8；產生器要 import 同資料夾模組時不加 -I（加了會 ModuleNotFoundError），讀外來檔（NAS、下載）的程式才加 -I。'
Log "新產出的檔名用前綴「$script:Prefix」，存檔時間用 Get-Date。"
Save-Report
exit 0
