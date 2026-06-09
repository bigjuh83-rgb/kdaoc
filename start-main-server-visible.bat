@echo off
chcp 65001 >nul

title OpenDAoC Launcher %RANDOM%%RANDOM%

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "REPO_WIN=%%~fI"
set "REPO_SLASH=%REPO_WIN:\=/%"
set "REPO_WSL=/mnt/c%REPO_SLASH:~2%"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%tools\cleanup-main-server-windows.ps1" >nul 2>nul

rem WSL only forwards selected Windows environment variables through WSLENV.
if defined WSLENV (
    set "WSLENV=%WSLENV%:GEMINI_API_KEY/u:OPENAI_API_KEY/u:OPENDAOC_RAG_DATABASE_URL/u:OPENDAOC_RAG_EMBEDDING_BASE_URL/u"
) else (
    set "WSLENV=GEMINI_API_KEY/u:OPENAI_API_KEY/u:OPENDAOC_RAG_DATABASE_URL/u:OPENDAOC_RAG_EMBEDDING_BASE_URL/u"
)

if /I not "%OPENDAOC_START_COMPANION_SERVICE%"=="0" (
    start "OpenDAoC Companion API Waiter" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%tools\start-companion-after-api-ready.ps1" -RepoRoot "%REPO_WIN%"
)

title OpenDAoC Main Server

C:\Windows\System32\wsl.exe -d Ubuntu --cd "%REPO_WSL%" --exec /bin/bash -lc "exec tools/start-main-visible-server.sh"
if /I "%OPENDAOC_PAUSE_ON_EXIT%"=="1" (
    echo.
    echo Server stopped. Press any key to close this window.
    pause >nul
)
exit /b
