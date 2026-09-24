param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot

try {
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object { $_.LocalPort -in @(5173, 8000) })
    foreach ($serviceId in @($listeners.OwningProcess | Select-Object -Unique)) {
        $service = Get-CimInstance Win32_Process -Filter "ProcessId = $serviceId"
        if (-not $service) { continue }

        # Only close servers belonging to this project, even if a port is reused.
        $backendPath = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
        $backendCommand = '^"?' + [regex]::Escape($backendPath) + '"?\s+-m\s+uvicorn\s+app\.main:app(?:\s|$)'
        $isBackend = $service.Name -ieq 'python.exe' -and
            $service.CommandLine -match $backendCommand
        $isFrontend = $false
        if ($service.Name -ieq 'node.exe') {
            foreach ($argument in [regex]::Matches([string]$service.CommandLine, '"([^"]+)"')) {
                $argumentPath = $argument.Groups[1].Value
                if ([IO.Path]::IsPathRooted($argumentPath)) {
                    $normalizedPath = [IO.Path]::GetFullPath($argumentPath)
                    if ($normalizedPath -ieq (Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js')) {
                        $isFrontend = $true
                    }
                }
            }
        }
        if (-not ($isBackend -or $isFrontend)) {
            throw "El proceso $serviceId no se pudo identificar como LiveClip; no se cerro."
        }

        if ($CheckOnly) {
            Write-Host "Proceso $serviceId identificado como LiveClip."
            continue
        }
        if ($isBackend) {
            Write-Host 'Deteniendo la transmision...'
            Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/streams/stop' -TimeoutSec 30 | Out-Null
        }
        # Include any remaining media subprocesses owned by this server.
        & taskkill.exe /PID $serviceId /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "No se pudo cerrar el proceso $serviceId." }
    }
    if ($CheckOnly) {
        Write-Host 'Verificacion completada sin apagar servicios.'
    } else {
        Write-Host 'LiveClip apagado. Puedes cerrar la pestana del navegador.'
    }
    exit 0
} catch {
    Write-Host "No se pudo completar el apagado: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
