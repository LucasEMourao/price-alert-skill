$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\sender_worker.py"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir ("sender-" + (Get-Date -Format "yyyy-MM-dd") + ".log")
$stopRequestFile = Join-Path $root "data\sender_stop.request"
$restartDelaySeconds = 60
$arguments = @(
    "-u"
    $script
    "--continuous"
)

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $python)) {
    throw "Python da venv nao encontrado em: $python"
}

Push-Location $root
try {
    while ($true) {
        if (Test-Path $stopRequestFile) {
            Remove-Item $stopRequestFile -Force -ErrorAction SilentlyContinue
            exit 0
        }

        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & $python @arguments *>> $logFile
            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }

        if (Test-Path $stopRequestFile) {
            Remove-Item $stopRequestFile -Force -ErrorAction SilentlyContinue
            exit 0
        }

        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        if ($exitCode -eq 0) {
            "[$timestamp] Sender worker exited cleanly. Restarting in $restartDelaySeconds seconds..." | Out-File -FilePath $logFile -Append
        }
        else {
            "[$timestamp] Sender worker exited with code $exitCode. Retrying in $restartDelaySeconds seconds..." | Out-File -FilePath $logFile -Append
        }

        Start-Sleep -Seconds $restartDelaySeconds
    }
}
catch {
    $_ | Out-File -FilePath $logFile -Append
    exit 1
}
finally {
    Pop-Location
}
