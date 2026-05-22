@echo off
chcp 65001 >nul
title OpenDAoC Fast Status

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "REPO_WIN=%%~fI"
set "REPO_SLASH=%REPO_WIN:\=/%"
set "REPO_WSL=/mnt/c%REPO_SLASH:~2%"

C:\Windows\System32\wsl.exe -d Ubuntu --cd "%REPO_WSL%" --exec /bin/bash -lc "exec tools/check-main-server-fast.sh"
echo.
pause
