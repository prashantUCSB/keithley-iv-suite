# Changelog

All notable changes to Keithley IV Suite are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [1.0.2] — 2026-04-01

### Fixed
- **2614B `could not convert string to float` error** — `SMU2600.measure_iv()` now
  strips non-numeric tokens (status words, stray whitespace) from the TSP
  `print(smua.measure.iv())` response before parsing. Automatically falls back to
  separate `measure.i()` / `measure.v()` queries if the simultaneous response is
  still unparseable, logging a warning. Affected firmware versions that append a
  status token to the two-value return. ([smu_2600.py](src/keithley_iv_suite/instruments/smu_2600.py))
- **"Disconnect" button text overflow** — removed `setFixedWidth(80)` on the
  connect/disconnect button in `InstrumentRow`; replaced with `setMinimumWidth(90)`
  so the button expands to fit its label. ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

---

## [1.0.1] — 2026-04-01

### Fixed
- **F5 not launching the app from VSCode** — `PYTHONPATH` was missing from the Run
  and Debug launch configs, so Python could not find the `keithley_iv_suite` package
  under `src/`. Added `"PYTHONPATH": "${workspaceFolder}/src"` to both configs.
  ([.vscode/launch.json](.vscode/launch.json))
- **`main.py` import error** — entry point used `from src.keithley_iv_suite...`
  which conflicts with the `PYTHONPATH`-based layout. Changed to
  `from keithley_iv_suite...`. ([main.py](main.py))
- **`run_windows.bat` import error** — added `set PYTHONPATH=%APP_DIR%\src` before
  launch so the batch launcher matches the VSCode environment.
  ([scripts/run_windows.bat](scripts/run_windows.bat))

---

## [1.0.0] — 2026-04-01

### Added
- Initial release of Keithley IV Suite.
- **Instrument drivers** — Keithley 2400/2401 via SCPI; 2602/2614B via TSP (Lua).
- **VISA auto-detection** — tries NI-VISA, Keysight IO Libraries, then pyvisa-py
  fallback. Works across all four lab computers with mixed driver installations.
- **Measurements** — nMOS Transfer (Id-Vgs), nMOS Output (Id-Vds family), Resistor IV.
- **Flexible terminal assignment** — per-run SMU-to-terminal (Gate/Drain/Source)
  mapping via UI dropdowns.
- **Live pyqtgraph plot** — real-time updates, multi-curve output family, pan/zoom.
- **Measurement queue** — ordered queue with Run All / Stop; auto-saves each result.
- **YAML/JSON recipe loader** — `File → Load Recipe…` populates the queue from a
  file (`recipes/nmos_full_characterization.yaml`, `recipes/resistor_sweep.yaml`).
- **CSV export** — timestamped files with full metadata header block.
- **Dark charcoal / amber theme** — full Qt stylesheet in `ui/theme.py`.
- **Deployment options** — `scripts/install_windows.bat` (venv),
  `scripts/build_exe.bat` (PyInstaller standalone), Docker + docker-compose.
- **VSCode integration** — `.vscode/launch.json` (F5 run/debug),
  `settings.json` (interpreter, editor), `extensions.json` (recommended extensions).
- **Student quickstart** — `QUICKSTART.md` step-by-step guide for novice users.
- **Keyboard shortcuts** — F5 run, Esc stop, Ctrl+S export, Ctrl+O recipe, Ctrl+A autoscale.
