$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\sender_worker.py"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir ("sender-" + (Get-Date -Format "yyyy-MM-dd") + ".log")
$stopRequestFile = Join-Path $root "data\sender_stop.request"
$restartDelaySeconds = 60
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$arguments = @(
    "-u"
    $script
    "--continuous"
)

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $python)) {
    throw "Python da venv nao encontrado em: $python"
}

[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONUTF8 = "1"

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
            & $python @arguments 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
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
            "[$timestamp] Sender worker exited cleanly. Restarting in $restartDelaySeconds seconds..." | Out-File -FilePath $logFile -Append -Encoding utf8
        }
        else {
            "[$timestamp] Sender worker exited with code $exitCode. Retrying in $restartDelaySeconds seconds..." | Out-File -FilePath $logFile -Append -Encoding utf8
        }

        Start-Sleep -Seconds $restartDelaySeconds
    }
}
catch {
    $_ | Out-File -FilePath $logFile -Append -Encoding utf8
    exit 1
}
finally {
    Pop-Location
}
