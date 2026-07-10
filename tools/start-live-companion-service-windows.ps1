param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-EnvValue {
    param(
        [string]$Name,
        [string]$Default = ""
    )

    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

function Get-EnvBool {
    param(
        [string]$Name,
        [string]$Default = "0"
    )

    $value = Get-EnvValue -Name $Name -Default $Default
    return $value -eq "1"
}

function Import-EnvFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $name, $value = $line.Split("=", 2)
        $name = $name.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if (-not [string]::IsNullOrWhiteSpace($name)) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Import-LocalApiPasswordFromDatabase {
    if (-not [string]::IsNullOrWhiteSpace((Get-EnvValue -Name "OPENDAOC_API_PASSWORD"))) {
        return
    }

    $configPath = Join-Path $RepoRoot "CoreServer\config\serverconfig.xml"
    if (-not (Test-Path -LiteralPath $configPath)) {
        return
    }
    $configText = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8
    $passwordMatch = [regex]::Match($configText, "Password=([^;]+)")
    if (-not $passwordMatch.Success) {
        return
    }

    $mysqlCandidates = @(
        "C:\Program Files\MariaDB 12.3\bin\mariadb.exe",
        "C:\Program Files\MariaDB 12.2\bin\mariadb.exe",
        "C:\Program Files\MariaDB 12.1\bin\mariadb.exe",
        "C:\Program Files\MariaDB 11.8\bin\mariadb.exe"
    )
    $mysql = $mysqlCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($mysql)) {
        return
    }

    $previousMysqlPassword = [Environment]::GetEnvironmentVariable("MYSQL_PWD", "Process")
    try {
        [Environment]::SetEnvironmentVariable("MYSQL_PWD", $passwordMatch.Groups[1].Value, "Process")
        $sql = 'SELECT Value FROM ServerProperty WHERE `Key`=''api_password'' LIMIT 1;'
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            $rows = @(& $mysql --batch --raw --skip-column-names --protocol=tcp -h 127.0.0.1 -P 3306 -u root opendaoc -e $sql 2>$null)
            $mysqlExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($mysqlExitCode -ne 0) {
            return
        }
        $apiPassword = $rows | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1
        if (-not [string]::IsNullOrWhiteSpace($apiPassword)) {
            [Environment]::SetEnvironmentVariable("OPENDAOC_API_PASSWORD", $apiPassword.Trim(), "Process")
        }
    } finally {
        [Environment]::SetEnvironmentVariable("MYSQL_PWD", $previousMysqlPassword, "Process")
    }
}

function Resolve-Python {
    $configured = Get-EnvValue -Name "OPENDAOC_COMPANION_PYTHON"
    if (-not [string]::IsNullOrWhiteSpace($configured) -and (Test-Path -LiteralPath $configured)) {
        return (Resolve-Path -LiteralPath $configured).Path
    }

    $candidates = @(
        (Join-Path $RepoRoot ".venv-companion-ai\Scripts\python.exe"),
        "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe",
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        return $command.Source
    }

    throw "Python executable was not found. Set OPENDAOC_COMPANION_PYTHON."
}

function Stop-ExistingCompanionService {
    param(
        [string]$StopFile,
        [int]$TimeoutSeconds = 12
    )

    $currentPid = $PID
    $processes = Get-CimInstance Win32_Process |
        Where-Object {
            $_.ProcessId -ne $currentPid -and
            $_.Name -match "python|py" -and
            $_.CommandLine -like "*tools*dummy-companion-service.py*"
        }

    if (-not $processes) {
        return
    }

    Write-Host "[OpenDAoC] Existing companion service detected; stopping it first..."
    if (-not [string]::IsNullOrWhiteSpace($StopFile)) {
        $stopPath = if ([System.IO.Path]::IsPathRooted($StopFile)) {
            [System.IO.Path]::GetFullPath($StopFile)
        } else {
            [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $StopFile))
        }
        $stopDir = Split-Path -Parent $stopPath
        if (-not [string]::IsNullOrWhiteSpace($stopDir)) {
            New-Item -ItemType Directory -Force -Path $stopDir | Out-Null
        }
        Set-Content -LiteralPath $stopPath -Value "stop" -Encoding UTF8
    }

    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(1, $TimeoutSeconds))
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $remaining = Get-CimInstance Win32_Process |
            Where-Object {
                $_.ProcessId -ne $currentPid -and
                $_.Name -match "python|py" -and
                $_.CommandLine -like "*tools*dummy-companion-service.py*"
            }
        if (-not $remaining) {
            Write-Host "[OpenDAoC] Previous companion service stopped gracefully."
            return
        }
    }

    Write-Host "[OpenDAoC] Previous companion service did not exit in time; forcing stop..."
    $processes = Get-CimInstance Win32_Process |
        Where-Object {
            $_.ProcessId -ne $currentPid -and
            $_.Name -match "python|py" -and
            $_.CommandLine -like "*tools*dummy-companion-service.py*"
        }
    foreach ($process in $processes) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Wait-CompanionApi {
    param(
        [string]$ApiUrl,
        [int]$TimeoutSeconds
    )

    $probeUrl = "$($ApiUrl.TrimEnd('/'))/api/dummy/companions/config"
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(0, $TimeoutSeconds))
    $lastError = ""
    Write-Host "[OpenDAoC] Waiting for companion API..."
    while ($true) {
        try {
            $request = [System.Net.HttpWebRequest]::Create($probeUrl)
            $request.Method = "GET"
            $request.Timeout = 2000
            $request.ReadWriteTimeout = 2000
            $response = $request.GetResponse()
            try {
                $statusCode = [int]$response.StatusCode
                if ($statusCode -ge 200 -and $statusCode -lt 500) {
                    Write-Host "[OpenDAoC] Companion API is ready."
                    return
                }
                $lastError = "HTTP $statusCode"
            } finally {
                $response.Close()
            }
        } catch {
            $lastError = $_.Exception.Message
        }

        if ([DateTime]::UtcNow -ge $deadline) {
            throw "[OpenDAoC] Companion API not ready after ${TimeoutSeconds}s: $lastError"
        }
        Start-Sleep -Seconds 1
    }
}

$envFile = Get-EnvValue -Name "OPENDAOC_COMPANION_ENV_FILE" -Default (Join-Path $RepoRoot ".env")
Import-EnvFile -Path $envFile
Import-LocalApiPasswordFromDatabase

$python = Resolve-Python
$apiUrl = Get-EnvValue -Name "OPENDAOC_COMPANION_API_URL" -Default "http://localhost:5000"
$accountsCsv = Get-EnvValue -Name "OPENDAOC_COMPANION_ACCOUNTS" -Default "tools/dummy-live-companions.csv"
$runDir = Get-EnvValue -Name "OPENDAOC_COMPANION_RUN_DIR" -Default "test-output/live-companion-service"
$pollInterval = Get-EnvValue -Name "OPENDAOC_COMPANION_POLL_INTERVAL" -Default "3"
$maxRuntime = Get-EnvValue -Name "OPENDAOC_COMPANION_MAX_RUNTIME" -Default "0"
$hold = Get-EnvValue -Name "OPENDAOC_COMPANION_HOLD" -Default "3600"
$attachTimeout = Get-EnvValue -Name "OPENDAOC_COMPANION_ATTACH_TIMEOUT" -Default "35"
$leaseRefresh = Get-EnvValue -Name "OPENDAOC_COMPANION_LEASE_REFRESH_INTERVAL" -Default "30"
$activeStatusInterval = Get-EnvValue -Name "OPENDAOC_COMPANION_ACTIVE_REQUEST_STATUS_INTERVAL" -Default "15"
$combatHomeLeash = Get-EnvValue -Name "OPENDAOC_COMPANION_COMBAT_HOME_LEASH_DISTANCE" -Default "4500"
$aiGatewayConfig = Get-EnvValue -Name "OPENDAOC_COMPANION_AI_GATEWAY_CONFIG" -Default (Get-EnvValue -Name "OPENDAOC_AI_GATEWAY_CONFIG" -Default "tools/opendaoc-ai-gateway.json")
$aiGatewayAlias = Get-EnvValue -Name "OPENDAOC_COMPANION_AI_GATEWAY_MODEL_ALIAS" -Default "small-dialogue"
$aiGuideAlias = Get-EnvValue -Name "OPENDAOC_COMPANION_AI_GUIDE_MODEL_ALIAS" -Default "openai-small-guide"
$aiGatewayTimeout = Get-EnvValue -Name "OPENDAOC_COMPANION_AI_GATEWAY_TIMEOUT" -Default "5"
$dialogueMinInterval = Get-EnvValue -Name "OPENDAOC_COMPANION_DIALOGUE_MIN_INTERVAL" -Default "5"
$waitApiTimeout = [int](Get-EnvValue -Name "OPENDAOC_COMPANION_WAIT_API_TIMEOUT" -Default "90")
$stopFile = Get-EnvValue -Name "OPENDAOC_COMPANION_STOP_FILE" -Default (Join-Path $runDir "companion-service.stop")

Push-Location $RepoRoot
try {
    if (-not (Test-Path -LiteralPath $accountsCsv)) {
        throw "[OpenDAoC] Missing companion account pool: $accountsCsv"
    }

    if (Get-EnvBool -Name "OPENDAOC_COMPANION_STOP_EXISTING" -Default "1") {
        Stop-ExistingCompanionService -StopFile $stopFile
    }

    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
    if (Test-Path -LiteralPath $stopFile) {
        Remove-Item -LiteralPath $stopFile -Force
    }

    Write-Host "[OpenDAoC] Starting live companion service."
    Write-Host "[OpenDAoC] API: $apiUrl"
    Write-Host "[OpenDAoC] Accounts: $accountsCsv"
    Write-Host "[OpenDAoC] Run dir: $runDir"

    if (Get-EnvBool -Name "OPENDAOC_COMPANION_WAIT_API" -Default "1") {
        Wait-CompanionApi -ApiUrl $apiUrl -TimeoutSeconds $waitApiTimeout
    }

    $command = @(
        "tools/dummy-companion-service.py",
        "--api-url", $apiUrl,
        "--accounts-csv", $accountsCsv,
        "--run-dir", $runDir,
        "--poll-interval", $pollInterval,
        "--max-runtime", $maxRuntime,
        "--hold", $hold,
        "--attach-timeout", $attachTimeout,
        "--active-lease-refresh-interval", $leaseRefresh,
        "--active-request-status-interval", $activeStatusInterval,
        "--combat-home-leash-distance", $combatHomeLeash,
        "--ai-gateway-model-alias", $aiGatewayAlias,
        "--ai-guide-model-alias", $aiGuideAlias,
        "--ai-gateway-timeout", $aiGatewayTimeout,
        "--dialogue-min-interval", $dialogueMinInterval,
        "--stop-file", $stopFile
    )

    if (-not [string]::IsNullOrWhiteSpace($aiGatewayConfig)) {
        $command += @("--ai-gateway-config", $aiGatewayConfig)
    }

    $command += if (Get-EnvBool -Name "OPENDAOC_COMPANION_ATTACH_GROUP" -Default "1") { "--attach-group" } else { "--no-attach-group" }
    $dialogueEnabled = Get-EnvBool -Name "OPENDAOC_COMPANION_DIALOGUE_ENABLED" -Default "0"
    $guideDefault = if ($dialogueEnabled) { "1" } else { "0" }
    $command += if ($dialogueEnabled) { "--dialogue-enabled" } else { "--no-dialogue-enabled" }
    $command += if (Get-EnvBool -Name "OPENDAOC_COMPANION_GUIDE_ENABLED" -Default $guideDefault) { "--guide-enabled" } else { "--no-guide-enabled" }

    if (Get-EnvBool -Name "OPENDAOC_COMPANION_ONCE" -Default "0") {
        $command += "--once"
    }
    if (Get-EnvBool -Name "OPENDAOC_COMPANION_DRY_RUN" -Default "0") {
        $command += "--dry-run"
    }

    & $python @command
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
