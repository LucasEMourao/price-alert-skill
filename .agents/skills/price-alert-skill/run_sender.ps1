$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\sender_worker.py"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir ("sender-" + (Get-Date -Format "yyyy-MM-dd") + ".log")
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
    & $python @arguments *>> $logFile
    exit $LASTEXITCODE
}
catch {
    $_ | Out-File -FilePath $logFile -Append
    exit 1
}
finally {
    Pop-Location
}
