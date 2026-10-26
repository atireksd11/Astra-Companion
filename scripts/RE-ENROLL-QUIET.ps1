# Wipe owner profile, restart bridge, run enrollment (use in a quiet room).
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

& (Join-Path $PSScriptRoot "reset-owner.ps1")
Start-Sleep -Seconds 2
Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "bridge.py" -WorkingDirectory (Join-Path $Root "server") -WindowStyle Minimized
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "=== Quiet enrollment ==="
Write-Host "Speak each line clearly, press Enter after each one."
Write-Host ""
Set-Location (Join-Path $Root "server")
C:\Python314\python.exe tools\enroll_owner.py

Write-Host ""
Write-Host "=== Next: test you ==="
Write-Host "  C:\Python314\python.exe laptop_voice.py --noisy"
Write-Host "  Hey Jarvis -> your sentence -> Enter"
Write-Host ""
Write-Host "=== Then: noise + friend ==="
Write-Host "  Same client; add background chatter; you talk again."
Write-Host "  Friend tries Hey Jarvis + sentence -> should NOT echo."
Write-Host ""
