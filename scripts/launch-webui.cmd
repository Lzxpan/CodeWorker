@echo off
setlocal EnableExtensions
call "%~dp0_env.cmd"

set "WEBUI_PORT=8764"
set "WEBUI_URL=http://127.0.0.1:%WEBUI_PORT%"
set "WEBUI_EXPECTED_VERSION=V1.02.000"
if exist "%ROOT_DIR%\VERSION" (
    set /p WEBUI_EXPECTED_VERSION=<"%ROOT_DIR%\VERSION"
)

if not exist "%WINPY_PYTHON%" (
    echo [INFO] Portable Python not found. Running bootstrap first...
    call "%~dp0bootstrap.cmd" -SkipModels
    if errorlevel 1 (
        echo [ERROR] Bootstrap failed while preparing portable Python.
        exit /b 1
    )
)

if not exist "%WINPY_PYTHON%" (
    echo [ERROR] Portable Python not found: "%WINPY_PYTHON%"
    exit /b 1
)

call :port_occupied %WEBUI_PORT%
if not errorlevel 1 (
    echo [INFO] Web UI is already running on %WEBUI_URL%. Restarting CodeWorker Web UI to load the current files...
    call :reclaim_webui_port %WEBUI_PORT% "%ROOT_DIR%"
    if errorlevel 1 (
        echo [ERROR] Port %WEBUI_PORT% is occupied by another process. Stop it first, then run launch-webui.cmd again.
        exit /b 1
    )
)

for /f %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "[DateTime]::Now.ToString('yyyyMMdd-HHmmss')"' ) do set "STAMP=%%I"
if not defined STAMP set "STAMP=unknown"
set "LOG_FILE=%LOGS_DIR%\webui-%STAMP%.log"
set "WEBUI_OPEN_URL=%WEBUI_URL%/?v=%WEBUI_EXPECTED_VERSION%-%STAMP%"

echo [INFO] Starting local Web UI on %WEBUI_URL%
echo [INFO] Expected Web UI version: %WEBUI_EXPECTED_VERSION%
echo [INFO] Root directory: %ROOT_DIR%
echo [INFO] Server script: %ROOT_DIR%\webui\server.py
start "USB Code Assistant Web UI" /min cmd /c ""%WINPY_PYTHON%" "%ROOT_DIR%\webui\server.py" --port %WEBUI_PORT% > "%LOG_FILE%" 2>&1"

call :wait_for_webui %WEBUI_PORT% "%WEBUI_EXPECTED_VERSION%"
if errorlevel 1 (
    echo [ERROR] Web UI failed to become ready. Check the log:
    echo         "%LOG_FILE%"
    exit /b 1
)

echo [OK] Web UI is ready at %WEBUI_URL%
call :open_browser "%WEBUI_OPEN_URL%"
exit /b 0

:port_occupied
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $listener = Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction Stop; if ($listener) { exit 0 } else { exit 1 } } catch { exit 1 }"
exit /b %ERRORLEVEL%

:reclaim_webui_port
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $port=[int]'%~1'; $root=(Resolve-Path -LiteralPath '%~2').Path.ToLowerInvariant(); $listeners=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($ownerPid in $listeners) { $proc=Get-CimInstance Win32_Process -Filter \"ProcessId=$ownerPid\"; $cmd=($proc.CommandLine + '').ToLowerInvariant(); $isCodeWorker=$cmd.Contains('webui\server.py') -and $cmd.Contains($root); if (-not $isCodeWorker) { Write-Host ('[ERROR] Port {0} is owned by PID {1}: {2}' -f $port, $ownerPid, $proc.CommandLine); exit 2 }; Stop-Process -Id $ownerPid -Force }; for ($i=0; $i -lt 10; $i++) { Start-Sleep -Milliseconds 500; $still=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if (-not $still) { exit 0 } }; exit 3"
exit /b %ERRORLEVEL%

:wait_for_webui
set /a RETRIES=30

:wait_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $status=Invoke-RestMethod -Uri 'http://127.0.0.1:%~1/api/status' -TimeoutSec 2; $expected='%~2'; if (-not $expected -or $status.data.appVersion -eq $expected) { exit 0 }; Write-Host ('[WAIT] Web UI responded with version {0}, expected {1}.' -f $status.data.appVersion, $expected); exit 1 } catch { exit 1 }"
if not errorlevel 1 exit /b 0

set /a RETRIES-=1
if %RETRIES% LEQ 0 exit /b 1

timeout /t 1 /nobreak >nul
goto wait_loop

:open_browser
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '%~1'"
exit /b 0
