param(
    [switch]$DryRun
)

$ErrorActionPreference = "SilentlyContinue"

$selfPid = $PID
$parentPid = 0
$selfProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$selfPid"
if ($selfProcess) {
    $parentPid = [int]$selfProcess.ParentProcessId
}

function Get-CurrentLauncherProcessIds {
    $ids = @{}
    $processesById = @{}

    Get-CimInstance Win32_Process |
        ForEach-Object { $processesById[[int]$_.ProcessId] = $_ }

    $processId = $selfPid
    while ($processId -gt 0 -and $processesById.ContainsKey($processId)) {
        $ids[$processId] = $true
        $process = $processesById[$processId]
        $processId = [int]$process.ParentProcessId
    }

    return $ids
}

$currentLauncherPids = Get-CurrentLauncherProcessIds
$stopped = @{}

function Stop-ProcessTree {
    param(
        [int]$ProcessId,
        [string]$Reason
    )

    if ($ProcessId -le 0) {
        return
    }
    if ($currentLauncherPids.ContainsKey($ProcessId)) {
        return
    }
    if ($stopped.ContainsKey($ProcessId)) {
        return
    }

    $stopped[$ProcessId] = $true
    if ($DryRun) {
        Write-Host "[OpenDAoC] would stop pid=$ProcessId reason=$Reason"
        return
    }

    & taskkill.exe /F /T /PID $ProcessId *> $null
}

function Stop-StaleOpenDaocCmdWindows {
    # Close old visible server console windows. The current launcher ancestry is
    # excluded so this script cannot close the batch/cmd that invoked it.
    Get-Process cmd -ErrorAction SilentlyContinue |
        Where-Object {
            -not $currentLauncherPids.ContainsKey($_.Id) -and (
                $_.MainWindowTitle -like "OpenDAoC Main Server*" -or
                $_.MainWindowTitle -like "OpenDAoC Visible Server*" -or
                $_.MainWindowTitle -like "Administrator:  OpenDAoC Main Server*" -or
                $_.MainWindowTitle -like "Administrator:  OpenDAoC Visible Server*"
            )
        } |
        ForEach-Object { Stop-ProcessTree -ProcessId $_.Id -Reason "old visible console" }

    $currentProcesses = Get-CimInstance Win32_Process

    # Close stale launchers that were opened by older helper files.
    $currentProcesses |
        Where-Object {
            -not $currentLauncherPids.ContainsKey($_.ProcessId) -and
            $_.Name -eq "cmd.exe" -and
            (
                $_.CommandLine -like "*start-main-server-visible.bat*" -or
                $_.CommandLine -like "*windows-open-visible-server.cmd*"
            )
        } |
        ForEach-Object { Stop-ProcessTree -ProcessId ([int]$_.ProcessId) -Reason "old OpenDAoC launcher" }
}

Stop-StaleOpenDaocCmdWindows

$processes = Get-CimInstance Win32_Process

# Close stale WSL bridge processes from previous visible launches. The Linux
# script performs the in-WSL CoreServer cleanup, so Windows only owns the
# console/bridge cleanup here.
$processes |
    Where-Object {
        $_.Name -in @("wsl.exe", "wslhost.exe") -and
        (
            $_.CommandLine -like "*tools/start-main-visible-server.sh*" -or
            $_.CommandLine -like "*tools/run-local-server.sh*"
        )
    } |
    ForEach-Object { Stop-ProcessTree -ProcessId ([int]$_.ProcessId) -Reason "old WSL server bridge" }

# Killing a stale WSL bridge can return the old batch file to its exit path.
# Sweep command windows again so it cannot sit at a stale prompt/pause window.
Stop-StaleOpenDaocCmdWindows

exit 0
