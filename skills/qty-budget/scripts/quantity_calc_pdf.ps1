# Open workbook in Excel, full recalc, save, export PDF (all sheets), dump cell text to a UTF-8 txt and scan it for ### / error values.
# Usage: quantity_calc_pdf.ps1 -xlsx <full path> [-dumpdir <dir for the check txt; default %TEMP%>]
# The check txt is NOT written to the delivery folder (keep check files out of it).
param([string]$xlsx, [string]$dumpdir = $env:TEMP)
$xlsx = (Resolve-Path -LiteralPath $xlsx).ProviderPath      # literal path: names with ( ) [ ] and CJK go to COM as-is
$pdf = [System.IO.Path]::ChangeExtension($xlsx, ".pdf")
$txt = Join-Path $dumpdir ([System.IO.Path]::GetFileNameWithoutExtension($xlsx) + ".values.txt")
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($xlsx)
  $xl.CalculateFull()
  $lines = @()
  foreach ($ws in $wb.Worksheets) {
    $lines += "===== " + $ws.Name
    $ur = $ws.UsedRange
    for ($r = 1; $r -le $ur.Rows.Count; $r++) {
      $vals = @()
      for ($c = 1; $c -le $ur.Columns.Count; $c++) { $vals += $ws.Cells.Item($r, $c).Text }
      $lines += ($vals -join "`t")
    }
  }
  $lines | Out-File -Encoding utf8 $txt
  $wb.Save()
  $wb.ExportAsFixedFormat(0, $pdf)
  $wb.Close($false)
} finally { $xl.Quit(); [System.Runtime.Interopservices.Marshal]::ReleaseComObject($xl) | Out-Null }
# Cell .Text shows ### when the column is too narrow for the recalculated value; scan after recalc, not before.
$bad = $lines | Select-String -Pattern '###|#VALUE!|#REF!|#DIV/0!|#NAME\?|#N/A|#NUM!|#NULL!'
"PDF: $pdf"
"Values: $txt"
"Overflow/error cells: " + @($bad).Count
$bad | Select-Object -First 20 | ForEach-Object { "  " + $_.Line }
