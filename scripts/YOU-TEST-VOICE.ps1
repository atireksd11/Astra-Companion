param([switch]$Fresh)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

if ($Fresh) {
    & (Join-Path $PSScriptRoot "reset-owner.ps1")
    Start-Sleep -Seconds 2
    Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "bridge.py" -WorkingDirectory (Join-Path $Root "server") -WindowStyle Minimized
    Start-Sleep -Seconds 3
    Write-Host "Run enrollment first:  .\scripts\ENROLL-VOICE.ps1`n"
    exit 0
}

$open = $false
try {
    $c = New-Object System.Net.Sockets.TcpClient
    $c.Connect("127.0.0.1", 8765)
    $open = $true
    $c.Close()
} catch {}
if (-not $open) {
    Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "bridge.py" -WorkingDirectory (Join-Path $Root "server") -WindowStyle Minimized
    Start-Sleep -Seconds 3
}

Write-Host @"

1) If you never enrolled:  .\scripts\ENROLL-VOICE.ps1
2) Hey Jarvis -> your sentence -> Enter
3) Hear echo = pass

"@
C:\Python314\python.exe laptop_voice.py --noisy
