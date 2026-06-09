param(
    [string]$RepoRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

$apiUrl = $env:OPENDAOC_COMPANION_API_URL
if ([string]::IsNullOrWhiteSpace($apiUrl)) {
    $apiUrl = "http://localhost:5000"
}
$apiUrl = $apiUrl.TrimEnd("/")
$probeUrl = "$apiUrl/api/dummy/companions/config"

$timeoutSeconds = 90
if (-not [string]::IsNullOrWhiteSpace($env:OPENDAOC_COMPANION_WAIT_API_TIMEOUT)) {
    $parsedTimeout = 0
    if ([int]::TryParse($env:OPENDAOC_COMPANION_WAIT_API_TIMEOUT, [ref]$parsedTimeout)) {
        $timeoutSeconds = [Math]::Max(0, $parsedTimeout)
    }
}

Write-Host "[OpenDAoC] Waiting for companion API at $probeUrl ..."
$deadline = [DateTime]::UtcNow.AddSeconds($timeoutSeconds)
$lastError = ""

while ($true) {
    try {
        $response = Invoke-WebRequest -Uri $probeUrl -Method Get -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            Write-Host "[OpenDAoC] Companion API is ready; starting visible companion service."
            $launcherPath = Join-Path $RepoRoot "start-live-companion-service-visible.bat"
            Start-Process -FilePath $launcherPath -WorkingDirectory $RepoRoot
            exit 0
        }
        $lastError = "HTTP $($response.StatusCode)"
    }
    catch {
        $lastError = $_.Exception.Message
    }

    if ([DateTime]::UtcNow -ge $deadline) {
        Write-Error "[OpenDAoC] Companion API not ready after ${timeoutSeconds}s: $lastError"
        exit 1
    }

    Start-Sleep -Seconds 1
}
