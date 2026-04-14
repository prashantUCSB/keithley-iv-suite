# ============================================================
# Keithley IV Suite v2.0.0 — PyInstaller spec
#
# Produces a one-directory bundle:
#   dist\Keithley_IV_Suite\Keithley_IV_Suite.exe   ← launcher
#   dist\Keithley_IV_Suite\_internal\              ← all DLLs / Python
#
# BUILD (run from repo root with .venv active):
#   pip install pyinstaller pyserial pyusb
#   pyinstaller keithley_iv_suite.spec --clean --noconfirm
#
# DISTRIBUTE:
#   Option A — portable folder: zip dist\Keithley_IV_Suite\ and copy anywhere.
#   Option B — installer:       run scripts\build_installer.bat  (needs Inno Setup 6)
# ============================================================

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(".").resolve()

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=[
        # Bundled YAML recipe files
        ("recipes", "recipes"),
    ],
    hiddenimports=[
        # ── pyvisa core ──────────────────────────────────────────────────────
        "pyvisa",
        "pyvisa.resources",
        "pyvisa.resources.gpib",
        "pyvisa.resources.usb",
        "pyvisa.resources.tcpip",
        "pyvisa.resources.serial",
        "pyvisa.resources.messagebased",
        "pyvisa.resources.registerbased",
        "pyvisa.ctwrapper",
        "pyvisa.highlevel",

        # ── pyvisa-py pure-Python backend ────────────────────────────────────
        # Allows instrument communication without NI-VISA installed.
        "pyvisa_py",
        "pyvisa_py.gpib",
        "pyvisa_py.usb",
        "pyvisa_py.tcpip",
        "pyvisa_py.serial",
        "pyvisa_py.common",

        # ── pyserial — RS-232 / USB-to-serial instruments ────────────────────
        "serial",
        "serial.tools",
        "serial.tools.list_ports",
        "serial.tools.list_ports_windows",
        "serial.serialutil",
        "serial.serialwin32",

        # ── pyusb — USB-TMC direct instruments ───────────────────────────────
        "usb",
        "usb.core",
        "usb.util",
        "usb.control",
        "usb.backend",
        "usb.backend.libusb1",
        "usb.backend.libusb0",
        "usb.backend.openusb",

        # ── PyQt6 ────────────────────────────────────────────────────────────
        "PyQt6.QtPrintSupport",
        "PyQt6.sip",

        # ── pyqtgraph ────────────────────────────────────────────────────────
        "pyqtgraph",
        "pyqtgraph.graphicsItems.PlotItem",
        "pyqtgraph.graphicsItems.ViewBox",
        "pyqtgraph.graphicsItems.AxisItem",
        "pyqtgraph.graphicsItems.LegendItem",
        "pyqtgraph.graphicsItems.ScatterPlotItem",
        "pyqtgraph.graphicsItems.InfiniteLine",
        "pyqtgraph.graphicsItems.TextItem",
        "pyqtgraph.graphicsItems.ArrowItem",
        "pyqtgraph.graphicsItems.PlotCurveItem",
        "pyqtgraph.graphicsItems.PlotDataItem",

        # ── numpy ─────────────────────────────────────────────────────────────
        "numpy",
        "numpy.core._multiarray_umath",
        "numpy.core._multiarray_tests",

        # ── pandas ─────────────────────────────────────────────────────────────
        "pandas",
        "pandas._libs.tslibs.base",
        "pandas._libs.tslibs.np_datetime",
        "pandas._libs.tslibs.timedeltas",
        "pandas._libs.tslibs.timestamps",
        "pandas._libs.tslibs.nattype",
        "pandas._libs.tslibs.offsets",
        "pandas._libs.tslibs.tzconversion",
        "pandas._libs.hashtable",
        "pandas._libs.lib",
        "pandas._libs.interval",
        "pandas._libs.missing",
        "pandas._libs.reduce",
        "pandas._libs.sparse",
        "pandas._libs.writers",

        # ── yaml ──────────────────────────────────────────────────────────────
        "yaml",

        # ── openpyxl — Excel export ───────────────────────────────────────────
        "openpyxl",
        "openpyxl.workbook",
        "openpyxl.worksheet",
        "openpyxl.styles",
        "openpyxl.utils",
        "openpyxl.reader.excel",
        "openpyxl.writer.excel",
        "et_xmlfile",

        # ── keithley_iv_suite.data ────────────────────────────────────────────
        "keithley_iv_suite.data",
        "keithley_iv_suite.data.exporter",
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
        "notebook",
        "wx",
        "PySide2",
        "PySide6",
        "PyQt5",
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
    console=False,            # windowed app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                # replace with "assets\icon.ico" when available
    version="version_info.txt",
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
