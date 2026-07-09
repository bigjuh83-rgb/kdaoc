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
    [switch]$DryRun,
    [switch]$FakeWorker
)

$ErrorActionPreference = "Stop"

for ($i = 0; $i -lt $args.Count; $i++) {
    $name = [string]$args[$i]
    $next = if ($i + 1 -lt $args.Count) { [string]$args[$i + 1] } else { "" }
    $consumeValue = $true

    switch ($name) {
        "--base-run-dir" { $BaseRunDir = $next }
        "--case-specs" { $CaseSpecs = $next }
        "--realms" { $Realms = $next }
        "--variants" { $Variants = $next }
        "--solo-repeats" { $SoloRepeats = [int]$next }
        "--duo-repeats" { $DuoRepeats = [int]$next }
        "--party4-repeats" { $Party4Repeats = [int]$next }
        "--party8-repeats" { $Party8Repeats = [int]$next }
        "--case-repeats" { $CaseRepeats = [int]$next }
        "--max-concurrent-cases" { $MaxConcurrentCases = [int]$next }
        "--max-concurrent-per-realm" { $MaxConcurrentPerRealm = [int]$next }
        "--max-segments" { $MaxSegments = [int]$next }
        "--max-level" { $MaxLevel = [int]$next }
        "--reset-level" { $ResetLevel = [int]$next }
        "--growth-party-carry-level-offset" { $GrowthPartyCarryLevelOffset = [int]$next }
        "--growth-party-carry-count" { $GrowthPartyCarryCount = [int]$next }
        "--start-base" { $StartBase = [int]$next }
        "--case-start-stride" { $CaseStartStride = [int]$next }
        "--host" { $HostAddress = $next }
        "--host-address" { $HostAddress = $next }
        "--nav-api-url" { $NavApiUrl = $next }
        "--api-port" { $ApiPort = [int]$next }
        "--mysql-bin" { $MysqlBin = $next }
        "--growth-hunting-index" { $GrowthHuntingIndex = $next }
        "--growth-fast-travel" { $GrowthFastTravel = $next }
        "--wsl-exe" { $WslExe = $next }
        "--wsl-work-dir" { $WslWorkDir = $next }
        "--progress-interval-seconds" { $ProgressIntervalSeconds = [int]$next }
        "--worker-timeout-grace-seconds" { $WorkerTimeoutGraceSeconds = [int]$next }
        "--worker-startup-no-output-fatal-seconds" { $WorkerStartupNoOutputFatalSeconds = [int]$next }
        "--completed-stall-fatal-segments" { $CompletedStallFatalSegments = [int]$next }
        "--bottleneck-auto-resume-attempts" { $BottleneckAutoResumeAttempts = [int]$next }
        "--continue-after-bottleneck" { $ContinueAfterBottleneck = $true; $consumeValue = $false }
        "--show-all-cases" { $ShowAllCases = $true; $consumeValue = $false }
        "--resume-supervisor" { $ResumeSupervisor = $true; $consumeValue = $false }
        "--skip-provision" { $SkipProvision = $true; $consumeValue = $false }
        "--no-reset-progress" { $NoResetProgress = $true; $consumeValue = $false }
        "--no-keep-alive" { $NoKeepAlive = $true; $consumeValue = $false }
        "--dry-run" { $DryRun = $true; $consumeValue = $false }
        "--fake-worker" { $FakeWorker = $true; $consumeValue = $false }
        "--worker-extra-args" {
            $WorkerExtraArgs = @()
            if ($i + 1 -lt $args.Count) {
                $WorkerExtraArgs = @($args[($i + 1)..($args.Count - 1)])
            }
            $i = $args.Count
            $consumeValue = $false
        }
        default { $consumeValue = $false }
    }

    if ($consumeValue) {
        $i++
    }
}

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$consoleScript = Join-Path $scriptDir "run-preservice-growth-case-supervisor-console.ps1"

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

function Quote-ProcessArgument {
    param([string]$Value)

    if ($Value -match '[\s"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

$pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
if ($pwsh) {
    $powerShellExe = $pwsh.Source
}
else {
    $powerShellExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
}

$arguments = @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $consoleScript,
    "-Realms", $Realms,
    "-Variants", $Variants,
    "-SoloRepeats", "$SoloRepeats",
    "-DuoRepeats", "$DuoRepeats",
    "-Party4Repeats", "$Party4Repeats",
    "-Party8Repeats", "$Party8Repeats",
    "-CaseRepeats", "$CaseRepeats",
    "-MaxConcurrentCases", "$MaxConcurrentCases",
    "-MaxConcurrentPerRealm", "$MaxConcurrentPerRealm",
    "-MaxSegments", "$MaxSegments",
    "-MaxLevel", "$MaxLevel",
    "-ResetLevel", "$ResetLevel",
    "-GrowthPartyCarryLevelOffset", "$GrowthPartyCarryLevelOffset",
    "-GrowthPartyCarryCount", "$GrowthPartyCarryCount",
    "-StartBase", "$StartBase",
    "-CaseStartStride", "$CaseStartStride",
    "-HostAddress", $HostAddress,
    "-NavApiUrl", $NavApiUrl,
    "-ApiPort", "$ApiPort",
    "-MysqlBin", $MysqlBin,
    "-GrowthHuntingIndex", $GrowthHuntingIndex,
    "-WslExe", $WslExe,
    "-ProgressIntervalSeconds", "$ProgressIntervalSeconds",
    "-GrowthFastTravel", $GrowthFastTravel,
    "-WorkerTimeoutGraceSeconds", "$WorkerTimeoutGraceSeconds",
    "-WorkerStartupNoOutputFatalSeconds", "$WorkerStartupNoOutputFatalSeconds",
    "-CompletedStallFatalSegments", "$CompletedStallFatalSegments",
    "-BottleneckAutoResumeAttempts", "$BottleneckAutoResumeAttempts"
)

if (-not [string]::IsNullOrWhiteSpace($CaseSpecs)) {
    $arguments += @("-CaseSpecs", $CaseSpecs)
}
if (-not [string]::IsNullOrWhiteSpace($BaseRunDir)) {
    $arguments += @("-BaseRunDir", $BaseRunDir)
}
if (-not [string]::IsNullOrWhiteSpace($WslWorkDir)) {
    $arguments += @("-WslWorkDir", $WslWorkDir)
}
if ($ShowAllCases) {
    $arguments += "-ShowAllCases"
}
if ($ContinueAfterBottleneck) {
    $arguments += "-ContinueAfterBottleneck"
}
if ($ResumeSupervisor) {
    $arguments += "-ResumeSupervisor"
}
if ($SkipProvision) {
    $arguments += "-SkipProvision"
}
if ($NoResetProgress) {
    $arguments += "-NoResetProgress"
}
if ($NoKeepAlive) {
    $arguments += "-NoKeepAlive"
}
if ($DryRun) {
    $arguments += "-DryRun"
}
if ($FakeWorker) {
    $arguments += "-FakeWorker"
}
if ($WorkerExtraArgs.Count -gt 0) {
    $arguments += "-WorkerExtraArgs"
    $arguments += $WorkerExtraArgs
}

$quotedArguments = @($arguments | ForEach-Object { Quote-ProcessArgument ([string]$_) })

Start-Process -FilePath $powerShellExe -WorkingDirectory $repoRoot -WindowStyle Normal -ArgumentList $quotedArguments

Write-Host "Started KDAOC case growth supervisor console."
Write-Host "BaseRunDir=$BaseRunDir"
Write-Host "ConsoleScript=$consoleScript"
