@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start-preservice-growth-variant-lanes-visible.ps1" %*
exit /b %ERRORLEVEL%
