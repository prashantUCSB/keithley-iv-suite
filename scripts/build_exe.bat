@echo off
:: ============================================================
:: Keithley IV Suite v2.0.0 - PyInstaller EXE builder
::
:: Produces: dist\Keithley_IV_Suite\Keithley_IV_Suite.exe
::
:: Usage:
::   Double-click this file, or run from cmd.exe / PowerShell.
::   The .venv must exist (run install_windows.bat first).
:: ============================================================
setlocal EnableDelayedExpansion

:: Resolve repo root as an absolute path (no ".." in the string)
pushd "%~dp0.."
set "APP_DIR=%CD%"

set "VENV_PY=%APP_DIR%\.venv\Scripts\python.exe"
set "VENV_PIP=%APP_DIR%\.venv\Scripts\pip.exe"

echo.
echo  ======================================================
echo   Keithley IV Suite -- EXE Builder
echo  ======================================================
echo.

:: -- Sanity check -------------------------------------------------------------
if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment not found at %APP_DIR%\.venv
    echo         Run scripts\install_windows.bat first.
    popd
    pause
    exit /b 1
)

:: -- Install / update build dependencies --------------------------------------
echo [1/3] Updating build dependencies...
"%VENV_PIP%" install --quiet --upgrade pyinstaller pyserial pyusb
if errorlevel 1 (
    echo [ERROR] Failed to update build dependencies.
    popd
    pause
    exit /b 1
)
echo [OK] Build dependencies ready.
echo.

:: -- Clean old build artifacts ------------------------------------------------
echo [2/3] Cleaning previous build...
if exist "build\Keithley_IV_Suite"   rmdir /s /q "build\Keithley_IV_Suite"
if exist "dist\Keithley_IV_Suite"    rmdir /s /q "dist\Keithley_IV_Suite"
echo [OK] Clean done.
echo.

:: -- Run PyInstaller ----------------------------------------------------------
echo [3/3] Running PyInstaller (this takes 2-5 minutes)...
"%VENV_PY%" -m PyInstaller keithley_iv_suite.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed. Check the output above for details.
    echo         Common causes:
    echo           - Missing module: add to hiddenimports in keithley_iv_suite.spec
    echo           - UPX not found: install UPX or set upx=False in the spec file
    popd
    pause
    exit /b 1
)

echo.
echo  ======================================================
echo   Build successful!
echo.
echo   Output folder:
echo     dist\Keithley_IV_Suite\
echo.
echo   To distribute:
echo     Option A -- Portable:  zip dist\Keithley_IV_Suite\ and copy
echo                            to any Windows 10/11 x64 machine.
echo     Option B -- Installer: run scripts\build_installer.bat
echo                            (requires Inno Setup 6 or 7)
echo  ======================================================
echo.
popd
pause
