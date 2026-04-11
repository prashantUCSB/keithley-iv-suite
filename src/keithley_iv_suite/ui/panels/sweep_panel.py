"""Center panel — tabbed sweep parameter configuration with SMU assignment."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QTabWidget,
    QVBoxLayout, QWidget,
)

from ...instruments.smu_base import SMUBase
from ...measurements.sweep_config import (
    FourPointProbeConfig,
    Generic4PortConfig,
    HallBarConfig,
    MeasurementType,
    OutputConfig,
    ResistorConfig,
    TerminalAssignment,
    TerminalRole,
    TransferConfig,
    VanDerPauwConfig,
)
from .. import theme

log = logging.getLogger(__name__)

_DOUBLE_STEP     = 0.01
_DOUBLE_DECIMALS = 4

# ── Range combobox data ───────────────────────────────────────────────────────

# For voltage-source modes — locks the sense ammeter range
_CURRENT_SENSE_RANGES: list[tuple[str, Optional[float]]] = [
    ("Auto",    None),
    ("1 nA",    1e-9),
    ("10 nA",   1e-8),
    ("100 nA",  1e-7),
    ("1 µA",    1e-6),
    ("10 µA",   1e-5),
    ("100 µA",  1e-4),
    ("1 mA",    1e-3),
    ("10 mA",   1e-2),
    ("100 mA",  1e-1),
    ("1 A",     1.0),
]

# For current-source modes — locks the current source range
_CURRENT_SOURCE_RANGES: list[tuple[str, Optional[float]]] = [
    ("Auto",    None),
    ("1 µA",    1e-6),
    ("10 µA",   1e-5),
    ("100 µA",  1e-4),
    ("1 mA",    1e-3),
    ("10 mA",   1e-2),
    ("100 mA",  1e-1),
    ("1 A",     1.0),
]

# Voltage source range (gate / drain / T1)
_VOLTAGE_SOURCE_RANGES: list[tuple[str, Optional[float]]] = [
    ("Auto",   None),
    ("200 mV", 0.2),
    ("2 V",    2.0),
    ("20 V",   20.0),
    ("200 V",  200.0),
]

# For current-source modes — locks the voltmeter sense range
_VOLTAGE_SENSE_RANGES: list[tuple[str, Optional[float]]] = [
    ("Auto",   None),
    ("10 mV",  0.01),
    ("100 mV", 0.1),
    ("1 V",    1.0),
    ("10 V",   10.0),
    ("100 V",  100.0),
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _spin(
    val: float,
    mn: float = -40.0,
    mx: float = 40.0,
    step: float = _DOUBLE_STEP,
    decimals: int = _DOUBLE_DECIMALS,
) -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setRange(mn, mx)
    w.setSingleStep(step)
    w.setDecimals(decimals)
    w.setValue(val)
    w.setSuffix("")
    return w


def _range_combo(choices: list[tuple[str, Optional[float]]]) -> QComboBox:
    cb = QComboBox()
    for label, value in choices:
        cb.addItem(label, value)
    return cb


def _delay_spin(default_ms: float, max_ms: float = 10000.0) -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setRange(0.0, max_ms)
    w.setSingleStep(1.0)
    w.setDecimals(1)
    w.setValue(default_ms)
    w.setSuffix(" ms")
    return w


def _instructions_widget(html: str) -> QWidget:
    """Wrap HTML content in a scrollable pane."""
    w = QWidget()
    vbox = QVBoxLayout(w)
    vbox.setContentsMargins(10, 10, 10, 10)
    lbl = QLabel(html)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setWordWrap(True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(lbl)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    vbox.addWidget(scroll)
    return w


def _mosfet_instructions_html() -> str:
    T = theme.TEXT_PRIMARY
    S = theme.TEXT_SECONDARY
    A = theme.AMBER
    return (
        f'<style>h3{{color:{A};margin:4px 0 4px 0}}p{{color:{S};margin:0 0 8px 0}}'
        f'b{{color:{T}}}</style>'
        f'<h3>NPLC</h3>'
        f'<p>Integration window per point (Number of Power Line Cycles). '
        f'At 50&nbsp;Hz: 1&nbsp;NPLC&nbsp;=&nbsp;20&nbsp;ms. '
        f'Higher values average out noise but slow the sweep proportionally.<br>'
        f'<b>Typical:</b> 1–2 (fast, routine) &nbsp;·&nbsp; '
        f'5–10 (precision / sub-nA gate leakage)</p>'
        f'<h3>Settling Delay</h3>'
        f'<p>Software wait after each V<sub>gs</sub> step before the SMU triggers. '
        f'Accounts for device RC transients.<br>'
        f'<b>Typical:</b> 20&nbsp;ms (silicon FETs) &nbsp;·&nbsp; '
        f'100–500&nbsp;ms (organics, large-gate-capacitance devices)</p>'
        f'<h3>Source Delay</h3>'
        f'<p>Hardware register in the SMU — holds the output at the new setpoint for this '
        f'duration before its internal ADC triggers. Adds on top of settling delay.<br>'
        f'<b>Typical:</b> 0&nbsp;ms (off, default) &nbsp;·&nbsp; '
        f'1–5&nbsp;ms when timing artifacts persist despite long software delay</p>'
        f'<h3>Drain Range</h3>'
        f'<p><b>Most important setting for step discontinuity artefacts.</b> '
        f'Without a fixed range, the SMU auto-ranges as I<sub>d</sub> crosses hardware '
        f'boundaries (e.g. 10&nbsp;µA&nbsp;→&nbsp;100&nbsp;µA), inserting a glitch. '
        f'Set to the first range <em>above</em> your expected maximum I<sub>d</sub>.<br>'
        f'<b>Example:</b> I<sub>d,max</sub> ≈ 2&nbsp;mA → choose <b>10&nbsp;mA</b><br>'
        f'<b>Example:</b> I<sub>d,max</sub> ≈ 80&nbsp;µA → choose <b>100&nbsp;µA</b></p>'
        f'<h3>Gate Range</h3>'
        f'<p>Locks the gate leakage measurement range. '
        f'Gate current on a well-behaved FET is pA–nA; setting a fixed range prevents '
        f'the gate SMU from auto-ranging and introducing its own glitch.<br>'
        f'<b>Typical:</b> 1&nbsp;µA (safe universal default) &nbsp;·&nbsp; '
        f'100&nbsp;nA (low-leakage monitoring)</p>'
        f'<h3>Source Range (V)</h3>'
        f'<p>Locks the voltage source range on both gate and drain SMUs. '
        f'Smaller range → finer DAC resolution → cleaner voltage steps.<br>'
        f'<b>Rule:</b> smallest range that covers your full sweep + ~10% headroom.<br>'
        f'<b>Example:</b> V<sub>gs</sub> from −1&nbsp;V to 3&nbsp;V → choose <b>20&nbsp;V</b></p>'
    )


def _current_source_instructions_html() -> str:
    T = theme.TEXT_PRIMARY
    S = theme.TEXT_SECONDARY
    A = theme.AMBER
    return (
        f'<style>h3{{color:{A};margin:4px 0 4px 0}}p{{color:{S};margin:0 0 8px 0}}'
        f'b{{color:{T}}}</style>'
        f'<h3>NPLC</h3>'
        f'<p>Integration window per point. At 50&nbsp;Hz: 1&nbsp;NPLC&nbsp;=&nbsp;20&nbsp;ms. '
        f'Use higher values for high-resistance samples (weaker voltage signal, more noise).<br>'
        f'<b>Typical:</b> 1 (fast) &nbsp;·&nbsp; 5–10 (low-noise, high-R<sub>s</sub>)</p>'
        f'<h3>Settling Delay</h3>'
        f'<p>Software wait after each current step. Increase for samples with slow '
        f'thermal or electronic relaxation.<br>'
        f'<b>Typical:</b> 20&nbsp;ms (metals, low-R<sub>s</sub>) &nbsp;·&nbsp; '
        f'100&nbsp;ms+ (high-R<sub>s</sub> semiconductors)</p>'
        f'<h3>Source Delay</h3>'
        f'<p>Hardware-side delay in the current source SMU before its ADC triggers.<br>'
        f'<b>Typical:</b> 0&nbsp;ms (off) &nbsp;·&nbsp; 1–5&nbsp;ms for precision work</p>'
        f'<h3>Current Source Range</h3>'
        f'<p>Locks the current source range. Choose the smallest range that spans your '
        f'full current sweep. Prevents re-ranging mid-sweep.<br>'
        f'<b>Example:</b> I<sub>max</sub>&nbsp;=&nbsp;100&nbsp;µA → choose <b>100&nbsp;µA</b><br>'
        f'<b>Example:</b> I<sub>max</sub>&nbsp;=&nbsp;1&nbsp;mA → choose <b>1&nbsp;mA</b></p>'
        f'<h3>Voltage Sense Range</h3>'
        f'<p>Locks the voltmeter measurement range. For high-R<sub>s</sub> materials the '
        f'voltage signal can be large (V&nbsp;=&nbsp;I&nbsp;×&nbsp;R); for metals it may be '
        f'µV–mV. Auto-ranging the voltmeter causes the same step discontinuities as on '
        f'the drain of a FET.<br>'
        f'<b>Rule:</b> first range above your expected maximum V<sub>sense</sub>.<br>'
        f'<b>Example:</b> expect V ≤ 200&nbsp;mV → choose <b>1&nbsp;V</b></p>'
    )


def _resistor_instructions_html() -> str:
    T = theme.TEXT_PRIMARY
    S = theme.TEXT_SECONDARY
    A = theme.AMBER
    return (
        f'<style>h3{{color:{A};margin:4px 0 4px 0}}p{{color:{S};margin:0 0 8px 0}}'
        f'b{{color:{T}}}</style>'
        f'<h3>NPLC</h3>'
        f'<p>Integration window per point. At 50&nbsp;Hz: 1&nbsp;NPLC = 20&nbsp;ms.<br>'
        f'<b>Typical:</b> 1 (fast) &nbsp;·&nbsp; 5–10 (precision / high-R)</p>'
        f'<h3>Settling Delay</h3>'
        f'<p>Software wait after each voltage step.<br>'
        f'<b>Typical:</b> 20&nbsp;ms (low-R devices) &nbsp;·&nbsp; '
        f'100&nbsp;ms (capacitive / high-R samples)</p>'
        f'<h3>Source Delay</h3>'
        f'<p>Hardware-side SMU source delay before triggering measurement.<br>'
        f'<b>Typical:</b> 0&nbsp;ms (off) &nbsp;·&nbsp; 1–5&nbsp;ms for stable precision readings</p>'
        f'<h3>Sense Range (I)</h3>'
        f'<p>Locks the current measurement range. Set to the first range above the '
        f'maximum current your device will draw at the highest applied voltage.<br>'
        f'<b>Example:</b> R&nbsp;≈&nbsp;1&nbsp;kΩ, V<sub>max</sub>&nbsp;=&nbsp;1&nbsp;V '
        f'→ I<sub>max</sub>&nbsp;=&nbsp;1&nbsp;mA → choose <b>1&nbsp;mA</b></p>'
        f'<h3>Source Range (V)</h3>'
        f'<p>Locks the voltage source range. Choose the smallest range covering your sweep.<br>'
        f'<b>Example:</b> sweep −1&nbsp;V to +1&nbsp;V → choose <b>2&nbsp;V</b></p>'
    )


def _generic4port_instructions_html() -> str:
    T = theme.TEXT_PRIMARY
    S = theme.TEXT_SECONDARY
    A = theme.AMBER
    return (
        f'<style>h3{{color:{A};margin:4px 0 4px 0}}p{{color:{S};margin:0 0 8px 0}}'
        f'b{{color:{T}}}</style>'
        f'<h3>NPLC</h3>'
        f'<p>Integration window per measurement point on T1.<br>'
        f'<b>Typical:</b> 1–2 (fast) &nbsp;·&nbsp; 5–10 (low-noise)</p>'
        f'<h3>Settling Delay</h3>'
        f'<p>Software wait after each T1 voltage step before measuring.<br>'
        f'<b>Typical:</b> 20&nbsp;ms (resistive) &nbsp;·&nbsp; '
        f'50–200&nbsp;ms (capacitive or slow devices)</p>'
        f'<h3>Source Delay</h3>'
        f'<p>Hardware-side delay on the T1 SMU before it triggers its ADC.<br>'
        f'<b>Typical:</b> 0&nbsp;ms (off)</p>'
        f'<h3>T1 Sense Range (I)</h3>'
        f'<p>Locks the T1 current measurement range. Set to the first range above '
        f'the maximum expected T1 current.<br>'
        f'<b>Example:</b> I<sub>max</sub>&nbsp;≈&nbsp;10&nbsp;mA → choose <b>10&nbsp;mA</b></p>'
        f'<h3>T1 Source Range (V)</h3>'
        f'<p>Locks the T1 voltage source range.<br>'
        f'<b>Example:</b> V sweep 0 to 5&nbsp;V → choose <b>20&nbsp;V</b></p>'
    )


def _quality_group_mosfet() -> tuple[QGroupBox, dict]:
    """Build and return a 'Measurement Quality' group for MOSFET tabs.

    Returns (group_box, refs) where refs is a dict of widget references.
    """
    grp = QGroupBox("Measurement Quality")
    form = QFormLayout(grp)
    form.setSpacing(5)
    form.setContentsMargins(8, 14, 8, 8)

    nplc          = _spin(1.0, mn=0.001, mx=25.0, step=0.5, decimals=2)
    settling_ms   = _delay_spin(20.0, max_ms=10000.0)
    source_dly_ms = _delay_spin(0.0,  max_ms=1000.0)
    drain_range   = _range_combo(_CURRENT_SENSE_RANGES)
    gate_range    = _range_combo(_CURRENT_SENSE_RANGES)
    source_range  = _range_combo(_VOLTAGE_SOURCE_RANGES)

    gate_range.setCurrentIndex(5)    # default 10 µA — typical FET gate leakage range

    form.addRow("NPLC:",           nplc)
    form.addRow("Settling delay:", settling_ms)
    form.addRow("Source delay:",   source_dly_ms)
    form.addRow("Drain range:",    drain_range)
    form.addRow("Gate range:",     gate_range)
    form.addRow("Source range:",   source_range)

    return grp, {
        "nplc": nplc, "settling_ms": settling_ms, "source_dly_ms": source_dly_ms,
        "drain_range": drain_range, "gate_range": gate_range, "source_range": source_range,
    }


def _quality_group_vsource() -> tuple[QGroupBox, dict]:
    """Quality group for voltage-source 2-terminal tabs (Resistor, Generic4Port T1)."""
    grp = QGroupBox("Measurement Quality")
    form = QFormLayout(grp)
    form.setSpacing(5)
    form.setContentsMargins(8, 14, 8, 8)

    nplc          = _spin(1.0, mn=0.001, mx=25.0, step=0.5, decimals=2)
    settling_ms   = _delay_spin(20.0, max_ms=10000.0)
    source_dly_ms = _delay_spin(0.0,  max_ms=1000.0)
    sense_range   = _range_combo(_CURRENT_SENSE_RANGES)
    source_range  = _range_combo(_VOLTAGE_SOURCE_RANGES)

    form.addRow("NPLC:",           nplc)
    form.addRow("Settling delay:", settling_ms)
    form.addRow("Source delay:",   source_dly_ms)
    form.addRow("Sense range (I):", sense_range)
    form.addRow("Source range (V):", source_range)

    return grp, {
        "nplc": nplc, "settling_ms": settling_ms, "source_dly_ms": source_dly_ms,
        "sense_range": sense_range, "source_range": source_range,
    }


def _quality_group_isource() -> tuple[QGroupBox, dict]:
    """Quality group for current-source tabs (VdP, Hall, 4PP)."""
    grp = QGroupBox("Measurement Quality")
    form = QFormLayout(grp)
    form.setSpacing(5)
    form.setContentsMargins(8, 14, 8, 8)

    nplc          = _spin(1.0, mn=0.001, mx=25.0, step=0.5, decimals=2)
    settling_ms   = _delay_spin(20.0, max_ms=10000.0)
    source_dly_ms = _delay_spin(0.0,  max_ms=1000.0)
    source_range  = _range_combo(_CURRENT_SOURCE_RANGES)
    sense_range   = _range_combo(_VOLTAGE_SENSE_RANGES)

    form.addRow("NPLC:",                nplc)
    form.addRow("Settling delay:",      settling_ms)
    form.addRow("Source delay:",        source_dly_ms)
    form.addRow("Current source range:", source_range)
    form.addRow("Voltage sense range:",  sense_range)

    return grp, {
        "nplc": nplc, "settling_ms": settling_ms, "source_dly_ms": source_dly_ms,
        "source_range": source_range, "sense_range": sense_range,
    }


# ── Terminal assignment ───────────────────────────────────────────────────────

class _TerminalRow(QWidget):
    """One terminal assignment row (role label + instrument combo)."""

    def __init__(self, role: TerminalRole, parent=None):
        super().__init__(parent)
        self.role = role
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QLabel(f"{role.value}:")
        lbl.setFixedWidth(75)
        lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        layout.addWidget(lbl)

        self.instr_combo = QComboBox()
        self.instr_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.instr_combo.addItem("-- select --", None)
        self.instr_combo.addItem("GND (ext.)", "GND")
        layout.addWidget(self.instr_combo)

    def populate_instruments(self, smu_map: dict[str, SMUBase]):
        current = self.instr_combo.currentData()
        self.instr_combo.blockSignals(True)
        while self.instr_combo.count() > 2:
            self.instr_combo.removeItem(2)
        for name in smu_map:
            self.instr_combo.addItem(name, name)
        idx = self.instr_combo.findData(current)
        self.instr_combo.setCurrentIndex(max(0, idx))
        self.instr_combo.blockSignals(False)

    def get_assignment(self) -> Optional[TerminalAssignment]:
        data = self.instr_combo.currentData()
        if data is None:
            return None
        grounded = data == "GND"
        instr_id = str(data)
        channel  = instr_id.split(":")[-1] if ":" in instr_id else ""
        return TerminalAssignment(
            role=self.role,
            instrument_id=instr_id,
            channel=channel,
            grounded=grounded,
        )


class _AssignmentGroup(QGroupBox):
    """Compact group of terminal rows for SMU assignment."""

    def __init__(self, roles: list[TerminalRole], title: str = "SMU Assignment", parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 16, 8, 8)
        self._rows: dict[TerminalRole, _TerminalRow] = {}
        for role in roles:
            row = _TerminalRow(role)
            self._rows[role] = row
            layout.addWidget(row)

    def populate(self, smu_map: dict[str, SMUBase]):
        for row in self._rows.values():
            row.populate_instruments(smu_map)

    def get_assignments(self) -> list[TerminalAssignment]:
        result = []
        for row in self._rows.values():
            a = row.get_assignment()
            if a is not None:
                result.append(a)
        return result


# ── Transfer Tab ─────────────────────────────────────────────────────────────

class TransferTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QTabWidget()

        # ── Settings ──
        sw = QWidget()
        layout = QVBoxLayout(sw)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.assignment = _AssignmentGroup(
            [TerminalRole.GATE, TerminalRole.DRAIN, TerminalRole.SOURCE],
            "SMU Assignment",
        )
        layout.addWidget(self.assignment)

        params = QGroupBox("Sweep Parameters")
        form = QFormLayout(params)
        form.setSpacing(6)
        self.vgs_start = _spin(-1.0)
        self.vgs_stop  = _spin(3.0)
        self.vgs_step  = _spin(0.05, mn=1e-4, mx=10.0, step=0.01)
        self.vds_fixed = _spin(0.1, mn=-40.0, mx=40.0)
        for w, s in [(self.vgs_start, " V"), (self.vgs_stop, " V"),
                     (self.vgs_step, " V"), (self.vds_fixed, " V")]:
            w.setSuffix(s)
        form.addRow("Vgs start:",   self.vgs_start)
        form.addRow("Vgs stop:",    self.vgs_stop)
        form.addRow("Vgs step:",    self.vgs_step)
        form.addRow("Vds (fixed):", self.vds_fixed)
        layout.addWidget(params)

        comp = QGroupBox("Compliance")
        cform = QFormLayout(comp)
        cform.setSpacing(6)
        self.comp_drain = _spin(0.1, mn=1e-9, mx=1.5, step=0.01)
        self.comp_gate  = _spin(0.01, mn=1e-9, mx=0.1, step=0.001)
        self.comp_drain.setSuffix(" A")
        self.comp_gate.setSuffix(" A")
        cform.addRow("Drain (Id):", self.comp_drain)
        cform.addRow("Gate (Ig):",  self.comp_gate)
        layout.addWidget(comp)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

        aw = QWidget()
        al = QVBoxLayout(aw)
        al.setContentsMargins(8, 8, 8, 8)
        al.setSpacing(8)
        qual, self._q = _quality_group_mosfet()
        al.addWidget(qual)
        al.addStretch()

        self._inner.addTab(sw, "Settings")
        self._inner.addTab(aw, "Advanced")
        self._inner.addTab(_instructions_widget(_mosfet_instructions_html()), "Instructions")
        outer.addWidget(self._inner, stretch=1)

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def build_config(self) -> TransferConfig:
        q = self._q
        return TransferConfig(
            label=self.label_edit.text().strip(),
            vgs_start=self.vgs_start.value(),
            vgs_stop=self.vgs_stop.value(),
            vgs_step=self.vgs_step.value(),
            vds_fixed=self.vds_fixed.value(),
            compliance_drain_A=self.comp_drain.value(),
            compliance_gate_A=self.comp_gate.value(),
            nplc=q["nplc"].value(),
            settling_delay_s=q["settling_ms"].value() / 1000.0,
            source_delay_s=q["source_dly_ms"].value() / 1000.0,
            drain_sense_range_A=q["drain_range"].currentData(),
            gate_sense_range_A=q["gate_range"].currentData(),
            source_range_V=q["source_range"].currentData(),
            assignments=self.assignment.get_assignments(),
        )


# ── Output Tab ───────────────────────────────────────────────────────────────

class OutputTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QTabWidget()

        sw = QWidget()
        layout = QVBoxLayout(sw)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.assignment = _AssignmentGroup(
            [TerminalRole.GATE, TerminalRole.DRAIN, TerminalRole.SOURCE],
            "SMU Assignment",
        )
        layout.addWidget(self.assignment)

        params = QGroupBox("Sweep Parameters")
        form = QFormLayout(params)
        form.setSpacing(6)
        self.vds_start = _spin(0.0)
        self.vds_stop  = _spin(3.0)
        self.vds_step  = _spin(0.05, mn=1e-4, mx=10.0, step=0.01)
        self.vgs_list_edit = QLineEdit("0.5, 1.0, 1.5, 2.0, 2.5, 3.0")
        for w, s in [(self.vds_start, " V"), (self.vds_stop, " V"), (self.vds_step, " V")]:
            w.setSuffix(s)
        form.addRow("Vds start:",     self.vds_start)
        form.addRow("Vds stop:",      self.vds_stop)
        form.addRow("Vds step:",      self.vds_step)
        form.addRow("Vgs values (V):", self.vgs_list_edit)
        hint = QLabel("Comma-separated list of Vgs values for the family of curves")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        layout.addWidget(params)

        comp = QGroupBox("Compliance")
        cform = QFormLayout(comp)
        cform.setSpacing(6)
        self.comp_drain = _spin(0.1, mn=1e-9, mx=1.5, step=0.01)
        self.comp_gate  = _spin(0.01, mn=1e-9, mx=0.1, step=0.001)
        self.comp_drain.setSuffix(" A")
        self.comp_gate.setSuffix(" A")
        cform.addRow("Drain:", self.comp_drain)
        cform.addRow("Gate:",  self.comp_gate)
        layout.addWidget(comp)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

        aw = QWidget()
        al = QVBoxLayout(aw)
        al.setContentsMargins(8, 8, 8, 8)
        al.setSpacing(8)
        qual, self._q = _quality_group_mosfet()
        al.addWidget(qual)
        al.addStretch()

        self._inner.addTab(sw, "Settings")
        self._inner.addTab(aw, "Advanced")
        self._inner.addTab(_instructions_widget(_mosfet_instructions_html()), "Instructions")
        outer.addWidget(self._inner, stretch=1)

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def _parse_vgs_list(self) -> list[float]:
        text = self.vgs_list_edit.text()
        values = []
        for tok in text.split(","):
            tok = tok.strip()
            if tok:
                try:
                    values.append(float(tok))
                except ValueError:
                    pass
        return values or [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    def build_config(self) -> OutputConfig:
        q = self._q
        return OutputConfig(
            label=self.label_edit.text().strip(),
            vds_start=self.vds_start.value(),
            vds_stop=self.vds_stop.value(),
            vds_step=self.vds_step.value(),
            vgs_list_values=self._parse_vgs_list(),
            compliance_drain_A=self.comp_drain.value(),
            compliance_gate_A=self.comp_gate.value(),
            nplc=q["nplc"].value(),
            settling_delay_s=q["settling_ms"].value() / 1000.0,
            source_delay_s=q["source_dly_ms"].value() / 1000.0,
            drain_sense_range_A=q["drain_range"].currentData(),
            gate_sense_range_A=q["gate_range"].currentData(),
            source_range_V=q["source_range"].currentData(),
            assignments=self.assignment.get_assignments(),
        )


# ── Resistor Tab ─────────────────────────────────────────────────────────────

class ResistorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QTabWidget()

        sw = QWidget()
        layout = QVBoxLayout(sw)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.assignment = _AssignmentGroup(
            [TerminalRole.TERMINAL_1, TerminalRole.TERMINAL_2],
            "SMU Assignment",
        )
        layout.addWidget(self.assignment)

        params = QGroupBox("Sweep Parameters")
        form = QFormLayout(params)
        form.setSpacing(6)
        self.v_start = _spin(-1.0)
        self.v_stop  = _spin(1.0)
        self.v_step  = _spin(0.05, mn=1e-4, mx=10.0, step=0.01)
        self.comp    = _spin(0.1, mn=1e-9, mx=1.5, step=0.01)
        for w, s in [(self.v_start, " V"), (self.v_stop, " V"),
                     (self.v_step, " V"), (self.comp, " A")]:
            w.setSuffix(s)
        form.addRow("V start:",     self.v_start)
        form.addRow("V stop:",      self.v_stop)
        form.addRow("V step:",      self.v_step)
        form.addRow("Compliance:",  self.comp)
        layout.addWidget(params)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

        aw = QWidget()
        al = QVBoxLayout(aw)
        al.setContentsMargins(8, 8, 8, 8)
        al.setSpacing(8)
        qual, self._q = _quality_group_vsource()
        al.addWidget(qual)
        al.addStretch()

        self._inner.addTab(sw, "Settings")
        self._inner.addTab(aw, "Advanced")
        self._inner.addTab(_instructions_widget(_resistor_instructions_html()), "Instructions")
        outer.addWidget(self._inner, stretch=1)

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def build_config(self) -> ResistorConfig:
        q = self._q
        return ResistorConfig(
            label=self.label_edit.text().strip(),
            v_start=self.v_start.value(),
            v_stop=self.v_stop.value(),
            v_step=self.v_step.value(),
            compliance_A=self.comp.value(),
            nplc=q["nplc"].value(),
            settling_delay_s=q["settling_ms"].value() / 1000.0,
            source_delay_s=q["source_dly_ms"].value() / 1000.0,
            sense_range_A=q["sense_range"].currentData(),
            source_range_V=q["source_range"].currentData(),
            assignments=self.assignment.get_assignments(),
        )


# ── Van der Pauw Tab ──────────────────────────────────────────────────────────

class VanDerPauwTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QTabWidget()

        sw = QWidget()
        layout = QVBoxLayout(sw)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.assignment = _AssignmentGroup(
            [TerminalRole.I_PLUS, TerminalRole.I_MINUS,
             TerminalRole.V_PLUS, TerminalRole.V_MINUS],
            "SMU Assignment",
        )
        layout.addWidget(self.assignment)

        params = QGroupBox("Sweep Parameters")
        form = QFormLayout(params)
        form.setSpacing(6)
        self.i_start = _spin(-10.0, mn=-10000.0, mx=10000.0, step=1.0, decimals=3)
        self.i_stop  = _spin( 10.0, mn=-10000.0, mx=10000.0, step=1.0, decimals=3)
        self.i_step  = _spin(  1.0, mn=0.001, mx=10000.0, step=0.1, decimals=3)
        self.comp_V  = _spin( 10.0, mn=0.1, mx=200.0, step=1.0, decimals=2)
        for w in (self.i_start, self.i_stop, self.i_step):
            w.setSuffix(" µA")
        self.comp_V.setSuffix(" V")
        form.addRow("I start:", self.i_start)
        form.addRow("I stop:",  self.i_stop)
        form.addRow("I step:",  self.i_step)
        form.addRow("Comp (V):", self.comp_V)
        layout.addWidget(params)

        thick = QGroupBox("Sample (optional)")
        tf = QFormLayout(thick)
        tf.setSpacing(6)
        self.thickness = _spin(0.0, mn=0.0, mx=1e7, step=1.0, decimals=1)
        self.thickness.setSuffix(" nm")
        self.thickness.setToolTip("Film thickness — used to compute ρ = Rs × t.\nLeave 0 to skip.")
        tf.addRow("Thickness:", self.thickness)
        layout.addWidget(thick)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional — e.g. Config 1)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

        aw = QWidget()
        al = QVBoxLayout(aw)
        al.setContentsMargins(8, 8, 8, 8)
        al.setSpacing(8)
        qual, self._q = _quality_group_isource()
        al.addWidget(qual)
        al.addStretch()

        self._inner.addTab(sw, "Settings")
        self._inner.addTab(aw, "Advanced")
        self._inner.addTab(_instructions_widget(_current_source_instructions_html()), "Instructions")
        outer.addWidget(self._inner, stretch=1)

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def build_config(self) -> VanDerPauwConfig:
        q = self._q
        t_nm = self.thickness.value()
        return VanDerPauwConfig(
            label=self.label_edit.text().strip(),
            i_start=self.i_start.value() * 1e-6,
            i_stop=self.i_stop.value()   * 1e-6,
            i_step=abs(self.i_step.value()) * 1e-6,
            compliance_V=self.comp_V.value(),
            thickness_m=t_nm * 1e-9 if t_nm > 0.0 else None,
            nplc=q["nplc"].value(),
            settling_delay_s=q["settling_ms"].value() / 1000.0,
            source_delay_s=q["source_dly_ms"].value() / 1000.0,
            source_range_A=q["source_range"].currentData(),
            sense_range_V=q["sense_range"].currentData(),
            assignments=self.assignment.get_assignments(),
        )


# ── Hall Bar Tab ──────────────────────────────────────────────────────────────

class HallBarTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QTabWidget()

        sw = QWidget()
        layout = QVBoxLayout(sw)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.assignment = _AssignmentGroup(
            [TerminalRole.I_PLUS, TerminalRole.I_MINUS,
             TerminalRole.V_HALL_PLUS, TerminalRole.V_HALL_MINUS],
            "SMU Assignment",
        )
        layout.addWidget(self.assignment)

        params = QGroupBox("Sweep Parameters")
        form = QFormLayout(params)
        form.setSpacing(6)
        self.i_start = _spin(-10.0, mn=-10000.0, mx=10000.0, step=1.0, decimals=3)
        self.i_stop  = _spin( 10.0, mn=-10000.0, mx=10000.0, step=1.0, decimals=3)
        self.i_step  = _spin(  1.0, mn=0.001, mx=10000.0, step=0.1, decimals=3)
        self.comp_V  = _spin( 10.0, mn=0.1, mx=200.0, step=1.0, decimals=2)
        for w in (self.i_start, self.i_stop, self.i_step):
            w.setSuffix(" µA")
        self.comp_V.setSuffix(" V")
        form.addRow("I start:",  self.i_start)
        form.addRow("I stop:",   self.i_stop)
        form.addRow("I step:",   self.i_step)
        form.addRow("Comp (V):", self.comp_V)
        layout.addWidget(params)

        mag = QGroupBox("Magnetic Field & Geometry")
        mf = QFormLayout(mag)
        mf.setSpacing(6)
        self.b_field = _spin(0.0, mn=-30.0, mx=30.0, step=0.01, decimals=4)
        self.b_field.setSuffix(" T")
        self.b_field.setToolTip("Magnetic field applied to sample (set manually on magnet)")
        self.thickness = _spin(0.0, mn=0.0, mx=1e7, step=1.0, decimals=1)
        self.thickness.setSuffix(" nm")
        mf.addRow("B field:",   self.b_field)
        mf.addRow("Thickness:", self.thickness)
        layout.addWidget(mag)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

        aw = QWidget()
        al = QVBoxLayout(aw)
        al.setContentsMargins(8, 8, 8, 8)
        al.setSpacing(8)
        qual, self._q = _quality_group_isource()
        al.addWidget(qual)
        al.addStretch()

        self._inner.addTab(sw, "Settings")
        self._inner.addTab(aw, "Advanced")
        self._inner.addTab(_instructions_widget(_current_source_instructions_html()), "Instructions")
        outer.addWidget(self._inner, stretch=1)

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def build_config(self) -> HallBarConfig:
        q = self._q
        t_nm = self.thickness.value()
        return HallBarConfig(
            label=self.label_edit.text().strip(),
            i_start=self.i_start.value() * 1e-6,
            i_stop=self.i_stop.value()   * 1e-6,
            i_step=abs(self.i_step.value()) * 1e-6,
            compliance_V=self.comp_V.value(),
            b_field_T=self.b_field.value(),
            thickness_m=t_nm * 1e-9 if t_nm > 0.0 else None,
            nplc=q["nplc"].value(),
            settling_delay_s=q["settling_ms"].value() / 1000.0,
            source_delay_s=q["source_dly_ms"].value() / 1000.0,
            source_range_A=q["source_range"].currentData(),
            sense_range_V=q["sense_range"].currentData(),
            assignments=self.assignment.get_assignments(),
        )


# ── Generic 4-Port Tab ────────────────────────────────────────────────────────

class Generic4PortTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QTabWidget()

        sw = QWidget()
        layout = QVBoxLayout(sw)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.assignment = _AssignmentGroup(
            [TerminalRole.T1, TerminalRole.T2, TerminalRole.T3, TerminalRole.T4],
            "SMU Assignment",
        )
        layout.addWidget(self.assignment)

        params = QGroupBox("T1 Sweep")
        form = QFormLayout(params)
        form.setSpacing(6)
        self.v_start = _spin(0.0)
        self.v_stop  = _spin(1.0)
        self.v_step  = _spin(0.05, mn=1e-4, mx=10.0, step=0.01)
        self.comp_A  = _spin(0.1, mn=1e-9, mx=1.5, step=0.01)
        for w, s in [(self.v_start, " V"), (self.v_stop, " V"),
                     (self.v_step, " V"), (self.comp_A, " A")]:
            w.setSuffix(s)
        form.addRow("V start:",       self.v_start)
        form.addRow("V stop:",        self.v_stop)
        form.addRow("V step:",        self.v_step)
        form.addRow("T1 compliance:", self.comp_A)
        layout.addWidget(params)

        bias = QGroupBox("T2 / T3 Fixed Bias")
        bf = QFormLayout(bias)
        bf.setSpacing(6)
        self.v_t2 = _spin(0.0)
        self.v_t3 = _spin(0.0)
        self.comp_t2 = _spin(0.01, mn=1e-9, mx=1.5, step=0.001)
        self.comp_t3 = _spin(0.01, mn=1e-9, mx=1.5, step=0.001)
        for w, s in [(self.v_t2, " V"), (self.v_t3, " V"),
                     (self.comp_t2, " A"), (self.comp_t3, " A")]:
            w.setSuffix(s)
        bf.addRow("T2 bias:", self.v_t2)
        bf.addRow("T2 comp:", self.comp_t2)
        bf.addRow("T3 bias:", self.v_t3)
        bf.addRow("T3 comp:", self.comp_t3)
        layout.addWidget(bias)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

        aw = QWidget()
        al = QVBoxLayout(aw)
        al.setContentsMargins(8, 8, 8, 8)
        al.setSpacing(8)
        qual, self._q = _quality_group_vsource()
        al.addWidget(qual)
        al.addStretch()

        self._inner.addTab(sw, "Settings")
        self._inner.addTab(aw, "Advanced")
        self._inner.addTab(_instructions_widget(_generic4port_instructions_html()), "Instructions")
        outer.addWidget(self._inner, stretch=1)

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def build_config(self) -> Generic4PortConfig:
        q = self._q
        return Generic4PortConfig(
            label=self.label_edit.text().strip(),
            v_start=self.v_start.value(),
            v_stop=self.v_stop.value(),
            v_step=self.v_step.value(),
            compliance_A=self.comp_A.value(),
            v_t2_bias=self.v_t2.value(),
            v_t3_bias=self.v_t3.value(),
            comp_t2_A=self.comp_t2.value(),
            comp_t3_A=self.comp_t3.value(),
            nplc=q["nplc"].value(),
            settling_delay_s=q["settling_ms"].value() / 1000.0,
            source_delay_s=q["source_dly_ms"].value() / 1000.0,
            sense_range_A=q["sense_range"].currentData(),
            source_range_V=q["source_range"].currentData(),
            assignments=self.assignment.get_assignments(),
        )


# ── Four-Point Probe Tab ──────────────────────────────────────────────────────

class FourPointProbeTab(QWidget):
    """Collinear four-point probe sheet-resistance (Signatone SP4 and similar)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QTabWidget()

        # ── Settings sub-tab ──────────────────────────────────────────────
        settings_w = QWidget()
        layout = QVBoxLayout(settings_w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.assignment = _AssignmentGroup(
            [TerminalRole.I_PLUS, TerminalRole.V_PLUS],
            "SMU Assignment",
        )
        layout.addWidget(self.assignment)

        sweep_box = QGroupBox("Current Sweep")
        sf = QFormLayout(sweep_box)
        sf.setSpacing(5)
        sf.setContentsMargins(8, 14, 8, 6)
        self.i_start = _spin(-0.010, mn=-500.0, mx=500.0, step=0.001, decimals=4)
        self.i_stop  = _spin( 0.010, mn=-500.0, mx=500.0, step=0.001, decimals=4)
        self.i_step  = _spin( 0.001, mn=0.0001, mx=100.0, step=0.001, decimals=4)
        self.comp_V  = _spin(10.0, mn=0.1, mx=200.0, step=1.0, decimals=1)
        for w in (self.i_start, self.i_stop, self.i_step):
            w.setSuffix(" mA")
        self.comp_V.setSuffix(" V")
        sf.addRow("I start:",    self.i_start)
        sf.addRow("I stop:",     self.i_stop)
        sf.addRow("I step:",     self.i_step)
        sf.addRow("Compliance:", self.comp_V)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(3)
        for lbl, tip, i_max_mA, step_mA in [
            ("Metals",  "Metals / silicides  ±100 mA",         100.0,  5.0),
            ("ITO",     "ITO / TCO / thin films  ±1 mA",         1.0,  0.05),
            ("Si",      "Doped Si / SiC  ±10 µA (0.010 mA)",   0.010,  0.001),
            ("Hi-Rs",   "Semi-insulating  ±1 µA (0.001 mA)",   0.001, 0.0001),
        ]:
            btn = QPushButton(lbl)
            btn.setFixedHeight(22)
            btn.setToolTip(tip)
            btn.setStyleSheet("font-size:8pt; padding:0 6px;")
            btn.clicked.connect(
                lambda _, im=i_max_mA, st=step_mA: self._apply_preset(im, st)
            )
            preset_row.addWidget(btn)
        preset_row.addStretch()
        sf.addRow("Presets:", preset_row)
        layout.addWidget(sweep_box)

        geo_box = QGroupBox("Probe Geometry")
        gf = QFormLayout(geo_box)
        gf.setSpacing(5)
        gf.setContentsMargins(8, 14, 8, 6)
        self.probe_spacing = _spin(1.016, mn=0.01, mx=50.0, step=0.001, decimals=3)
        self.probe_spacing.setSuffix(" mm")
        self.probe_spacing.setToolTip(
            "SP4 standard: 1.016 mm (40 mil)\n"
            "Used for display only — does not affect the Rs formula."
        )
        gf.addRow("Spacing s:", self.probe_spacing)
        self.correction_F = _spin(1.0, mn=0.01, mx=2.0, step=0.001, decimals=4)
        self.correction_F.setToolTip(
            "Geometric correction factor F (Smits 1958):\n"
            "  1.000 — semi-infinite plane  ← default\n"
            "  10 mm chip (s = 1.016 mm):  F ≈ 0.998\n"
            "   5 mm chip (s = 1.016 mm):  F ≈ 0.985"
        )
        gf.addRow("Correction F:", self.correction_F)
        self.thickness_nm = _spin(0.0, mn=0.0, mx=1e6, step=1.0, decimals=1)
        self.thickness_nm.setSuffix(" nm")
        self.thickness_nm.setToolTip(
            "Film thickness — used to compute ρ = Rs × t.\nLeave 0 to skip."
        )
        gf.addRow("Thickness (opt.):", self.thickness_nm)
        layout.addWidget(geo_box)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

        aw = QWidget()
        al = QVBoxLayout(aw)
        al.setContentsMargins(8, 8, 8, 8)
        al.setSpacing(8)
        qual, self._q = _quality_group_isource()
        al.addWidget(qual)
        al.addStretch()

        self._inner.addTab(settings_w, "Settings")
        self._inner.addTab(aw, "Advanced")

        # ── Wiring Guide sub-tab ──────────────────────────────────────────
        guide_w = QWidget()
        guide_layout = QVBoxLayout(guide_w)
        guide_layout.setContentsMargins(12, 12, 12, 12)
        guide_layout.setSpacing(0)
        guide_lbl = QLabel(
            f'<h3 style="margin:0 0 8px 0; color:{theme.AMBER};">'
            f'Four-Point Probe Wiring</h3>'
            f'<p style="margin:0 0 4px 0; color:{theme.TEXT_PRIMARY};">'
            f'<b>Mode A &mdash; Two-SMU</b> (recommended; assign both I+ and V+)</p>'
            f'<p style="margin:0 0 4px 0; color:{theme.TEXT_SECONDARY};">'
            f'I+ SMU forces current (outer probes); V+ SMU reads voltage (inner probes):</p>'
            f'<table cellspacing="0" cellpadding="3">'
            f'<tr style="color:{theme.TEXT_MUTED};">'
            f'  <th align="left" style="padding-right:14px;">Tip</th>'
            f'  <th align="left" style="padding-right:14px;">Role</th>'
            f'  <th align="left">Connect to</th>'
            f'</tr>'
            f'<tr><td>1&nbsp;(outer)</td><td>I+</td>'
            f'<td><b>I+ SMU</b> Force Hi&nbsp;(sources +I)</td></tr>'
            f'<tr><td>2&nbsp;(inner)</td><td>V+</td>'
            f'<td><b>V+ SMU</b> Force Hi&nbsp;(voltmeter)</td></tr>'
            f'<tr><td>3&nbsp;(inner)</td><td>V&minus;</td>'
            f'<td><b>V+ SMU</b> Force Lo&nbsp;(voltmeter)</td></tr>'
            f'<tr><td>4&nbsp;(outer)</td><td>I&minus;</td>'
            f'<td><b>I+ SMU</b> Force Lo&nbsp;(sinks current)</td></tr>'
            f'</table>'
            f'<p style="margin:10px 0 4px 0; color:{theme.TEXT_PRIMARY};">'
            f'<b>Mode B &mdash; Single-SMU RSEN</b> (leave V+ unassigned)</p>'
            f'<p style="margin:0 0 4px 0; color:{theme.TEXT_SECONDARY};">'
            f'One instrument with 4-wire Kelvin (SYST:RSEN ON):</p>'
            f'<table cellspacing="0" cellpadding="3">'
            f'<tr style="color:{theme.TEXT_MUTED};">'
            f'  <th align="left" style="padding-right:14px;">Tip</th>'
            f'  <th align="left" style="padding-right:14px;">Role</th>'
            f'  <th align="left">Connect to (I+ SMU)</th>'
            f'</tr>'
            f'<tr><td>1&nbsp;(outer)</td><td>Force Hi</td>'
            f'<td>SMU <b>Output Hi</b>&nbsp;(sources +I)</td></tr>'
            f'<tr><td>2&nbsp;(inner)</td><td>Sense Hi</td>'
            f'<td>SMU <b>Sense Hi</b>&nbsp;(voltage sense)</td></tr>'
            f'<tr><td>3&nbsp;(inner)</td><td>Sense Lo</td>'
            f'<td>SMU <b>Sense Lo</b>&nbsp;(voltage sense)</td></tr>'
            f'<tr><td>4&nbsp;(outer)</td><td>Force Lo</td>'
            f'<td>SMU <b>Output Lo</b>&nbsp;(sinks current)</td></tr>'
            f'</table>'
            f'<p style="margin-top:10px; color:{theme.TEXT_SECONDARY};">'
            f'<b style="color:{theme.TEXT_PRIMARY};">Sheet resistance</b>: '
            f'R<sub>s</sub>&nbsp;=&nbsp;(&pi;/ln&nbsp;2)&nbsp;&times;&nbsp;'
            f'(V<sub>sense</sub>/I<sub>actual</sub>)&nbsp;&times;&nbsp;F&nbsp;&asymp;&nbsp;'
            f'4.532&nbsp;&times;&nbsp;(V/I)&nbsp;&times;&nbsp;F&nbsp;[&Omega;/&#9633;]<br>'
            f'&rho;&nbsp;=&nbsp;R<sub>s</sub>&nbsp;&times;&nbsp;t'
            f'&nbsp;&nbsp;(Ohm&middot;m, if thickness entered).<br>'
            f'<b style="color:{theme.TEXT_PRIMARY};">Signatone SP4</b>: '
            f's&nbsp;=&nbsp;1.016&nbsp;mm&nbsp;(40&nbsp;mil).</p>'
        )
        guide_lbl.setTextFormat(Qt.TextFormat.RichText)
        guide_lbl.setWordWrap(True)
        guide_layout.addWidget(guide_lbl)
        guide_layout.addStretch()
        self._inner.addTab(guide_w, "Wiring Guide")

        # ── Instructions sub-tab ──────────────────────────────────────────
        self._inner.addTab(
            _instructions_widget(_current_source_instructions_html()), "Instructions"
        )

        outer.addWidget(self._inner, stretch=1)

    def _apply_preset(self, i_max_mA: float, step_mA: float):
        self.i_start.setValue(-i_max_mA)
        self.i_stop.setValue(i_max_mA)
        self.i_step.setValue(step_mA)

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def build_config(self) -> FourPointProbeConfig:
        q = self._q
        t_nm = self.thickness_nm.value()
        return FourPointProbeConfig(
            label=self.label_edit.text().strip(),
            i_start=self.i_start.value() * 1e-3,
            i_stop=self.i_stop.value()   * 1e-3,
            i_step=abs(self.i_step.value()) * 1e-3,
            compliance_V=self.comp_V.value(),
            probe_spacing_m=self.probe_spacing.value() * 1e-3,
            correction_F=self.correction_F.value(),
            thickness_m=t_nm * 1e-9 if t_nm > 0.0 else None,
            nplc=q["nplc"].value(),
            settling_delay_s=q["settling_ms"].value() / 1000.0,
            source_delay_s=q["source_dly_ms"].value() / 1000.0,
            source_range_A=q["source_range"].currentData(),
            sense_range_V=q["sense_range"].currentData(),
            assignments=self.assignment.get_assignments(),
        )


# ── Sweep Panel (container) ──────────────────────────────────────────────────

class SweepPanel(QWidget):
    """Tabbed sweep configuration panel."""

    run_requested          = pyqtSignal(object)   # emits a SweepConfig
    add_to_queue_requested = pyqtSignal(object)   # emits a SweepConfig

    def __init__(self, parent=None):
        super().__init__(parent)
        self._smu_map: dict[str, SMUBase] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QLabel("SWEEP CONFIGURATION")
        header.setProperty("role", "section")
        header.setContentsMargins(12, 10, 12, 6)
        root.addWidget(header)

        self._tabs = QTabWidget()
        self._transfer_tab   = TransferTab()
        self._output_tab     = OutputTab()
        self._resistor_tab   = ResistorTab()
        self._vdp_tab        = VanDerPauwTab()
        self._hall_tab       = HallBarTab()
        self._fpp_tab        = FourPointProbeTab()
        self._generic4p_tab  = Generic4PortTab()
        self._tabs.addTab(self._transfer_tab,  "Transfer (Id-Vgs)")
        self._tabs.addTab(self._output_tab,    "Output (Id-Vds)")
        self._tabs.addTab(self._resistor_tab,  "Resistor IV")
        self._tabs.addTab(self._vdp_tab,       "Van der Pauw")
        self._tabs.addTab(self._hall_tab,      "Hall Bar")
        self._tabs.addTab(self._fpp_tab,       "4-Point Probe")
        self._tabs.addTab(self._generic4p_tab, "Generic 4-Port")
        root.addWidget(self._tabs, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(10, 8, 10, 10)
        btn_row.setSpacing(8)
        self._run_btn = QPushButton("▶  Run Now")
        self._run_btn.setProperty("role", "primary")
        self._run_btn.clicked.connect(self._on_run)
        self._add_queue_btn = QPushButton("+ Add to Queue")
        self._add_queue_btn.clicked.connect(self._on_add_queue)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._add_queue_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def update_instruments(self, smu_map: dict[str, SMUBase]):
        self._smu_map = smu_map
        for tab in (self._transfer_tab, self._output_tab, self._resistor_tab,
                    self._vdp_tab, self._hall_tab, self._fpp_tab, self._generic4p_tab):
            tab.update_instruments(smu_map)

    def set_running(self, running: bool):
        self._run_btn.setEnabled(not running)
        self._add_queue_btn.setEnabled(not running)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_run(self):
        cfg = self._current_config()
        if cfg:
            self.run_requested.emit(cfg)

    def _on_add_queue(self):
        cfg = self._current_config()
        if cfg:
            self.add_to_queue_requested.emit(cfg)

    def _current_config(self):
        idx = self._tabs.currentIndex()
        tabs = [self._transfer_tab, self._output_tab, self._resistor_tab,
                self._vdp_tab, self._hall_tab, self._fpp_tab, self._generic4p_tab]
        return tabs[idx].build_config()
