@echo off
setlocal EnableExtensions
call "%~dp0_env.cmd"

if not exist "%WINPY_PYTHON%" (
    echo [INFO] Portable Python not found. Running bootstrap first...
    call "%~dp0bootstrap.cmd" -SkipModels
    if errorlevel 1 (
        echo [ERROR] Bootstrap failed while preparing portable Python.
        exit /b 1
    )
)

if not exist "%WINPY_PYTHON%" (
    echo [ERROR] Portable Python not found after bootstrap: "%WINPY_PYTHON%"
    exit /b 1
)

echo [INFO] Ensuring pip is available...
"%WINPY_PYTHON%" -m ensurepip --upgrade >nul 2>&1

echo [INFO] Upgrading pip...
"%WINPY_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    exit /b 1
)

echo [INFO] Installing aider-chat into portable Python...
"%WINPY_PYTHON%" -m pip install --upgrade aider-chat
if errorlevel 1 (
    echo [ERROR] Failed to install aider-chat.
    exit /b 1
)

echo [OK] aider-chat is installed in "%WINPY_RUNTIME%".
exit /b 0
