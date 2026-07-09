@echo off
chcp 65001 >nul
title OpenDAoC Fast Status

set "SCRIPT_DIR=%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%tools\check-main-server-fast-windows.ps1"
if /I not "%CODEX_SHELL%"=="1" (
    echo.
    pause
)
