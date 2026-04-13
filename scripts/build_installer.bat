@echo off
:: ============================================================
:: Keithley IV Suite v2.0.0 — Full installer pipeline
::
:: Step 1: PyInstaller  →  dist\Keithley_IV_Suite\  (portable folder)
:: Step 2: Inno Setup   →  release\Keithley_IV_Suite_v2.0.0_Setup.exe
::                          (self-extracting Windows installer, ~60 MB)
::
:: The installer:
::   - Installs to %ProgramFiles%\Keithley IV Suite\
::   - Creates Start Menu shortcut
::   - Offers optional Desktop shortcut
::   - Registers in Add/Remove Programs with uninstaller
::   - Works on any Windows 10/11 x64 machine, no Python needed
::
:: REQUIREMENTS:
::   - .venv already created (run install_windows.bat first)
::   - Inno Setup 6 or 7 installed from https://jrsoftware.org/isdl.php
:: ============================================================
setlocal EnableDelayedExpansion

set "APP_DIR=%~dp0.."
set "VENV_PY=%APP_DIR%\.venv\Scripts\python.exe"
set "VENV_PIP=%APP_DIR%\.venv\Scripts\pip.exe"

:: Inno Setup compiler — check all common install locations (v6 and v7, x64 and x86)
set "ISCC="
if exist "C:\Program Files\Inno Setup 7\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 7\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 7\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

echo.
echo  ======================================================
echo   Keithley IV Suite -- Full Installer Builder
echo  ======================================================
echo.

:: ── Sanity checks ────────────────────────────────────────────────────────────
if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment not found at %APP_DIR%\.venv
    echo         Run scripts\install_windows.bat first.
    pause
    exit /b 1
)

if "%ISCC%"=="" (
    echo [ERROR] Inno Setup 6 not found.
    echo         Download and install from:  https://jrsoftware.org/isdl.php
    echo         Then re-run this script.
    echo.
    echo         Alternatively, run scripts\build_exe.bat to get the
    echo         portable folder version  (dist\Keithley_IV_Suite\).
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

:: ── Step 1: PyInstaller ───────────────────────────────────────────────────────
echo [1/4] Updating build dependencies (pyinstaller, pyserial, pyusb)...
"%VENV_PIP%" install --quiet --upgrade pyinstaller pyserial pyusb
if errorlevel 1 goto :pip_error
echo [OK]
echo.

echo [2/4] Cleaning previous PyInstaller build...
if exist "build\Keithley_IV_Suite"  rmdir /s /q "build\Keithley_IV_Suite"
if exist "dist\Keithley_IV_Suite"   rmdir /s /q "dist\Keithley_IV_Suite"
echo [OK]
echo.

echo [3/4] Building EXE bundle with PyInstaller (2-5 minutes)...
"%VENV_PY%" -m PyInstaller keithley_iv_suite.spec --clean --noconfirm
if errorlevel 1 goto :pyinstaller_error
echo [OK] EXE bundle at dist\Keithley_IV_Suite\
echo.

:: ── Step 2: Inno Setup ────────────────────────────────────────────────────────
echo [4/4] Compiling installer with Inno Setup...
if not exist "release" mkdir "release"
"%ISCC%" "%APP_DIR%\installer.iss"
if errorlevel 1 goto :iscc_error

echo.
echo  ======================================================
echo   Installer built successfully!
echo.
echo   Output:  release\Keithley_IV_Suite_v2.0.0_Setup.exe
echo.
echo   Distribute this single EXE to any Windows 10/11 x64
echo   machine.  No Python or VISA drivers required for
echo   Ethernet/USB-TMC instruments.
echo   (GPIB still requires NI-VISA or Keysight IO Libraries)
echo  ======================================================
echo.
pause
exit /b 0

:: ── Error handlers ────────────────────────────────────────────────────────────
:pip_error
echo [ERROR] pip dependency update failed.
pause
exit /b 1

:pyinstaller_error
echo [ERROR] PyInstaller build failed.
echo         Check the output above.  Common fixes:
echo           - Add missing modules to hiddenimports in keithley_iv_suite.spec
echo           - Set upx=False in the spec if UPX is not installed
pause
exit /b 1

:iscc_error
echo [ERROR] Inno Setup compilation failed.
echo         Check that dist\Keithley_IV_Suite\ was created by PyInstaller.
pause
exit /b 1
