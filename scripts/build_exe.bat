@echo off
:: ============================================================
:: Keithley IV Suite — PyInstaller EXE builder
::
:: Run ONCE to produce dist\Keithley_IV_Suite\Keithley_IV_Suite.exe
:: Then copy the entire dist\Keithley_IV_Suite\ folder to other computers.
:: No Python installation required on target machines.
:: VISA drivers (NI or Keysight) still need to be installed on targets.
:: ============================================================
setlocal

set "APP_DIR=%~dp0.."
set "VENV_PY=%APP_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] Run scripts\install_windows.bat first.
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

echo [1/2] Installing PyInstaller...
"%APP_DIR%\.venv\Scripts\pip.exe" install pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

echo [2/2] Building executable...
"%VENV_PY%" -m PyInstaller keithley_iv_suite.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo  ======================================================
echo   Build complete!
echo   Output: dist\Keithley_IV_Suite\Keithley_IV_Suite.exe
echo.
echo   Copy the entire dist\Keithley_IV_Suite\ folder to
echo   each instrument computer and run the .exe directly.
echo   (VISA drivers must already be installed on targets.)
echo  ======================================================
echo.
pause
