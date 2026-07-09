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
$consoleScript = Join-Path $scriptDir "run-preservice-growth-variant-lanes-console.ps1"

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
    "-MaxConcurrentLanes", "$MaxConcurrentLanes",
    "-MaxSegments", "$MaxSegments",
    "-MaxLevel", "$MaxLevel",
    "-ResetLevel", "$ResetLevel",
    "-StartBase", "$StartBase",
    "-LaneStartStride", "$LaneStartStride",
    "-HostAddress", $HostAddress,
    "-NavApiUrl", $NavApiUrl,
    "-ApiPort", "$ApiPort",
    "-WslExe", $WslExe,
    "-ProgressIntervalSeconds", "$ProgressIntervalSeconds"
)

if (-not [string]::IsNullOrWhiteSpace($BaseRunDir)) {
    $arguments += @("-BaseRunDir", $BaseRunDir)
}
if (-not [string]::IsNullOrWhiteSpace($WslWorkDir)) {
    $arguments += @("-WslWorkDir", $WslWorkDir)
}
if ($Resume) {
    $arguments += "-Resume"
}
if ($SkipProvision) {
    $arguments += "-SkipProvision"
}
if ($NoResetProgress) {
    $arguments += "-NoResetProgress"
}

$quotedArguments = @($arguments | ForEach-Object { Quote-ProcessArgument ([string]$_) })

Start-Process -FilePath $powerShellExe -WorkingDirectory $repoRoot -WindowStyle Normal -ArgumentList $quotedArguments

Write-Host "Started KDAOC dummy growth progress console."
Write-Host "BaseRunDir=$BaseRunDir"
Write-Host "ConsoleScript=$consoleScript"
