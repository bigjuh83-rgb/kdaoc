param(
    [string]$BaseRunDir = "",
    [int]$MaxConcurrentLanes = 3,
    [int]$MaxSegments = 2,
    [int]$MaxLevel = 50,
    [int]$ResetLevel = 1,
    [int]$StartBase = 6001,
    [int]$LaneStartStride = 1000,
    [string]$HostAddress = "192.168.0.42",
    [string]$NavApiUrl = "http://192.168.0.42:5000",
    [int]$ApiPort = 5000,
    [string]$WslExe = "C:\Windows\System32\wsl.exe",
    [string]$WslWorkDir = "/mnt/d/다옥프리서버/OpenDAoC-Core",
    [int]$ProgressIntervalSeconds = 30,
    [switch]$Resume,
    [switch]$SkipProvision,
    [switch]$NoResetProgress,
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

if ($MaxConcurrentLanes -lt 1) {
    throw "-MaxConcurrentLanes must be positive"
}

if ([string]::IsNullOrWhiteSpace($BaseRunDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BaseRunDir = "test-output/preservice-growth-50x-variant-lanes-$stamp"
}

$baseLocalRunDir = Join-Path (Get-Location) $BaseRunDir
New-Item -ItemType Directory -Force -Path $baseLocalRunDir | Out-Null

$variantLanes = @(
    [pscustomobject]@{
        Name = "solo-s150-r2"
        PartySizes = "1"
        CaseRepeats = 2
        ParallelCases = 1
        SegmentSeconds = 150
        StartOffset = 0
        ExtraArgs = @("--travel-aggro-clear-grace", "18")
    },
    [pscustomobject]@{
        Name = "duo-s150"
        PartySizes = "2"
        CaseRepeats = 1
        ParallelCases = 1
        SegmentSeconds = 150
        StartOffset = $LaneStartStride
        ExtraArgs = @("--travel-aggro-clear-grace", "16", "--party-rescue-assist-after", "3")
    },
    [pscustomobject]@{
        Name = "party4-s180"
        PartySizes = "4"
        CaseRepeats = 1
        ParallelCases = 1
        SegmentSeconds = 180
        StartOffset = 2 * $LaneStartStride
        ExtraArgs = @("--travel-aggro-clear-grace", "12", "--party-rescue-assist-after", "2", "--party-rescue-emergency-assist-after", "1")
    }
)

$realmOrder = @("alb", "mid", "hib")
$realmStartOffsets = @{
    alb = 0
    mid = 40
    hib = 80
}

$lanes = @()
for ($wave = 0; $wave -lt $realmOrder.Count; $wave++) {
    for ($variantIndex = 0; $variantIndex -lt $variantLanes.Count; $variantIndex++) {
        $variant = $variantLanes[$variantIndex]
        $realm = $realmOrder[($wave + $variantIndex) % $realmOrder.Count]
        $lanes += [pscustomobject]@{
            Name = "$($variant.Name)-$realm"
            VariantName = $variant.Name
            Realm = $realm
            Realms = $realm
            PartySizes = $variant.PartySizes
            CaseRepeats = $variant.CaseRepeats
            ParallelCases = $variant.ParallelCases
            SegmentSeconds = $variant.SegmentSeconds
            Start = $StartBase + [int]$variant.StartOffset + [int]$realmStartOffsets[$realm]
            ExtraArgs = [string[]]$variant.ExtraArgs
        }
    }
}

$laneRows = foreach ($lane in $lanes) {
    $runDir = "$BaseRunDir/$($lane.Name)"
    $localRunDir = Join-Path (Get-Location) $runDir
    New-Item -ItemType Directory -Force -Path $localRunDir | Out-Null
    [pscustomobject]@{
        Name = $lane.Name
        VariantName = $lane.VariantName
        Realm = $lane.Realm
        RunDir = $runDir
        Realms = $lane.Realms
        PartySizes = $lane.PartySizes
        CaseRepeats = $lane.CaseRepeats
        ParallelCases = $lane.ParallelCases
        SegmentSeconds = $lane.SegmentSeconds
        MaxSegments = $MaxSegments
        MaxLevel = $MaxLevel
        ResetLevel = $ResetLevel
        Start = $lane.Start
        ExtraArgs = [string[]]$lane.ExtraArgs
        ExtraArgsText = ([string[]]$lane.ExtraArgs) -join " "
        StdoutLog = Join-Path $localRunDir "runner.stdout.log"
        StderrLog = Join-Path $localRunDir "runner.stderr.log"
    }
}

$laneRows | Export-Csv -LiteralPath (Join-Path $baseLocalRunDir "lanes.csv") -NoTypeInformation -Encoding UTF8

$wrapper = Join-Path $scriptDir "run-preservice-growth-parallel-batch.ps1"
$jobs = @()
$completed = @()

function Receive-FinishedLaneJob {
    param([System.Management.Automation.Job]$Job)
    $received = Receive-Job -Job $Job
    Remove-Job -Job $Job
    return $received
}

function Convert-ToProgressInt {
    param($Value)
    if ($null -eq $Value) {
        return 0
    }
    $parsed = 0
    if ([int]::TryParse(([string]$Value), [ref]$parsed)) {
        return $parsed
    }
    return 0
}

function Import-CsvQuiet {
    param([string]$Path)
    try {
        if ((Test-Path -LiteralPath $Path) -and ((Get-Item -LiteralPath $Path).Length -gt 0)) {
            return @(Import-Csv -LiteralPath $Path)
        }
    }
    catch {
        return @()
    }
    return @()
}

function Get-LaneProgressSnapshot {
    param(
        [pscustomobject]$Lane,
        [string]$Status
    )

    $localRunDir = Join-Path (Get-Location) $Lane.RunDir
    $timelineRows = Import-CsvQuiet -Path (Join-Path $localRunDir "timeline.csv")
    if ($timelineRows.Count -gt 0) {
        $latest = $timelineRows[-1]
        $maxLevel = 0
        $maxSegment = 0
        $xp = 0
        $money = 0
        $deaths = 0
        $kills = 0
        $train = 0
        $stallRows = 0
        foreach ($row in $timelineRows) {
            $level = Convert-ToProgressInt $row.level_after
            if ($level -gt $maxLevel) { $maxLevel = $level }
            $segment = Convert-ToProgressInt $row.segment
            if ($segment -gt $maxSegment) { $maxSegment = $segment }
            $rowXp = Convert-ToProgressInt $row.xp_effective_delta
            $rowKills = Convert-ToProgressInt $row.target_removed
            $rowMoney = Convert-ToProgressInt $row.money_delta_copper
            $xp += $rowXp
            $money += Convert-ToProgressInt $row.money_delta_copper
            $deaths += Convert-ToProgressInt $row.death_delta
            $kills += $rowKills
            $train += Convert-ToProgressInt $row.train_verified
            if ($rowXp -eq 0 -and $rowKills -eq 0 -and $rowMoney -eq 0) {
                $stallRows += 1
            }
        }

        $metricFiles = @()
        try {
            if (Test-Path -LiteralPath $localRunDir) {
                $metricFiles = @(Get-ChildItem -LiteralPath $localRunDir -Recurse -Filter "segment-*-metrics.csv")
            }
        }
        catch {
            $metricFiles = @()
        }

        $maxMetricSegment = 0
        $metricDeathsAfterTimeline = 0
        $metricKillsAfterTimeline = 0
        foreach ($file in $metricFiles) {
            if ($file.Name -notmatch "segment-(\d+)-metrics\.csv") {
                continue
            }
            $metricSegment = [int]$matches[1]
            if ($metricSegment -le $maxSegment) {
                continue
            }
            if ($metricSegment -gt $maxMetricSegment) { $maxMetricSegment = $metricSegment }
            foreach ($row in (Import-CsvQuiet -Path $file.FullName)) {
                $metricDeathsAfterTimeline += Convert-ToProgressInt $row.player_deaths
                $metricKillsAfterTimeline += Convert-ToProgressInt $row.target_removed
            }
        }

        $displaySegment = $maxSegment
        $latestText = "$($latest.case)/s$($latest.segment)/$($latest.account)/L$($latest.level_after)"
        if ($maxMetricSegment -gt $maxSegment) {
            $displaySegment = $maxMetricSegment
            $latestText = "metrics/s$maxMetricSegment"
        }

        return [pscustomobject]@{
            Name = $Lane.Name
            Realm = $Lane.Realm
            Status = $Status
            Segment = $displaySegment
            MaxLevel = $maxLevel
            Xp = $xp
            Money = $money
            Deaths = $deaths + $metricDeathsAfterTimeline
            Kills = $kills + $metricKillsAfterTimeline
            Train = $train
            Stall = $stallRows
            Latest = $latestText
        }
    }

    $metricFiles = @()
    try {
        if (Test-Path -LiteralPath $localRunDir) {
            $metricFiles = @(Get-ChildItem -LiteralPath $localRunDir -Recurse -Filter "segment-*-metrics.csv")
        }
    }
    catch {
        $metricFiles = @()
    }

    $maxMetricSegment = 0
    $metricDeaths = 0
    $metricKills = 0
    foreach ($file in $metricFiles) {
        if ($file.Name -match "segment-(\d+)-metrics\.csv") {
            $segment = [int]$matches[1]
            if ($segment -gt $maxMetricSegment) { $maxMetricSegment = $segment }
        }
        foreach ($row in (Import-CsvQuiet -Path $file.FullName)) {
            $metricDeaths += Convert-ToProgressInt $row.player_deaths
            $metricKills += Convert-ToProgressInt $row.target_removed
        }
    }

    return [pscustomobject]@{
        Name = $Lane.Name
        Realm = $Lane.Realm
        Status = $Status
        Segment = $maxMetricSegment
        MaxLevel = 0
        Xp = 0
        Money = 0
        Deaths = $metricDeaths
        Kills = $metricKills
        Train = 0
        Stall = 0
        Latest = if ($maxMetricSegment -gt 0) { "metrics/s$maxMetricSegment" } else { "waiting" }
    }
}

$lastProgressAt = [datetime]::MinValue

function Write-ProgressSnapshot {
    param(
        [object[]]$LaneRows,
        [System.Management.Automation.Job[]]$Jobs,
        [object[]]$CompletedRows,
        [switch]$Force
    )

    if ($ProgressIntervalSeconds -lt 1 -and -not $Force) {
        return
    }

    $now = Get-Date
    if (-not $Force -and ($now - $script:lastProgressAt).TotalSeconds -lt $ProgressIntervalSeconds) {
        return
    }
    $script:lastProgressAt = $now

    $runningNames = @($Jobs | ForEach-Object { $_.Name })
    $completedNames = @($CompletedRows | ForEach-Object { $_.Name })
    $failedNames = @($CompletedRows | Where-Object { [int]$_.ExitCode -ne 0 } | ForEach-Object { $_.Name })
    Write-Host ("progress {0} base={1}" -f $now.ToString("HH:mm:ss"), $BaseRunDir)
    foreach ($lane in $LaneRows) {
        $status = "queued"
        if ($failedNames -contains $lane.Name) {
            $status = "failed"
        }
        elseif ($completedNames -contains $lane.Name) {
            $status = "done"
        }
        elseif ($runningNames -contains $lane.Name) {
            $status = "running"
        }
        $snapshot = Get-LaneProgressSnapshot -Lane $lane -Status $status
        Write-Host ("  {0,-17} {1,-7} realm={2,-3} seg={3}/{4} maxL={5} xp={6} money={7} deaths={8} kills={9} train={10} stall={11} latest={12}" -f `
            $snapshot.Name,
            $snapshot.Status,
            $snapshot.Realm,
            $snapshot.Segment,
            $MaxSegments,
            $snapshot.MaxLevel,
            $snapshot.Xp,
            $snapshot.Money,
            $snapshot.Deaths,
            $snapshot.Kills,
            $snapshot.Train,
            $snapshot.Stall,
            $snapshot.Latest)
    }
}

function Get-RunningLaneRealmMap {
    param(
        [object[]]$LaneRows,
        [System.Management.Automation.Job[]]$Jobs
    )

    $realms = @{}
    foreach ($job in $Jobs) {
        $jobName = $job.Name
        $lane = $LaneRows | Where-Object { $_.Name -eq $jobName } | Select-Object -First 1
        if ($null -ne $lane) {
            $realms[[string]$lane.Realm] = $true
        }
    }
    return $realms
}

function Start-VariantLaneJob {
    param([object]$Lane)

    $job = Start-Job -Name $Lane.Name -ScriptBlock {
        param(
            [string]$Wrapper,
            [string]$LaneName,
            [string]$LaneRunDir,
            [string]$LaneRealms,
            [string]$LanePartySizes,
            [int]$LaneCaseRepeats,
            [int]$LaneParallelCases,
            [int]$LaneSegmentSeconds,
            [int]$LaneMaxSegments,
            [int]$LaneStart,
            [string]$LaneExtraArgsText,
            [string]$LaneStdoutLog,
            [string]$LaneStderrLog,
            [int]$MaxLevel,
            [int]$ResetLevel,
            [string]$HostAddress,
            [string]$NavApiUrl,
            [int]$ApiPort,
            [string]$WslExe,
            [string]$WslWorkDir,
            [bool]$Resume,
            [bool]$SkipProvision,
            [bool]$NoResetProgress
        )

        $wrapperParams = @{
            RunDir = $LaneRunDir
            Realms = $LaneRealms
            PartySizes = $LanePartySizes
            CaseRepeats = $LaneCaseRepeats
            ParallelCases = $LaneParallelCases
            SegmentSeconds = $LaneSegmentSeconds
            MaxSegments = $LaneMaxSegments
            MaxLevel = $MaxLevel
            ResetLevel = $ResetLevel
            Start = $LaneStart
            HostAddress = $HostAddress
            NavApiUrl = $NavApiUrl
            ApiPort = $ApiPort
            WslExe = $WslExe
            WslWorkDir = $WslWorkDir
        }
        $laneExtraArgs = @()
        if (-not [string]::IsNullOrWhiteSpace($LaneExtraArgsText)) {
            $laneExtraArgs = @($LaneExtraArgsText -split "\s+" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
            $wrapperParams.ExtraArgs = $laneExtraArgs
        }
        if ($Resume) {
            $wrapperParams.Resume = $true
        }
        if ($SkipProvision) {
            $wrapperParams.SkipProvision = $true
        }
        if ($NoResetProgress) {
            $wrapperParams.NoResetProgress = $true
        }
        & $Wrapper @wrapperParams 1> $LaneStdoutLog 2> $LaneStderrLog
        $runnerExitCode = $LASTEXITCODE

        & $WslExe --cd $WslWorkDir --exec python3 tools/summarize-dummy-growth-run.py $LaneRunDir 1>> $LaneStdoutLog 2>> $LaneStderrLog
        $summaryExitCode = $LASTEXITCODE

        $exitCode = $runnerExitCode
        if ($exitCode -eq 0) {
            $exitCode = $summaryExitCode
        }

        [pscustomobject]@{
            Name = $LaneName
            RunDir = $LaneRunDir
            ExitCode = $exitCode
            RunnerExitCode = $runnerExitCode
            SummaryExitCode = $summaryExitCode
            StdoutLog = $LaneStdoutLog
            StderrLog = $LaneStderrLog
        }
    } -ArgumentList @(
        $wrapper,
        $Lane.Name,
        $Lane.RunDir,
        $Lane.Realms,
        $Lane.PartySizes,
        [int]$Lane.CaseRepeats,
        [int]$Lane.ParallelCases,
        [int]$Lane.SegmentSeconds,
        [int]$Lane.MaxSegments,
        [int]$Lane.Start,
        $Lane.ExtraArgsText,
        $Lane.StdoutLog,
        $Lane.StderrLog,
        $MaxLevel,
        $ResetLevel,
        $HostAddress,
        $NavApiUrl,
        $ApiPort,
        $WslExe,
        $WslWorkDir,
        [bool]$Resume,
        [bool]$SkipProvision,
        [bool]$NoResetProgress
    )

    Write-Host "started lane $($Lane.Name) run_dir=$($Lane.RunDir) job=$($job.Id)"
    return $job
}

$pendingLanes = [System.Collections.Generic.List[object]]::new()
foreach ($lane in $laneRows) {
    [void]$pendingLanes.Add($lane)
}

while ($pendingLanes.Count -gt 0) {
    $startedAny = $false

    while ($jobs.Count -lt $MaxConcurrentLanes -and $pendingLanes.Count -gt 0) {
        $runningRealms = Get-RunningLaneRealmMap -LaneRows $laneRows -Jobs $jobs
        $startIndex = -1
        for ($index = 0; $index -lt $pendingLanes.Count; $index++) {
            $candidateLane = $pendingLanes[$index]
            if (-not $runningRealms.ContainsKey([string]$candidateLane.Realm)) {
                $startIndex = $index
                break
            }
        }

        if ($startIndex -lt 0) {
            break
        }

        $lane = $pendingLanes[$startIndex]
        $pendingLanes.RemoveAt($startIndex)
        $jobs += Start-VariantLaneJob -Lane $lane
        $startedAny = $true
        Write-ProgressSnapshot -LaneRows $laneRows -Jobs $jobs -CompletedRows $completed -Force
    }

    if ($NoWait) {
        Write-Host "BASE_RUN_DIR=$BaseRunDir"
        Write-Host "LANES_CSV=$(Join-Path $baseLocalRunDir 'lanes.csv')"
        return
    }

    if ($pendingLanes.Count -eq 0) {
        break
    }

    Write-ProgressSnapshot -LaneRows $laneRows -Jobs $jobs -CompletedRows $completed
    if ($jobs.Count -le 0) {
        throw "no active lane jobs while lanes remain queued"
    }

    $finished = Wait-Job -Job $jobs -Any -Timeout 5
    if ($null -eq $finished) {
        if (-not $startedAny) {
            Start-Sleep -Seconds 1
        }
        continue
    }
    $completed += Receive-FinishedLaneJob -Job $finished
    $jobs = @($jobs | Where-Object { $_.Id -ne $finished.Id })
    Write-ProgressSnapshot -LaneRows $laneRows -Jobs $jobs -CompletedRows $completed -Force
}

if ($NoWait) {
    Write-Host "BASE_RUN_DIR=$BaseRunDir"
    Write-Host "LANES_CSV=$(Join-Path $baseLocalRunDir 'lanes.csv')"
    return
}

while ($jobs.Count -gt 0) {
    Write-ProgressSnapshot -LaneRows $laneRows -Jobs $jobs -CompletedRows $completed
    $finished = Wait-Job -Job $jobs -Any -Timeout 5
    if ($null -eq $finished) {
        continue
    }
    $completed += Receive-FinishedLaneJob -Job $finished
    $jobs = @($jobs | Where-Object { $_.Id -ne $finished.Id })
    Write-ProgressSnapshot -LaneRows $laneRows -Jobs $jobs -CompletedRows $completed -Force
}

$completed | Export-Csv -LiteralPath (Join-Path $baseLocalRunDir "lane-results.csv") -NoTypeInformation -Encoding UTF8
$completed | Format-Table -AutoSize

$failed = @($completed | Where-Object { [int]$_.ExitCode -ne 0 })
if ($failed.Count -gt 0) {
    throw "one or more variant lanes failed; see lane-results.csv under $BaseRunDir"
}

Write-Host "BASE_RUN_DIR=$BaseRunDir"
Write-Host "LANES_CSV=$(Join-Path $baseLocalRunDir 'lanes.csv')"
Write-Host "LANE_RESULTS_CSV=$(Join-Path $baseLocalRunDir 'lane-results.csv')"
