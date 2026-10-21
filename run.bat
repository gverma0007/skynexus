@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SkyNexus
cd /d "%~dp0"

rem ------------------------------------------------------------------
rem  SkyNexus launcher for Windows. Double-click to use.
rem  Optional: run.bat live | demo | stop | logs | reset | wipe
rem ------------------------------------------------------------------

set "WEB_PORT=5173"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="WEB_PORT" if not "%%B"=="" set "WEB_PORT=%%B"
  )
)
set "URL=http://localhost:%WEB_PORT%"

call :check_docker || goto :end_pause

if not exist ".env" (
  if exist ".env.example" (
    copy /y ".env.example" ".env" >nul
    echo Created .env from .env.example.
  )
)

if not "%~1"=="" (
  set "CHOICE=%~1"
  goto :dispatch
)

:menu
cls
echo.
echo   SkyNexus
echo   ------------------------------------------------
echo    1  Start with live data   (real feeds, needs internet)
echo    2  Start with demo data   (works offline, best for demos)
echo    3  Stop SkyNexus
echo    4  Show backend logs
echo    5  Regenerate the demo world
echo    6  Delete all data and stop
echo    7  Open the dashboard in the browser
echo    0  Exit
echo   ------------------------------------------------
set "CHOICE="
set /p "CHOICE=  Choose an option and press Enter: "
if "%CHOICE%"=="1" set "CHOICE=live"
if "%CHOICE%"=="2" set "CHOICE=demo"
if "%CHOICE%"=="3" set "CHOICE=stop"
if "%CHOICE%"=="4" set "CHOICE=logs"
if "%CHOICE%"=="5" set "CHOICE=reset"
if "%CHOICE%"=="6" set "CHOICE=wipe"
if "%CHOICE%"=="7" set "CHOICE=open"
if "%CHOICE%"=="0" goto :eof

:dispatch
if /i "%CHOICE%"=="live"  goto :start_live
if /i "%CHOICE%"=="demo"  goto :start_demo
if /i "%CHOICE%"=="stop"  goto :stop
if /i "%CHOICE%"=="logs"  goto :logs
if /i "%CHOICE%"=="reset" goto :reset
if /i "%CHOICE%"=="wipe"  goto :wipe
if /i "%CHOICE%"=="open"  goto :open
echo   Unknown option "%CHOICE%".
timeout /t 2 >nul
goto :menu

:start_live
set "DATA_MODE=live"
set "DEMO_RESET=0"
goto :start

:start_demo
set "DATA_MODE=demo"
set "DEMO_RESET=0"
goto :start

:reset
set "DATA_MODE=demo"
set "DEMO_RESET=1"
goto :start

:start
rem Remember the chosen mode so restarts from Docker Desktop keep it.
if exist ".env" (
  powershell -NoProfile -Command "$f='.env'; $c=Get-Content $f; if ($c -match '^DATA_MODE=') { $c = $c -replace '^DATA_MODE=.*','DATA_MODE=%DATA_MODE%' } else { $c += 'DATA_MODE=%DATA_MODE%' }; Set-Content -Path $f -Value $c" >nul 2>nul
)
echo.
echo   Building and starting SkyNexus in %DATA_MODE% mode.
echo   The first run downloads images and can take 5 to 10 minutes.
echo.
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo   Docker could not start SkyNexus. Read the messages above.
  echo   A common cause is another program using port %WEB_PORT%, 8000 or 5432.
  echo   Change WEB_PORT, API_PORT or DB_PORT in .env and try again.
  goto :end_pause
)
call :wait_ready
if errorlevel 1 goto :end_pause
start "" "%URL%"
echo.
echo   SkyNexus is running at %URL%
echo   API documentation: http://localhost:8000/docs
echo   Run this file again and choose 3 to stop it.
goto :end_pause

:stop
echo.
docker compose stop
echo   SkyNexus stopped. Your data is kept.
goto :end_pause

:logs
echo.
echo   Showing backend logs. Press Ctrl+C to return.
docker compose logs -f --tail 100 backend
goto :end_pause

:wipe
echo.
set "CONFIRM="
set /p "CONFIRM=  This deletes the database and all saved reports. Type YES to continue: "
if /i not "%CONFIRM%"=="YES" (
  echo   Cancelled.
  goto :end_pause
)
docker compose down -v
echo   All SkyNexus containers and data were removed.
goto :end_pause

:open
start "" "%URL%"
goto :eof

rem ------------------------------------------------------------------
:check_docker
where docker >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Docker is not installed.
  echo   Install Docker Desktop from https://www.docker.com/products/docker-desktop/
  echo   then run this file again.
  exit /b 1
)
docker info >nul 2>nul
if not errorlevel 1 exit /b 0
echo   Docker Desktop is not running. Trying to start it...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
  start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
)
for /l %%i in (1,1,60) do (
  docker info >nul 2>nul
  if not errorlevel 1 (
    echo   Docker is ready.
    exit /b 0
  )
  timeout /t 3 >nul
)
echo.
echo   Docker Desktop did not start. Open it yourself, wait until it says
echo   "Engine running", then run this file again.
exit /b 1

:wait_ready
echo.
echo   Waiting for SkyNexus to be ready (demo data takes about a minute)...
set "HAS_CURL=0"
where curl >nul 2>nul && set "HAS_CURL=1"
for /l %%i in (1,1,120) do (
  if "!HAS_CURL!"=="1" (
    curl -s -f -o nul "%URL%/api/health" >nul 2>nul
  ) else (
    powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 '%URL%/api/health' | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
  )
  if not errorlevel 1 (
    echo   Ready.
    exit /b 0
  )
  timeout /t 3 >nul
)
echo.
echo   SkyNexus did not answer within 6 minutes. Showing the last backend logs:
docker compose logs --tail 40 backend
exit /b 1

:end_pause
echo.
pause
goto :eof
