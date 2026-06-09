# Local MariaDB + .NET Server Runbook

This runbook is for running OpenDAoC-Core without Docker, using the local `OpenDAoC-Database` folder and the .NET 10 SDK.

## Folder Layout

Expected local layout:

```text
/mnt/c/Users/uihan/Desktop/다옥프리서버/
  OpenDAoC-Core/
  OpenDAoC-Database/
  OpenDAoCClient/
  DOLSharp-master/        # reference only; do not run this as the live server
```

Use `OpenDAoC-Core` as the server repo. `DOLSharp-master` is an old reference server only.

## Prerequisites

Install or confirm:

```bash
dotnet --list-sdks
mariadb --version
```

The project targets `net10.0`, so the active SDK must include .NET 10.

For MariaDB, the Docker setup used these important defaults:

```text
database: opendaoc
user: root
password: opendaoc-local
host: 127.0.0.1
port: 3306
```

If MariaDB is installed inside Linux/WSL, table-name case sensitivity can matter. The Docker setup used `lower_case_table_names=1`. On Windows MariaDB this is usually already case-insensitive, but on Linux it must be set before the database directory is initialized.

## Standard Main-Computer Restart

Use this single path for routine main-computer server restarts:

```text
C:\Users\uihan\Desktop\다옥프리서버\OpenDAoC-Core\start-main-server-visible.bat
```

This batch file is the standard entrypoint. It closes old OpenDAoC visible
server consoles, starts the WSL local MariaDB if needed, stops any old
`CoreServer.dll --start` process inside WSL, and then starts the main server in
a visible Windows console.

Do not use ad-hoc commands such as `dotnet CoreServer.dll --start` for routine
main-computer testing. Direct `dotnet` launches are only for short diagnostics,
and they must be stopped before returning to normal testing.

Fast status check:

```text
C:\Users\uihan\Desktop\다옥프리서버\OpenDAoC-Core\check-main-server-fast.bat
```

The expected quick result is `OK tcp 10300`, `OK udp 10400`, and `OK db 3306`.
If the game port is down, restart with `start-main-server-visible.bat` instead
of searching for a new launch command.

Windows cleanup logic lives in:

```text
C:\Users\uihan\Desktop\다옥프리서버\OpenDAoC-Core\tools\cleanup-main-server-windows.ps1
```

Keep this cleanup in a `.ps1` file and call it with PowerShell `-File`. Do not
copy the cleanup pipeline into a Bash double-quoted `powershell -Command`
string, because shell expansion can change PowerShell variables before
PowerShell receives the command.

## One-Command Local Start

From `OpenDAoC-Core`:

```bash
DB_PASSWORD='opendaoc-local' tools/run-local-server.sh
```

If `dotnet` is not on the WSL `PATH`, the script will fall back to:

```text
/home/bigjuh/.dotnet/dotnet
```

What the script does:

- prepares `CoreServer/config/serverconfig.xml` from the example if it is missing
- points the config at local MariaDB
- disables UPnP for local testing
- builds `CoreServer/CoreServer.csproj`
- starts `Debug/CoreServer.dll --start` from the `Debug` output folder

The server is up when the console shows:

```text
Server is now listening for incoming connections
GameServer startup completed
```

To stop it, type:

```text
exit
```

## First Database Import

If the local `opendaoc` database is empty, import the SQL from the adjacent database repo:

```bash
DB_PASSWORD='opendaoc-local' tools/run-local-server.sh --init-db --no-run
```

This imports:

```text
../OpenDAoC-Database/opendaoc-db-core/*.sql
```

Only use `--init-db` for initial setup or deliberate re-imports. Existing data can conflict with schema/data already loaded into the database.

## Manual Config

The config file is:

```text
CoreServer/config/serverconfig.xml
```

The key values for local MariaDB are:

```xml
<DBType>MYSQL</DBType>
<DBConnectionString>Server=127.0.0.1;Port=3306;Database=opendaoc;UserId=root;Password=opendaoc-local;TreatTinyAsBoolean=false;Pooling=true;MinimumPoolSize=0;MaximumPoolSize=60;ConnectionReset=false;CharSet=utf8mb4</DBConnectionString>
<ScriptCompilationTarget>./lib/GameServerScripts.dll</ScriptCompilationTarget>
<EnableCompilation>True</EnableCompilation>
<AutoAccountCreation>True</AutoAccountCreation>
```

Build copies this config into:

```text
Debug/config/serverconfig.xml
```

Run the server from the output folder so relative paths such as `./config/logconfig.xml`, `./languages`, and `./lib/GameServerScripts.dll` resolve correctly:

```bash
dotnet build CoreServer/CoreServer.csproj -c Debug
cd Debug
dotnet CoreServer.dll --start
```

## Useful Variants

Use a different DB password:

```bash
DB_PASSWORD='your-password' tools/run-local-server.sh
```

Use a different DB user:

```bash
DB_USER='opendaoc' DB_PASSWORD='your-password' tools/run-local-server.sh
```

Use a local MariaDB account with no password:

```bash
DB_PASSWORD='' tools/run-local-server.sh
```

Tune local MariaDB connection pooling:

```bash
DB_MIN_POOL_SIZE=0 DB_MAX_POOL_SIZE=60 tools/run-local-server.sh
```

For the portable local MariaDB setup, keep `DB_MIN_POOL_SIZE=0`. A high minimum
pool size can create too many startup connections while the server registers
database tables.

Prepare config/build without starting:

```bash
tools/run-local-server.sh --no-run
```

Start without rebuilding:

```bash
tools/run-local-server.sh --skip-build
```

## Local Korean Checks

Before a real client test:

```bash
tools/check-localization.sh --build
```

Then start the server and test Korean display with:

```text
/language kr
/kotest
```

`/kotest` should print Korean in system/chat/popup/custom text windows.

## Public Dashboard

Enable the Atlas API and periodic stat saving before using the public dashboard:

- `atlas_api=True`
- `statsave_interval=1`

Dashboard URLs:

- `http://<server-host>:<api-port>/dashboard`
- `http://<server-host>:<api-port>/api/dashboard/live`
- `http://<server-host>:<api-port>/api/dashboard/history?range=24h`
- `http://<server-host>:<api-port>/api/dashboard/realm-activity?range=7d`
- `http://<server-host>:<api-port>/status/badge.png`

For Naver Cafe, use `/status/badge.png` as a plain image and link the image to `/dashboard` if the cafe editor allows image links. The badge does not require JavaScript or iframe support. Include the API port in both URLs when the dashboard is not served on port 80/443:

```html
<a href="http://<public-ip>:<api-port>/dashboard" target="_blank">
  <img src="http://<public-ip>:<api-port>/status/badge.png" alt="KDAOC real-time population">
</a>
```

Do not use `https://<public-ip>/...` unless a valid HTTPS reverse proxy is already serving the dashboard. A raw HTTP Kestrel dashboard on port 5000 will not answer on HTTPS port 443.

Gold and realm point charts intentionally show server-issued inflow only. Player trades, consignment payouts, guild transfers, vault movement, removed money, and manual GM money/RP grants are excluded.

Quick smoke checks when a MariaDB-backed server is already running:

```bash
curl -I http://localhost:5000/dashboard
curl -s http://localhost:5000/api/dashboard/live
curl -s http://localhost:5000/api/dashboard/history?range=24h
curl -s http://localhost:5000/api/dashboard/realm-activity?range=7d
curl -I http://localhost:5000/status/badge.png
```
