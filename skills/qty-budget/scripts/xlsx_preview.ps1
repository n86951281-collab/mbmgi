# Export the first N rows of each sheet as PNG via Excel CopyPicture, for visual layout check (sheet1.png, sheet2.png ...).
# Usage: xlsx_preview.ps1 -xlsx <full path> -outdir <scratch dir, not the delivery folder> [-rows 18] [-delay 1500]
# Activate the sheet first, then wait before Paste; without the delay the chart pastes empty and the PNG comes out blank.
param([string]$xlsx, [string]$outdir, [int]$rows = 18, [int]$delay = 1500)
$xlsx = (Resolve-Path -LiteralPath $xlsx).ProviderPath
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($xlsx)
  $i = 0
  foreach ($ws in $wb.Worksheets) {
    $i++; $ws.Activate()
    $ur = $ws.UsedRange
    $last = [Math]::Min($rows, $ur.Rows.Count)
    $rng = $ws.Range($ws.Cells.Item(1, 1), $ws.Cells.Item($last, $ur.Columns.Count))
    $rng.CopyPicture(1, 2) | Out-Null
    $co = $ws.ChartObjects().Add(0, 0, $rng.Width, $rng.Height)
    Start-Sleep -Milliseconds $delay
    $co.Chart.Paste() | Out-Null
    $co.Chart.Export((Join-Path $outdir ("sheet$i.png"))) | Out-Null
    $co.Delete()
  }
  $wb.Close($false)
} finally { $xl.Quit(); [System.Runtime.Interopservices.Marshal]::ReleaseComObject($xl) | Out-Null }
"done"
