# Mantiene la app viva: si Streamlit se cae (o se queda colgado), lo reinicia.
# Pensado para correr oculto desde el Programador de tareas (keep_alive.vbs).
# Manual:  powershell -ExecutionPolicy Bypass -File keep_alive.ps1

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$port = 8501
$log = Join-Path $PSScriptRoot "watchdog.log"

function Write-Log([string]$msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Write-Host $line
    try { Add-Content -Path $log -Value $line -Encoding utf8 } catch { }
}

function Test-AppPort {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(1000)) { return $false }
        $client.EndConnect($iar)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-AppHealth {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/_stcore/health" -TimeoutSec 5
        return ($r.StatusCode -eq 200 -and $r.Content -match "ok")
    } catch {
        return $false
    }
}

function Get-PortOwner {
    try {
        $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
            Select-Object -First 1
        return $c.OwningProcess
    } catch {
        return $null
    }
}

# Evita dos vigilantes a la vez.
$mutex = New-Object System.Threading.Mutex($false, "Global\MomentumGuardWatchdog")
try {
    if (-not $mutex.WaitOne(0)) {
        Write-Log "Ya hay otro vigilante activo; salgo."
        exit 0
    }
} catch {
    # Si no se puede crear el mutex, seguimos igual.
}

$out = Join-Path $PSScriptRoot "streamlit.out.log"
$err = Join-Path $PSScriptRoot "streamlit.err.log"

Write-Log "vigilante iniciado (pid $PID)"

while ($true) {
    if (Test-AppPort) {
        # Ya hay algo escuchando (app levantada a mano o por nosotros).
        Start-Sleep -Seconds 10
        continue
    }

    Write-Log "puerto $port libre: iniciando Streamlit..."
    try {
        $proc = Start-Process -FilePath "python" `
            -ArgumentList "-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "$port", "--browser.gatherUsageStats", "false" `
            -WorkingDirectory $PSScriptRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $out `
            -RedirectStandardError $err `
            -PassThru
        Write-Log "pid $($proc.Id) -> http://localhost:$port"

        # Mientras vive, chequeamos que responda; si se cuelga 3 veces, lo matamos.
        $strikes = 0
        while (-not $proc.HasExited) {
            Start-Sleep -Seconds 5
            if ($proc.HasExited) { break }
            if (Test-AppHealth) {
                $strikes = 0
            } else {
                $strikes++
                if ($strikes -ge 3) {
                    Write-Log "la app no responde al health check; la reinicio"
                    try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch { }
                    break
                }
            }
        }
        try { $proc.WaitForExit(5000) | Out-Null } catch { }
        Write-Log "el proceso termino; reinicio en 3s..."
    } catch {
        Write-Log "error al iniciar ($($_.Exception.Message)); reintento en 10s..."
        Start-Sleep -Seconds 10
    }
    Start-Sleep -Seconds 3
}
