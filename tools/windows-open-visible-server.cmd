@echo off
chcp 65001 >nul
title OpenDAoC Visible Server

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_WIN=%%~fI"

set "REPO_SLASH=%REPO_WIN:\=/%"
set "REPO_WSL=/mnt/c%REPO_SLASH:~2%"

echo OpenDAoC visible server console
echo Repo: %REPO_WIN%
echo WSL:  %REPO_WSL%
echo.
echo This window is the server console. Close it only when you want to stop watching it.
echo.

wsl.exe -e bash -lc "set -e; cd '%REPO_WSL%'; DB_ROOT='/home/bigjuh/.local/opendaoc-mariadb'; MYSQLD=\"$DB_ROOT/current/bin/mariadbd\"; MYSQLADMIN=\"$DB_ROOT/current/bin/mariadb-admin\"; MY_CNF=\"$DB_ROOT/etc/my.cnf\"; if ! ss -ltn | grep -q ':3306 '; then echo '[OpenDAoC] Starting local MariaDB...'; nohup \"$MYSQLD\" --defaults-file=\"$MY_CNF\" --console >> \"$DB_ROOT/logs/mariadb.console.log\" 2>&1 & for i in {1..30}; do if \"$MYSQLADMIN\" --protocol=tcp -h 127.0.0.1 -P 3306 -uroot -pmy-secret-pw ping >/dev/null 2>&1; then break; fi; sleep 1; done; fi; echo '[OpenDAoC] Starting game server on 127.0.0.1:10300...'; DB_PASSWORD='my-secret-pw' DOTNET_BIN='/home/bigjuh/.dotnet/dotnet' tools/run-local-server.sh --skip-build"

echo.
echo OpenDAoC server process ended.
pause
