"""Left panel — instrument connection and status."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget, QComboBox, QLineEdit,
    QFormLayout,
)

from ...instruments.visa_manager import VISAManager
from ...instruments.smu_2400 import SMU2400
from ...instruments.smu_2600 import SMU2600
from ...instruments.smu_base import SMUBase
from .. import theme

log = logging.getLogger(__name__)

_MODEL_DRIVER = {
    "2400": ("2400", SMU2400),
    "2401": ("2401", SMU2400),
    "2602": ("2602", lambda r: SMU2600(r, "A")),
    "2602A": ("2602A", lambda r: SMU2600(r, "A")),
    "2614B": ("2614B", lambda r: SMU2600(r, "A")),
    "2614": ("2614B", lambda r: SMU2600(r, "A")),
}

_STATUS_COLORS = {
    "connected":    theme.SUCCESS,
    "disconnected": theme.TEXT_MUTED,
    "error":        theme.ERROR,
    "scanning":     theme.AMBER,
}


class _ScanWorker(QThread):
    """Background VISA scan thread."""
    done = pyqtSignal(list)

    def __init__(self, vm: VISAManager):
        super().__init__()
        self._vm = vm

    def run(self):
        try:
            results = self._vm.list_resources_with_info()
        except Exception as exc:
            log.error("VISA scan error: %s", exc)
            results = []
        self.done.emit(results)


class InstrumentRow(QWidget):
    """One row in the instrument panel — shows status dot, name, address, connect button."""

    connect_requested    = pyqtSignal(str)   # resource_string
    disconnect_requested = pyqtSignal(str)

    def __init__(self, resource_string: str, friendly: str, parent=None):
        super().__init__(parent)
        self.resource_string = resource_string
        self.friendly = friendly
        self._connected = False
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        self._set_dot_color(theme.TEXT_MUTED)
        layout.addWidget(self._dot)

        info = QVBoxLayout()
        info.setSpacing(1)
        self._name_lbl = QLabel(self.friendly)
        self._name_lbl.setStyleSheet(f"font-weight: 600; color: {theme.TEXT_PRIMARY};")
        self._addr_lbl = QLabel(self.resource_string)
        self._addr_lbl.setStyleSheet(f"font-size: 8pt; color: {theme.TEXT_MUTED};")
        info.addWidget(self._name_lbl)
        info.addWidget(self._addr_lbl)
        layout.addLayout(info, stretch=1)

        self._btn = QPushButton("Connect")
        self._btn.setMinimumWidth(90)
        self._btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._btn.clicked.connect(self._on_button)
        layout.addWidget(self._btn)

    def set_connected(self, ok: bool):
        self._connected = ok
        self._set_dot_color(theme.SUCCESS if ok else theme.TEXT_MUTED)
        self._btn.setText("Disconnect" if ok else "Connect")

    def set_error(self):
        self._set_dot_color(theme.ERROR)
        self._btn.setText("Retry")
        self._connected = False

    def set_scanning(self):
        self._set_dot_color(theme.AMBER)

    def _set_dot_color(self, color: str):
        self._dot.setStyleSheet(f"color: {color}; font-size: 14pt;")

    def _on_button(self):
        if self._connected:
            self.disconnect_requested.emit(self.resource_string)
        else:
            self.connect_requested.emit(self.resource_string)


class InstrumentPanel(QWidget):
    """
    Left panel: VISA scan, per-instrument connect/disconnect, status display.

    Signals
    -------
    instruments_changed(smu_map)   — emitted whenever connected set changes.
                                     smu_map: dict[instrument_id -> SMUBase]
    """

    instruments_changed = pyqtSignal(dict)

    def __init__(self, visa_manager: VISAManager, parent=None):
        super().__init__(parent)
        self._vm = visa_manager
        self._rows: dict[str, InstrumentRow] = {}       # resource_string -> row
        self._smu_map: dict[str, SMUBase] = {}          # instrument_id  -> driver
        self._resources: dict[str, dict] = {}           # resource_string -> info dict
        self._scan_worker: Optional[_ScanWorker] = None
        self._build_ui()
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(280)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Title
        title = QLabel("INSTRUMENTS")
        title.setProperty("role", "section")
        root.addWidget(title)

        # Scan button
        self._scan_btn = QPushButton("⟳  Scan VISA")
        self._scan_btn.setProperty("role", "primary")
        self._scan_btn.clicked.connect(self._on_scan)
        root.addWidget(self._scan_btn)

        # Manual entry
        manual_box = QGroupBox("Manual Entry")
        manual_layout = QFormLayout(manual_box)
        manual_layout.setSpacing(4)
        self._manual_addr = QLineEdit()
        self._manual_addr.setPlaceholderText("GPIB0::24::INSTR or USB0::...")
        self._manual_model = QComboBox()
        self._manual_model.addItems(["2400", "2401", "2602", "2602A", "2614B"])
        self._manual_id = QLineEdit()
        self._manual_id.setPlaceholderText("My label (optional)")
        manual_layout.addRow("Address:", self._manual_addr)
        manual_layout.addRow("Model:", self._manual_model)
        manual_layout.addRow("Label:", self._manual_id)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_manual_add)
        manual_layout.addRow("", add_btn)
        root.addWidget(manual_box)

        # Connect all
        self._conn_all_btn = QPushButton("Connect All")
        self._conn_all_btn.clicked.connect(self._connect_all)
        root.addWidget(self._conn_all_btn)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        # Instrument list
        self._list_box = QGroupBox("Discovered / Added")
        list_layout = QVBoxLayout(self._list_box)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(4)
        self._scroll_content = QVBoxLayout()
        self._scroll_content.setSpacing(2)
        list_layout.addLayout(self._scroll_content)
        root.addWidget(self._list_box, stretch=1)

        # Status label
        self._status_lbl = QLabel("No instruments found. Click 'Scan VISA'.")
        self._status_lbl.setProperty("role", "muted")
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _on_scan(self):
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("Scanning…")
        self._status_lbl.setText("Scanning VISA bus…")
        self._scan_worker = _ScanWorker(self._vm)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, results: list):
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("⟳  Scan VISA")
        for info in results:
            rstr = info["resource_string"]
            if rstr not in self._rows:
                self._resources[rstr] = info
                self._add_row(rstr, info.get("friendly", rstr))
        count = len(self._rows)
        self._status_lbl.setText(
            f"{count} instrument(s) found." if count else "No VISA instruments found."
        )

    def _on_manual_add(self):
        rstr = self._manual_addr.text().strip()
        if not rstr:
            return
        model = self._manual_model.currentText()
        label = self._manual_id.text().strip() or f"Keithley {model}"
        info = {
            "resource_string": rstr,
            "interface": "Manual",
            "address": rstr,
            "friendly": label,
            "idn": "",
            "model_hint": model,
        }
        self._resources[rstr] = info
        if rstr not in self._rows:
            self._add_row(rstr, label)
        self._manual_addr.clear()
        self._manual_id.clear()

    def _add_row(self, resource_string: str, friendly: str):
        row = InstrumentRow(resource_string, friendly)
        row.connect_requested.connect(self._connect_instrument)
        row.disconnect_requested.connect(self._disconnect_instrument)
        self._rows[resource_string] = row
        self._scroll_content.addWidget(row)

    def _connect_all(self):
        for rstr in list(self._rows.keys()):
            self._connect_instrument(rstr)

    # ------------------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------------------

    def _connect_instrument(self, resource_string: str):
        row = self._rows.get(resource_string)
        if not row:
            return
        info = self._resources.get(resource_string, {})
        model_hint = info.get("model_hint", "") or self._guess_model(info.get("idn", ""))

        try:
            res = self._vm.open_resource(resource_string)
            driver = self._make_driver(res, model_hint, resource_string)
            driver.reset()
            idn = driver.identify()
            instr_id = self._label_for(resource_string, model_hint, idn)
            self._smu_map[instr_id] = driver
            row.set_connected(True)
            row.friendly = instr_id
            row._name_lbl.setText(instr_id)
            log.info("Connected: %s (%s)", instr_id, resource_string)
            self._status_lbl.setText(f"Connected: {instr_id}")
        except Exception as exc:
            row.set_error()
            self._status_lbl.setText(f"Error: {exc}")
            log.error("Connect failed for %s: %s", resource_string, exc)
            return

        self.instruments_changed.emit(dict(self._smu_map))

    def _disconnect_instrument(self, resource_string: str):
        row = self._rows.get(resource_string)
        # Find instrument by resource string
        to_remove = [k for k, v in self._smu_map.items()
                     if hasattr(v, "_resource") and str(v._resource.resource_name) == resource_string]
        for k in to_remove:
            try:
                self._smu_map[k].disconnect()
            except Exception:
                pass
            del self._smu_map[k]
        if row:
            row.set_connected(False)
        self.instruments_changed.emit(dict(self._smu_map))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _guess_model(idn: str) -> str:
        for key in ("2614B", "2614", "2602A", "2602", "2401", "2400"):
            if key.lower() in idn.lower():
                return key
        return "2400"

    @staticmethod
    def _make_driver(resource, model_hint: str, resource_string: str) -> SMUBase:
        m = model_hint.upper()
        if "2614" in m or "2602" in m:
            # Default channel A; user can add channel B separately
            channel = "A"
            return SMU2600(resource, channel=channel)
        return SMU2400(resource)

    @staticmethod
    def _label_for(resource_string: str, model_hint: str, idn: str) -> str:
        if model_hint:
            return f"Keithley {model_hint}"
        parts = idn.split(",")
        if len(parts) >= 2:
            return f"{parts[0].strip()} {parts[1].strip()}"
        return resource_string

    @property
    def smu_map(self) -> dict[str, SMUBase]:
        return dict(self._smu_map)
