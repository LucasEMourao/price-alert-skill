$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$lockFile = Join-Path $root "data\sender_worker.lock"
$stopRequestFile = Join-Path $root "data\sender_stop.request"
$stopRequestedAt = Get-Date -Format "o"

Set-Content -Path $stopRequestFile -Value "requested_at=$stopRequestedAt" -Encoding UTF8

if (-not (Test-Path $lockFile)) {
    Remove-Item $stopRequestFile -Force -ErrorAction SilentlyContinue
    exit 0
}

$content = Get-Content $lockFile -ErrorAction SilentlyContinue
if ($content -match "pid=(\d+)") {
    $pidValue = [int]$matches[1]
    $deadline = (Get-Date).AddMinutes(3)

    while ((Get-Date) -lt $deadline) {
        $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if (-not $process -and -not (Test-Path $lockFile)) {
            break
        }

        if (-not (Test-Path $lockFile)) {
            break
        }

        Start-Sleep -Seconds 2
    }

    if (Get-Process -Id $pidValue -ErrorAction SilentlyContinue) {
        try {
            Stop-Process -Id $pidValue -Force -ErrorAction Stop
        }
        catch {
        }
    }
}

try {
    Remove-Item $lockFile -Force -ErrorAction Stop
}
catch {
}

Remove-Item $stopRequestFile -Force -ErrorAction SilentlyContinue
