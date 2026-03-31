@echo off
:: ============================================================
:: Keithley IV Suite — Windows Launcher
:: Double-click to start the application.
:: Run install_windows.bat first if you haven't already.
:: ============================================================
setlocal

set "APP_DIR=%~dp0.."
set "VENV_PY=%APP_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment not found.
    echo         Run scripts\install_windows.bat first.
    pause
    exit /b 1
)

cd /d "%APP_DIR%"
set "PYTHONPATH=%APP_DIR%\src"
"%VENV_PY%" main.py
