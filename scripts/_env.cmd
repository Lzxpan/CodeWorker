@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT_DIR=%%~fI"
set "CONFIG_DIR=%ROOT_DIR%\config"
set "LOGS_DIR=%ROOT_DIR%\logs"
set "MODELS_DIR=%ROOT_DIR%\models"
set "RUNTIME_DIR=%ROOT_DIR%\runtime"
set "LLAMA_RUNTIME=%RUNTIME_DIR%\llama.cpp"
set "WINPY_RUNTIME=%RUNTIME_DIR%\WinPython"
set "PORTABLE_GIT_HOME=%RUNTIME_DIR%\PortableGit"
set "LLAMA_SERVER=%LLAMA_RUNTIME%\llama-server.exe"
set "WINPY_PYTHON=%WINPY_RUNTIME%\python.exe"
if not exist "%WINPY_PYTHON%" set "WINPY_PYTHON=%WINPY_RUNTIME%\python\python.exe"
set "PORTABLE_GIT_CMD=%PORTABLE_GIT_HOME%\cmd\git.exe"
set "PORTABLE_GIT_BIN=%PORTABLE_GIT_HOME%\bin\git.exe"
set "AIDER_CONFIG=%CONFIG_DIR%\.aider.conf.yml"
set "AIDER_MODEL_SETTINGS=%CONFIG_DIR%\.aider.model.settings.yml"
set "AIDER_MODEL_METADATA=%CONFIG_DIR%\.aider.model.metadata.json"
set "DEFAULT_PORT=8082"

if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%" >nul 2>&1

endlocal & (
    set "ROOT_DIR=%ROOT_DIR%"
    set "CONFIG_DIR=%CONFIG_DIR%"
    set "LOGS_DIR=%LOGS_DIR%"
    set "MODELS_DIR=%MODELS_DIR%"
    set "RUNTIME_DIR=%RUNTIME_DIR%"
    set "LLAMA_RUNTIME=%LLAMA_RUNTIME%"
    set "WINPY_RUNTIME=%WINPY_RUNTIME%"
    set "PORTABLE_GIT_HOME=%PORTABLE_GIT_HOME%"
    set "LLAMA_SERVER=%LLAMA_SERVER%"
    set "WINPY_PYTHON=%WINPY_PYTHON%"
    set "PORTABLE_GIT_CMD=%PORTABLE_GIT_CMD%"
    set "PORTABLE_GIT_BIN=%PORTABLE_GIT_BIN%"
    set "AIDER_CONFIG=%AIDER_CONFIG%"
    set "AIDER_MODEL_SETTINGS=%AIDER_MODEL_SETTINGS%"
    set "AIDER_MODEL_METADATA=%AIDER_MODEL_METADATA%"
    set "DEFAULT_PORT=%DEFAULT_PORT%"
)

goto :eof
