# Changelog

All notable changes to Keithley IV Suite are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [1.0.9] — 2026-04-03

### Added

- **3-tab plot panel** — replaced the single plot widget with a `QTabWidget`
  containing three tabs populated at sweep completion:
  - **Linear** — live linear-scale plot with fit/marker overlay
  - **Log Scale** — log-Y plot of |Id| or |I|
  - **Analysis** (label varies by measurement type):
    - *Resistor IV* → "Residuals": measured − fit scatter + σ annotation
    - *nMOS Transfer* → "gm": transconductance vs Vgs
    - *nMOS Output* → "gd": output conductance vs Vds per curve
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Resistor best-fit line** — unconstrained linear fit `I = m·V + b`
  computed at sweep end; dashed amber overlay extrapolated ±20% beyond
  data; equation and R² annotated on the plot; R, R², and σ(residual)
  shown in the params label and status bar.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **nMOS Transfer post-sweep analysis** — gm peak, Vgs at gm peak, and
  Vth (via √Id linear extrapolation near gm peak) computed at sweep end;
  Vth shown as a dashed vertical marker on both Linear and Log tabs.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **nMOS Output post-sweep analysis** — gd (dId/dVds) computed per curve
  at sweep end; all curves shown in Analysis tab.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Export PNG** — "Export PNG" button exports the currently visible tab
  as a PNG image via `pyqtgraph.exporters.ImageExporter`; also available
  via View → Export Plot as PNG (Ctrl+P).
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py),
  [main_window.py](src/keithley_iv_suite/ui/main_window.py))

- **Extracted params in status bar** — `params_updated` signal wired to
  `MainWindow._on_params_updated`; R / gm / Vth / gd appear in the
  status bar in amber after each sweep.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py))

---

## [1.0.8] — 2026-04-02

### Changed

- **Auto-scaling SI prefix axis labels** — plot axes now display natural
  unit prefixes (mA, µA, nA, pA, fA, mV, …) instead of raw SI (A, V).
  X-axis prefix is pre-selected from the sweep voltage range at measurement
  start. Y-axis prefix starts from the compliance estimate and updates
  live as each point arrives — all curves are redrawn immediately when the
  prefix changes so the scale is always correct.
  Supported prefixes: f, p, n, µ, m, (none), k.
  Raw SI values are still stored internally and exported to CSV unchanged.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

---

## [1.0.7] — 2026-04-02

### Fixed

- **Root cause of "cannot modify table" TSP error** — `output_on()` and
  `output_off()` sent `smua.output = ...` which is not a valid TSP attribute.
  The 2600-series TSP `__newindex` metamethod rejects unknown fields on the
  `smua`/`smub` table with "cannot modify table". Correct attribute is
  `smua.source.output` (confirmed against the Keithley MATLAB reference
  implementation). Also corrected `configure_voltage_source()` end-of-config
  command from `source.levelv = 0` to `source.output = OUTPUT_OFF` to match.
  ([smu_2600.py](src/keithley_iv_suite/instruments/smu_2600.py))

---

## [1.0.6] — 2026-04-02

### Fixed

- **TSP "cannot modify table" runtime error on instrument front panel** —
  `smua.AUTOZERO_AUTO` and `smua.AUTORANGE_ON` symbolic constants are `nil`
  on some 2602/2614B firmware versions. Assigning `nil` to a TSP-protected
  attribute raises the Lua "cannot modify table" error. Replaced all three
  occurrences with their documented integer literals: `2` (AUTOZERO\_AUTO),
  `1` (AUTORANGE\_ON).
  ([smu_2600.py](src/keithley_iv_suite/instruments/smu_2600.py))

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
