param(
    [Parameter(Mandatory = $true)]
    [string]$BaseRunDir,
    [int]$IntervalSeconds = 2,
    [int]$TailLines = 40,
    [switch]$Replay
)

$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
}
catch {
}

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
Set-Location $repoRoot

try {
    $Host.UI.RawUI.WindowTitle = "KDAOC Dummy Error Monitor"
}
catch {
}

$logDir = Join-Path $BaseRunDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$monitorLog = Join-Path $logDir "error-monitor.log"
$controlDir = Join-Path $BaseRunDir "control"
$eventsPath = Join-Path $BaseRunDir "case-events.jsonl"
$offsetPath = Join-Path $controlDir "error-monitor.offset"
$latestErrorPath = Join-Path $controlDir "latest-error.json"

if (-not $Replay) {
    New-Item -ItemType Directory -Force -Path $controlDir | Out-Null
    $eventSize = 0
    if (Test-Path $eventsPath) {
        $eventSize = (Get-Item $eventsPath).Length
    }
    Set-Content -Path $offsetPath -Value "$eventSize" -Encoding UTF8
    Remove-Item -LiteralPath $latestErrorPath -Force -ErrorAction SilentlyContinue
}

$python = Get-Command python.exe -ErrorAction SilentlyContinue
$pythonPrefixArgs = @()
if (-not $python) {
    $python = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($python) {
        $pythonPrefixArgs = @("-3")
    }
}
if (-not $python) {
    throw "python.exe or py.exe was not found in PATH"
}

$watcher = Join-Path $scriptDir "watch-preservice-growth-errors.py"

Write-Host "KDAOC Dummy Error Monitor"
Write-Host "BaseRunDir=$BaseRunDir"
Write-Host "Latest error: $BaseRunDir/control/latest-error.json"
Write-Host "Alert log: $BaseRunDir/control/error-alerts.jsonl"
Write-Host "Console log: $monitorLog"
Write-Host ""

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8:replace"
    $firstRun = $true
    while ($true) {
        $watcherArgs = @(
            $watcher,
            "--base-run-dir", $BaseRunDir,
            "--interval-seconds", "$IntervalSeconds",
            "--tail-lines", "$TailLines"
        )
        if ($Replay -and $firstRun) {
            $watcherArgs += "--replay"
        }
        $firstRun = $false

        & $python.Source @pythonPrefixArgs @watcherArgs 2>&1 | ForEach-Object {
            "$_"
        } | Tee-Object -FilePath $monitorLog -Append

        $exitCode = $LASTEXITCODE
        $restartLine = "[{0}] watcher exited code={1}; restarting in 2s" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $exitCode
        Write-Host $restartLine
        Add-Content -LiteralPath $monitorLog -Value $restartLine -Encoding UTF8
        Start-Sleep -Seconds 2
    }
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
