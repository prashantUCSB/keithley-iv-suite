"""Center panel — tabbed sweep parameter configuration with SMU assignment."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from ...instruments.smu_base import SMUBase
from ...measurements.sweep_config import (
    MeasurementType,
    OutputConfig,
    ResistorConfig,
    TerminalAssignment,
    TerminalRole,
    TransferConfig,
)
from .. import theme

log = logging.getLogger(__name__)

_DOUBLE_STEP = 0.01
_DOUBLE_DECIMALS = 4


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


class _TerminalRow(QWidget):
    """One terminal assignment row (role label + instrument combo + channel combo)."""

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
        self.instr_combo.setMinimumWidth(110)
        self.instr_combo.addItem("-- select --", None)
        self.instr_combo.addItem("GND (ext.)", "GND")
        layout.addWidget(self.instr_combo)

        self.ch_combo = QComboBox()
        self.ch_combo.setFixedWidth(60)
        self.ch_combo.addItems(["--", "A", "B"])
        layout.addWidget(self.ch_combo)

    def populate_instruments(self, smu_map: dict[str, SMUBase]):
        current = self.instr_combo.currentData()
        self.instr_combo.blockSignals(True)
        # Keep first two items (placeholder + GND)
        while self.instr_combo.count() > 2:
            self.instr_combo.removeItem(2)
        for name in smu_map:
            self.instr_combo.addItem(name, name)
        # Restore selection if still valid
        idx = self.instr_combo.findData(current)
        self.instr_combo.setCurrentIndex(max(0, idx))
        self.instr_combo.blockSignals(False)

    def get_assignment(self) -> Optional[TerminalAssignment]:
        data = self.instr_combo.currentData()
        if data is None:
            return None
        grounded = data == "GND"
        channel = self.ch_combo.currentText()
        if channel == "--":
            channel = ""
        return TerminalAssignment(
            role=self.role,
            instrument_id=str(data),
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Assignment
        self.assignment = _AssignmentGroup(
            [TerminalRole.GATE, TerminalRole.DRAIN, TerminalRole.SOURCE],
            "SMU Assignment",
        )
        layout.addWidget(self.assignment)

        # Sweep params
        params = QGroupBox("Sweep Parameters")
        form = QFormLayout(params)
        form.setSpacing(6)
        self.vgs_start = _spin(-1.0)
        self.vgs_stop  = _spin(3.0)
        self.vgs_step  = _spin(0.05, mn=1e-4, mx=10.0, step=0.01)
        self.vds_fixed = _spin(0.1, mn=-40.0, mx=40.0)
        self.vgs_start.setSuffix(" V")
        self.vgs_stop.setSuffix(" V")
        self.vgs_step.setSuffix(" V")
        self.vds_fixed.setSuffix(" V")
        form.addRow("Vgs start:", self.vgs_start)
        form.addRow("Vgs stop:", self.vgs_stop)
        form.addRow("Vgs step:", self.vgs_step)
        form.addRow("Vds (fixed):", self.vds_fixed)
        layout.addWidget(params)

        # Compliance
        comp = QGroupBox("Compliance")
        cform = QFormLayout(comp)
        self.comp_drain = _spin(0.1, mn=1e-9, mx=1.5, step=0.01)
        self.comp_gate  = _spin(0.01, mn=1e-9, mx=0.1, step=0.001)
        self.comp_drain.setSuffix(" A")
        self.comp_gate.setSuffix(" A")
        self.nplc = _spin(1.0, mn=0.001, mx=25.0, step=0.1)
        cform.addRow("Drain (Id):", self.comp_drain)
        cform.addRow("Gate (Ig):", self.comp_gate)
        cform.addRow("NPLC:", self.nplc)
        layout.addWidget(comp)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def build_config(self) -> TransferConfig:
        return TransferConfig(
            label=self.label_edit.text().strip(),
            vgs_start=self.vgs_start.value(),
            vgs_stop=self.vgs_stop.value(),
            vgs_step=self.vgs_step.value(),
            vds_fixed=self.vds_fixed.value(),
            compliance_drain_A=self.comp_drain.value(),
            compliance_gate_A=self.comp_gate.value(),
            nplc=self.nplc.value(),
            assignments=self.assignment.get_assignments(),
        )


# ── Output Tab ───────────────────────────────────────────────────────────────

class OutputTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

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
        self.vds_start.setSuffix(" V")
        self.vds_stop.setSuffix(" V")
        self.vds_step.setSuffix(" V")
        form.addRow("Vds start:", self.vds_start)
        form.addRow("Vds stop:", self.vds_stop)
        form.addRow("Vds step:", self.vds_step)
        form.addRow("Vgs values (V):", self.vgs_list_edit)
        hint = QLabel("Comma-separated list of Vgs values for the family of curves")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        layout.addWidget(params)

        comp = QGroupBox("Compliance")
        cform = QFormLayout(comp)
        self.comp_drain = _spin(0.1, mn=1e-9, mx=1.5, step=0.01)
        self.comp_gate  = _spin(0.01, mn=1e-9, mx=0.1, step=0.001)
        self.nplc = _spin(1.0, mn=0.001, mx=25.0, step=0.1)
        self.comp_drain.setSuffix(" A")
        self.comp_gate.setSuffix(" A")
        cform.addRow("Drain:", self.comp_drain)
        cform.addRow("Gate:", self.comp_gate)
        cform.addRow("NPLC:", self.nplc)
        layout.addWidget(comp)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

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
        return OutputConfig(
            label=self.label_edit.text().strip(),
            vds_start=self.vds_start.value(),
            vds_stop=self.vds_stop.value(),
            vds_step=self.vds_step.value(),
            vgs_list_values=self._parse_vgs_list(),
            compliance_drain_A=self.comp_drain.value(),
            compliance_gate_A=self.comp_gate.value(),
            nplc=self.nplc.value(),
            assignments=self.assignment.get_assignments(),
        )


# ── Resistor Tab ─────────────────────────────────────────────────────────────

class ResistorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

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
        self.nplc    = _spin(1.0, mn=0.001, mx=25.0, step=0.1)
        for w in (self.v_start, self.v_stop, self.v_step):
            w.setSuffix(" V")
        self.comp.setSuffix(" A")
        form.addRow("V start:", self.v_start)
        form.addRow("V stop:", self.v_stop)
        form.addRow("V step:", self.v_step)
        form.addRow("Compliance:", self.comp)
        form.addRow("NPLC:", self.nplc)
        layout.addWidget(params)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Run label (optional)")
        layout.addWidget(self.label_edit)
        layout.addStretch()

    def update_instruments(self, smu_map):
        self.assignment.populate(smu_map)

    def build_config(self) -> ResistorConfig:
        return ResistorConfig(
            label=self.label_edit.text().strip(),
            v_start=self.v_start.value(),
            v_stop=self.v_stop.value(),
            v_step=self.v_step.value(),
            compliance_A=self.comp.value(),
            nplc=self.nplc.value(),
            assignments=self.assignment.get_assignments(),
        )


# ── Sweep Panel (container) ──────────────────────────────────────────────────

class SweepPanel(QWidget):
    """Tabbed sweep configuration panel."""

    run_requested         = pyqtSignal(object)   # emits a SweepConfig
    add_to_queue_requested = pyqtSignal(object)  # emits a SweepConfig

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
        self._transfer_tab = TransferTab()
        self._output_tab = OutputTab()
        self._resistor_tab = ResistorTab()
        self._tabs.addTab(self._transfer_tab, "Transfer (Id-Vgs)")
        self._tabs.addTab(self._output_tab,   "Output (Id-Vds)")
        self._tabs.addTab(self._resistor_tab, "Resistor IV")
        root.addWidget(self._tabs, stretch=1)

        # Action buttons
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
        for tab in (self._transfer_tab, self._output_tab, self._resistor_tab):
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
        tabs = [self._transfer_tab, self._output_tab, self._resistor_tab]
        return tabs[idx].build_config()
