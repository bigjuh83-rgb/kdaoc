@echo off
chcp 65001 >nul

title OpenDAoC Companion Launcher %RANDOM%%RANDOM%

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "REPO_WIN=%%~fI"

title OpenDAoC Companion Service

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%tools\start-live-companion-service-windows.ps1" -RepoRoot "%REPO_WIN%"
if /I "%OPENDAOC_COMPANION_PAUSE_ON_EXIT%"=="1" (
    echo.
    echo Companion service stopped. Press any key to close this window.
    pause >nul
)
exit /b
