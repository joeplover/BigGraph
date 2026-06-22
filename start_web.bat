@echo off
setlocal

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"
set "APP_URL=http://%HOST%:%PORT%"

echo.
echo ========================================
echo   BigGraph Web Launcher
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] python was not found. Install Python 3.11 or add Python to PATH.
  echo.
  pause
  exit /b 1
)

python -c "import fastapi, uvicorn, multipart" >nul 2>nul
if errorlevel 1 (
  echo [SETUP] Installing web runtime dependencies...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed. Check network or Python environment.
    echo.
    pause
    exit /b 1
  )
)

if "%DEEPSEEK_API_KEY%"=="" (
  echo [NOTICE] DEEPSEEK_API_KEY is not set.
  echo          The page can open, but PPT generation needs this API key.
  echo.
)

echo [START] URL: %APP_URL%
echo [TIP] Keep this window open. Closing it stops the service.
echo.

start "" "%APP_URL%"
python -m uvicorn api.main:create_app --factory --host %HOST% --port %PORT%

echo.
echo [STOPPED] Service stopped.
echo.
pause
