[CmdletBinding(PositionalBinding=$false)]
param(
    [string]$BaseRunDir = "",
    [string]$CaseSpecs = "",
    [string]$Realms = "alb,mid,hib",
    [string]$Variants = "solo-s150-r2,duo-s150,party4-s180,party8-s240",
    [int]$SoloRepeats = 2,
    [int]$DuoRepeats = 1,
    [int]$Party4Repeats = 1,
    [int]$Party8Repeats = 1,
    [int]$CaseRepeats = 0,
    [int]$MaxConcurrentCases = 6,
    [int]$MaxConcurrentPerRealm = 0,
    [int]$MaxSegments = 5,
    [int]$MaxLevel = 50,
    [int]$ResetLevel = 1,
    [int]$GrowthPartyCarryLevelOffset = 12,
    [int]$GrowthPartyCarryCount = -1,
    [int]$StartBase = 42001,
    [int]$CaseStartStride = 40,
    [string]$HostAddress = "192.168.0.42",
    [string]$NavApiUrl = "http://192.168.0.42:5000",
    [int]$ApiPort = 5000,
    [string]$MysqlBin = "/mnt/c/Program Files/MariaDB 12.3/bin/mariadb.exe",
    [string]$GrowthHuntingIndex = "tools/test-output/preservice-growth-hunting-index-latest.csv",
    [string]$GrowthFastTravel = "route-home",
    [string]$WslExe = "C:\Windows\System32\wsl.exe",
    [string]$WslWorkDir = "",
    [int]$ProgressIntervalSeconds = 30,
    [int]$WorkerTimeoutGraceSeconds = 300,
    [int]$WorkerStartupNoOutputFatalSeconds = 120,
    [int]$CompletedStallFatalSegments = 2,
    [int]$BottleneckAutoResumeAttempts = 3,
    [string[]]$WorkerExtraArgs = @(),
    [switch]$ContinueAfterBottleneck,
    [switch]$ShowAllCases,
    [switch]$ResumeSupervisor,
    [switch]$SkipProvision,
    [switch]$NoResetProgress,
    [switch]$NoKeepAlive,
    [switch]$NoErrorMonitor,
    [switch]$DryRun,
    [switch]$FakeWorker,
    [int]$ErrorMonitorIntervalSeconds = 2
)

$ErrorActionPreference = "Stop"

function Normalize-GrowthFastTravel {
    param([string]$Value)

    $normalized = ([string]$Value).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return "route-home"
    }
    if ($normalized -eq "teleport") {
        return "route-home"
    }
    if ($normalized -in @("off", "route-home")) {
        return $normalized
    }
    Write-Warning "Unknown GrowthFastTravel '$Value'; using route-home."
    return "route-home"
}

$GrowthFastTravel = Normalize-GrowthFastTravel $GrowthFastTravel

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
Set-Location $repoRoot

try {
    $Host.UI.RawUI.WindowTitle = "KDAOC Case Growth Supervisor"
}
catch {
}

if ([string]::IsNullOrWhiteSpace($BaseRunDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BaseRunDir = "test-output/preservice-growth-50x-case-supervisor-visible-$stamp"
}

$logDir = Join-Path $BaseRunDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$consoleLog = Join-Path $logDir "supervisor-console.log"

Write-Host "KDAOC Case Growth Supervisor"
Write-Host "BaseRunDir=$BaseRunDir"
Write-Host "Realms=$Realms Variants=$Variants"
Write-Host "MaxConcurrentCases=$MaxConcurrentCases MaxConcurrentPerRealm=$MaxConcurrentPerRealm MaxSegments=$MaxSegments"
Write-Host "GrowthPartyCarryCount=$GrowthPartyCarryCount GrowthPartyCarryLevelOffset=$GrowthPartyCarryLevelOffset"
Write-Host "Control file: $BaseRunDir/control/commands.jsonl"
Write-Host "Console log: $consoleLog"
Write-Host ""

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

$runner = Join-Path $scriptDir "run-preservice-growth-case-supervisor.py"
$runnerArgs = @(
    $runner,
    "--base-run-dir", $BaseRunDir,
    "--realms", $Realms,
    "--variants", $Variants,
    "--solo-repeats", "$SoloRepeats",
    "--duo-repeats", "$DuoRepeats",
    "--party4-repeats", "$Party4Repeats",
    "--party8-repeats", "$Party8Repeats",
    "--case-repeats", "$CaseRepeats",
    "--max-concurrent-cases", "$MaxConcurrentCases",
    "--max-concurrent-per-realm", "$MaxConcurrentPerRealm",
    "--max-segments", "$MaxSegments",
    "--max-level", "$MaxLevel",
    "--reset-level", "$ResetLevel",
    "--growth-party-carry-level-offset", "$GrowthPartyCarryLevelOffset",
    "--growth-party-carry-count", "$GrowthPartyCarryCount",
    "--start-base", "$StartBase",
    "--case-start-stride", "$CaseStartStride",
    "--host", $HostAddress,
    "--nav-api-url", $NavApiUrl,
    "--api-port", "$ApiPort",
    "--mysql-bin", $MysqlBin,
    "--wsl-exe", $WslExe,
    "--progress-interval-seconds", "$ProgressIntervalSeconds",
    "--worker-timeout-grace-seconds", "$WorkerTimeoutGraceSeconds",
    "--worker-startup-no-output-fatal-seconds", "$WorkerStartupNoOutputFatalSeconds",
    "--completed-stall-fatal-segments", "$CompletedStallFatalSegments",
    "--bottleneck-auto-resume-attempts", "$BottleneckAutoResumeAttempts"
)

if (-not [string]::IsNullOrWhiteSpace($CaseSpecs)) {
    $runnerArgs += @("--case-specs", $CaseSpecs)
}

if (-not [string]::IsNullOrWhiteSpace($GrowthHuntingIndex)) {
    $runnerArgs += @("--growth-hunting-index", $GrowthHuntingIndex)
}

if ($GrowthFastTravel -ne "off") {
    $runnerArgs += @("--growth-fast-travel", $GrowthFastTravel)
}

if (-not [string]::IsNullOrWhiteSpace($WslWorkDir)) {
    $runnerArgs += @("--wsl-work-dir", $WslWorkDir)
}

if ($ShowAllCases) {
    $runnerArgs += "--show-all-cases"
}
if ($ContinueAfterBottleneck) {
    $runnerArgs += "--continue-after-bottleneck"
}
if ($ResumeSupervisor) {
    $runnerArgs += "--resume-supervisor"
}
if ($SkipProvision) {
    $runnerArgs += "--skip-provision"
}
if ($NoResetProgress) {
    $runnerArgs += "--no-reset-progress"
}
if (-not $NoKeepAlive) {
    $runnerArgs += "--keep-alive"
}
if ($DryRun) {
    $runnerArgs += "--dry-run"
}
if ($FakeWorker) {
    $runnerArgs += "--fake-worker"
}
if ($WorkerExtraArgs.Count -gt 0) {
    $runnerArgs += "--worker-extra-args"
    $runnerArgs += $WorkerExtraArgs
}

if (-not $NoErrorMonitor) {
    $monitorWrapper = Join-Path $scriptDir "watch-preservice-growth-errors-console.ps1"
    $monitorScriptMatch = "*watch-preservice-growth-errors.py*"
    $monitorWrapperMatch = "*watch-preservice-growth-errors-console.ps1*"
    $baseRunMatch = "*$BaseRunDir*"
    $existingMonitor = Get-CimInstance Win32_Process |
        Where-Object {
            ($_.CommandLine -like $monitorScriptMatch -or $_.CommandLine -like $monitorWrapperMatch) -and
            $_.CommandLine -like $baseRunMatch
        } |
        Select-Object -First 1
    if (-not $existingMonitor) {
        $monitorProcess = Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoExit",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $monitorWrapper,
            "-BaseRunDir",
            $BaseRunDir,
            "-IntervalSeconds",
            "$ErrorMonitorIntervalSeconds"
        ) -WindowStyle Normal -PassThru
        "Started dummy error monitor. PID=$($monitorProcess.Id)" | Tee-Object -FilePath $consoleLog -Append
    }
    else {
        "Dummy error monitor is already running. PID=$($existingMonitor.ProcessId)" | Tee-Object -FilePath $consoleLog -Append
    }
}

$commandLine = @($python.Source) + $pythonPrefixArgs + $runnerArgs
("[" + (Get-Date -Format "o") + "] " + ($commandLine -join " ")) | Tee-Object -FilePath $consoleLog -Append
& $python.Source @pythonPrefixArgs @runnerArgs 2>&1 | Tee-Object -FilePath $consoleLog -Append
$exitCode = 0
if ($LASTEXITCODE -is [int]) {
    $exitCode = [int]$LASTEXITCODE
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "Case supervisor finished."
}
else {
    Write-Host "Case supervisor stopped with failures or quarantined cases. Check BaseRunDir status files."
}
Write-Host "This console stays open for progress review. Type exit to close it."
exit $exitCode
