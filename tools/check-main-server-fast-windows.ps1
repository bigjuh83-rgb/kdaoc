param(
    [int]$GamePort = 10300,
    [int]$UdpPort = 10400,
    [int]$DbPort = 3306,
    [int]$ApiPort = $(if ($env:OPENDAOC_API_PORT) { [int]$env:OPENDAOC_API_PORT } else { 5000 })
)

$ok = $true

function Test-TcpListen {
    param([int]$Port)
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        return $true
    }

    return [bool](netstat -ano | Select-String -SimpleMatch "TCP    0.0.0.0:$Port" | Select-String -SimpleMatch "LISTENING")
}

function Test-UdpListen {
    param([int]$Port)
    if (Get-NetUDPEndpoint -LocalPort $Port -ErrorAction SilentlyContinue) {
        return $true
    }

    return [bool](netstat -ano | Select-String -SimpleMatch "UDP    0.0.0.0:$Port")
}

if (Test-TcpListen $GamePort) {
    Write-Host "OK tcp $GamePort"
} else {
    Write-Host "DOWN tcp $GamePort"
    $ok = $false
}

if (Test-UdpListen $UdpPort) {
    Write-Host "OK udp $UdpPort"
} else {
    Write-Host "DOWN udp $UdpPort"
    $ok = $false
}

if (Test-TcpListen $DbPort) {
    Write-Host "OK db $DbPort"
} else {
    Write-Host "DOWN db $DbPort"
    $ok = $false
}

try {
    $uri = "http://127.0.0.1:$ApiPort/api/world/dynamic-quests/story-config"
    Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2 | Out-Null
    Write-Host "OK api $ApiPort"
} catch {
    Write-Host "DOWN api $ApiPort"
    $ok = $false
}

if ($ok) {
    exit 0
}

exit 1
