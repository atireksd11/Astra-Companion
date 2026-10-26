# Vision end-to-end test (image + test tone). Starts bridge if port 8765 is free.
param(
    [string]$Image = "C:\Users\atire\Downloads\Me\myimage.jpeg"
)
$ErrorActionPreference = "Stop"
$root = "C:\The XyZ Plan\Astra Companion"
$server = Join-Path $root "server"
$py = "C:\Python314\python.exe"
if (-not (Test-Path $Image)) {
    Write-Host "Image not found: $Image"
    exit 1
}
$on8765 = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if (-not $on8765) {
    Write-Host "Starting bridge (wait for stt ready)..."
    Start-Process -FilePath $py -ArgumentList "bridge.py" -WorkingDirectory $server
    Start-Sleep -Seconds 45
}
Set-Location $server
& $py tools\make_test_wav.py tools\test-tone.wav | Out-Null
& $py tools\vision_smoke.py $Image
