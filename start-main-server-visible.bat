@echo off
chcp 65001 >nul

title OpenDAoC Launcher %RANDOM%%RANDOM%

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "REPO_WIN=%%~fI"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%tools\cleanup-main-server-windows.ps1" >nul 2>nul

title OpenDAoC Main Server

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%tools\start-main-visible-server-windows.ps1" -RepoRoot "%REPO_WIN%"
if /I "%OPENDAOC_PAUSE_ON_EXIT%"=="1" (
    echo.
    echo Server stopped. Press any key to close this window.
    pause >nul
)
exit /b
