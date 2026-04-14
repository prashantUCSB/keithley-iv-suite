@echo off
:: ============================================================
:: Keithley IV Suite - Windows Setup Script
::
:: Run this ONCE on each instrument computer.
:: Requires Python 3.10+ installed and on PATH.
:: NI-VISA or Keysight IO Libraries must already be installed.
::
:: Usage:  Double-click  OR  run from cmd.exe
:: ============================================================
setlocal EnableDelayedExpansion

:: Resolve repo root as an absolute path (no ".." in the string)
pushd "%~dp0.."
set "APP_DIR=%CD%"

set "VENV_DIR=%APP_DIR%\.venv"

echo.
echo  ======================================================
echo   Keithley IV Suite -- Windows Installer
echo  ======================================================
echo.

:: Check Python exists
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo         Download from: https://www.python.org/downloads/
    echo         Make sure "Add Python to PATH" is checked during install.
    popd
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [OK] Found %PY_VER%

:: Check minimum version (3.10)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 or newer is required.
    popd
    pause
    exit /b 1
)

echo.
echo [1/4] Creating virtual environment at %VENV_DIR% ...
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    popd
    pause
    exit /b 1
)
echo [OK] Virtual environment created.

echo.
echo [2/4] Upgrading pip ...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip --quiet
echo [OK] pip upgraded.

echo.
echo [3/4] Installing dependencies ...
"%VENV_DIR%\Scripts\pip.exe" install -r "%APP_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your internet connection.
    popd
    pause
    exit /b 1
)
echo [OK] All packages installed.

echo.
echo [4/4] Verifying VISA backend ...
"%VENV_DIR%\Scripts\python.exe" "%APP_DIR%\scripts\verify_visa.py" 2>nul
if errorlevel 1 (
    echo [WARN] No VISA backend found with NI/Keysight drivers.
    echo        Falling back to pyvisa-py ^(limited GPIB support^).
    echo        Install NI-VISA from: https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html
    echo        or Keysight IO from:  https://www.keysight.com/find/iosuites
) else (
    echo [OK] VISA backend detected.
)

echo.
echo  ======================================================
echo   Installation complete!
echo   Run the app:  scripts\run_windows.bat
echo  ======================================================
echo.
popd
pause
