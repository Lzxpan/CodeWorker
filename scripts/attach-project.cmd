@echo off
setlocal EnableExtensions
call "%~dp0_env.cmd"

if "%~1"=="" (
    echo Usage: %~nx0 ^<project_path^>
    exit /b 1
)

for %%I in ("%~1") do set "PROJECT_DIR=%%~fI"

if not exist "%PROJECT_DIR%\" (
    echo [ERROR] Project directory not found: "%PROJECT_DIR%"
    exit /b 1
)

call :resolve_git
if errorlevel 1 exit /b 1

if not exist "%PROJECT_DIR%\.git\" (
    echo [INFO] Initializing git repository in "%PROJECT_DIR%"
    "%GIT_EXE%" -C "%PROJECT_DIR%" init
    if errorlevel 1 (
        echo [ERROR] Failed to initialize git repository.
        exit /b 1
    )
)

call :ensure_identity
if errorlevel 1 exit /b 1

"%GIT_EXE%" -C "%PROJECT_DIR%" rev-parse --verify HEAD >nul 2>&1
if not errorlevel 1 (
    echo [OK] Git repository is ready.
    exit /b 0
)

call :prepare_excludes
if errorlevel 1 exit /b 1

echo [INFO] Creating initial snapshot commit...
"%GIT_EXE%" -C "%PROJECT_DIR%" add -A
if errorlevel 1 (
    echo [ERROR] Failed to stage project files.
    exit /b 1
)

"%GIT_EXE%" -C "%PROJECT_DIR%" diff --cached --quiet >nul 2>&1
if errorlevel 1 (
    "%GIT_EXE%" -C "%PROJECT_DIR%" -c commit.gpgsign=false commit -m "Initial snapshot before aider session" --no-verify --no-gpg-sign
) else (
    "%GIT_EXE%" -C "%PROJECT_DIR%" -c commit.gpgsign=false commit --allow-empty -m "Initial snapshot before aider session" --no-verify --no-gpg-sign
)

if errorlevel 1 (
    echo [ERROR] Failed to create initial commit.
    exit /b 1
)

"%GIT_EXE%" -C "%PROJECT_DIR%" branch -M main >nul 2>&1
echo [OK] Initial snapshot is ready.
exit /b 0

:resolve_git
if exist "%PORTABLE_GIT_CMD%" (
    set "GIT_EXE=%PORTABLE_GIT_CMD%"
    exit /b 0
)

if exist "%PORTABLE_GIT_BIN%" (
    set "GIT_EXE=%PORTABLE_GIT_BIN%"
    exit /b 0
)

echo [INFO] PortableGit not found. Running bootstrap first...
call "%~dp0bootstrap.cmd" -SkipModels
if errorlevel 1 (
    echo [ERROR] Bootstrap failed while preparing PortableGit.
    exit /b 1
)

if exist "%PORTABLE_GIT_CMD%" (
    set "GIT_EXE=%PORTABLE_GIT_CMD%"
    exit /b 0
)

if exist "%PORTABLE_GIT_BIN%" (
    set "GIT_EXE=%PORTABLE_GIT_BIN%"
    exit /b 0
)

echo [ERROR] PortableGit not found under "%PORTABLE_GIT_HOME%"
exit /b 1

:prepare_excludes
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare-git-exclude.ps1" -ProjectDir "%PROJECT_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to prepare git exclude rules.
    exit /b 1
)
exit /b 0

:ensure_identity
"%GIT_EXE%" -C "%PROJECT_DIR%" config user.name >nul 2>&1
if errorlevel 1 (
    "%GIT_EXE%" -C "%PROJECT_DIR%" config user.name "USB Code Assistant"
    if errorlevel 1 (
        echo [ERROR] Failed to set local git user.name
        exit /b 1
    )
)

"%GIT_EXE%" -C "%PROJECT_DIR%" config user.email >nul 2>&1
if errorlevel 1 (
    "%GIT_EXE%" -C "%PROJECT_DIR%" config user.email "local@offline.invalid"
    if errorlevel 1 (
        echo [ERROR] Failed to set local git user.email
        exit /b 1
    )
)

exit /b 0
