# DWG -> DXF via AutoCAD accoreconsole (DXFOUT), with timeout.
# Source DWG is only read: it is copied to an ASCII-only work folder first.
# This file is ASCII only on purpose (Windows PowerShell 5.1 reads BOM-less .ps1 as ANSI).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File run_dxfout.ps1 -Dwg <source.dwg> -OutDxf <dest.dxf> [-Work D:\cadtmp\v2] [-TimeoutSec 180] [-Version 2018]
# -Dwg / -OutDxf may contain Chinese; -Work must be ASCII only (no "~").
param(
  [Parameter(Mandatory = $true)][string]$Dwg,
  [Parameter(Mandatory = $true)][string]$OutDxf,
  [string]$Work = "D:\cadtmp\dxfout",
  [int]$TimeoutSec = 180,
  [string]$Version = "2018",
  [string]$Acc = "C:\Program Files\Autodesk\AutoCAD 2022\accoreconsole.exe",
  [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
)
$ErrorActionPreference = "Stop"
$Work = [IO.Path]::GetFullPath($Work)
if ($Work -match '[^\x20-\x7E]' -or $Work.Contains('~')) { throw "Work folder must be ASCII only, no '~': $Work" }
if (-not (Test-Path -LiteralPath $Dwg)) { throw "DWG not found: $Dwg" }
if (-not (Test-Path -LiteralPath $Acc)) { throw "accoreconsole not found: $Acc" }
New-Item -ItemType Directory -Force -Path $Work | Out-Null

$src = Join-Path $Work "src.dwg"
$tmpDxf = Join-Path $Work "src.dxf"
$scr = Join-Path $Work "dxfout.scr"
Copy-Item -LiteralPath $Dwg -Destination $src -Force
if (Test-Path -LiteralPath $tmpDxf) { Remove-Item -LiteralPath $tmpDxf -Force -Confirm:$false }

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONIOENCODING = "utf-8"
& $Python -I (Join-Path $here "make_dxfout_scr.py") $tmpDxf $scr --version $Version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "make_dxfout_scr.py failed" }

$p = Start-Process -FilePath $Acc -ArgumentList @('/i', "`"$src`"", '/s', "`"$scr`"", '/l', 'zh-TW') -PassThru -WindowStyle Hidden
if (-not $p.WaitForExit($TimeoutSec * 1000)) {
  try { $p.Kill() } catch {}
  Get-Process accoreconsole -ErrorAction SilentlyContinue | Where-Object { $_.Id -eq $p.Id } | Stop-Process -Force -Confirm:$false
  throw "accoreconsole timed out after $TimeoutSec s (killed). Check paths are ASCII and the DWG opens without prompts."
}
if (-not (Test-Path -LiteralPath $tmpDxf)) { throw "DXFOUT produced no file (exit $($p.ExitCode))" }

$destDir = Split-Path -Parent $OutDxf
if ($destDir) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
Copy-Item -LiteralPath $tmpDxf -Destination $OutDxf -Force
$len = (Get-Item -LiteralPath $OutDxf).Length
Write-Output "OK $len bytes -> $OutDxf"
