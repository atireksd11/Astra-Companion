# Wipes voice profiles so the next Hey Jarvis enrolls you as owner.
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Db = Join-Path $Root "server\astra.db"

Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { taskkill /PID $_ /F 2>$null }

Start-Sleep -Seconds 1
if (Test-Path $Db) {
    $bak = "$Db.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Move-Item $Db $bak -Force
    Write-Host "Backed up to $bak"
}
Write-Host "Owner cleared. Start bridge:  cd `"$Root`"; C:\Python314\python.exe bridge.py"
Write-Host "Then:  .\scripts\YOU-TEST-VOICE.ps1"
