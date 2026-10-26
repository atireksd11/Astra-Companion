# Phase 6 contract tests (+ Phase 5 and Phase 0 auth regression).
$ErrorActionPreference = "Stop"
$root = "C:\The XyZ Plan\Astra Companion"
$server = Join-Path $root "server"
$py = "C:\Python314\python.exe"
if (-not (Test-Path $py)) {
    $py = "python"
}
Set-Location $server
& $py -m pytest tests/test_phase6.py tests/test_phase5.py tests/test_phase0_auth.py -q
