$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$lockFile = Join-Path $root "data\sender_worker.lock"

if (-not (Test-Path $lockFile)) {
    exit 0
}

$content = Get-Content $lockFile -ErrorAction SilentlyContinue
if ($content -match "pid=(\d+)") {
    $pidValue = [int]$matches[1]
    try {
        Stop-Process -Id $pidValue -Force -ErrorAction Stop
    }
    catch {
    }
}

try {
    Remove-Item $lockFile -Force -ErrorAction Stop
}
catch {
}
