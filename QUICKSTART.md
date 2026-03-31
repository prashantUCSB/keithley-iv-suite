# Keithley IV Suite — Student Quickstart

This guide walks you through running the IV measurement app from scratch.
No programming experience is required.

---

## Step 1 — Install the tools (one time per computer)

You need three things installed. Check each one:

### 1a. Python

1. Go to <https://www.python.org/downloads/>
2. Click the big yellow **"Download Python 3.x.x"** button
3. Run the installer
4. **Important:** On the first screen, check the box that says **"Add Python to PATH"** before clicking Install

To verify it worked, open the Start menu, type `cmd`, press Enter, and type:

```text
python --version
```

You should see something like `Python 3.12.0`. If you see an error, reinstall Python and make sure you checked "Add to PATH".

---

### 1b. VISA drivers (for talking to the instruments)

The instruments (Keithley 2400, 2614B, etc.) speak a language called VISA over GPIB or USB cables. You need a driver so your computer understands it.

**Check if you already have one** — open Start and search for:

- `NI MAX` (NI Measurement & Automation Explorer) → you have NI-VISA ✓
- `Keysight Connection Expert` → you have Keysight IO ✓

If you have neither, download NI-VISA (free):
<https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html>

---

### 1c. Visual Studio Code

1. Go to <https://code.visualstudio.com/>
2. Download and install (all defaults are fine)

---

## Step 2 — Get the code

### Option A: Git (recommended if you have it)

Open a terminal (`cmd` or PowerShell) and run:

```bash
git clone https://github.com/prashantUCSB/keithley-iv-suite.git
cd keithley-iv-suite
```

### Option B: Download ZIP

1. Go to <https://github.com/prashantUCSB/keithley-iv-suite>
2. Click the green **"Code"** button → **"Download ZIP"**
3. Unzip the folder somewhere you can find it (e.g. `Documents\keithley-iv-suite`)

---

## Step 3 — Install Python packages (one time per computer)

Navigate into the `keithley-iv-suite` folder, then double-click:

```text
scripts\install_windows.bat
```

A black terminal window will open and install everything automatically. When it says **"Installation complete!"** press any key to close it.

This creates a `.venv` folder inside the project — it contains all the Python packages the app needs, isolated from the rest of your computer.

---

## Step 4 — Open the project in VSCode

1. Open VSCode
2. Click **File → Open Folder…**
3. Navigate to the `keithley-iv-suite` folder and click **Select Folder**
4. VSCode may ask **"Do you trust the authors of this folder?"** → click **Yes, I trust the authors**

### Install recommended extensions

A pop-up should appear in the bottom-right corner:

> "Do you want to install the recommended extensions?"

Click **Install**. This adds Python support and other helpers.

If the pop-up doesn't appear:

1. Click the Extensions icon in the left sidebar (looks like four squares)
2. Search for `Python` and install **Python** by Microsoft
3. Search for `Pylance` and install **Pylance** by Microsoft

---

## Step 5 — Select the Python interpreter

The app needs to use the `.venv` Python we created in Step 3, not your system Python.

1. Look at the **bottom-left of the VSCode window** — you'll see something like `Python 3.x.x`
2. Click it
3. A menu appears at the top — select the one that says **`.venv` (Python 3.x.x)**
   - It will look like: `Python 3.12.0 ('.venv': venv)`
   - If you don't see it, click **"Enter interpreter path…"** and navigate to `.venv\Scripts\python.exe`

After selecting, the bottom-left should show `Python 3.x.x ('.venv': venv)`.

---

## Step 6 — Run the app

Press **F5** (or go to **Run → Start Debugging**).

The Keithley IV Suite window should open.

> If you see an error in the terminal at the bottom, read it carefully.
> The most common issue is that the `.venv` interpreter wasn't selected — go back to Step 5.

You can also click the **Run** button (▷) at the top right of any `.py` file, but **F5 is better** because it shows errors clearly.

---

## Step 7 — Using the app

### Connect your instruments

1. Click **"⟳ Scan VISA"** in the left panel
2. The app will find all connected Keithley instruments automatically
3. Click **"Connect"** next to each one you want to use
4. Or type in a GPIB address manually (e.g. `GPIB0::24::INSTR`) and click **"Add"**

> **How do I find the GPIB address?**
> Look at the front panel of the Keithley instrument.
> Press the **MENU** button → find **COMMUNICATION** → **GPIB** → the address number shown there.
> For example, address 24 → resource string is `GPIB0::24::INSTR`

---

### Run a measurement

1. Click the **"Transfer (Id-Vgs)"** tab (or Output or Resistor)
2. Under **SMU Assignment**, choose which connected instrument goes to which terminal:
   - **Gate** → the SMU whose + terminal is connected to the transistor gate
   - **Drain** → the SMU whose + terminal is connected to the drain
   - **Source** → select `GND (ext.)` if source is grounded at the probe station
3. Set your sweep parameters (start/stop voltage, step size, compliance)
4. Click **"▶ Run Now"** (or press **F5** in the app — not VSCode's F5)

The live plot updates in real time as data comes in.

---

### Save your data

- Click **"Export CSV"** below the plot after a sweep
- Or use the menu: **Measurement → Export Last Result…** (Ctrl+S)
- Data is also auto-saved to `Documents\IV_Data\` when running a queue

---

### Load a recipe (batch measurement)

A recipe is a text file that tells the app to run a sequence of measurements automatically.
Two examples are included in the `recipes\` folder.

1. **File → Load Recipe…** (Ctrl+O)
2. Pick `nmos_full_characterization.yaml`
3. The queue on the right fills up with the measurements
4. Click **"▶▶ Run Queue"** — the app runs all of them in order and auto-saves each result

---

## Common problems

| Problem | Fix |
| --- | --- |
| App won't start / import error | Make sure `.venv` interpreter is selected (Step 5) |
| "No VISA instruments found" | Check cable, check instrument is powered on, check GPIB address |
| "VISA backend not found" | Install NI-VISA or Keysight IO (Step 1b) |
| Compliance hit immediately | Reduce compliance current, or check wiring (gate/drain/source) |
| Plot shows nothing | Instrument connected but output stays at 0 V — check SMU assignment |
| VSCode shows red underlines everywhere | Install the **Python** and **Pylance** extensions (Step 4) |

---

## Keyboard shortcuts (inside the app window)

| Key | Action |
| --- | --- |
| F5 | Run current sweep |
| Esc | Stop measurement |
| Ctrl+S | Export data to CSV |
| Ctrl+O | Load a recipe file |
| Ctrl+A | Autoscale the plot |
| Ctrl+Q | Quit |

---

## Where is my data?

CSV files are saved to:

```text
C:\Users\<YourName>\Documents\IV_Data\
```

Each file is named with a timestamp, e.g. `20260331_143022_transfer.csv`.
Open it in Excel, MATLAB, or the **Rainbow CSV** VSCode extension.

---

## Questions?

Ask the lab supervisor or open an issue at:
<https://github.com/prashantUCSB/keithley-iv-suite/issues>
