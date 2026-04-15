# Changelog

All notable changes to Keithley IV Suite are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.2.2] — 2026-04-15

### Fixed

- **Error 802 "Output blocked by interlock"** — the 2600-series requires the
  INTLK pin shorted to AGND on the rear-panel digital I/O connector before
  allowing outputs above ~42 V.  Previously this caused a silent failure or a
  cryptic VISA exception.  The driver now detects error 802 in `output_on()` and
  in `set_voltage()` (checked whenever the setpoint crosses 42 V) and raises a
  `RuntimeError` with a clear, actionable message:
  *"Short INTLK to AGND on the rear-panel digital I/O connector before sourcing
  above ~42 V — see the Interlock section of your model's Reference Manual for
  exact pin numbers."*
  ([smu_2600.py](src/keithley_iv_suite/instruments/smu_2600.py))

---

## [2.2.1] — 2026-04-15

### Fixed

- **Error 350 "Queue Overflow" on instrument LCD** — the Keithley error/event
  queue (max 10 entries on 2600-series) was never cleared between measurements.
  Compliance hits, autorange transitions, and source range changes are silently
  logged as status events; once the queue fills, the instrument appends error 350
  and displays it on the front panel.
  - *2600 driver*: `smu.reset()` resets the channel but does **not** touch the
    global `errorqueue`. Added `errorqueue.clear()` in `reset()` and at the start
    of `configure_voltage_source` / `configure_current_source`.
  - *2400 driver*: `reset()` already issues `*CLS`, but added it at the top of
    both configure methods as a second line of defence — events from the previous
    measurement can accumulate between `reset()` and `configure_*`.
  ([smu_2600.py](src/keithley_iv_suite/instruments/smu_2600.py),
  [smu_2400.py](src/keithley_iv_suite/instruments/smu_2400.py))

---

## [2.2.0] — 2026-04-15

### Added

- **Photodiode IV tab** — new measurement mode sweeps voltage from reverse bias
  (dark current / leakage characterisation, nA–µA range) to forward bias
  (exponential turn-on, ideality-factor extraction). Anode connected to T1 SMU;
  cathode grounded. Defaults: −5 V → +1.5 V, 0.05 V step, 100 mA compliance.
  Full CSV, PNG, and Excel export support. Instructions tab with wiring notes,
  ideality-factor formula, and source-range guidance.
  ([sweep_config.py](src/keithley_iv_suite/measurements/sweep_config.py),
  [photodiode_iv.py](src/keithley_iv_suite/measurements/photodiode_iv.py),
  [sweep_panel.py](src/keithley_iv_suite/ui/panels/sweep_panel.py))

### Changed

- **Output (Id-Vds) Vds sweep range** extended from ±40 V to ±210 V — allows
  high-voltage breakdown characterisation on MOSFETs rated above 40 V. The Vds
  step maximum is also raised from 10 V to 50 V to keep point counts manageable
  at wide sweeps.
  ([sweep_panel.py](src/keithley_iv_suite/ui/panels/sweep_panel.py))

- **Transfer (Id-Vgs) voltage ranges** extended to ±210 V for Vgs and Vds fixed
  bias, matching the Output tab.

- **Source SMU compliance** for nMOS Output sweeps now inherits `compliance_drain_A`
  from the sweep config (was hardcoded to 100 mA). If drain compliance is raised to
  500 mA or 1 A, the source SMU now matches, preventing premature compliance trips.
  ([nmos_output.py](src/keithley_iv_suite/measurements/nmos_output.py))

---

## [2.1.0] — 2026-04-14

### Added

- **Queue Export** — each queue item carries a "Save" checkbox (checked by default,
  opt-out model). When a measurement completes, if the box is checked the result is
  auto-saved in a background thread via `ExportWorker(QThread)`. Formats:
  - *CSV* — one `.csv` + `.png` per measurement inside a `YYYYMMDD_HHMMSS/` subfolder
    of the output directory.
  - *Excel* — one `.xlsx` workbook per queue run (`IV_Data_<timestamp>.xlsx`), one
    sheet per measurement with styled header rows, config metadata block, and data
    columns. Thread-safe: a shared `threading.Lock` serialises concurrent sheet
    appends.
  - *Both* — CSV/PNG subfolder and Excel sheet in parallel.
  A "Check All" button marks every queued item for export. The format selector
  (CSV / Excel / Both) lives in the Queue panel.
  ([queue_panel.py](src/keithley_iv_suite/ui/panels/queue_panel.py),
  [export_worker.py](src/keithley_iv_suite/ui/workers/export_worker.py),
  [exporter.py](src/keithley_iv_suite/data/exporter.py))

- **SMU Wiring Guide (F1)** — in-app HTML reference dialog (`WiringGuideDialog`)
  covering terminal nomenclature, BNC/triax wiring, screw-terminal breakout pinout,
  2-wire vs 4-wire sense comparison, Guard at probe-tip guidance, and per-measurement
  wiring diagrams (MOSFET, 4PP, Van der Pauw, Hall bar, resistor).
  Accessible via Help → Wiring Guide or F1.
  ([wiring_guide_dialog.py](src/keithley_iv_suite/ui/dialogs/wiring_guide_dialog.py),
  [main_window.py](src/keithley_iv_suite/ui/main_window.py))

- **Developer attribution** — "Prashant Srinivasan" (muted slate) and "v2.1.0"
  (bright green `#22c55e`) are always visible in the top bar, to the right of the
  app title. Also shown in the About dialog.
  ([theme.py](src/keithley_iv_suite/ui/theme.py),
  [main_window.py](src/keithley_iv_suite/ui/main_window.py),
  [about_dialog.py](src/keithley_iv_suite/ui/dialogs/about_dialog.py))

- **Output-directory path bar** — a flat button in the top bar shows the last two
  components of the current output path (e.g. `📁 Documents/IV_Data`). Clicking it
  opens the directory picker (same as File → Set Output Directory). Tooltip shows
  the full path.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py))

- **Queue menu** — new "Queue" menu between View and Help:
  - *Show Queue* (Ctrl+Shift+Q, checkable) — shows / hides the floating dock.
  - *Run Queue* (F6) — starts the queue.
  - *Stop* (Esc) — stops the running measurement.
  - *Check All for Export* — marks every queue item for auto-save.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py))

### Changed

- **Queue panel → floating QDockWidget** — the queue is no longer embedded in
  the left vertical splitter. It opens as a floating window (default 300 × 520 px)
  that can be dragged, resized, or docked to any edge of the main window. The sweep
  panel now occupies the full height of its column with no sharing.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py),
  [queue_panel.py](src/keithley_iv_suite/ui/panels/queue_panel.py))

- **Queue panel UX** — removed the ↑/↓ reorder buttons (the table is scrollable).
  "Remove Selected" now posts a status-bar message: `Removed '<name>' from queue`.
  ([queue_panel.py](src/keithley_iv_suite/ui/panels/queue_panel.py))

- **Plot panel de-clutter** — removed the "LIVE PLOT" section header, the
  inline "Export CSV" and "Export PNG" buttons (still available in the Measurement
  and View menus), and the equation/params label (values appear in the status bar
  via `params_updated`). The Curve Style toolbar is now hidden by default; a "⚙ Style"
  toggle button in the control row shows it on demand. "Overlay runs" checkbox moved
  to the main control row for quick access.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

### Fixed

- **4-wire sense mode lost after reset** — `SMUBase.reset()` sends `*RST` (2400) or
  `smu.reset()` (2600), both of which clear the hardware sense setting. Drivers now
  store `_remote_sense` and restore it at the end of every `reset()` call, so the
  4W Sense button in the Instrument Panel remains effective across measurement runs.
  ([smu_base.py](src/keithley_iv_suite/instruments/smu_base.py),
  [smu_2400.py](src/keithley_iv_suite/instruments/smu_2400.py),
  [smu_2600.py](src/keithley_iv_suite/instruments/smu_2600.py))

- **Curve "Color" button invisible in dark theme** — the no-selection stylesheet
  lacked a `color:` property, making the label text blend into the dark background.
  Added `color:{TEXT_PRIMARY}` to the unselected state.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **"Color" button text clipped** — changed from `setFixedSize(56, 24)` to
  `setMinimumWidth(64)` so the label is never truncated.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

---

## [Unreleased]

### Fixed

- **`install_windows.bat` — `. was unexpected at this time.` on VISA verify step** —
  three separate CMD parsing bugs combined to produce this error at step [4/4]:

  1. **Unescaped `)` inside an `if` block** — `echo        Falling back to
     pyvisa-py (limited GPIB support).` was inside a parenthesized `if errorlevel 1 (...)`
     block. CMD's batch parser does not respect double-quoted strings inside compound
     blocks; the `)` in `(limited GPIB support)` was treated as closing the `if` block
     early. The `.` that followed on the same line then became an unexpected token,
     producing the error. Fixed by escaping both parens: `^(limited GPIB support^)`.
     This is the same class of bug fixed in `build_exe.bat` on 2026-04-13
     (commit `d5a87d0`).

  2. **Inline Python `-c` with parentheses** — the original VISA check used
     `python.exe -c "import pyvisa; rm=pyvisa.ResourceManager(); print(...); rm.close()"`.
     The `()` in `ResourceManager()` and `rm.close()` can confuse the CMD tokenizer
     when `EnableDelayedExpansion` is active. Extracted to a standalone helper
     `scripts/verify_visa.py` and call it by path instead.

  3. **`APP_DIR` set to a path containing `..`** — `set "APP_DIR=%~dp0.."` left a
     literal `..` in the variable (e.g. `C:\...\scripts\..`). Replaced with the
     `pushd "%~dp0.." / set "APP_DIR=%CD%"` pattern so `APP_DIR` is always an
     absolute, normalized path. `popd` added before every `exit /b 1` and at end of
     script to restore the original working directory on all paths.

  Also removed non-ASCII em-dash characters (`—`) from the script header and `echo`
  lines (replaced with `--`), which can cause misparse on systems where the console
  code page does not match the file encoding.
  ([scripts/install_windows.bat](scripts/install_windows.bat),
  [scripts/verify_visa.py](scripts/verify_visa.py))

---

## [1.5.0] — 2026-04-09

### Fixed

- **VISA duplicate instruments** — NI-VISA enumerates the same USB device
  under two resource strings (with and without the interface-index suffix,
  e.g. `::INSTR` vs `::0::INSTR`).  A deduplication step now extracts the
  `(vendor, product, serial)` tuple from each USB resource string before
  probing and skips any second occurrence with the same serial.
  ([visa_manager.py](src/keithley_iv_suite/instruments/visa_manager.py))

### Changed

- **Marker size spinbox** — `setFixedWidth(50)` replaced with
  `setMinimumWidth(52)` and range extended to 1–30 so two-digit values are
  no longer clipped by the widget boundary.

- **Fit line color + show/hide** — a color swatch button and "Show" checkbox
  for the fit line (dashed overlay) are now in the style toolbar.  The color
  button opens a color picker and immediately recolors all `PlotDataItem` fit
  lines on the current plot.  The "Show" checkbox toggles visibility of all
  overlay items (fit lines, Vth marker, text annotations) in one click.

- **Curve color swatch** — the "Color" button now renders its background in
  the selected curve's current color so the active color is always visible
  without opening the dialog.

- **Overlay runs** — a new "Overlay runs" checkbox in the style toolbar.
  When checked, `prepare()` skips `clear()` and advances the curve-ID offset
  so each new sweep gets the next color in the palette without overwriting
  previous data.  Each overlaid run produces its own independent fit line.
  When unchecked (default), the plot clears on each new sweep as before.
  Applies to Resistor IV and Transfer sweeps.  Use the "Clear" button to
  reset the plot when finished overlaying.

---

## [1.4.0] — 2026-04-09

### Fixed

- **Live plot scroll loop** — pyqtgraph's default `enableAutoRange` caused the
  view to re-fit on every `setData` call at 25 Hz, producing a constant
  scrolling / jumping effect.  `disableAutoRange()` is now called in
  `prepare()` and axes are pre-set to the sweep range + compliance from the
  config.  `autoRange()` is called once in `mark_done()` for a final fit after
  the sweep completes.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Nonsense Y readings during measurement** — `_y_scale` (the SI prefix
  multiplier) was updated dynamically in `append_point()` as larger currents
  arrived, causing the axis label and all plotted values to silently change
  units mid-sweep while the view range stayed fixed.  The scale is now frozen
  at the value computed in `prepare()` from the compliance setting; the
  post-sweep `autoRange()` rescales to the actual data.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

### Changed

- **Layout rearrangement** — queue panel moved below sweep configuration in a
  vertical splitter; live plot now occupies all remaining horizontal space.
  New hierarchy:
  `[instruments | [sweep / queue (vertical)] | plot (expands)]`.
  All dividers are draggable; instrument and sweep+queue columns have a
  minimum width but no fixed width, so the user can resize freely.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py),
  [queue_panel.py](src/keithley_iv_suite/ui/panels/queue_panel.py),
  [instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

- **VISA scan robustness** — connect buttons on existing rows are disabled
  while a background scan is running to prevent VISA resource contention.
  `open_resource()` now passes `open_timeout` to pyvisa.  GPIB resources
  receive a `clear()` before the `*IDN?` query to flush stale I/O from prior
  sessions.  `VisaIOError` is caught and logged with the resource address for
  easier diagnosis of intermittent connection failures.
  ([visa_manager.py](src/keithley_iv_suite/instruments/visa_manager.py),
  [instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

- **Connect robustness** — `_connect_instrument` now retries `open_resource()`
  once after a 500 ms delay and retries `*IDN?` once after 300 ms.  A failed
  `reset()` logs a warning but no longer blocks the connection — the driver is
  still registered so measurement can proceed.
  ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

---

## [1.3.0] — 2026-04-09

### Changed

- **Single live PlotWidget** — replaced the three-panel side-by-side layout
  with one `PlotWidget` that fills all available space.  Multiple panels were
  the root cause of the post-sweep GUI freeze: each panel triggered its own
  repaint chain and the combined cost blocked the main thread.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Forced V / Sensed V radio toggle** — two radio buttons in the header row
  select which voltage column drives the X axis.  Both datasets are always
  accumulated; toggling during or after a sweep redraws immediately from the
  stored data.  Default is Forced V; switch to Sensed V for 4-wire (Kelvin)
  measurements where the two diverge.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Log |I| checkbox** — replaces the old tab-based log view.  Toggling live
  switches pyqtgraph's Y log mode and redraws from stored data; no data loss.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Lightweight post-sweep overlay** — `_add_overlay()` replaces the old
  `_compute_analysis()`.  It adds at most two items to the existing plot (a
  dashed fit line for resistor sweeps, a Vth `InfiniteLine` for transfer
  sweeps) instead of rebuilding separate analysis panels.  Output family
  curves need no annotation.  The main thread is never blocked.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

### Removed

- Separate analysis panels (Residuals / gm / gd plot widgets) — primary users
  want raw IV curves; derived quantities can be computed offline from the CSV.

---

## [1.2.1] — 2026-04-06

### Fixed

- **GUI freeze during measurement** — `append_point` was calling `setData` +
  triggering a full repaint on every incoming sample, which on three plots can
  saturate the Qt event loop at high data rates.  All repaints are now batched
  through a 25 Hz `QTimer` (`_flush_paint`); data accumulates between ticks and
  the paint timer stops automatically when the sweep ends or is cleared.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Sweep panel dominated the vertical space** — the vertical `QSplitter` was
  dividing space proportionally on resize, so the sweep config panel grew at the
  expense of the plots.  Stretch factors are now `0 / 1` (sweep / plots), the
  initial split is `240 / 720`, and the window default is `1500 × 960`.
  Sweep panel can now be fully collapsed by dragging the handle.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py))

- **Instrument and queue panels grew when window was widened** — horizontal
  splitter stretch factors set to `0 / 1 / 0` so only the centre plot area
  absorbs extra horizontal space.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py))

---

## [1.2.0] — 2026-04-03

### Changed

- **Three side-by-side live plots** — replaced the single-tab + Forced/Sensed
  toggle with a horizontal `QSplitter` containing three simultaneously visible
  `PlotWidget`s: *Forced V* (left), *Sensed V* (centre), and *Analysis* (right).
  All three update in real time as data arrives.  The analysis pane shows
  log |I| during the sweep, then is replaced at sweep completion with the
  type-specific post-sweep result (Residuals / gm / gd).
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Fit line shown on both Forced and Sensed panes** — resistor best-fit line
  is computed independently for V_forced and V_sensed and drawn on each pane.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

### Fixed

- **Forced/Sensed plots not rendering** — the previous toggle approach shared
  a single curve dict with `_pw1`; switching mode called `_redraw_pw1()` but
  the curve objects were already attached to the old plot item.  The new design
  creates independent `PlotDataItem` pairs (one per pane) so each pane always
  holds its own live data.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Fonts not scaling with window / DPI** — removed hardcoded `font-size:8pt`
  inline overrides from `InstrumentRow` (address label and 2W/4W button) and
  `MainWindow` top-bar labels; all sizes now use `theme.FONT_SIZE_*` constants.
  Added `_apply_dpi_font_scale()` in `__main__.py` that bumps the theme
  constants proportionally when the primary screen reports > 120 DPI.
  ([\_\_main\_\_.py](src/keithley_iv_suite/__main__.py),
  [instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py),
  [main_window.py](src/keithley_iv_suite/ui/main_window.py))

- **Single instrument badly positioned in Discovered panel** — added
  `AlignTop` to the `_scroll_content` `QVBoxLayout` so a lone instrument row
  sits at the top of the group box instead of vertically centred or expanded.
  ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

- **"Disconnect" button text clipped** — increased `setMinimumWidth` from 90
  to 110 px to give "Disconnect" (10 chars + padding) enough room at all font
  sizes.
  ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

- **Autoscale (Ctrl+A) only scaled the forced plot** — menu action now calls
  `_autoscale_all()` which calls `autoRange()` on all three plot widgets.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py))

---

## [1.1.0] — 2026-04-03

### Added

- **Forced / Sensed V / Readback toggle** — three-button row above the plot
  switches the X-axis between commanded setpoint (Forced V), SMU voltage
  readback (Sensed V), and full readback (Readback). All three data sets are
  stored per point; switching is instant.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Style toolbar** — always-visible panel below the plot; click any curve to
  select it, then adjust Color (QColorDialog), Line style (Solid/Dash/Dot/
  DashDot/None), Marker shape (Circle/Square/Triangle/Star/Diamond/None), and
  Marker size (1–20 px). Changes apply only to the selected curve.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Draggable annotations** — equation/gm/residual `TextItem` overlays on the
  plot can be click-dragged anywhere on the canvas via `ItemIsMovable` flag.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **Equation text box** — `y = mx + b` fit equation displayed in a
  non-clipping `QLabel` below the plot (selectable text, dark background,
  amber color); also shown as a draggable overlay on the Linear tab.
  ([plot_panel.py](src/keithley_iv_suite/ui/panels/plot_panel.py))

- **2W / 4W sense mode toggle** — per-instrument row button in the Instrument
  Panel; clicking toggles 2-wire (local) / 4-wire (remote Kelvin) sense.
  If the instrument is already connected, `set_sense_mode()` is called
  immediately. Button turns blue when 4-wire is active.
  ([instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

- **`set_sense_mode(remote)`** on SMU2400 (`:SYST:RSEN ON/OFF`) and SMU2600
  (`smua.sense = SENSE_REMOTE/LOCAL`); no-op default in SMUBase.
  ([smu_base.py](src/keithley_iv_suite/instruments/smu_base.py),
  [smu_2400.py](src/keithley_iv_suite/instruments/smu_2400.py),
  [smu_2600.py](src/keithley_iv_suite/instruments/smu_2600.py))

- **V_sensed column in CSV** — all exports now include both V_forced
  (commanded setpoint) and V_sensed (SMU readback), plus a header comment
  explaining the difference. Transfer: `Vgs_forced, Vgs_sensed, Id, Ig,
  Vds_sensed`. Output per curve: `Vds_forced, Vds_sensed, Id, Ig`. Resistor:
  `V_forced, V_sensed, I, R`.
  ([exporter.py](src/keithley_iv_suite/data/exporter.py),
  [nmos_transfer.py](src/keithley_iv_suite/measurements/nmos_transfer.py),
  [nmos_output.py](src/keithley_iv_suite/measurements/nmos_output.py),
  [resistor_iv.py](src/keithley_iv_suite/measurements/resistor_iv.py))

### Fixed

- **VISA scan showing phantom instruments** — `list_resources_with_info()`
  now skips any resource that fails to open OR returns an empty `*IDN?`
  response. Non-SMU instruments (printers, DAQ cards) are shown with their
  full IDN string for identification but cannot be connected as SMUs.
  ([visa_manager.py](src/keithley_iv_suite/instruments/visa_manager.py),
  [instrument_panel.py](src/keithley_iv_suite/ui/panels/instrument_panel.py))

- **`data_point` signal arity mismatch** — signal changed from `(float, float,
  int)` to `(float, float, float, int)` carrying `(v_forced, i_meas, v_sensed,
  curve_id)`; `_on_data_point` and `append_point` updated accordingly.
  ([measurement_worker.py](src/keithley_iv_suite/ui/workers/measurement_worker.py),
  [main_window.py](src/keithley_iv_suite/ui/main_window.py))

- **`_on_params_updated` triple inline import** — consolidated to single
  import at call site.
  ([main_window.py](src/keithley_iv_suite/ui/main_window.py))

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
