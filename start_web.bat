@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "ROOT=%CD%"
set "BACKEND_HOST=127.0.0.1"
set "BACKEND_PORT=8000"
set "FRONTEND_HOST=127.0.0.1"
set "FRONTEND_PORT=3002"
set "BACKEND_URL=http://%BACKEND_HOST%:%BACKEND_PORT%"
set "FRONTEND_URL=http://%FRONTEND_HOST%:%FRONTEND_PORT%"

echo.
echo ========================================
echo   BigGraph One-Click Launcher
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] python was not found. Install Python 3.11 or add Python to PATH.
  echo.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm was not found. Install Node.js LTS or add npm to PATH.
  echo.
  pause
  exit /b 1
)

echo [CHECK] Python web runtime...
python -c "import fastapi, uvicorn, multipart" >nul 2>nul
if errorlevel 1 (
  echo [SETUP] Installing backend dependencies from requirements.txt...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo [ERROR] Backend dependency installation failed.
    echo.
    pause
    exit /b 1
  )
)

if not exist "%ROOT%\frontend\node_modules" (
  echo [SETUP] Installing frontend dependencies...
  pushd "%ROOT%\frontend"
  call npm install
  if errorlevel 1 (
    popd
    echo.
    echo [ERROR] Frontend dependency installation failed.
    echo.
    pause
    exit /b 1
  )
  popd
)

echo.
echo [START] Backend API: %BACKEND_URL%
start "BigGraph Backend API" cmd /k "cd /d ""%ROOT%"" && python -m uvicorn api.main:create_app --factory --host %BACKEND_HOST% --port %BACKEND_PORT%"

echo [START] Frontend Dev Server: %FRONTEND_URL%
start "BigGraph Frontend" cmd /k "cd /d ""%ROOT%\frontend"" && npm run dev -- --host %FRONTEND_HOST% --port %FRONTEND_PORT%"

echo.
echo [WAIT] Giving services a few seconds to start...
timeout /t 5 /nobreak >nul

echo [OPEN] %FRONTEND_URL%
start "" "%FRONTEND_URL%"

echo.
echo BigGraph is starting in two separate terminal windows.
echo Backend:  %BACKEND_URL%/api/health
echo Frontend: %FRONTEND_URL%
echo.
echo Close the Backend and Frontend terminal windows to stop the app.
echo.
pause
