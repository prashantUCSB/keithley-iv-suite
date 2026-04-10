# Keithley IV Suite — Windows Deployment Guide

This guide covers everything needed to run Keithley IV Suite on a **brand-new Windows computer
with nothing pre-installed** — both as a standalone EXE (zero-Python) and as a developer setup
with VSCode.

---

## Option A — Standalone EXE (Recommended for instrument computers)

This is the simplest path. No Python, no VSCode, no configuration needed on the target machine.

### What you need
- The file `Keithley_IV_Suite_v2.0.0_Setup.exe` (built once on a dev machine — see below)
- A VISA driver if you use GPIB instruments (USB and Ethernet work without one)

### Steps on the target computer

1. **Run the installer**
   Double-click `Keithley_IV_Suite_v2.0.0_Setup.exe` and follow the wizard.
   - Installs to `C:\Program Files\Keithley IV Suite\`
   - Creates a Start Menu shortcut
   - Optional Desktop shortcut (tick the checkbox on the last screen)

2. **Install a VISA driver** *(only needed for GPIB instruments)*

   | Interface | Driver needed? |
   |---|---|
   | USB-TMC (USB cable, rectangular plug) | No — works out of the box |
   | Ethernet (TCPIP/LAN) | No — works out of the box |
   | RS-232 (DB-9 serial cable) | No — works out of the box |
   | GPIB (IEEE-488 cable) | **Yes** — install NI-VISA |

   Download NI-VISA (free):
   https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html

3. **Launch the app**
   Start Menu → **Keithley IV Suite**, or double-click the Desktop shortcut.

> **That's it.** No Python, no terminal, no configuration files.

---

### Building the installer (do this once on your dev machine)

If you need to rebuild the installer after code changes:

1. Make sure `scripts\install_windows.bat` has been run at least once (sets up `.venv`)
2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
3. Double-click `scripts\build_installer.bat`
4. Output: `release\Keithley_IV_Suite_v2.0.0_Setup.exe`

To build only the portable folder (no Inno Setup required):

```
scripts\build_exe.bat
```

Output: `dist\Keithley_IV_Suite\` — zip this folder and copy it to any Windows 10/11 x64 machine.

---

---

## Option B — Developer setup with VSCode

Use this if you want to edit code, add measurement types, or debug the application.

### Step 1 — Install Python

1. Go to https://www.python.org/downloads/
2. Download **Python 3.11** or **3.12** (either works; avoid 3.13 — some packages lag behind)
3. Run the installer
4. **Critical:** On the first screen tick **"Add Python to PATH"** before clicking Install

Verify in a new terminal (`Win + R` → `cmd`):
```
python --version
```
Expected output: `Python 3.11.x` or `Python 3.12.x`

---

### Step 2 — Install Git

1. Go to https://git-scm.com/download/win
2. Download and run the installer (all defaults are fine)
3. Verify: open a new terminal and run `git --version`

---

### Step 3 — Install Visual Studio Code

1. Go to https://code.visualstudio.com/
2. Download and install (all defaults are fine)
3. Launch VSCode

---

### Step 4 — Get the code

Open a terminal (`Win + R` → `cmd` or PowerShell):

```
git clone https://github.com/prashantUCSB/keithley-iv-suite.git
cd keithley-iv-suite
```

Or download the ZIP from https://github.com/prashantUCSB/keithley-iv-suite
(Code → Download ZIP → unzip to `Documents\keithley-iv-suite`)

---

### Step 5 — Create the virtual environment

Double-click `scripts\install_windows.bat`.

A terminal window runs through four steps:
1. Creates `.venv\` inside the project folder
2. Upgrades pip
3. Installs all Python packages (PyQt6, pyqtgraph, pyvisa, etc.)
4. Checks whether a VISA backend is available

When it prints **"Installation complete!"** press any key.

> The `.venv` folder is **self-contained** — it only affects this project, never your system Python.

---

### Step 6 — Open the project in VSCode

1. In VSCode: **File → Open Folder…**
2. Navigate to the `keithley-iv-suite` folder and click **"Select Folder"**
3. If asked "Do you trust the authors?" → click **"Yes, I trust the authors"**

---

### Step 7 — Install VSCode extensions

A notification will appear in the bottom-right corner:
> "Do you want to install the recommended extensions for this repository?"

Click **"Install All"**.

If the notification doesn't appear:

1. Press `Ctrl + Shift + X` to open Extensions
2. Search for and install each of these:
   - **Python** (by Microsoft)
   - **Pylance** (by Microsoft)
   - **Python Debugger** (by Microsoft) — usually installed automatically with Python

---

### Step 8 — Select the Python interpreter (`.venv`)

This is the most important step. VSCode must use the `.venv` Python, not your system Python.

**Method 1 — Status bar (quickest)**

1. Look at the **bottom-left corner** of the VSCode window
2. Click the Python version shown there (e.g. `Python 3.12.0`)
3. A picker opens at the top of the screen — look for the entry that says:
   ```
   Python 3.x.x ('.venv': venv)
   ```
   with a path ending in `.venv\Scripts\python.exe`
4. Click it

**Method 2 — Command Palette (if Method 1 doesn't show the venv)**

1. Press `Ctrl + Shift + P`
2. Type `Python: Select Interpreter` and press Enter
3. If `.venv` appears in the list, click it
4. If it does not appear, click **"Enter interpreter path…"**, then **"Find…"**,
   navigate to `.venv\Scripts\python.exe` inside the project folder, and click **"Select Interpreter"**

**Verify it worked:**
The bottom-left corner should now show `Python 3.x.x ('.venv': venv)` — the `('.venv')` part is the confirmation.

> **Why this matters:** If VSCode uses the wrong Python, it will fail to find PyQt6, pyvisa, and every other
> package that was installed into `.venv`. You will see import errors and red underlines everywhere.

---

### Step 9 — Run the application

Press **F5**.

The app window should open. If you see errors in the terminal panel, check:

| Error message | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'PyQt6'` | `.venv` interpreter not selected — repeat Step 8 |
| `ModuleNotFoundError: No module named 'pyvisa'` | Same as above |
| `No VISA backend found` | Install NI-VISA (GPIB) or ignore (USB/Ethernet work without it) |
| `python: can't open file 'main.py'` | Wrong working directory — VSCode must open the `keithley-iv-suite` folder |

You can also run without debugging by pressing `Ctrl + F5`, which is slightly faster.

---

### Step 10 — Install a VISA driver (GPIB instruments only)

USB-TMC, Ethernet, and RS-232 instruments work with the bundled `pyvisa-py` backend.
GPIB instruments additionally need a hardware driver:

**NI-VISA (most common, free):**
https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html

After installing, restart the PC, then launch the app — it will auto-detect NI-VISA.

---

## Connecting instruments

### Auto-scan (USB and Ethernet)
1. Click **"⟳ Scan VISA"** in the Instruments panel
2. Connected instruments appear automatically
3. Click **"Connect"** next to each one

### Manual entry (GPIB, RS-232, or if scan misses an instrument)

Click **"Manual Entry"** and type the VISA resource string:

| Connection | Resource string format | Example |
|---|---|---|
| GPIB | `GPIB0::<addr>::INSTR` | `GPIB0::24::INSTR` |
| USB-TMC | `USB0::0x05E6::0x2400::<serial>::INSTR` | (paste from NI MAX) |
| Ethernet | `TCPIP0::<ip>::inst0::INSTR` | `TCPIP0::192.168.1.10::inst0::INSTR` |
| RS-232 | `ASRL<n>::INSTR` | `ASRL3::INSTR` (= COM3) |

For RS-232: a **Baud rate** dropdown appears automatically when you type `ASRL`.
Factory default for 2400/2401 is **9600**. Check `MENU → RS232 → BAUD` on the front panel if unsure.

**Finding the GPIB address:** Press `MENU` on the instrument → `COMMUNICATION` → `GPIB` → note the number shown.

---

## Folder structure after setup

```
keithley-iv-suite\
├── .venv\                  ← Python virtual environment (created by install_windows.bat)
│   └── Scripts\python.exe  ← This is what VSCode should point to
├── .vscode\
│   ├── settings.json       ← Tells VSCode to use .venv automatically
│   └── launch.json         ← F5 run configuration
├── main.py                 ← App entry point
├── requirements.txt
├── scripts\
│   ├── install_windows.bat ← Run once to create .venv
│   ├── run_windows.bat     ← Launch app without VSCode
│   ├── build_exe.bat       ← Build portable EXE folder
│   └── build_installer.bat ← Build self-installing Setup.exe
├── src\keithley_iv_suite\  ← All application source code
└── recipes\                ← Example YAML measurement recipes
```

---

## Troubleshooting

### VSCode shows red underlines everywhere / IntelliSense is broken

The Python extension is using the wrong interpreter.
Repeat **Step 8** — make sure the status bar shows `('.venv': venv)`.

### Terminal opens but `python` or `pip` is not found

The `.venv` is not activated in the terminal. In VSCode:
- Press `` Ctrl + ` `` to open a new terminal — VSCode should activate `.venv` automatically
- If not, run manually: `.venv\Scripts\activate` then re-run your command

### `install_windows.bat` fails at "Installing dependencies"

Usually a network issue. Check:
- You are connected to the internet
- No proxy is blocking pip (common on university networks) — try: `pip install --proxy http://proxy:port -r requirements.txt`

### App launches but plots are blank / all values are zero

Check the SMU Assignment panel — verify each terminal (Gate, Drain, Source) is assigned to a connected instrument, not left on `-- select --`.

### Measurement starts but immediately hits compliance

- Reduce compliance current (Compliance group in the Settings tab)
- Check wiring — a gate/drain swap causes immediate compliance

---

## Quick reference: running without VSCode

```
scripts\run_windows.bat
```

This activates `.venv` and launches `main.py` directly — no IDE needed.

---

*For bugs or questions: https://github.com/prashantUCSB/keithley-iv-suite/issues*
