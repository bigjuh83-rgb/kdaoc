@echo off
chcp 65001 >nul

title OpenDAoC Companion Launcher %RANDOM%%RANDOM%

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "REPO_WIN=%%~fI"
set "REPO_SLASH=%REPO_WIN:\=/%"
set "REPO_WSL=/mnt/c%REPO_SLASH:~2%"

title OpenDAoC Companion Service

rem WSL only forwards selected Windows environment variables through WSLENV.
if defined WSLENV (
    set "WSLENV=%WSLENV%:GEMINI_API_KEY/u:OPENAI_API_KEY/u:OPENDAOC_RAG_DATABASE_URL/u:OPENDAOC_RAG_EMBEDDING_BASE_URL/u"
) else (
    set "WSLENV=GEMINI_API_KEY/u:OPENAI_API_KEY/u:OPENDAOC_RAG_DATABASE_URL/u:OPENDAOC_RAG_EMBEDDING_BASE_URL/u"
)

C:\Windows\System32\wsl.exe -d Ubuntu --cd "%REPO_WSL%" --exec /bin/bash -lc "exec tools/start-live-companion-service.sh"
if /I "%OPENDAOC_COMPANION_PAUSE_ON_EXIT%"=="1" (
    echo.
    echo Companion service stopped. Press any key to close this window.
    pause >nul
)
exit /b
