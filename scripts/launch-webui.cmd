@echo off
setlocal EnableExtensions
call "%~dp0_env.cmd"

set "WEBUI_PORT=8764"
set "WEBUI_URL=http://127.0.0.1:%WEBUI_PORT%"

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
    echo [INFO] Web UI is already running on %WEBUI_URL%
    call :open_browser "%WEBUI_URL%"
    exit /b 0
)

for /f %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "[DateTime]::Now.ToString('yyyyMMdd-HHmmss')"' ) do set "STAMP=%%I"
if not defined STAMP set "STAMP=unknown"
set "LOG_FILE=%LOGS_DIR%\webui-%STAMP%.log"

echo [INFO] Starting local Web UI on %WEBUI_URL%
start "USB Code Assistant Web UI" /min cmd /c ""%WINPY_PYTHON%" "%ROOT_DIR%\webui\server.py" --port %WEBUI_PORT% > "%LOG_FILE%" 2>&1"

call :wait_for_webui %WEBUI_PORT%
if errorlevel 1 (
    echo [ERROR] Web UI failed to become ready. Check the log:
    echo         "%LOG_FILE%"
    exit /b 1
)

echo [OK] Web UI is ready at %WEBUI_URL%
call :open_browser "%WEBUI_URL%"
exit /b 0

:port_occupied
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $listener = Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction Stop; if ($listener) { exit 0 } else { exit 1 } } catch { exit 1 }"
exit /b %ERRORLEVEL%

:wait_for_webui
set /a RETRIES=30

:wait_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:%~1/api/status' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 exit /b 0

set /a RETRIES-=1
if %RETRIES% LEQ 0 exit /b 1

timeout /t 1 /nobreak >nul
goto wait_loop

:open_browser
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '%~1'"
exit /b 0
