param(
    [string]$RunDir = "",
    [string]$Realms = "alb,mid,hib",
    [string]$PartySizes = "1,2,4",
    [int]$CaseRepeats = 1,
    [int]$ParallelCases = 6,
    [int]$SegmentSeconds = 150,
    [int]$MaxSegments = 2,
    [int]$MaxLevel = 50,
    [int]$ResetLevel = 1,
    [int]$Start = 5001,
    [int]$StartStride = 40,
    [string]$HostAddress = "192.168.0.42",
    [string]$NavApiUrl = "http://192.168.0.42:5000",
    [int]$ApiPort = 5000,
    [string]$GrowthStage = "custom",
    [string]$GrowthSpeedProfile = "fast-balance",
    [string]$MysqlBin = "/mnt/c/Program Files/MariaDB 12.3/bin/mariadb.exe",
    [string]$WslExe = "C:\Windows\System32\wsl.exe",
    [string]$WslWorkDir = "",
    [switch]$Resume,
    [switch]$SkipProvision,
    [switch]$NoResetProgress,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs = @()
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($WslWorkDir)) {
    $WslWorkDir = (& $WslExe --exec wslpath -a $repoRoot.Path).Trim()
}

if ([string]::IsNullOrWhiteSpace($RunDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $RunDir = "test-output/preservice-growth-50x-parallel-multiseg-$stamp"
}

$localRunDir = Join-Path (Get-Location) $RunDir
New-Item -ItemType Directory -Force -Path $localRunDir | Out-Null

$growthArgs = @(
    "--mysql-bin", $MysqlBin,
    "--growth-stage", $GrowthStage,
    "--growth-speed-profile", $GrowthSpeedProfile,
    "--segment-seconds", "$SegmentSeconds",
    "--max-segments", "$MaxSegments",
    "--max-level", "$MaxLevel",
    "--reset-level", "$ResetLevel",
    "--realms", $Realms,
    "--party-sizes", $PartySizes,
    "--case-repeats", "$CaseRepeats",
    "--parallel-cases", "$ParallelCases",
    "--start", "$Start",
    "--start-stride", "$StartStride",
    "--host", $HostAddress,
    "--nav-api-url", $NavApiUrl,
    "--api-port", "$ApiPort",
    "--run-dir", $RunDir
)

if ($Resume) {
    $growthArgs += "--resume"
}
if ($SkipProvision) {
    $growthArgs += "--skip-provision"
}
if ($NoResetProgress) {
    $growthArgs += "--no-reset-progress"
}
if ($ExtraArgs.Count -gt 0) {
    $growthArgs += $ExtraArgs
}

$wslArgs = @(
    "--cd", $WslWorkDir,
    "--exec", "python3", "tools/run-dummy-growth-suite.py"
) + $growthArgs

Write-Host "RUN_DIR=$RunDir"
Write-Host "PARALLEL_CASES=$ParallelCases"
Write-Host "PARTY_SIZES=$PartySizes"
Write-Host "MAX_SEGMENTS=$MaxSegments"
& $WslExe @wslArgs
exit $LASTEXITCODE
