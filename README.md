# Keithley IV Suite

**Multi-SMU IV Characterization Platform** — PyQt6 desktop app for measuring nMOS transistors and resistors with Keithley 2400, 2401, 2602, and 2614B source-measure units.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-amber)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

| Feature | Details |
|---|---|
| **Instruments** | Keithley 2400, 2401 (SCPI) · 2602, 2614B (TSP/Lua) |
| **VISA backends** | NI-VISA · Keysight IO Libraries · pyvisa-py (pure Python fallback) |
| **Measurements** | nMOS Transfer (Id-Vgs) · nMOS Output (Id-Vds family) · Resistor IV |
| **Terminal assignment** | Flexible per-run SMU-to-terminal mapping via UI |
| **Real-time plot** | Live pyqtgraph with pan/zoom, multi-curve output family |
| **Queue & automation** | Build ordered measurement queues; load YAML/JSON recipes |
| **Data export** | CSV with full metadata header |
| **Theme** | Dark charcoal / amber — easy on the eyes in dark labs |

---

## Quick Start

### 1. Install dependencies

```bash
cd keithley-iv-suite
pip install -r requirements.txt
```

> **VISA backend note:** This app tries NI-VISA or Keysight IO first (whichever is installed),
> then falls back to `pyvisa-py`.  
> - NI-VISA: install from [ni.com/visa](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html)  
> - Keysight IO: install from [keysight.com/find/iosuites](https://www.keysight.com/us/en/lib/software-detail/computer-software/io-libraries-suite-downloads-2175637.html)  
> - Pure Python: `pip install pyvisa-py pyusb gpib-ctypes` (limited functionality for some interfaces)

### 2. Run

```bash
python main.py
```

---

## Interface Overview

```
┌─────────────────┬───────────────────────────────┬────────────┐
│  INSTRUMENTS    │   SWEEP CONFIGURATION         │  QUEUE     │
│  ─────────────  │   (tabbed: Transfer/Output/   │  ────────  │
│  ● 2400  GPIB24 │    Resistor)                  │  ⏳ Trans  │
│  ● 2614B USB    │                               │  ⏳ Output │
│  ● 2602  GPIB6  │   SMU Assignment              │            │
│  ○ 2401  ----   │   Sweep Parameters            │  [Run All] │
│                 │   Compliance / NPLC           │            │
│  [Scan VISA]    │                               │  [Stop]    │
│  [Connect All]  │   [▶ Run Now]  [+Add Queue]   │            │
├─────────────────┴───────────────────────────────┴────────────┤
│   LIVE PLOT                                    [⤢ Autoscale] │
│   Id (mA) ▲                                                   │
│           │      ╱‾‾‾‾                                        │
│           │    ╱                                              │
│           │╱___________________ Vgs (V)                      │
│                                                               │
│   [Export CSV]  [Clear Plot]          80/80 pts ✓            │
└───────────────────────────────────────────────────────────────┘
```

---

## SMU–to–Instrument Mapping

| Keithley Model | Driver | Channels | Interface |
|---|---|---|---|
| 2400 | SCPI | Single | GPIB / USB |
| 2401 | SCPI | Single | GPIB / USB |
| 2602 | TSP (Lua) | A, B | GPIB / USB |
| 2614B | TSP (Lua) | A, B | GPIB / USB / Ethernet |

The 2600-series instruments expose two independent channels (smua / smub).  
When you connect a 2602 or 2614B the app connects **Channel A** by default.  
To use Channel B, add the same instrument again in the Manual Entry box with `Channel B` selected.

---

## Recipe Files

Automate full measurement sequences by loading a YAML or JSON recipe:

```
File → Load Recipe…
```

Example (`recipes/nmos_full_characterization.yaml`):

```yaml
measurements:
  - type: nmos_transfer
    label: "Vth extraction"
    vgs_start: -1.0
    vgs_stop: 3.0
    vgs_step: 0.05
    vds_fixed: 0.1
    assignments:
      gate:  { instrument: "Keithley 2400" }
      drain: { instrument: "Keithley 2614B", channel: "A" }
      source: gnd

  - type: nmos_output
    label: "Output family"
    vds_start: 0.0
    vds_stop: 3.0
    vds_step: 0.05
    vgs_list: [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    assignments:
      gate:  { instrument: "Keithley 2400" }
      drain: { instrument: "Keithley 2614B", channel: "A" }
      source: gnd
```

---

## Keyboard Shortcuts

| Action | Shortcut |
|---|---|
| Run current sweep | F5 |
| Stop measurement | Esc |
| Export last result | Ctrl+S |
| Load recipe | Ctrl+O |
| Autoscale plot | Ctrl+A |
| Quit | Ctrl+Q |

---

## Project Structure

```
keithley-iv-suite/
├── main.py
├── requirements.txt
├── pyproject.toml
├── recipes/
│   ├── nmos_full_characterization.yaml
│   └── resistor_sweep.yaml
└── src/keithley_iv_suite/
    ├── instruments/          # VISA manager + SMU drivers (2400, 2600)
    ├── measurements/         # Sweep configs, measurement functions, queue
    ├── data/                 # CSV exporter
    └── ui/
        ├── theme.py          # Charcoal/amber stylesheet
        ├── main_window.py    # QMainWindow
        ├── panels/           # Instrument, Sweep, Plot, Queue panels
        ├── dialogs/          # About dialog
        └── workers/          # QThread measurement worker
```

---

## Multi-Computer Setup

The VISA backend is auto-detected at startup.  
On machines with **both** NI-VISA and Keysight IO installed, NI-VISA is preferred.  
To force a specific backend, edit `VISAManager("@py")` in `main_window.py` or set the
`PYVISA_LIBRARY` environment variable.

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built by [prashantUCSB](https://github.com/prashantUCSB)*
