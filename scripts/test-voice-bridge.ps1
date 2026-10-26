# Quick check: bridge echo test (starts bridge only if port 8765 is free)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Server = Join-Path $Root "server"
Set-Location $Server

python tools/make_test_wav.py tools/test-tone.wav

$listening = $false
try {
    $c = New-Object System.Net.Sockets.TcpClient
    $c.Connect("127.0.0.1", 8765)
    $listening = $true
    $c.Close()
} catch {}

if (-not $listening) {
    Write-Host "Starting bridge in background..."
    Start-Process -FilePath "python" -ArgumentList "bridge.py" -WorkingDirectory $Server -WindowStyle Normal
    Start-Sleep -Seconds 2
}

python tools/sim_robot.py tools/test-tone.wav
python tools/report.py
