# pack_handoff.ps1
# 送件機：把一個案件打包成「Claude 工作包」，給另一台電腦接續。
# PowerShell 5.1 相容。只複製，不移動、不刪除來源檔。
#
# 兩個階段：
#   1. 打包（預設）：檢查 git → 複製記憶、案件程式、最新交付成果 → 產生說明骨架、handoff_info.json、manifest.csv
#      打包完由 Claude 依案件記憶填寫 00_說明_先讀這份.md 的【待填】段落。
#   2. 上傳（-UploadPackage）：重算 manifest → 複製到 NAS → 在 NAS 端重算 SHA256 比對。
#
# 例：
#   .\pack_handoff.ps1 -CaseName 東山街排水 -CaseDir 'D:\Claude_工作區\共用\地形出圖\cases\P33_新社東山' `
#       -DeliverableDir 'D:\Claude_工作區\輸出\P33_新社東山' -OutputDir 'D:\Claude_工作區\輸出\交接包' `
#       -MemoryFiles p33-xinshe-dongshan-ditch.md -NasDest '\\NAS\C2storagecjec\...\01_收資料'
#   （填完說明檔後）
#   .\pack_handoff.ps1 -UploadPackage 'D:\Claude_工作區\輸出\交接包\（桃園）20261105_2120_東山街排水_Claude工作包' -NasDest '\\NAS\...\01_收資料'
#
# 結束代碼：0 成功；2 git 有未提交或未推送（未加 -AllowUnpushed）；3 manifest 比對不符；1 其他錯誤。

[CmdletBinding(DefaultParameterSetName = 'Pack')]
param(
    [Parameter(ParameterSetName = 'Pack', Mandatory = $true)] [string]$CaseName,
    [Parameter(ParameterSetName = 'Pack', Mandatory = $true)] [string]$CaseDir,
    [Parameter(ParameterSetName = 'Pack', Mandatory = $true)] [string]$OutputDir,
    [Parameter(ParameterSetName = 'Pack')] [string]$DeliverableDir,
    [Parameter(ParameterSetName = 'Pack')] [string]$MemoryDir = (Join-Path $env:USERPROFILE '.claude\projects\D--Claude----\memory'),
    [Parameter(ParameterSetName = 'Pack')] [string[]]$MemoryFiles = @(),
    [Parameter(ParameterSetName = 'Pack')] [string[]]$MemoryKeywords = @(),
    [Parameter(ParameterSetName = 'Pack')] [string[]]$ExtraDirs = @(),
    [Parameter(ParameterSetName = 'Pack')] [switch]$IncludeConversation,
    [Parameter(ParameterSetName = 'Pack')] [string]$ConversationPath,
    [Parameter(ParameterSetName = 'Pack')] [string[]]$Repos = @('D:\Claude_工作區\mbmgi'),
    [Parameter(ParameterSetName = 'Pack')] [switch]$AllowUnpushed,
    [Parameter(ParameterSetName = 'Pack')] [string]$MachineLabel,
    [Parameter(ParameterSetName = 'Pack')] [int]$MaxFileMB = 100,
    [Parameter(ParameterSetName = 'Pack')] [string]$TemplatePath,

    [Parameter(ParameterSetName = 'Upload', Mandatory = $true)] [string]$UploadPackage,

    [string]$NasDest
)

$ErrorActionPreference = 'Stop'

function Resolve-Full([string]$p) {
    # 展開 8.3 短檔名（例 ADMINI~1）；否則與 Get-ChildItem 回傳的長檔名長度不同，Substring 算相對路徑會切錯
    $full = (Resolve-Path -LiteralPath $p).ProviderPath
    if ($full -like '*~*' -and $full -notlike '\\*') {
        if (-not ('LongPath.Native' -as [type])) {
            Add-Type -Namespace LongPath -Name Native -MemberDefinition '[DllImport("kernel32.dll", CharSet = CharSet.Unicode)] public static extern uint GetLongPathName(string s, System.Text.StringBuilder l, uint n);'
        }
        $sb = New-Object Text.StringBuilder 1024
        if ([LongPath.Native]::GetLongPathName($full, $sb, 1024) -gt 0) { $full = $sb.ToString() }
    }
    $full
}
$env:GIT_TERMINAL_PROMPT = '0'   # fetch 不跳登入視窗卡住

# 用 powershell -File 呼叫時，a.md,b.md 會變成一整串字串；這裡統一拆開，兩種呼叫方式結果相同。
function Split-List([string[]]$list) { @($list | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ }) }
$MemoryFiles    = Split-List $MemoryFiles
$MemoryKeywords = Split-List $MemoryKeywords
$ExtraDirs      = Split-List $ExtraDirs
$Repos          = Split-List $Repos
$ReadmeName   = '00_說明_先讀這份.md'
$ManifestName = 'manifest.csv'
$InfoName     = 'handoff_info.json'
$utf8NoBom    = New-Object Text.UTF8Encoding($false)

function Write-Utf8([string]$path, [string]$text) { [IO.File]::WriteAllText($path, $text, $utf8NoBom) }

function Get-MachineLabel {
    switch ($env:COMPUTERNAME.ToUpper()) {
        'LLPC-237' { return '（桃園）' }
        'LLPC-48'  { return '(臺中48)' }
        default    { return "（$($env:COMPUTERNAME)）" }
    }
}

# ---------- manifest ----------
function New-Manifest([string]$root) {
    $rootFull = (Resolve-Full $root).TrimEnd('\')
    $rows = foreach ($f in Get-ChildItem -LiteralPath $rootFull -Recurse -File | Sort-Object FullName) {
        if ($f.Name -eq $ManifestName -and $f.DirectoryName.TrimEnd('\') -eq $rootFull) { continue }
        [pscustomobject]@{
            RelativePath = $f.FullName.Substring($rootFull.Length + 1)
            Size         = $f.Length
            SHA256       = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        }
    }
    $rows = @($rows)
    $rows | Export-Csv -LiteralPath (Join-Path $rootFull $ManifestName) -NoTypeInformation -Encoding UTF8
    return $rows
}

function Compare-Manifest([string]$root) {
    # 回傳不符清單（空陣列＝全部相符）
    $rootFull = (Resolve-Full $root).TrimEnd('\')
    $rows = Import-Csv -LiteralPath (Join-Path $rootFull $ManifestName) -Encoding UTF8
    $bad = New-Object System.Collections.Generic.List[string]
    $listed = @{}
    foreach ($r in $rows) {
        $listed[$r.RelativePath] = $true
        $p = Join-Path $rootFull $r.RelativePath
        if (-not (Test-Path -LiteralPath $p)) { $bad.Add("缺檔：$($r.RelativePath)"); continue }
        $f = Get-Item -LiteralPath $p
        if ([int64]$r.Size -ne $f.Length) { $bad.Add("大小不符：$($r.RelativePath)（$($r.Size) → $($f.Length)）"); continue }
        $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
        if ($h -ne $r.SHA256) { $bad.Add("SHA256 不符：$($r.RelativePath)") }
    }
    foreach ($f in Get-ChildItem -LiteralPath $rootFull -Recurse -File) {
        $rel = $f.FullName.Substring($rootFull.Length + 1)
        if ($rel -eq $ManifestName) { continue }
        if (-not $listed.ContainsKey($rel)) { $bad.Add("清單外多出：$rel") }
    }
    return ,$bad.ToArray()
}

# ---------- 上傳階段 ----------
if ($PSCmdlet.ParameterSetName -eq 'Upload') {
    if (-not $NasDest) { throw '上傳要給 -NasDest（NAS 上的上層資料夾）。' }
    $pkg = (Resolve-Full $UploadPackage).TrimEnd('\')
    $readme = Get-Content -LiteralPath (Join-Path $pkg $ReadmeName) -Raw -Encoding UTF8
    if ($readme -match '【待填】') {
        Write-Warning "說明檔仍有【待填】段落，請先由 Claude 依案件記憶填完再上傳。"
        exit 1
    }
    $dst = Join-Path $NasDest (Split-Path $pkg -Leaf)
    if (-not (Test-Path -LiteralPath $NasDest)) { throw "找不到 NAS 上層資料夾：$NasDest（臺中機請用 IP 路徑）" }
    if (Test-Path -LiteralPath $dst) { throw "目的地已存在，不覆蓋：$dst" }
    $rows = New-Manifest $pkg
    Write-Host "已重算 manifest：$($rows.Count) 個檔案。"
    & robocopy $pkg $dst /E /COPY:DAT /R:2 /W:5 /NP /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy 失敗，代碼 $LASTEXITCODE" }
    $bad = Compare-Manifest $dst
    if ($bad.Count -gt 0) {
        Write-Host "NAS 端比對不符 $($bad.Count) 項：" -ForegroundColor Red
        $bad | ForEach-Object { Write-Host "  $_" }
        exit 3
    }
    Write-Host "已上傳並在 NAS 端比對 $($rows.Count) 個檔案，SHA256 全部相符：" -ForegroundColor Green
    Write-Host "  $dst"
    exit 0
}

# ---------- 打包階段 ----------
if (-not $MachineLabel) { $MachineLabel = Get-MachineLabel }
$now      = Get-Date
$stamp    = $now.ToString('yyyyMMdd_HHmm')
$pkgName  = "$MachineLabel${stamp}_${CaseName}_Claude工作包"
$CaseDir  = (Resolve-Full $CaseDir).TrimEnd('\')
if ($DeliverableDir) { $DeliverableDir = (Resolve-Full $DeliverableDir).TrimEnd('\') }
if (-not (Test-Path -LiteralPath $OutputDir)) { New-Item -ItemType Directory -Force $OutputDir | Out-Null }
$OutputDir = (Resolve-Full $OutputDir).TrimEnd('\')
$pkg      = Join-Path $OutputDir $pkgName
if (Test-Path -LiteralPath $pkg) { throw "打包資料夾已存在，不覆蓋：$pkg" }
$log      = New-Object System.Collections.Generic.List[string]
function Log([string]$s) { $log.Add($s); Write-Host $s }

Log "打包：$pkgName"
Log "機器：$($env:COMPUTERNAME)　時間：$($now.ToString('yyyy-MM-dd HH:mm'))"

# 1. git 檢查
$gitBlock = New-Object System.Collections.Generic.List[string]
$repoInfo = @()
foreach ($repo in $Repos) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) { Log "【略過】不是 git 倉庫：$repo"; continue }
    git -C $repo fetch --all --quiet 2>$null
    $wts = @()
    $cur = $null
    foreach ($line in (git -C $repo worktree list --porcelain)) {
        if ($line -like 'worktree *') { $cur = @{ path = $line.Substring(9); branch = '' }; $wts += $cur }
        elseif ($line -like 'branch *' -and $cur) { $cur.branch = $line.Substring(7) -replace '^refs/heads/', '' }
    }
    foreach ($w in $wts) {
        if (-not (Test-Path -LiteralPath $w.path)) { continue }
        # .claude/worktrees 是 Claude 的工作樹資料夾，不算未提交
        $dirty = @(git -C $w.path status --porcelain -- . ':(exclude).claude/worktrees')
        if ($dirty.Count -gt 0) {
            $gitBlock.Add("未提交：$($w.path)（分支 $($w.branch)，$($dirty.Count) 個檔）")
            $dirty | Select-Object -First 10 | ForEach-Object { $gitBlock.Add("    $_") }
        }
    }
    $heads = @()
    foreach ($b in (git -C $repo for-each-ref --format='%(refname:short)' refs/heads)) {
        $n = [int](git -C $repo rev-list --count $b --not --remotes)
        $up = (git -C $repo for-each-ref --format='%(upstream:short)' "refs/heads/$b")
        if ($n -gt 0) { $gitBlock.Add("未推送：$repo 分支 $b（$n 個提交不在任何遠端）") }
        $heads += [pscustomobject]@{ branch = $b; upstream = $up; unpushed = $n; sha = (git -C $repo rev-parse --short $b) }
    }
    $main = $wts | Select-Object -First 1
    $repoInfo += [pscustomobject]@{
        path    = $repo
        remote  = (git -C $repo remote get-url origin 2>$null)
        current = $main.branch
        branches = $heads
    }
}
if ($gitBlock.Count -gt 0) {
    Log ''
    Log 'git 檢查：有未提交或未推送的變更，收件機會拿不到：'
    $gitBlock | ForEach-Object { Log "  $_" }
    if (-not $AllowUnpushed) {
        Log ''
        Log '已停止打包。請使用者決定：提交並推送後重跑，或確認不需要後加 -AllowUnpushed 重跑。腳本不會自動提交。'
        exit 2
    }
    Log '已加 -AllowUnpushed，照常打包；說明檔會列出上述項目。'
} else {
    Log 'git 檢查：所有分支都已提交並推送。'
}

New-Item -ItemType Directory -Force $pkg | Out-Null
$folders = @()   # 資料夾對照表
$skipped = New-Object System.Collections.Generic.List[string]

function Test-Excluded([IO.FileInfo]$f, [string]$root) {
    $rel = $f.FullName.Substring($root.Length + 1)
    foreach ($part in ($rel -split '\\')) {
        if ($part -in @('__pycache__', '.git', '.ipynb_checkpoints', 'OLD', '_作廢', '暫存', 'tmp', 'temp')) { return '排除資料夾' }
    }
    if ($f.Name -like '*_bak_*' -or $f.Extension -in @('.pyc', '.bak', '.tmp')) { return '備份或暫存檔' }
    if ($f.Name -like '~$*') { return 'Office 暫存檔' }
    if ($f.Length -gt $MaxFileMB * 1MB) { return "大於 $MaxFileMB MB" }
    return $null
}

function Copy-Tree([string]$src, [string]$dst) {
    $n = 0
    foreach ($f in Get-ChildItem -LiteralPath $src -Recurse -File) {
        $why = Test-Excluded $f $src
        $rel = $f.FullName.Substring($src.Length + 1)
        if ($why) { $skipped.Add("$rel（$why）"); continue }
        $t = Join-Path $dst $rel
        New-Item -ItemType Directory -Force (Split-Path $t -Parent) | Out-Null
        Copy-Item -LiteralPath $f.FullName -Destination $t
        $n++
    }
    return $n
}

# 2. 對話紀錄
$idx = 1
if ($IncludeConversation) {
    $d = Join-Path $pkg ('{0:00}_對話紀錄' -f $idx); New-Item -ItemType Directory -Force $d | Out-Null
    if ($ConversationPath -and (Test-Path -LiteralPath $ConversationPath)) {
        Copy-Item -LiteralPath $ConversationPath -Destination $d
        Log "對話紀錄：$(Split-Path $ConversationPath -Leaf)"
        $folders += [pscustomobject]@{ name = (Split-Path $d -Leaf); content = '對話匯出'; source = $ConversationPath }
    } else {
        Write-Utf8 (Join-Path $d '請把對話匯出檔放這裡.txt') "Claude 桌面版：設定 → 匯出對話，把 zip 放進本資料夾後，再跑上傳階段（會重算 manifest）。"
        Log '對話紀錄：未提供 -ConversationPath，已放提示檔，請手動匯出後放入。'
        $folders += [pscustomobject]@{ name = (Split-Path $d -Leaf); content = '對話匯出（手動放入）'; source = 'Claude 桌面版匯出' }
    }
}
$idx = 2

# 3. 記憶
$memDst = Join-Path $pkg ('{0:00}_記憶' -f $idx); New-Item -ItemType Directory -Force $memDst | Out-Null
$memPicked = @()
if (Test-Path -LiteralPath $MemoryDir) {
    foreach ($m in Get-ChildItem -LiteralPath $MemoryDir -File -Filter *.md) {
        $take = $false
        if ($m.Name -eq 'MEMORY.md') { $take = $true }
        elseif ($MemoryFiles -contains $m.Name -or $MemoryFiles -contains $m.BaseName) { $take = $true }
        elseif ($MemoryKeywords.Count -gt 0) {
            $txt = Get-Content -LiteralPath $m.FullName -Raw -Encoding UTF8
            foreach ($k in $MemoryKeywords) { if ($m.Name -like "*$k*" -or $txt -like "*$k*") { $take = $true; break } }
        }
        if ($take) { Copy-Item -LiteralPath $m.FullName -Destination $memDst; $memPicked += $m.Name }
    }
    $missing = @($MemoryFiles | Where-Object { $_ -notin $memPicked -and "$_.md" -notin $memPicked })
    if ($missing.Count -gt 0) { Log "【注意】記憶資料夾找不到：$($missing -join '、')" }
} else { Log "【注意】找不到記憶資料夾：$MemoryDir" }
Log "記憶：$($memPicked.Count) 份（$($memPicked -join '、')）"
$folders += [pscustomobject]@{ name = (Split-Path $memDst -Leaf); content = "本案記憶與 MEMORY.md 索引（$($memPicked.Count) 份）"; source = $MemoryDir }
$idx++

# 4. 案件程式與中間資料
$caseDst = Join-Path $pkg ('{0:00}_案件程式與中間資料' -f $idx); New-Item -ItemType Directory -Force $caseDst | Out-Null
$n = Copy-Tree $CaseDir $caseDst
Log "案件程式與中間資料：$n 個檔"
$folders += [pscustomobject]@{ name = (Split-Path $caseDst -Leaf); content = '程式、設定檔、測量圖、TIN、定線、csv'; source = $CaseDir }
$idx++

# 5. 交付成果（每組取最新版次）
$delivPicked = @()
if ($DeliverableDir) {
    $delDst = Join-Path $pkg ('{0:00}_交付成果' -f $idx); New-Item -ItemType Directory -Force $delDst | Out-Null
    $rx = '^(?<pfx>[（(][^）)]*[）)])?(?<ts>\d{8}_\d{4})_(?<rest>.+)$'
    $groups = @{}
    foreach ($f in Get-ChildItem -LiteralPath $DeliverableDir -Recurse -File) {
        $why = Test-Excluded $f $DeliverableDir
        $rel = $f.FullName.Substring($DeliverableDir.Length + 1)
        if ($why) { $skipped.Add("交付成果\$rel（$why）"); continue }
        $m = [regex]::Match($f.Name, $rx)
        if (-not $m.Success) { $groups["$($f.FullName)"] = @(@{ f = $f; ver = [version]'0.0'; ts = '' }); continue }
        $rest = $m.Groups['rest'].Value
        $vm = [regex]::Match($rest, '_v(\d+(?:\.\d+){0,3})(?=[_.])')
        $ver = [version]'0.0'
        if ($vm.Success) { $v = $vm.Groups[1].Value; if ($v -notmatch '\.') { $v += '.0' }; $ver = [version]$v; $rest = $rest.Remove($vm.Index, $vm.Length).Insert($vm.Index, '_v*') }
        $key = "$($f.DirectoryName)|$rest"
        if (-not $groups.ContainsKey($key)) { $groups[$key] = @() }
        $groups[$key] += @{ f = $f; ver = $ver; ts = $m.Groups['ts'].Value }
    }
    $older = 0
    foreach ($k in $groups.Keys) {
        $best = $groups[$k] | Sort-Object @{ e = { $_.ver } }, @{ e = { $_.ts } } | Select-Object -Last 1
        $older += $groups[$k].Count - 1
        $rel = $best.f.FullName.Substring($DeliverableDir.Length + 1)
        $t = Join-Path $delDst $rel
        New-Item -ItemType Directory -Force (Split-Path $t -Parent) | Out-Null
        Copy-Item -LiteralPath $best.f.FullName -Destination $t
        $delivPicked += $rel
    }
    $delivPicked = @($delivPicked | Sort-Object)
    Log "交付成果：取最新 $($delivPicked.Count) 個檔，略過舊版 $older 個"
    $folders += [pscustomobject]@{ name = (Split-Path $delDst -Leaf); content = '最新版交付成果（每組依版次、存檔時間取最新）'; source = $DeliverableDir }
    $idx++
}

# 6. 其他資料夾
foreach ($x in $ExtraDirs) {
    $xs = (Resolve-Full $x).TrimEnd('\')
    $xd = Join-Path $pkg ('{0:00}_{1}' -f $idx, (Split-Path $xs -Leaf)); New-Item -ItemType Directory -Force $xd | Out-Null
    $n = Copy-Tree $xs $xd
    Log "其他：$(Split-Path $xd -Leaf) $n 個檔"
    $folders += [pscustomobject]@{ name = (Split-Path $xd -Leaf); content = '【待填】'; source = $xs }
    $idx++
}
if ($skipped.Count -gt 0) { Log "排除 $($skipped.Count) 個檔（__pycache__、*_bak_*、暫存、過大等），清單見打包報告。" }

# 7. handoff_info.json（給 restore_handoff.ps1 讀）
$info = [ordered]@{
    case_name     = $CaseName
    machine       = $env:COMPUTERNAME
    machine_label = $MachineLabel
    packed_at     = $now.ToString('yyyy-MM-dd HH:mm')
    case_dir      = $CaseDir
    case_folder   = (Split-Path $caseDst -Leaf)
    deliverable_dir = $DeliverableDir
    memory_dir    = $MemoryDir
    memory_files  = $memPicked
    nas_dest      = $NasDest
    folders       = $folders
    repos         = $repoInfo
    git_issues    = @($gitBlock)
}
Write-Utf8 (Join-Path $pkg $InfoName) ($info | ConvertTo-Json -Depth 6)

# 8. 說明骨架
if (-not $TemplatePath) { $TemplatePath = Join-Path (Split-Path -Parent $PSScriptRoot) 'templates\handoff_readme.template.md' }
$tpl = Get-Content -LiteralPath $TemplatePath -Raw -Encoding UTF8
$tbl = ($folders | ForEach-Object { "| $($_.name) | $($_.content) | ``$($_.source)`` |" }) -join "`r`n"
$deliv = if ($delivPicked.Count -gt 0) { ($delivPicked | ForEach-Object { "- ``$_``" }) -join "`r`n" } else { '（未打包交付成果）' }
$gitTxt = if ($gitBlock.Count -gt 0) { "打包時仍有下列未提交或未推送項目（使用者已同意照常打包），收件機拿不到：`r`n`r`n" + (($gitBlock | ForEach-Object { "- $_" }) -join "`r`n") } else { '打包時所有相關倉庫都已提交並推送。' }
$repoTxt = ($repoInfo | ForEach-Object { "- ``$($_.path)``：目前分支 ``$($_.current)``（$($_.remote)）" }) -join "`r`n"
$readme = $tpl.Replace('{{CASE_NAME}}', $CaseName).
    Replace('{{PACKED_AT}}', $now.ToString('yyyy-MM-dd HH:mm')).
    Replace('{{MACHINE}}', "$MachineLabel $($env:COMPUTERNAME)").
    Replace('{{PACKAGE_NAME}}', $pkgName).
    Replace('{{FOLDER_TABLE}}', $tbl).
    Replace('{{DELIVERABLES}}', $deliv).
    Replace('{{GIT_STATUS}}', $gitTxt).
    Replace('{{REPOS}}', $repoTxt).
    Replace('{{CASE_DIR}}', $CaseDir).
    Replace('{{CASE_FOLDER}}', (Split-Path $caseDst -Leaf)).
    Replace('{{MEMORY_DIR}}', $MemoryDir)
Write-Utf8 (Join-Path $pkg $ReadmeName) $readme

# 9. manifest
$rows = New-Manifest $pkg
$total = ($rows | Measure-Object Size -Sum).Sum
Log ("manifest：{0} 個檔，共 {1:N1} MB" -f $rows.Count, ($total / 1MB))

# 打包報告放在工作包外面（不影響 manifest）
$report = Join-Path $OutputDir "$pkgName`_打包報告.txt"
$all = @($log) + @('', '排除的檔案：') + @($skipped | ForEach-Object { "  $_" }) + @('', '交付成果（最新版）：') + @($delivPicked | ForEach-Object { "  $_" })
Write-Utf8 $report ($all -join "`r`n")
Write-Host ''
Write-Host "已打包：$pkg" -ForegroundColor Green
Write-Host "打包報告：$report"
Write-Host "下一步：由 Claude 依案件記憶填寫 $ReadmeName 的【待填】段落，再跑 -UploadPackage 上傳到 NAS 並比對。"
exit 0
