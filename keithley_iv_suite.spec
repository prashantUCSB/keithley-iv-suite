# ============================================================
# PyInstaller spec — builds a standalone Windows .exe
#
# BUILD (run from repo root with venv active):
#   pip install pyinstaller
#   pyinstaller keithley_iv_suite.spec
#
# Output: dist\Keithley_IV_Suite\Keithley_IV_Suite.exe
#         (copy the entire dist\Keithley_IV_Suite\ folder)
# ============================================================

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[
        # Bundle the recipes folder
        ("recipes", "recipes"),
        # PyVISA needs its visa.conf resources
        ("src/keithley_iv_suite", "keithley_iv_suite"),
    ],
    hiddenimports=[
        # PyVISA backends
        "pyvisa",
        "pyvisa.resources",
        "pyvisa.resources.gpib",
        "pyvisa.resources.usb",
        "pyvisa.resources.tcpip",
        "pyvisa.resources.serial",
        "pyvisa_py",
        "pyvisa_py.gpib",
        "pyvisa_py.usb",
        "pyvisa_py.tcpip",
        # PyQt6 plugins
        "PyQt6.QtPrintSupport",
        "PyQt6.sip",
        # pyqtgraph
        "pyqtgraph.graphicsItems.PlotItem",
        "pyqtgraph.graphicsItems.ViewBox",
        # numpy
        "numpy",
        "numpy.core._multiarray_umath",
        # yaml
        "yaml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "tkinter",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Keithley_IV_Suite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Add an .ico file path here if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Keithley_IV_Suite",
)
