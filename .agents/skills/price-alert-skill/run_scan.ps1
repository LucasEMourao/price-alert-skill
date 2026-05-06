$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\scan_deals.py"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir ("scan-" + (Get-Date -Format "yyyy-MM-dd") + ".log")
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$arguments = @(
    "-u"
    $script
    "--all"
    "--scan-only"
    "--min-discount"
    "10"
    "--max-results"
    "8"
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
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $python @arguments 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        "[$timestamp] Scan process exited with code $exitCode." | Out-File -FilePath $logFile -Append -Encoding utf8
    }

    exit $exitCode
}
catch {
    $_ | Out-File -FilePath $logFile -Append -Encoding utf8
    exit 1
}
finally {
    Pop-Location
}
