@echo off
chcp 65001 >nul

title OpenDAoC Build Server

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "REPO_WIN=%%~fI"
set "REPO_SLASH=%REPO_WIN:\=/%"
set "REPO_WSL=/mnt/c%REPO_SLASH:~2%"

echo ============================================
echo OpenDAoC CoreServer Build
echo ============================================
echo.

C:\Windows\System32\wsl.exe -d Ubuntu --cd "%REPO_WSL%" --exec /bin/bash -lc "/home/bigjuh/.dotnet/dotnet build CoreServer/CoreServer.csproj -c Debug 2>&1; rc=$?; echo BUILD_EXIT_CODE=$rc; exit $rc"

echo.
echo ============================================
if %ERRORLEVEL% EQU 0 (
    echo BUILD SUCCESS
) else (
    echo BUILD FAILED
)
echo ============================================

if /I "%OPENDAOC_PAUSE_ON_EXIT%"=="1" (
    pause >nul
)
exit /b %ERRORLEVEL%
