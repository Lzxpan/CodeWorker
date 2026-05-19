@echo off
setlocal EnableExtensions
call "%~dp0_env.cmd"

set "WEBUI_PORT=8764"
set "CODEWORKER_WEBUI_URL=http://127.0.0.1:%WEBUI_PORT%"

where npx >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npx was not found. Install Node.js/npm, then run this script again.
  exit /b 1
)

echo [INFO] Starting or refreshing CodeWorker Web UI at %CODEWORKER_WEBUI_URL%
call "%~dp0launch-webui.cmd"
if errorlevel 1 exit /b 1

echo [INFO] Ensuring Playwright Chromium is available. First run may download browser files.
npx --yes --package @playwright/test playwright install chromium
if errorlevel 1 exit /b 1

echo [INFO] Running CodeWorker Web UI E2E tests
npx --yes --package @playwright/test playwright test "%ROOT_DIR%\scripts\run_webui_e2e.mjs" --project=chromium --reporter=line
exit /b %ERRORLEVEL%
