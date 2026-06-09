@echo off
setlocal
cd /d "%~dp0.."
wsl bash -lc "cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' && python3 tools/run-multi-dummy-movement-session.py %*"
exit /b %ERRORLEVEL%
