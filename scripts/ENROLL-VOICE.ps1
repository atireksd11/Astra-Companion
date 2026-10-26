$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location (Join-Path $Root "server")
Write-Host "Owner enrollment: speak each line, press Enter when done."
Write-Host ""
C:\Python314\python.exe tools\enroll_owner.py
