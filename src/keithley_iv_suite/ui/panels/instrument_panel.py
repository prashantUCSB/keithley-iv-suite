"""Left panel — instrument connection, status, and sense-mode control."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget, QComboBox, QLineEdit,
    QFormLayout,
)

from ...instruments.visa_manager import VISAManager
from ...instruments.smu_2400 import SMU2400
from ...instruments.smu_2600 import SMU2600
from ...instruments.smu_base import SMUBase
from .. import theme

log = logging.getLogger(__name__)


class ElidedLabel(QLabel):
    """QLabel that clips overflowing text with '…' instead of wrapping."""

    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.rect(), int(self.alignment()), elided)


# 2600-series models that have two independent channels (A and B).
# Both are registered in smu_map so the user can assign them separately
# to drain / gate / source in the sweep panel.
_DUAL_CHANNEL_MODELS = frozenset(
    ["2602", "2602A", "2602B", "2604", "2611", "2612", "2612B",
     "2614", "2614B", "2634", "2634B", "2636", "2636B"]
)


class _ScanWorker(QThread):
    done = pyqtSignal(list)

    def __init__(self, vm: VISAManager, skip_resources: "set[str] | None" = None):
        super().__init__()
        self._vm = vm
        self._skip = skip_resources or set()

    def run(self):
        try:
            results = self._vm.list_resources_with_info(skip=self._skip)
        except Exception as exc:
            log.error("VISA scan error: %s", exc)
            results = []
        self.done.emit(results)


class InstrumentRow(QWidget):
    """One instrument row — status dot, name, address, sense toggle, connect button."""

    connect_requested      = pyqtSignal(str)   # resource_string
    disconnect_requested   = pyqtSignal(str)
    sense_mode_changed     = pyqtSignal(str, bool)  # resource_string, remote

    def __init__(self, resource_string: str, friendly: str,
                 is_smu: bool = True, idn: str = "", parent=None):
        super().__init__(parent)
        self.resource_string = resource_string
        self.friendly = friendly
        self.is_smu = is_smu
        self.idn = idn
        self._connected = False
        self._remote_sense = False
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        self._set_dot_color(theme.TEXT_MUTED)
        layout.addWidget(self._dot)

        info = QVBoxLayout()
        info.setSpacing(1)
        self._name_lbl = ElidedLabel(self.friendly)
        self._name_lbl.setStyleSheet(f"font-weight:600; color:{theme.TEXT_PRIMARY};")
        # Show IDN substring for non-SMU devices so the user knows what it is
        addr_text = self._short_address(self.resource_string)
        if not self.is_smu and self.idn:
            addr_text = self.idn[:40]
        self._addr_lbl = ElidedLabel(addr_text)
        self._addr_lbl.setProperty("role", "muted")
        info.addWidget(self._name_lbl)
        info.addWidget(self._addr_lbl)
        layout.addLayout(info, stretch=1)

        # 2W/4W sense toggle — only meaningful for SMUs
        if self.is_smu:
            self._sense_btn = QPushButton("2W Sense")
            self._sense_btn.setMinimumWidth(68)
            self._sense_btn.setToolTip(
                "2W Sense (local) — standard two-wire measurement\n"
                "4W Sense (remote) — four-wire Kelvin measurement;\n"
                "eliminates lead resistance; use for low-resistance devices.\n"
                "Connect separate Force and Sense leads to each terminal."
            )
            self._sense_btn.setStyleSheet(
                f"font-size:8pt; font-weight:700; color:{theme.TEXT_MUTED};"
            )
            self._sense_btn.clicked.connect(self._toggle_sense)
            layout.addWidget(self._sense_btn)
        else:
            self._sense_btn = None

        self._btn = QPushButton("Connect" if self.is_smu else "—")
        self._btn.setMinimumWidth(110)
        self._btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        if self.is_smu:
            self._btn.clicked.connect(self._on_button)
        else:
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(f"color:{theme.TEXT_MUTED};")
        layout.addWidget(self._btn)

    def set_connected(self, ok: bool):
        self._connected = ok
        self._set_dot_color(theme.SUCCESS if ok else theme.TEXT_MUTED)
        self._btn.setText("Disconnect" if ok else "Connect")
        if self._sense_btn:
            self._sense_btn.setEnabled(ok)
            active = ok and self._remote_sense
            color = "#00BFFF" if active else theme.TEXT_MUTED
            self._sense_btn.setStyleSheet(
                f"font-size:8pt; font-weight:700; color:{color};"
            )

    def set_error(self):
        self._set_dot_color(theme.ERROR)
        self._btn.setText("Retry")
        self._connected = False

    def _set_dot_color(self, color: str):
        self._dot.setStyleSheet(f"color:{color}; font-size:14pt;")

    def _on_button(self):
        if self._connected:
            self.disconnect_requested.emit(self.resource_string)
        else:
            self.connect_requested.emit(self.resource_string)

    def _toggle_sense(self):
        self._remote_sense = not self._remote_sense
        label = "4W Sense" if self._remote_sense else "2W Sense"
        color = "#00BFFF" if self._remote_sense else theme.TEXT_MUTED
        self._sense_btn.setText(label)
        self._sense_btn.setStyleSheet(
            f"font-size:8pt; font-weight:700; color:{color};"
        )
        self.sense_mode_changed.emit(self.resource_string, self._remote_sense)

    @property
    def remote_sense(self) -> bool:
        return self._remote_sense

    @staticmethod
    def _short_address(rstr: str) -> str:
        import re
        upper = rstr.upper()
        if upper.startswith("GPIB"):
            parts = rstr.split("::")
            return f"GPIB · {parts[1] if len(parts) > 1 else '?'}"
        if upper.startswith("USB"):
            m = re.match(r"USB\d*::0x[0-9A-Fa-f]+::0x([0-9A-Fa-f]+)::", rstr, re.IGNORECASE)
            return f"USB · 0x{m.group(1).upper()}" if m else "USB"
        if upper.startswith("TCPIP"):
            parts = rstr.split("::")
            return f"LAN · {parts[1]}" if len(parts) > 1 else "LAN"
        return rstr


class InstrumentPanel(QWidget):
    """
    Left panel: VISA scan, per-instrument connect/disconnect, 2W/4W toggle.

    Signals
    -------
    instruments_changed(smu_map)  — emitted whenever connected set changes.
    """

    instruments_changed = pyqtSignal(dict)

    def __init__(self, visa_manager: VISAManager, parent=None):
        super().__init__(parent)
        self._vm = visa_manager
        self._rows: dict[str, InstrumentRow] = {}
        self._smu_map: dict[str, SMUBase] = {}
        self._resources: dict[str, dict] = {}
        self._scan_worker: Optional[_ScanWorker] = None
        self._build_ui()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(240)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("INSTRUMENTS")
        title.setProperty("role", "section")
        root.addWidget(title)

        self._scan_btn = QPushButton("⟳  Scan VISA")
        self._scan_btn.setProperty("role", "primary")
        self._scan_btn.clicked.connect(self._on_scan)
        root.addWidget(self._scan_btn)

        # Manual entry
        manual_box = QGroupBox("Manual Entry")
        manual_layout = QFormLayout(manual_box)
        manual_layout.setSpacing(4)
        self._manual_addr = QLineEdit()
        self._manual_addr.setPlaceholderText("GPIB0::24::INSTR  or  USB0::...")
        self._manual_model = QComboBox()
        self._manual_model.addItems(["2400", "2401", "2602", "2602A", "2614B"])
        self._manual_id = QLineEdit()
        self._manual_id.setPlaceholderText("Label (optional)")
        manual_layout.addRow("Address:", self._manual_addr)
        manual_layout.addRow("Model:", self._manual_model)
        manual_layout.addRow("Label:", self._manual_id)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_manual_add)
        manual_layout.addRow("", add_btn)
        root.addWidget(manual_box)

        self._conn_all_btn = QPushButton("Connect All")
        self._conn_all_btn.clicked.connect(self._connect_all)
        root.addWidget(self._conn_all_btn)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        self._list_box = QGroupBox("Discovered / Added")
        list_layout = QVBoxLayout(self._list_box)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(4)
        self._scroll_content = QVBoxLayout()
        self._scroll_content.setSpacing(2)
        self._scroll_content.setAlignment(Qt.AlignmentFlag.AlignTop)
        list_layout.addLayout(self._scroll_content)
        root.addWidget(self._list_box, stretch=1)

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
        # Disable connect buttons on existing rows to prevent a race condition
        # between the scan's open_resource calls and a manual connect attempt.
        for row in self._rows.values():
            row.setEnabled(False)
        # Skip resources that our own connected drivers already hold open —
        # attempting to reopen them causes VI_ERROR_NCIC in NI-VISA.
        connected_rstrings: set[str] = set()
        for smu in self._smu_map.values():
            if hasattr(smu, "_resource"):
                try:
                    connected_rstrings.add(str(smu._resource.resource_name))
                except Exception:
                    pass
        self._scan_worker = _ScanWorker(self._vm, skip_resources=connected_rstrings)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, results: list):
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("⟳  Scan VISA")
        for row in self._rows.values():
            row.setEnabled(True)
        new_count = 0
        for info in results:
            rstr = info["resource_string"]
            if rstr not in self._rows:
                self._resources[rstr] = info
                self._add_row(
                    rstr,
                    info.get("friendly", rstr),
                    is_smu=info.get("is_smu", True),
                    idn=info.get("idn", ""),
                )
                new_count += 1
        total = len(self._rows)
        if total == 0:
            self._status_lbl.setText("No VISA instruments found.")
        else:
            self._status_lbl.setText(
                f"{total} instrument(s) found"
                + (f" ({new_count} new)." if new_count else " (already listed).")
            )

    def _on_manual_add(self):
        rstr = self._manual_addr.text().strip()
        if not rstr:
            return
        model = self._manual_model.currentText()
        label = self._manual_id.text().strip() or f"Keithley {model}"
        info = {
            "resource_string": rstr, "interface": "Manual",
            "address": rstr, "friendly": label,
            "idn": "", "model_hint": model, "is_smu": True,
        }
        self._resources[rstr] = info
        if rstr not in self._rows:
            self._add_row(rstr, label, is_smu=True, idn="")
        self._manual_addr.clear()
        self._manual_id.clear()

    def _add_row(self, resource_string: str, friendly: str,
                 is_smu: bool = True, idn: str = ""):
        row = InstrumentRow(resource_string, friendly, is_smu=is_smu, idn=idn)
        row.connect_requested.connect(self._connect_instrument)
        row.disconnect_requested.connect(self._disconnect_instrument)
        row.sense_mode_changed.connect(self._on_sense_mode_changed)
        self._rows[resource_string] = row
        self._scroll_content.addWidget(row)

    def _connect_all(self):
        for rstr, row in self._rows.items():
            if row.is_smu:
                self._connect_instrument(rstr)

    # ------------------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------------------

    def _connect_instrument(self, resource_string: str):
        import time
        import pyvisa.errors

        row = self._rows.get(resource_string)
        if not row or not row.is_smu:
            return
        info = self._resources.get(resource_string, {})
        manual_model_hint = info.get("model_hint", "")

        row.setEnabled(False)
        self._status_lbl.setText(f"Connecting to {resource_string}…")

        try:
            # Retry opening the resource once — handles the case where the
            # instrument is momentarily busy after a prior scan or disconnect.
            res = None
            for attempt in range(2):
                try:
                    res = self._vm.open_resource(resource_string)
                    break
                except pyvisa.errors.VisaIOError as exc:
                    if attempt == 0:
                        log.warning("open_resource failed (attempt 1), retrying: %s", exc)
                        time.sleep(0.5)
                    else:
                        raise

            # Clear the VISA interface before querying — for USBTMC this sends
            # INITIATE_CLEAR which flushes any stale measurement data from the
            # instrument's output buffer (e.g. a previous sweep's last reading).
            try:
                res.clear()
                time.sleep(0.05)
            except Exception:
                pass

            # Query *IDN? — retry once on timeout (instrument may be processing
            # a previous command from the scan).
            real_idn = ""
            for attempt in range(2):
                try:
                    real_idn = res.query("*IDN?").strip()
                    break
                except Exception as exc:
                    if attempt == 0:
                        log.warning("IDN query failed (attempt 1), retrying: %s", exc)
                        time.sleep(0.3)
                    else:
                        log.warning("IDN query gave no response for %s; continuing anyway", resource_string)
            log.debug("IDN for %s: %r", resource_string, real_idn)

            model_hint = manual_model_hint or self._guess_model(real_idn)
            base_id    = self._label_for(resource_string, model_hint, real_idn)
            drivers    = self._make_drivers(res, model_hint)

            registered: list[str] = []
            for suffix, driver in drivers:
                try:
                    driver.reset()
                except Exception as exc:
                    log.warning(
                        "reset() failed for %s%s: %s — continuing",
                        base_id, suffix, exc,
                    )
                if row.remote_sense:
                    try:
                        driver.set_sense_mode(True)
                    except Exception as exc:
                        log.warning("set_sense_mode failed for %s%s: %s", base_id, suffix, exc)
                instr_id = base_id + suffix
                self._smu_map[instr_id] = driver
                registered.append(instr_id)

            # Update the row label to reflect the registered entries.
            display_id = (
                f"{base_id} (A+B)" if len(registered) > 1 else registered[0]
            )
            row.set_connected(True)
            row.friendly = display_id
            row._name_lbl.setText(display_id)
            log.info("Connected: %s  IDN=%r  channels=%s", display_id, real_idn, registered)
            self._status_lbl.setText(f"Connected: {display_id}")
        except Exception as exc:
            row.set_error()
            self._status_lbl.setText(f"Error: {exc}")
            log.error("Connect failed for %s: %s", resource_string, exc)
            row.setEnabled(True)
            return
        finally:
            row.setEnabled(True)

        self.instruments_changed.emit(dict(self._smu_map))

    def _disconnect_instrument(self, resource_string: str):
        row = self._rows.get(resource_string)
        to_remove = [k for k, v in self._smu_map.items()
                     if hasattr(v, "_resource")
                     and str(v._resource.resource_name) == resource_string]
        for k in to_remove:
            try:
                self._smu_map[k].disconnect()
            except Exception:
                pass
            del self._smu_map[k]
        if row:
            row.set_connected(False)
        self.instruments_changed.emit(dict(self._smu_map))

    def _on_sense_mode_changed(self, resource_string: str, remote: bool):
        """Apply sense mode change to already-connected SMU immediately."""
        for smu in self._smu_map.values():
            if (hasattr(smu, "_resource")
                    and str(smu._resource.resource_name) == resource_string):
                try:
                    smu.set_sense_mode(remote)
                    log.info(
                        "%s sense mode → %s",
                        resource_string, "4-wire" if remote else "2-wire",
                    )
                except Exception as exc:
                    log.warning("set_sense_mode failed: %s", exc)
                break

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
    def _make_drivers(resource, model_hint: str) -> list[tuple[str, SMUBase]]:
        """Return [(label_suffix, driver), ...].

        2600-series dual-channel instruments (2602, 2614, etc.) produce two
        entries — one for channel A and one for channel B — so the user can
        assign them independently in the sweep panel (e.g. Ch.A → Drain,
        Ch.B → Gate).  Single-channel instruments return a single entry with
        an empty suffix.
        """
        m = model_hint.upper().replace(" ", "")
        # Check against the dual-channel set by looking for any key in the hint
        is_dual = any(key in m for key in _DUAL_CHANNEL_MODELS)
        if is_dual:
            return [
                (" Ch.A", SMU2600(resource, channel="A")),
                (" Ch.B", SMU2600(resource, channel="B")),
            ]
        if "2614" in m or "2602" in m or "2612" in m or "2636" in m:
            # Fallback if model hint wasn't matched above
            return [
                (" Ch.A", SMU2600(resource, channel="A")),
                (" Ch.B", SMU2600(resource, channel="B")),
            ]
        return [("", SMU2400(resource))]

    @staticmethod
    def _label_for(resource_string: str, model_hint: str, idn: str) -> str:
        if idn:
            parts = [p.strip() for p in idn.split(",")]
            if len(parts) >= 2:
                model_field = parts[1].upper().replace("MODEL", "").strip()
                if model_field:
                    return f"Keithley {model_field}"
        if model_hint:
            return f"Keithley {model_hint}"
        return resource_string

    @property
    def smu_map(self) -> dict[str, SMUBase]:
        return dict(self._smu_map)
