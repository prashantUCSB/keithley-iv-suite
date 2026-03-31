@echo off
:: ============================================================
:: Keithley IV Suite — Docker launcher for Windows hosts
::
:: REQUIREMENTS:
::   - Docker Desktop installed and running
::   - VcXsrv OR X410 installed and running as X server
::     VcXsrv (free): https://sourceforge.net/projects/vcxsrv/
::     X410 (paid):   https://x410.dev/
::
:: VISA HARDWARE LIMITS ON WINDOWS DOCKER:
::   - Ethernet VISA:  WORKS  (uses --network=host equivalent)
::   - USB VISA:       NEEDS usbipd-win (see notes below)
::   - GPIB-USB:       NOT SUPPORTED via Docker on Windows
::                     Use scripts\run_windows.bat instead.
::
:: USB PASSTHROUGH (optional, advanced):
::   Install usbipd-win: https://github.com/dorssel/usbipd-win
::   Then in PowerShell (admin):
::     usbipd wsl list
::     usbipd wsl attach --busid <busid>
::
:: ============================================================
setlocal

:: --- Detect X server ---
set "DISPLAY=host.docker.internal:0.0"

:: Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running. Start it first.
    pause
    exit /b 1
)

:: Build if image doesn't exist
docker image inspect keithley-iv-suite:latest >nul 2>&1
if errorlevel 1 (
    echo [INFO] Image not found. Building now...
    cd /d "%~dp0.."
    docker build -t keithley-iv-suite:latest .
    if errorlevel 1 (
        echo [ERROR] Docker build failed.
        pause
        exit /b 1
    )
)

:: Get host IP for X11 (needed when not using host networking)
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "169.254"') do (
    set "HOST_IP=%%i"
    set "HOST_IP=!HOST_IP: =!"
    goto :got_ip
)
:got_ip

echo [INFO] Using DISPLAY=%DISPLAY%
echo [INFO] Starting Keithley IV Suite in Docker...
echo [INFO] Close the app window to stop the container.
echo.

docker run --rm -it ^
    -e DISPLAY=%DISPLAY% ^
    -e QT_QPA_PLATFORM=xcb ^
    -v "%USERPROFILE%\Documents\IV_Data:/root/Documents/IV_Data" ^
    -v "%~dp0..\recipes:/app/recipes:ro" ^
    --network host ^
    --name keithley-iv-suite ^
    keithley-iv-suite:latest

echo.
echo [INFO] Container stopped.
pause
