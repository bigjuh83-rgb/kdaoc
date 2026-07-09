param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

function Resolve-RequiredFile {
    param(
        [string[]]$Candidates,
        [string]$Name
    )

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "$Name was not found."
}

function Test-TcpListen {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-StaleCoreServer {
    $currentPid = $PID
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.ProcessId -ne $currentPid -and
            $_.Name -in @("dotnet.exe", "CoreServer.exe") -and
            $_.CommandLine -match "CoreServer(\.dll|\.exe)" -and
            $_.CommandLine -match "--start"
        } |
        ForEach-Object {
            Write-Host "[OpenDAoC] stopping stale CoreServer pid=$($_.ProcessId)"
            taskkill.exe /F /T /PID $_.ProcessId | Out-Null
        }
}

function Ensure-MariaDb {
    if (Test-TcpListen 3306) {
        Write-Host "[OpenDAoC] MariaDB already listening on 3306."
        return
    }

    $mariadbd = Resolve-RequiredFile -Name "mariadbd.exe" -Candidates @(
        "C:\Program Files\MariaDB 12.3\bin\mariadbd.exe",
        "C:\Program Files\MariaDB 12.2\bin\mariadbd.exe",
        "C:\Program Files\MariaDB 12.1\bin\mariadbd.exe",
        "C:\Program Files\MariaDB 11.8\bin\mariadbd.exe"
    )
    $myIni = Resolve-RequiredFile -Name "MariaDB my.ini" -Candidates @(
        "C:\Program Files\MariaDB 12.3\data\my.ini",
        "C:\Program Files\MariaDB 12.2\data\my.ini",
        "C:\Program Files\MariaDB 12.1\data\my.ini",
        "C:\Program Files\MariaDB 11.8\data\my.ini"
    )

    Write-Host "[OpenDAoC] starting MariaDB..."
    Start-Process -FilePath $mariadbd -ArgumentList @("--defaults-file=""$myIni""", "--console") -WindowStyle Hidden | Out-Null

    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpListen 3306) {
            Write-Host "[OpenDAoC] MariaDB is listening on 3306."
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw "MariaDB did not open port 3306 in time."
}

$dotnet = Resolve-RequiredFile -Name "dotnet.exe" -Candidates @(
    "C:\Program Files\dotnet\dotnet.exe",
    "C:\Program Files (x86)\dotnet\dotnet.exe",
    (Get-Command dotnet -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
)

Push-Location $RepoRoot
try {
    if (Test-Path -LiteralPath (Join-Path $RepoRoot "tools\cleanup-main-server-windows.ps1")) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "tools\cleanup-main-server-windows.ps1") | Out-Null
    }

    Stop-StaleCoreServer
    Ensure-MariaDb

    Write-Host "[OpenDAoC] building CoreServer..."
    & $dotnet build "CoreServer\CoreServer.csproj" -c Debug
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    if ($env:OPENDAOC_START_COMPANION_SERVICE -ne "0") {
        $waiter = Join-Path $RepoRoot "tools\start-companion-after-api-ready.ps1"
        if (Test-Path -LiteralPath $waiter) {
            Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $waiter, "-RepoRoot", $RepoRoot) -WindowStyle Hidden | Out-Null
        }
    }

    Write-Host "[OpenDAoC] starting CoreServer..."
    Push-Location (Join-Path $RepoRoot "Debug")
    try {
        & $dotnet "CoreServer.dll" "--start"
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
}
