# Open the rebar-check workbook in Excel, recalc, save, export PDF; dump columns A-D,F of sheet 1 to a UTF-8 txt for checking.
# Usage: rebar_check_pdf.ps1 -xlsx <full path> [-dumpdir <dir for the check txt; default %TEMP%>]
param([string]$xlsx, [string]$dumpdir = $env:TEMP)
$xlsx = (Resolve-Path -LiteralPath $xlsx).ProviderPath
$pdf = [System.IO.Path]::ChangeExtension($xlsx, ".pdf")
$txt = Join-Path $dumpdir ([System.IO.Path]::GetFileNameWithoutExtension($xlsx) + ".values.txt")
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($xlsx)
  $xl.CalculateFull()
  $ws = $wb.Worksheets.Item(1)
  $n = $ws.UsedRange.Rows.Count
  $lines = @()
  for ($r = 2; $r -le $n; $r++) {
    $lines += ("{0}`t{1}`t{2}`t{3}`t{4}" -f $ws.Cells.Item($r,1).Text, $ws.Cells.Item($r,2).Text, $ws.Cells.Item($r,3).Text, $ws.Cells.Item($r,4).Text, $ws.Cells.Item($r,6).Text)
  }
  $lines | Out-File -Encoding utf8 $txt
  $wb.Save()
  $wb.ExportAsFixedFormat(0, $pdf)
  $wb.Close($false)
} finally { $xl.Quit(); [System.Runtime.Interopservices.Marshal]::ReleaseComObject($xl) | Out-Null }
$bad = $lines | Select-String -Pattern '###|#VALUE!|#REF!|#DIV/0!|#NAME\?|#N/A|#NUM!|#NULL!'
"PDF: $pdf"
"Values: $txt"
"Overflow/error cells: " + @($bad).Count
