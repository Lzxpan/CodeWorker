@echo off
setlocal EnableExtensions
call "%~dp0_env.cmd"

set "MODEL_KEY=%~1"
if "%MODEL_KEY%"=="" set "MODEL_KEY=gemma4"

set "PORT=%~2"
set "CONTEXT_SIZE=%~3"

for /f %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "[DateTime]::Now.ToString('yyyyMMdd-HHmmss')"' ) do set "STAMP=%%I"
if not defined STAMP set "STAMP=unknown"

set "LOG_FILE=%LOGS_DIR%\llama-server-%MODEL_KEY%-%STAMP%.log"
set "ERR_FILE=%LOGS_DIR%\llama-server-%MODEL_KEY%-%STAMP%.err.log"
echo [LOG_FILE] %LOG_FILE%

if not exist "%LLAMA_SERVER%" (
    echo [INFO] llama-server.exe not found. Running bootstrap runtime setup...
    call "%~dp0bootstrap.cmd" -SkipModels
    if errorlevel 1 (
        call :emit_error RUNTIME_MISSING "Bootstrap failed while preparing llama.cpp runtime." "%LLAMA_SERVER%"
        exit /b 1
    )
)

if not exist "%LLAMA_SERVER%" (
    call :emit_error RUNTIME_MISSING "llama-server.exe not found." "%LLAMA_SERVER%"
    exit /b 1
)

call :resolve_model "%MODEL_KEY%"
if errorlevel 1 exit /b 1

if "%PORT%"=="" set "PORT=%MODEL_PORT%"
if "%CONTEXT_SIZE%"=="" set "CONTEXT_SIZE=%MODEL_CONTEXT%"
set "CACHE_ARGS="
if defined MODEL_CACHE_TYPE_K set "CACHE_ARGS=%CACHE_ARGS% --cache-type-k %MODEL_CACHE_TYPE_K%"
if defined MODEL_CACHE_TYPE_V set "CACHE_ARGS=%CACHE_ARGS% --cache-type-v %MODEL_CACHE_TYPE_V%"

call :check_memory
if errorlevel 1 exit /b 1

echo [INFO] Validating llama-server runtime...
"%LLAMA_SERVER%" --version >nul 2>&1
if errorlevel 1 (
    call :emit_error RUNTIME_INVALID "llama-server.exe failed to start." "The host may lack required CPU features such as AVX2, or the runtime is incomplete."
    exit /b 1
)

set "NEED_MODEL_BOOTSTRAP=0"
if "%MODEL_FILE%"=="" (
    set "NEED_MODEL_BOOTSTRAP=1"
) else (
    if not exist "%MODEL_FILE%" set "NEED_MODEL_BOOTSTRAP=1"
)
if defined MODEL_MMPROJ_PATTERNS if "%MODEL_MMPROJ%"=="" set "NEED_MODEL_BOOTSTRAP=1"
if defined MODEL_MMPROJ if not exist "%MODEL_MMPROJ%" set "NEED_MODEL_BOOTSTRAP=1"
if "%NEED_MODEL_BOOTSTRAP%"=="1" (
    echo [INFO] Model file not found. Running bootstrap for model "%MODEL_KEY%"...
    call "%~dp0bootstrap.cmd" -SkipRuntime -Models "%MODEL_KEY%"
    if errorlevel 1 (
        call :emit_error MODEL_MISSING "Bootstrap failed while preparing model." "%MODEL_DIR%"
        exit /b 1
    )
    call :resolve_model "%MODEL_KEY%"
    if errorlevel 1 exit /b 1
)

if "%MODEL_FILE%"=="" (
    call :emit_error MODEL_MISSING "Model file not found after bootstrap." "%MODEL_DIR% patterns=%MODEL_FILE_PATTERNS%"
    exit /b 1
)
if defined MODEL_MMPROJ_PATTERNS if "%MODEL_MMPROJ%"=="" (
    call :emit_error MODEL_MISSING "Model mmproj file not found after bootstrap." "%MODEL_DIR% patterns=%MODEL_MMPROJ_PATTERNS%"
    exit /b 1
)

if defined MODEL_MMPROJ (
    echo [INFO] Resolved mmproj file: "%MODEL_MMPROJ%"
    call :validate_model_file "%MODEL_MMPROJ%"
    if errorlevel 1 exit /b 1
)

echo [INFO] Resolved model file: "%MODEL_FILE%"
call :validate_model_file "%MODEL_FILE%"
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:%PORT%/v1/models' -TimeoutSec 2; if ($resp.data | Where-Object { $_.id -eq '%MODEL_ALIAS%' }) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 (
    echo [OK] Server already running on port %PORT% with model "%MODEL_ALIAS%".
    exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $listener = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction Stop; if ($listener) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 (
    call :emit_error MODEL_START_FAILED "Port is already in use." "Port %PORT% is occupied by another process."
    exit /b 1
)

echo [INFO] Starting llama-server with "%MODEL_FILE%"
if not exist "%WINPY_PYTHON%" (
    call :emit_error RUNTIME_MISSING "Portable Python runtime not found." "%WINPY_PYTHON%"
    exit /b 1
)
if defined MODEL_MMPROJ (
    start "" /b "%WINPY_PYTHON%" "%~dp0launch_llama_server.py" --server "%LLAMA_SERVER%" --host 127.0.0.1 --port "%PORT%" --alias "%MODEL_ALIAS%" --model "%MODEL_FILE%" --mmproj "%MODEL_MMPROJ%" --context "%CONTEXT_SIZE%" %CACHE_ARGS% --threads "%NUMBER_OF_PROCESSORS%" --log "%LOG_FILE%" --err "%ERR_FILE%" >nul 2>nul
) else (
    start "" /b "%WINPY_PYTHON%" "%~dp0launch_llama_server.py" --server "%LLAMA_SERVER%" --host 127.0.0.1 --port "%PORT%" --alias "%MODEL_ALIAS%" --model "%MODEL_FILE%" --context "%CONTEXT_SIZE%" %CACHE_ARGS% --threads "%NUMBER_OF_PROCESSORS%" --log "%LOG_FILE%" --err "%ERR_FILE%" >nul 2>nul
)

set /a RETRIES=30
:wait_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:%PORT%/v1/models' -TimeoutSec 2; if ($resp.data | Where-Object { $_.id -eq '%MODEL_ALIAS%' }) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 goto ready

set /a RETRIES-=1
if %RETRIES% LEQ 0 (
    call :emit_error MODEL_START_FAILED "Server failed to become ready." "%LOG_FILE%"
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2" >nul
goto wait_loop

:ready
echo [OK] Server is ready on http://127.0.0.1:%PORT%/v1
echo [INFO] Model alias: %MODEL_ALIAS%
echo [INFO] Log file: "%LOG_FILE%"
if exist "%ERR_FILE%" echo [INFO] Error log: "%ERR_FILE%"
exit /b 0

:resolve_model
set "MODEL_MMPROJ="
set "MODEL_MMPROJ_PATTERNS="
set "MODEL_FILE_PATTERNS="
set "RESOLVE_PYTHON=%WINPY_PYTHON%"
if not exist "%RESOLVE_PYTHON%" set "RESOLVE_PYTHON=python"
set "MODEL_ENV_FILE=%TEMP%\codeworker-model-env-%RANDOM%-%RANDOM%.cmd"
"%RESOLVE_PYTHON%" "%~dp0resolve_model_env.py" "%~1" > "%MODEL_ENV_FILE%"
if errorlevel 1 (
    type "%MODEL_ENV_FILE%" 2>nul
    del "%MODEL_ENV_FILE%" >nul 2>nul
    call :emit_error MODEL_START_FAILED "Unknown model." "%~1"
    exit /b 1
)
findstr /b /c:"[ERROR_" "%MODEL_ENV_FILE%" >nul
if not errorlevel 1 (
    type "%MODEL_ENV_FILE%"
    del "%MODEL_ENV_FILE%" >nul 2>nul
    call :emit_error MODEL_START_FAILED "Unknown model." "%~1"
    exit /b 1
)
call "%MODEL_ENV_FILE%"
del "%MODEL_ENV_FILE%" >nul 2>nul
if "%MODEL_DIR%"=="" (
    call :emit_error MODEL_START_FAILED "Unknown model." "%~1"
    exit /b 1
)
exit /b 0

:check_memory
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $recommended = 32GB; $total = [int64](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory; if ($total -gt 0 -and $total -lt $recommended) { Write-Host ('[WARN] Recommended system memory for larger local models is 32GB RAM or above. Detected: {0:N1} GB' -f ($total / 1GB)); Write-Host '[WARN] Integrated graphics may reduce available system memory.' }; exit 0 } catch { Write-Host '[WARN] Unable to determine total physical memory; skipping RAM check.'; exit 0 }"
exit /b %ERRORLEVEL%

:validate_model_file
if not exist "%~1" (
    call :emit_error MODEL_MISSING "Model file not found." "%~1"
    exit /b 1
)
for %%F in ("%~1") do set "MODEL_SIZE=%%~zF"
if "%MODEL_SIZE%"=="0" (
    call :emit_error MODEL_INVALID "Model file is empty." "%~1"
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $stream = [System.IO.File]::Open('%~1', 'Open', 'Read', 'ReadWrite'); $stream.Dispose(); exit 0 } catch { Write-Host '[ERROR_CODE] MODEL_INVALID'; Write-Host '[ERROR_MESSAGE] Model file is not readable.'; Write-Host ('[ERROR_DETAILS] ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 exit /b 1
exit /b 0

:emit_error
echo [ERROR_CODE] %~1
echo [ERROR_MESSAGE] %~2
echo [ERROR_DETAILS] %~3
echo [LOG_FILE] %LOG_FILE%
exit /b 1
