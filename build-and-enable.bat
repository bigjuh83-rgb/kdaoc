@echo off
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "REPO_WIN=%%~fI"
set "REPO_SLASH=%REPO_WIN:\=/%"
set "REPO_WSL=/mnt/c%REPO_SLASH:~2%"

echo.
echo ============================================
echo [1/3] Building GameServer...
echo ============================================
C:\Windows\System32\wsl.exe -d Ubuntu --cd "%REPO_WSL%" --exec /bin/bash -lc "export LANG=C.UTF-8; exec /home/bigjuh/.dotnet/dotnet build GameServer/GameServer.csproj -c Debug"
if %ERRORLEVEL% NEQ 0 (
    echo BUILD FAILED
    pause
    exit /b 1
)
echo BUILD OK

echo.
echo ============================================
echo [2/3] Enabling dialogue in DB...
echo ============================================
C:\Windows\System32\wsl.exe -d Ubuntu -- bash -c "mariadb --protocol=tcp -h 127.0.0.1 -P 3306 -uroot -pzmstkfka83 opendaoc -e \"UPDATE ServerProperty SET Value = 'True' WHERE \\\`Key\\\` = 'dummy_companion_dialogue_enabled';\""
if %ERRORLEVEL% EQU 0 (
    echo DB UPDATE OK
    C:\Windows\System32\wsl.exe -d Ubuntu -- bash -c "mariadb --protocol=tcp -h 127.0.0.1 -P 3306 -uroot -pzmstkfka83 opendaoc -e \"SELECT \\\`Key\\\`, Value FROM ServerProperty WHERE \\\`Key\\\` = 'dummy_companion_dialogue_enabled';\""
) else (
    echo DB UPDATE FAILED - MariaDB might not be running. Start server first.
)

echo.
echo ============================================
echo [3/3] Ready. Now run:
echo   start-main-server-visible.bat
echo   start-live-companion-service-visible.bat
echo ============================================

if /I "%OPENDAOC_PAUSE_ON_EXIT%"=="1" pause >nul
exit /b 0
