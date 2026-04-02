# Changelog

All notable changes to Keithley IV Suite are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [1.0.5] — 2026-04-02

### Fixed

- **`ValueError: could not convert string to float` in fallback path of `measure_iv()`** —
  some 2614B firmware versions return tab-separated `current\tvoltage` even from
  `measure.i()` (not just `measure.iv()`). The fallback path was calling `float()`
  directly on the raw string. Extracted a `_extract_floats()` helper and made all
  code paths parse defensively: if `measure.i()` returns two values they are used
  directly; if it returns one the separate `measure.v()` call follows; if neither
  yields a parseable result a clear `RuntimeError` is raised instead of a confusing
  `ValueError`.
  ([smu_2600.py](src/keithley_iv_suite/instruments/smu_2600.py))

---

## [1.0.4] — 2026-04-01

### Fixed

- **USB instruments showing raw VISA string instead of model number** — replaced the
  old string-based `_KEITHLEY_USB_IDS` dict (keys like `"05E6::2614"` never matched
  `"0x05E6::0x2614"`) with integer product-ID lookup via a compiled regex. Now correctly
  identifies 2614B, 2602, 2634B, etc. from USB resource strings even when `*IDN?`
  is unavailable at scan time.
  ([visa_manager.py](src/keithley_iv_suite/instruments/visa_manager.py))
- **`_friendly_name` including full manufacturer string** — was returning
  `"KEITHLEY INSTRUMENTS INC. MODEL 2614B"`; now extracts the model field only
  (`"Keithley 2614B"`).
  ([visa_manager.py](src/keithley_iv_suite/instruments/visa_manager.py))
- **Instrument name and address text overflow** — replaced plain `QLabel` with a new
  `ElidedLabel` subclass that overrides `paintEvent` to render text with `…` when it
  exceeds the widget width. Both the name and address sub-labels in `InstrumentRow`
  now use it.
  ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))
- **Address sub-label showing full VISA resource string** — replaced with a short
  human-readable form: `GPIB · 24`, `USB · 0x2614`, `LAN · 192.168.1.10`.
  ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

---

## [1.0.3] — 2026-04-01

### Fixed

- **2614B misidentified as 2400** — `_connect_instrument()` now queries `*IDN?`
  directly on the freshly-opened VISA resource before creating any typed driver.
  Previously, model detection relied on the scan-time IDN which could be empty
  (500 ms timeout too short for 2600-series), causing `_guess_model()` to fall
  back to `"2400"` and create an `SMU2400` driver for the 2614B.
  ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))
- **Label ignored real IDN** — `_label_for()` trusted the guessed `model_hint`
  over the actual `*IDN?` response. Rewrote to parse `IDN` field 2 (`"MODEL 2614B"`)
  first; `model_hint` is now only used as a fallback.
  ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))
- **Scan-time IDN timeout** — `list_resources_with_info()` raised `open_timeout`
  from 500 ms to 2000 ms and set `res.timeout = 2000` so 2600-series instruments
  have enough time to respond during the VISA scan.
  ([visa_manager.py](src/keithley_iv_suite/instruments/visa_manager.py))

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
