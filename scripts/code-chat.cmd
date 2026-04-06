@echo off
setlocal EnableExtensions
call "%~dp0_env.cmd"

if "%~1"=="" (
    echo Usage: %~nx0 ^<project_path^> [qwen^|gemma4^|codellama] [--browser]
    exit /b 1
)

for %%I in ("%~1") do set "PROJECT_DIR=%%~fI"
if not exist "%PROJECT_DIR%\" (
    echo [ERROR] Project directory not found: "%PROJECT_DIR%"
    exit /b 1
)

set "MODEL_KEY=qwen"
set "USE_BROWSER=0"

:parse_optional_args
if "%~2"=="" goto args_done

if /I "%~2"=="qwen" (
    set "MODEL_KEY=qwen"
    shift
    goto parse_optional_args
)

if /I "%~2"=="gemma4" (
    set "MODEL_KEY=gemma4"
    shift
    goto parse_optional_args
)

if /I "%~2"=="codellama" (
    set "MODEL_KEY=codellama"
    shift
    goto parse_optional_args
)

if /I "%~2"=="--browser" (
    set "USE_BROWSER=1"
    shift
    goto parse_optional_args
)

echo [ERROR] Unknown option: "%~2"
echo         Supported options: qwen, gemma4, codellama, --browser
exit /b 1

:args_done

if not exist "%WINPY_PYTHON%" (
    echo [INFO] Portable Python not found. Running bootstrap...
    call "%~dp0bootstrap.cmd"
    if errorlevel 1 (
        echo [ERROR] Bootstrap failed while preparing runtime and models.
        exit /b 1
    )
)

if not exist "%WINPY_PYTHON%" (
    echo [ERROR] Portable Python not found: "%WINPY_PYTHON%"
    exit /b 1
)

"%WINPY_PYTHON%" -m aider --help >nul 2>&1
if errorlevel 1 (
    echo [INFO] aider is not installed. Installing into portable Python...
    call "%~dp0install-aider.cmd"
    if errorlevel 1 (
        echo [ERROR] Failed to install aider into portable Python.
        exit /b 1
    )
)

call "%~dp0attach-project.cmd" "%PROJECT_DIR%"
if errorlevel 1 exit /b 1

call "%~dp0start-server.cmd" "%MODEL_KEY%" "%DEFAULT_PORT%"
if errorlevel 1 exit /b 1

set "OPENAI_API_BASE=http://127.0.0.1:%DEFAULT_PORT%/v1"
set "OPENAI_API_KEY=local-not-used"
set "AIDER_ANALYTICS_DISABLE=1"
set "LITELLM_DISABLE_TELEMETRY=1"

pushd "%PROJECT_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to enter project directory.
    exit /b 1
)

if /I "%MODEL_KEY%"=="gemma4" (
    set "AIDER_MODEL=gemma4"
)
if /I "%MODEL_KEY%"=="codellama" (
    set "AIDER_MODEL=codellama"
)
if /I "%MODEL_KEY%"=="qwen" (
    set "AIDER_MODEL=qwen"
)

echo [INFO] Launching aider in "%PROJECT_DIR%"
echo [INFO] API endpoint: %OPENAI_API_BASE%
echo [INFO] Model alias: %AIDER_MODEL%

if "%USE_BROWSER%"=="1" (
    "%WINPY_PYTHON%" -m aider --config "%AIDER_CONFIG%" --model-settings-file "%AIDER_MODEL_SETTINGS%" --model-metadata-file "%AIDER_MODEL_METADATA%" --model "%AIDER_MODEL%" --openai-api-base "%OPENAI_API_BASE%" --openai-api-key "%OPENAI_API_KEY%" --no-analytics --browser
) else (
    "%WINPY_PYTHON%" -m aider --config "%AIDER_CONFIG%" --model-settings-file "%AIDER_MODEL_SETTINGS%" --model-metadata-file "%AIDER_MODEL_METADATA%" --model "%AIDER_MODEL%" --openai-api-base "%OPENAI_API_BASE%" --openai-api-key "%OPENAI_API_KEY%" --no-analytics
)

set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
