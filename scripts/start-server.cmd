@echo off
setlocal EnableExtensions
call "%~dp0_env.cmd"

set "MODEL_KEY=%~1"
if "%MODEL_KEY%"=="" set "MODEL_KEY=qwen"

set "PORT=%~2"
if "%PORT%"=="" set "PORT=%DEFAULT_PORT%"

for /f %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "[DateTime]::Now.ToString('yyyyMMdd-HHmmss')"' ) do set "STAMP=%%I"
if not defined STAMP set "STAMP=unknown"

call :resolve_model "%MODEL_KEY%"
if errorlevel 1 exit /b 1

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

call :check_memory
if errorlevel 1 exit /b 1

echo [INFO] Validating llama-server runtime...
"%LLAMA_SERVER%" --version >nul 2>&1
if errorlevel 1 (
    call :emit_error RUNTIME_INVALID "llama-server.exe failed to start." "The host may lack required CPU features such as AVX2, or the runtime is incomplete."
    exit /b 1
)

call :find_model_file "%MODEL_DIR%"
if errorlevel 1 (
    echo [INFO] Model file not found. Running bootstrap for model "%MODEL_KEY%"...
    call "%~dp0bootstrap.cmd" -SkipRuntime -Models "%MODEL_KEY%"
    if errorlevel 1 (
        call :emit_error MODEL_MISSING "Bootstrap failed while preparing model." "%MODEL_DIR%"
        exit /b 1
    )
    call :find_model_file "%MODEL_DIR%"
    if errorlevel 1 (
        call :emit_error MODEL_MISSING "No GGUF model found." "%MODEL_DIR%"
        exit /b 1
    )
)

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
"%WINPY_PYTHON%" "%~dp0launch_llama_server.py" --server "%LLAMA_SERVER%" --host 127.0.0.1 --port "%PORT%" --alias "%MODEL_ALIAS%" --model "%MODEL_FILE%" --context 8192 --threads "%NUMBER_OF_PROCESSORS%" --log "%LOG_FILE%" --err "%ERR_FILE%" >nul
if errorlevel 1 (
    call :emit_error MODEL_START_FAILED "Failed to launch llama-server process." "%LLAMA_SERVER%"
    exit /b 1
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

timeout /t 2 /nobreak >nul
goto wait_loop

:ready
echo [OK] Server is ready on http://127.0.0.1:%PORT%/v1
echo [INFO] Model alias: %MODEL_ALIAS%
echo [INFO] Log file: "%LOG_FILE%"
if exist "%ERR_FILE%" echo [INFO] Error log: "%ERR_FILE%"
exit /b 0

:resolve_model
set "MODEL_INPUT=%~1"
if /I "%MODEL_INPUT%"=="qwen" (
    set "MODEL_DIR=%MODELS_DIR%\qwen2.5-coder-7b-instruct-q4"
    set "MODEL_ALIAS=qwen-local"
    exit /b 0
)
if /I "%MODEL_INPUT%"=="gemma4" (
    set "MODEL_DIR=%MODELS_DIR%\gemma4-e4b-it-q4"
    set "MODEL_ALIAS=gemma4-local"
    exit /b 0
)
if /I "%MODEL_INPUT%"=="codellama" (
    set "MODEL_DIR=%MODELS_DIR%\codellama-7b-instruct-q4"
    set "MODEL_ALIAS=codellama-local"
    exit /b 0
)
call :emit_error MODEL_START_FAILED "Unknown model." "%MODEL_INPUT%"
exit /b 1

:check_memory
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $minimum = 16GB; $total = [int64](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory; if ($total -ge $minimum) { exit 0 } else { Write-Host ('[ERROR_CODE] RUNTIME_INVALID'); Write-Host ('[ERROR_MESSAGE] Need at least 16GB RAM.'); Write-Host ('[ERROR_DETAILS] Detected: {0:N1} GB' -f ($total / 1GB)); exit 1 } } catch { Write-Host '[WARN] Unable to determine total physical memory; skipping RAM check.'; exit 0 }"
exit /b %ERRORLEVEL%

:find_model_file
set "MODEL_FILE="
for /f "delims=" %%I in ('dir /b /a-d "%~1\*.gguf" 2^>nul') do if not defined MODEL_FILE set "MODEL_FILE=%~1\%%I"
if defined MODEL_FILE exit /b 0
exit /b 1

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
