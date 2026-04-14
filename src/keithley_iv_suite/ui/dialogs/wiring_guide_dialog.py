"""SMU Wiring Guide dialog.

Opens from Help > Wiring Guide…  — a resizable QTextBrowser window that
explains how to connect a Keithley 2400/2600-series SMU for every
measurement type the app supports, for both screw-terminal breakout
boxes and triax terminal-block adapters.

Why QTextBrowser instead of opening a browser / QWebEngineView?
  - Stays inside the app with the same dark theme — no OS browser flash
  - Supports full HTML tables, anchor navigation, and inline CSS
  - Zero extra dependencies; QTextBrowser is part of Qt Widgets
  - ~0 MB added to the installer vs ~50 MB for QWebEngineView
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextBrowser, QSizePolicy,
)

from .. import theme


# ---------------------------------------------------------------------------
# HTML content
# ---------------------------------------------------------------------------

_CSS = f"""
<style>
  body  {{ background:{theme.BG_BASE}; color:{theme.TEXT_PRIMARY};
           font-family:'Segoe UI',Arial,sans-serif; font-size:10pt;
           margin:16px 20px; }}
  h1    {{ color:{theme.AMBER}; font-size:15pt; border-bottom:1px solid {theme.BORDER};
           padding-bottom:6px; margin-top:4px; }}
  h2    {{ color:{theme.AMBER_LIGHT}; font-size:12pt; margin-top:22px;
           margin-bottom:4px; border-left:3px solid {theme.AMBER};
           padding-left:8px; }}
  h3    {{ color:{theme.TEXT_PRIMARY}; font-size:10pt; margin-top:14px;
           margin-bottom:3px; }}
  p     {{ color:{theme.TEXT_SECONDARY}; margin:4px 0 10px 0; line-height:1.5; }}
  a     {{ color:{theme.INFO}; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  code  {{ background:{theme.BG_WIDGET}; color:{theme.AMBER_LIGHT};
           padding:1px 5px; border-radius:3px; font-family:Consolas,monospace; }}

  /* Navigation bar */
  .toc  {{ background:{theme.BG_PANEL}; border:1px solid {theme.BORDER};
           border-radius:6px; padding:10px 16px; margin-bottom:18px; }}
  .toc p {{ margin:2px 0; color:{theme.TEXT_SECONDARY}; font-size:9pt; }}
  .toc a {{ font-size:9pt; }}

  /* Connection tables */
  table {{ border-collapse:collapse; width:100%; margin:10px 0 16px 0;
           font-size:9.5pt; }}
  th    {{ background:{theme.BG_WIDGET}; color:{theme.AMBER};
           padding:6px 10px; text-align:left;
           border:1px solid {theme.BORDER_LITE}; }}
  td    {{ padding:5px 10px; border:1px solid {theme.BORDER};
           color:{theme.TEXT_SECONDARY}; vertical-align:top; }}
  tr:nth-child(even) td {{ background:{theme.BG_PANEL}; }}

  /* Diagram pre-blocks */
  pre   {{ background:{theme.BG_DEEP}; color:#A8D8A8;
           border:1px solid {theme.BORDER}; border-radius:4px;
           padding:12px 14px; font-family:Consolas,monospace;
           font-size:9pt; line-height:1.4; overflow-x:auto; }}

  /* Callout boxes */
  .note {{ background:{theme.BG_PANEL}; border-left:3px solid {theme.INFO};
           padding:8px 12px; margin:10px 0; border-radius:0 4px 4px 0; }}
  .warn {{ background:{theme.BG_PANEL}; border-left:3px solid {theme.WARNING};
           padding:8px 12px; margin:10px 0; border-radius:0 4px 4px 0; }}
  .note p, .warn p {{ color:{theme.TEXT_SECONDARY}; margin:2px 0; }}

  hr    {{ border:none; border-top:1px solid {theme.BORDER}; margin:20px 0; }}
</style>
"""

_HTML = (
    _CSS
    + """
<h1>SMU Wiring Guide</h1>

<div class="toc">
<p><b>Quick navigation</b></p>
<p>
  <a href="#terminals">1. Terminal reference</a> &nbsp;·&nbsp;
  <a href="#screw">2. Screw-terminal breakout</a> &nbsp;·&nbsp;
  <a href="#triax">3. Triax terminal-block adapter</a> &nbsp;·&nbsp;
  <a href="#2wire4wire">4. 2-wire vs 4-wire sense</a>
</p>
<p>
  <a href="#mosfet">5. MOSFET transfer &amp; output</a> &nbsp;·&nbsp;
  <a href="#4pp">6. Four-point probe</a> &nbsp;·&nbsp;
  <a href="#vdp">7. Van der Pauw</a> &nbsp;·&nbsp;
  <a href="#hall">8. Hall bar</a> &nbsp;·&nbsp;
  <a href="#resistor">9. Resistor I-V</a>
</p>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="terminals">1. Terminal Reference</a></h2>

<p>Every Keithley SMU exposes six logical terminals.
Understanding them is the key to correct wiring for any measurement.</p>

<table>
  <tr>
    <th>Terminal</th>
    <th>Symbol</th>
    <th>Function</th>
  </tr>
  <tr>
    <td><b>Force HI</b></td>
    <td><code>F+</code></td>
    <td>High-side current output — carries the sourced current <i>to</i> the device.</td>
  </tr>
  <tr>
    <td><b>Sense HI</b></td>
    <td><code>S+</code></td>
    <td>High-side Kelvin sense — measures voltage at the device terminal (4-wire only).
    In 2-wire mode tie to Force HI at the terminal block.</td>
  </tr>
  <tr>
    <td><b>Guard</b></td>
    <td><code>GRD</code></td>
    <td>Active guard driven to the same potential as Force HI.
    Surrounds the HI lead to eliminate leakage on high-resistance measurements
    (&gt;10 MΩ). Leave unconnected for routine work.</td>
  </tr>
  <tr>
    <td><b>Sense LO</b></td>
    <td><code>S−</code></td>
    <td>Low-side Kelvin sense — measures voltage at the device return terminal
    (4-wire only). Tie to Force LO at the block in 2-wire mode.</td>
  </tr>
  <tr>
    <td><b>Force LO</b></td>
    <td><code>F−</code></td>
    <td>Low-side current return — carries current back from the device.</td>
  </tr>
  <tr>
    <td><b>Chassis GND</b></td>
    <td><code>⏚</code></td>
    <td>Earth ground / instrument chassis. <i>Not</i> the measurement LO.
    Connect to a probe station chuck guard ring if required by safety.</td>
  </tr>
</table>

<div class="note"><p>
  <b>Rule of thumb:</b> Force lines carry current; Sense lines measure voltage.
  Keeping them separate eliminates the resistance of the cables from your
  voltage reading (Kelvin / remote-sense principle).
</p></div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="screw">2. Screw-Terminal Breakout Box</a></h2>

<p>A screw-terminal breakout (e.g. a custom box, the Pomona 5600 series,
or a lab-built adapter) converts the instrument's triax or multi-pin rear
connector into individual binding-post or screw-lug terminals.
The standard labeling is shown below.</p>

<pre>
  ┌─────────────────────────────────────────────────────────┐
  │            SCREW-TERMINAL BREAKOUT BOX                  │
  │                                                         │
  │  ● FORCE HI   (red)         ● FORCE LO   (black)       │
  │  ● SENSE HI   (white)       ● SENSE LO   (green)       │
  │  ● GUARD      (orange)      ● CHASSIS    (bare/yellow)  │
  └─────────────────────────────────────────────────────────┘
</pre>

<h3>Connecting to the instrument rear panel</h3>
<p>The 2400/2401 rear panel provides a 3-slot connector for the HI side
and a separate binding post for the LO side.
A breakout cable wired from the factory (or home-made) maps as follows:</p>

<table>
  <tr>
    <th>Breakout terminal</th>
    <th>2400/2401 rear connector pin</th>
    <th>Notes</th>
  </tr>
  <tr>
    <td>Force HI</td>
    <td>HI 3-slot — centre pin</td>
    <td>Main current source lead</td>
  </tr>
  <tr>
    <td>Sense HI</td>
    <td>HI 3-slot — shell/inner</td>
    <td>Remote sense; tie to Force HI for 2-wire</td>
  </tr>
  <tr>
    <td>Guard</td>
    <td>HI 3-slot — outer shell</td>
    <td>Leave open unless measuring &gt;10 MΩ</td>
  </tr>
  <tr>
    <td>Force LO</td>
    <td>LO binding post</td>
    <td>Current return</td>
  </tr>
  <tr>
    <td>Sense LO</td>
    <td>LO binding post (tie)</td>
    <td>Tie to Force LO at block for 2-wire; separate Kelvin lead for 4-wire</td>
  </tr>
  <tr>
    <td>Chassis GND</td>
    <td>GND binding post</td>
    <td>Earth; do not use as measurement return</td>
  </tr>
</table>

<div class="warn"><p>
  <b>Never connect Chassis GND to Force LO</b> unless you explicitly need a
  grounded (non-floating) LO. Most SMU measurements work best with a
  floating LO to avoid ground-loop errors.
</p></div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="triax">3. Triax Terminal-Block Adapter</a></h2>

<p>A triax terminal-block adapter (e.g. Keithley 8501, custom triax-to-barrier
strip) converts a standard triax BNC/SMB connector into three screw
terminals.  Triax connectors have three concentric conductors:</p>

<pre>
         Triax cable cross-section
         ┌──────────────────────────┐
         │  outer braid  = COMMON   │  Force LO / circuit return
         │  ┌────────────────────┐  │
         │  │  inner braid = GUARD│  │  Active guard (driven)
         │  │  ┌──────────────┐  │  │
         │  │  │  centre pin  │  │  │  Force HI (signal)
         │  │  └──────────────┘  │  │
         │  └────────────────────┘  │
         └──────────────────────────┘
</pre>

<table>
  <tr>
    <th>Adapter terminal label</th>
    <th>Triax conductor</th>
    <th>Connects to</th>
  </tr>
  <tr>
    <td><b>FORCE</b> (or HI, or SIG)</td>
    <td>Centre pin</td>
    <td>Device terminal — the measurement node</td>
  </tr>
  <tr>
    <td><b>GUARD</b> (or GRD)</td>
    <td>Inner braid / shield</td>
    <td>Guard ring around cable; leave open or connect to guard ring of probe station</td>
  </tr>
  <tr>
    <td><b>COMMON</b> (or LO, or RTN)</td>
    <td>Outer braid</td>
    <td>Current return; ties to Force LO of the SMU</td>
  </tr>
</table>

<p>For a <b>4-wire (Kelvin)</b> measurement with triax adapters you need
<i>two</i> adapter channels per terminal — one channel carries Force
(HI and LO) and a second channel carries Sense (HI and LO) as separate
triax cables.</p>

<div class="note"><p>
  <b>2600-series instruments</b> (2602B, 2612B, 2636B) have triax output
  connectors directly on the front panel.  Each SMU channel has its own
  FORCE and SENSE triax.  Use one adapter per SMU channel.
</p></div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="2wire4wire">4. 2-Wire vs 4-Wire (Remote Sense)</a></h2>

<table>
  <tr>
    <th>Mode</th>
    <th>Sense wires</th>
    <th>When to use</th>
    <th>Settings in app</th>
  </tr>
  <tr>
    <td><b>2-Wire</b></td>
    <td>Tie Sense HI → Force HI and Sense LO → Force LO at the terminal block</td>
    <td>Sample resistance &lt;1 kΩ; short cables; routine wafer probing</td>
    <td>Settings tab → Sense: <code>2-wire</code></td>
  </tr>
  <tr>
    <td><b>4-Wire (Kelvin)</b></td>
    <td>Sense HI and Sense LO run as separate wires directly to the DUT pads</td>
    <td>Low-resistance samples (&lt;100 Ω); long cables; precision measurement</td>
    <td>Settings tab → Sense: <code>4-wire (RSEN)</code></td>
  </tr>
</table>

<pre>
  2-WIRE                           4-WIRE (Kelvin / remote sense)

  SMU                              SMU
  ┌──────────┐                     ┌──────────┐
  │ Force HI ┼──┬───────► DUT+     │ Force HI ┼──────────► DUT+
  │ Sense HI ┼──┘                  │ Sense HI ┼──────────► DUT+  (separate wire)
  │          │                     │          │
  │ Force LO ┼──┬───────► DUT−     │ Force LO ┼──────────► DUT−
  │ Sense LO ┼──┘                  │ Sense LO ┼──────────► DUT−  (separate wire)
  └──────────┘                     └──────────┘

  Cable R included in reading!     Cable R cancelled → true DUT voltage
</pre>

<hr>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="mosfet">5. MOSFET Transfer &amp; Output Curves</a></h2>

<p>Two SMUs are required: one for the Gate (SMU1) and one for the
Drain (SMU2). The Source is connected to the common LO of both SMUs.</p>

<h3>Screw-terminal breakout — 2-wire</h3>

<pre>
         SMU1 (Gate)                    SMU2 (Drain)
         ┌───────────┐                  ┌───────────┐
         │ Force HI  ┼──────────────► Gate pad
         │ Force LO  ┼──┐              │ Force HI  ┼──────────────► Drain pad
         │ Sense HI  ┼──┘(tie)         │ Force LO  ┼──┐
         │ Sense LO  ┼──┘              │ Sense HI  ┼──┘(tie)
         └───────────┘                 │ Sense LO  ┼──┘
                                       └───────────┘
              Force LO ────────── Force LO ────────────► Source pad
                                                         (common GND)
</pre>

<h3>Screw-terminal breakout — 4-wire Drain (Kelvin)</h3>
<pre>
         SMU2 (Drain, 4-wire)
         ┌───────────┐
         │ Force HI  ┼────────────────► Drain current pad  (inner probe)
         │ Sense HI  ┼────────────────► Drain voltage pad  (outer probe, same node)
         │ Force LO  ┼────────────────► Source current pad
         │ Sense LO  ┼────────────────► Source voltage pad (separate Kelvin contact)
         └───────────┘
</pre>

<h3>Triax adapter — 2-wire</h3>
<table>
  <tr><th>Adapter</th><th>Terminal</th><th>Connect to</th></tr>
  <tr><td>SMU1 FORCE</td><td>Centre pin</td><td>Gate pad</td></tr>
  <tr><td>SMU1 COMMON</td><td>Outer braid</td><td>Source pad (circuit common)</td></tr>
  <tr><td>SMU2 FORCE</td><td>Centre pin</td><td>Drain pad</td></tr>
  <tr><td>SMU2 COMMON</td><td>Outer braid</td><td>Source pad (same node as SMU1 COMMON)</td></tr>
</table>

<div class="note"><p>
  <b>App assignment:</b> In the <i>SMU Assignment</i> panel, assign the gate
  SMU to <b>Gate</b> and the drain SMU to <b>Drain</b>. Leave <b>Source</b>
  as the common LO — it does not need a separate SMU channel unless you want
  to apply a non-zero source bias.
</p></div>

<hr>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="4pp">6. Four-Point Probe (Linear)</a></h2>

<p>Current is forced through the two outer probes; voltage is sensed across
the two inner probes. Two SMU channels are used: one as a current source
(outer probes), one as a voltmeter (inner probes, compliance = 0 V
current source).</p>

<pre>
  Sample surface — probe spacing s

  ◄──── s ────►◄──── s ────►◄──── s ────►
  │            │            │            │
  P1           P2           P3           P4
  (I+)         (V+)         (V−)         (I−)

  SMU1  Force HI  ────────────────────────► P1  (I+)
  SMU1  Force LO  ────────────────────────► P4  (I−)

  SMU2  Sense HI  ────────────────────────► P2  (V+)   [voltmeter channel]
  SMU2  Sense LO  ────────────────────────► P3  (V−)   [voltmeter channel]
</pre>

<h3>Screw-terminal breakout</h3>
<table>
  <tr><th>Breakout terminal</th><th>Probe</th><th>Role</th></tr>
  <tr><td>SMU1 Force HI</td><td>P1 (outermost)</td><td>Current source (+)</td></tr>
  <tr><td>SMU1 Force LO</td><td>P4 (outermost)</td><td>Current return (−)</td></tr>
  <tr><td>SMU2 Force HI / Sense HI</td><td>P2</td><td>Voltage sense (+)</td></tr>
  <tr><td>SMU2 Force LO / Sense LO</td><td>P3</td><td>Voltage sense (−)</td></tr>
</table>

<div class="note"><p>
  For the voltage-sense SMU, use <b>Force HI = Sense HI</b> and
  <b>Force LO = Sense LO</b> (2-wire) since it operates as a voltmeter
  (zero-current source). The sheet resistance is
  R<sub>sh</sub> = (π / ln 2) × V / I ≈ 4.532 × V / I.
</p></div>

<hr>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="vdp">7. Van der Pauw</a></h2>

<p>Four contacts at the periphery of an arbitrarily-shaped sample.
The measurement rotates current and voltage terminals through four
configurations (R12,34 · R23,41 · R34,12 · R41,23) to extract sheet resistance.</p>

<pre>
             Contact 1 (top-left)          Contact 2 (top-right)
                    ●──────────────────────────●
                    │                          │
                    │          Sample          │
                    │                          │
                    ●──────────────────────────●
             Contact 4 (bot-left)          Contact 3 (bot-right)
</pre>

<table>
  <tr><th>Configuration</th><th>Current (I+/I−)</th><th>Voltage (V+/V−)</th></tr>
  <tr><td>R<sub>12,34</sub></td><td>1 → 2</td><td>3, 4</td></tr>
  <tr><td>R<sub>23,41</sub></td><td>2 → 3</td><td>4, 1</td></tr>
  <tr><td>R<sub>34,12</sub></td><td>3 → 4</td><td>1, 2</td></tr>
  <tr><td>R<sub>41,23</sub></td><td>4 → 1</td><td>2, 3</td></tr>
</table>

<p>The app cycles through these automatically. Wire all four contacts
permanently to SMU terminals; the software handles the switching sequence.</p>

<table>
  <tr><th>Breakout terminal</th><th>Contact</th></tr>
  <tr><td>SMU1 Force HI</td><td>Contact 1</td></tr>
  <tr><td>SMU1 Force LO</td><td>Contact 2</td></tr>
  <tr><td>SMU2 Force HI / Sense HI</td><td>Contact 3</td></tr>
  <tr><td>SMU2 Force LO / Sense LO</td><td>Contact 4</td></tr>
</table>

<hr>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="hall">8. Hall Bar</a></h2>

<p>A Hall-bar geometry provides current along the bar length and
Hall voltage across the bar width under an applied magnetic field B⊥.</p>

<pre>
     Current contact             Current contact
          ●────────────────────────────────────●
          │  +──────────────────────────────+  │
     (I+) │  │  ●  ●              ●  ●     │  │ (I−)
          │  │  │  │              │  │     │  │
          │  │ VH+ VL+           VL− VH−  │  │
          │  +──────────────────────────────+  │
          ●────────────────────────────────────●

  VH+/VH−  = Hall voltage contacts (perpendicular to current)
  VL+/VL−  = Longitudinal voltage contacts (along current direction)
</pre>

<table>
  <tr><th>Breakout terminal</th><th>Hall-bar contact</th><th>Role</th></tr>
  <tr><td>SMU1 Force HI</td><td>Current in (+)</td><td>Source current</td></tr>
  <tr><td>SMU1 Force LO</td><td>Current out (−)</td><td>Current return</td></tr>
  <tr><td>SMU2 Force HI / Sense HI</td><td>V<sub>Hall</sub> (+)</td><td>Hall voltage sense</td></tr>
  <tr><td>SMU2 Force LO / Sense LO</td><td>V<sub>Hall</sub> (−)</td><td>Hall voltage return</td></tr>
  <tr><td>SMU3 Force HI / Sense HI</td><td>V<sub>Long</sub> (+)</td><td>Longitudinal voltage sense</td></tr>
  <tr><td>SMU3 Force LO / Sense LO</td><td>V<sub>Long</sub> (−)</td><td>Longitudinal return</td></tr>
</table>

<div class="warn"><p>
  <b>Magnetic field safety:</b> The SMU cables must not loop through the
  magnet bore — induced EMF will corrupt measurements. Dress cables
  straight out from the probe station and twist each Force/Sense pair.
</p></div>

<hr>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<h2><a name="resistor">9. Resistor I-V</a></h2>

<p>A single SMU sweeps voltage and measures current through a two-terminal
resistor (or any passive device). Use 4-wire sense for low-resistance
devices (&lt;100 Ω) to eliminate cable resistance.</p>

<h3>2-wire (routine)</h3>
<pre>
  SMU  Force HI ──────────────┬──► +terminal
       Force LO ──────────────┴──► −terminal
       (Sense tied to Force at block)
</pre>

<h3>4-wire (Kelvin, &lt;100 Ω)</h3>
<pre>
  SMU  Force HI  ───────────────► +terminal  (current lead)
       Sense HI  ───────────────► +terminal  (voltage sense, separate contact)
       Force LO  ───────────────► −terminal  (current lead)
       Sense LO  ───────────────► −terminal  (voltage sense, separate contact)
</pre>

<table>
  <tr><th>Breakout terminal</th><th>Connect to</th></tr>
  <tr><td>Force HI</td><td>Resistor terminal A — current lead</td></tr>
  <tr><td>Sense HI</td><td>Resistor terminal A — voltage sense (4-wire) or tie to Force HI (2-wire)</td></tr>
  <tr><td>Sense LO</td><td>Resistor terminal B — voltage sense (4-wire) or tie to Force LO (2-wire)</td></tr>
  <tr><td>Force LO</td><td>Resistor terminal B — current return</td></tr>
</table>

<hr>

<!-- footer -->
<p style="color:{muted}; font-size:8.5pt; margin-top:20px;">
  Keithley IV Suite — Wiring Guide &nbsp;·&nbsp;
  <a href="https://github.com/prashantUCSB/keithley-iv-suite">github.com/prashantUCSB/keithley-iv-suite</a>
</p>
""".format(
        muted=theme.TEXT_MUTED
    )
)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class WiringGuideDialog(QDialog):
    """Resizable wiring-guide window, opened from Help > Wiring Guide…"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SMU Wiring Guide")
        self.resize(820, 680)
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(0)

        # ── Browser ─────────────────────────────────────────────────────────
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setHtml(_HTML)
        self._browser.scrollToAnchor("terminals")

        # Force dark background to match theme (some platforms override it)
        pal = self._browser.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor(theme.BG_BASE))
        pal.setColor(QPalette.ColorRole.Text, QColor(theme.TEXT_PRIMARY))
        self._browser.setPalette(pal)

        layout.addWidget(self._browser)

        # ── Close button ─────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(10, 6, 10, 0)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setProperty("role", "primary")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
