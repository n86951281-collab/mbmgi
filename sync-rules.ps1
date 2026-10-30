# sync-rules.ps1
# 把 GitHub 上的規則正本（本倉庫的 CLAUDE.md）同步到這台電腦的全域 CLAUDE.md。
#
# 用法：在本倉庫資料夾裡執行
#     .\sync-rules.ps1
#
# 它只會覆蓋全域 CLAUDE.md 裡 RULES:BEGIN 與 RULES:END 之間的內容，
# 標記以外的機器專屬規則（NAS 路徑、檔名前綴等）不動。
# 覆蓋前會存一份 CLAUDE.md.bak。

$ErrorActionPreference = 'Stop'

$repo   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$target = Join-Path $env:USERPROFILE '.claude\CLAUDE.md'
$begin  = '<!-- RULES:BEGIN 以下由 sync-rules.ps1 從 GitHub 同步，請勿手改 -->'
$end    = '<!-- RULES:END -->'

Write-Host "倉庫：$repo"
Write-Host "目標：$target"
Write-Host ""

# 1. 取得最新的正本
$dirty = git -C $repo status --porcelain
if ($dirty) {
    throw "倉庫裡有未提交的變更，請先處理再同步：`n$dirty"
}
Write-Host "正在取得最新規則..."
git -C $repo fetch origin main --quiet
git -C $repo checkout main --quiet
git -C $repo merge --ff-only origin/main --quiet
$sha = git -C $repo rev-parse --short HEAD
Write-Host "規則版本：$sha"

$rules = Get-Content (Join-Path $repo 'CLAUDE.md') -Raw -Encoding UTF8

# 2. 找出全域檔裡的標記
if (-not (Test-Path $target)) {
    throw "找不到 $target 。請先建立全域 CLAUDE.md，並在裡面放這兩行標記：`n$begin`n$end"
}
$doc = Get-Content $target -Raw -Encoding UTF8
$i = $doc.IndexOf($begin)
$j = $doc.IndexOf($end)
if ($i -lt 0 -or $j -lt 0) {
    throw "全域 CLAUDE.md 裡找不到標記。請在檔案最後加上這兩行，中間留白：`n$begin`n$end"
}
if ($j -lt $i) {
    throw "標記順序顛倒：RULES:END 出現在 RULES:BEGIN 之前。"
}

# 3. 置換標記之間的內容
$head = $doc.Substring(0, $i + $begin.Length)
$tail = $doc.Substring($j)
$new  = $head + "`r`n`r`n" + $rules.Trim() + "`r`n`r`n" + $tail

if ($new -eq $doc) {
    Write-Host ""
    Write-Host "規則沒有變動，不需要更新。" -ForegroundColor Green
    exit 0
}

Copy-Item $target "$target.bak" -Force
[IO.File]::WriteAllText($target, $new, (New-Object Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "已更新全域 CLAUDE.md（$sha）。" -ForegroundColor Green
Write-Host "原檔備份：$target.bak"
Write-Host "請重新開啟 Claude Code，新規則才會生效。"
