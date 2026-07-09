param(
    [string]$BaseRunDir = "",
    [int]$MaxConcurrentLanes = 3,
    [int]$MaxSegments = 5,
    [int]$MaxLevel = 50,
    [int]$ResetLevel = 1,
    [int]$StartBase = 42001,
    [int]$LaneStartStride = 1000,
    [string]$HostAddress = "192.168.0.42",
    [string]$NavApiUrl = "http://192.168.0.42:5000",
    [int]$ApiPort = 5000,
    [string]$WslExe = "C:\Windows\System32\wsl.exe",
    [string]$WslWorkDir = "",
    [int]$ProgressIntervalSeconds = 30,
    [switch]$Resume,
    [switch]$SkipProvision,
    [switch]$NoResetProgress
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
Set-Location $repoRoot

try {
    $Host.UI.RawUI.WindowTitle = "KDAOC Dummy Growth Progress"
}
catch {
}

if ([string]::IsNullOrWhiteSpace($BaseRunDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BaseRunDir = "test-output/preservice-growth-50x-variant-lanes-visible-$stamp"
}

Write-Host "KDAOC Dummy Growth Progress"
Write-Host "BaseRunDir=$BaseRunDir"
Write-Host "MaxSegments=$MaxSegments MaxConcurrentLanes=$MaxConcurrentLanes ProgressIntervalSeconds=$ProgressIntervalSeconds"
Write-Host ""

$runner = Join-Path $scriptDir "run-preservice-growth-variant-lanes.ps1"
$runnerParams = @{
    BaseRunDir = $BaseRunDir
    MaxConcurrentLanes = $MaxConcurrentLanes
    MaxSegments = $MaxSegments
    MaxLevel = $MaxLevel
    ResetLevel = $ResetLevel
    StartBase = $StartBase
    LaneStartStride = $LaneStartStride
    HostAddress = $HostAddress
    NavApiUrl = $NavApiUrl
    ApiPort = $ApiPort
    WslExe = $WslExe
    ProgressIntervalSeconds = $ProgressIntervalSeconds
}

if (-not [string]::IsNullOrWhiteSpace($WslWorkDir)) {
    $runnerParams.WslWorkDir = $WslWorkDir
}
if ($Resume) {
    $runnerParams.Resume = $true
}
if ($SkipProvision) {
    $runnerParams.SkipProvision = $true
}
if ($NoResetProgress) {
    $runnerParams.NoResetProgress = $true
}

$exitCode = 0
try {
    & $runner @runnerParams
    if ($LASTEXITCODE -is [int]) {
        $exitCode = [int]$LASTEXITCODE
    }
}
catch {
    $exitCode = 1
    Write-Host ""
    Write-Host "Dummy growth runner failed: $($_.Exception.Message)"
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "Dummy growth lanes finished."
}
else {
    Write-Host "Dummy growth lanes stopped with failures. Check the BaseRunDir logs above."
}
Write-Host "This console stays open for progress review. Type exit to close it."
