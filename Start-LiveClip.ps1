$projectRoot = $PSScriptRoot
$backend = Join-Path $projectRoot 'scripts\start-backend.ps1'
$frontend = Join-Path $projectRoot 'scripts\start-frontend.ps1'
function Test-LocalService([string]$address) {
    try { return (Invoke-WebRequest -UseBasicParsing -Uri $address -TimeoutSec 2).StatusCode -eq 200 }
    catch { return $false }
}
if (-not (Test-LocalService 'http://127.0.0.1:8000/health')) {
    Start-Process powershell -WindowStyle Hidden -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $backend + '"'))
}
if (-not (Test-LocalService 'http://127.0.0.1:5173')) {
    Start-Process powershell -WindowStyle Hidden -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $frontend + '"'))
}
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if ((Test-LocalService 'http://127.0.0.1:8000/health') -and (Test-LocalService 'http://127.0.0.1:5173')) { break }
    Start-Sleep -Seconds 1
}
Start-Process 'http://127.0.0.1:5173'
