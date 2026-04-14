"""Floating queue panel — measurement queue management."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...measurements.queue_manager import MeasurementQueue, QueueItem, QueueItemStatus
from ...measurements.sweep_config import SweepConfig
from .. import theme

log = logging.getLogger(__name__)

_COL_STATUS = 0
_COL_TYPE   = 1
_COL_LABEL  = 2
_COL_NPTS   = 3
_COL_EXPORT = 4   # save-to-file checkbox


class QueuePanel(QWidget):
    """
    Queue management panel — lives inside a QDockWidget.

    Signals
    -------
    run_queue_requested()       — user clicked "Run Queue"
    stop_queue_requested()      — user clicked "Stop"
    item_removed(display_name)  — an item was deleted; carries its label/type
    """

    run_queue_requested  = pyqtSignal()
    stop_queue_requested = pyqtSignal()
    item_removed         = pyqtSignal(str)

    def __init__(self, queue: MeasurementQueue, parent=None):
        super().__init__(parent)
        self._queue = queue
        self._build_ui()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(200)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Table — 5 columns; scrollable, no fixed height
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["", "Type", "Label", "Pts", "Save"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setColumnWidth(_COL_STATUS, 20)
        self._table.setColumnWidth(_COL_TYPE,   76)
        self._table.setColumnWidth(_COL_LABEL,  80)
        self._table.setColumnWidth(_COL_NPTS,   36)
        self._table.setColumnWidth(_COL_EXPORT, 36)
        self._table.setAlternatingRowColors(True)
        self._table.itemChanged.connect(self._on_item_changed)
        root.addWidget(self._table, stretch=1)

        # Remove button
        self._del_btn = QPushButton("Remove Selected")
        self._del_btn.setProperty("role", "danger")
        self._del_btn.clicked.connect(self._remove_selected)
        root.addWidget(self._del_btn)

        # Clear / Check All
        clear_export_row = QHBoxLayout()
        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.clicked.connect(self._clear_queue)
        self._export_all_btn = QPushButton("Check All")
        self._export_all_btn.setToolTip("Mark all items for export")
        self._export_all_btn.clicked.connect(self._check_all_export)
        clear_export_row.addWidget(self._clear_btn)
        clear_export_row.addWidget(self._export_all_btn)
        root.addLayout(clear_export_row)

        # Export format selector
        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("Format:")
        fmt_lbl.setProperty("role", "muted")
        self._format_combo = QComboBox()
        self._format_combo.addItem("CSV", userData="csv")
        self._format_combo.addItem("Excel", userData="excel")
        self._format_combo.addItem("Both", userData="both")
        self._format_combo.setCurrentIndex(0)
        self._format_combo.setToolTip(
            "CSV: one .csv + .png per measurement in a date-time subfolder\n"
            "Excel: one .xlsx workbook with one sheet per measurement\n"
            "Both: CSV + Excel"
        )
        fmt_row.addWidget(fmt_lbl)
        fmt_row.addWidget(self._format_combo, stretch=1)
        root.addLayout(fmt_row)

        self._run_all_btn = QPushButton("▶▶  Run Queue")
        self._run_all_btn.setProperty("role", "primary")
        self._run_all_btn.clicked.connect(self.run_queue_requested.emit)
        root.addWidget(self._run_all_btn)

        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setProperty("role", "stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_queue_requested.emit)
        root.addWidget(self._stop_btn)

        self._count_lbl = QLabel("Queue empty")
        self._count_lbl.setProperty("role", "muted")
        root.addWidget(self._count_lbl)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_config(self, config: SweepConfig):
        item = self._queue.add(config)
        self._append_row(item)
        self._refresh_count()

    def refresh(self):
        """Rebuild the table from the queue (call after programmatic queue changes)."""
        self._table.setRowCount(0)
        for item in self._queue:
            self._append_row(item)
        self._refresh_count()

    def update_item_status(self, uid: str, status: QueueItemStatus):
        for row in range(self._table.rowCount()):
            cell = self._table.item(row, _COL_STATUS)
            if cell and cell.data(Qt.ItemDataRole.UserRole) == uid:
                symbol = {
                    QueueItemStatus.PENDING:  "⏳",
                    QueueItemStatus.RUNNING:  "▶",
                    QueueItemStatus.DONE:     "✓",
                    QueueItemStatus.ABORTED:  "⊘",
                    QueueItemStatus.ERROR:    "✗",
                }.get(status, "?")
                color = {
                    QueueItemStatus.PENDING:  theme.TEXT_MUTED,
                    QueueItemStatus.RUNNING:  theme.AMBER,
                    QueueItemStatus.DONE:     theme.SUCCESS,
                    QueueItemStatus.ABORTED:  theme.WARNING,
                    QueueItemStatus.ERROR:    theme.ERROR,
                }.get(status, theme.TEXT_PRIMARY)
                cell.setText(symbol)
                cell.setForeground(
                    __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(color)
                )
                break

    def set_running(self, running: bool):
        self._run_all_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._clear_btn.setEnabled(not running)
        self._del_btn.setEnabled(not running)

    def is_export_checked(self, uid: str) -> bool:
        for row in range(self._table.rowCount()):
            status_cell = self._table.item(row, _COL_STATUS)
            if status_cell and status_cell.data(Qt.ItemDataRole.UserRole) == uid:
                export_cell = self._table.item(row, _COL_EXPORT)
                if export_cell:
                    return export_cell.checkState() == Qt.CheckState.Checked
        return False

    @property
    def export_format(self) -> str:
        return self._format_combo.currentData()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append_row(self, item: QueueItem):
        self._table.blockSignals(True)
        row = self._table.rowCount()
        self._table.insertRow(row)

        status_cell = QTableWidgetItem(item.status_symbol)
        status_cell.setData(Qt.ItemDataRole.UserRole, item.uid)
        status_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        n_pts = self._calc_pts(item)
        self._table.setItem(row, _COL_STATUS, status_cell)
        self._table.setItem(row, _COL_TYPE,   QTableWidgetItem(item.display_type[:10]))
        self._table.setItem(row, _COL_LABEL,  QTableWidgetItem(item.config.label or "—"))
        self._table.setItem(row, _COL_NPTS,   QTableWidgetItem(str(n_pts)))

        export_cell = QTableWidgetItem()
        export_cell.setCheckState(Qt.CheckState.Checked)
        export_cell.setFlags(
            Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        export_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, _COL_EXPORT, export_cell)
        self._table.blockSignals(False)

    @staticmethod
    def _calc_pts(item: QueueItem) -> int:
        cfg = item.config
        from ...measurements.sweep_config import TransferConfig, OutputConfig, ResistorConfig
        if isinstance(cfg, TransferConfig):
            return cfg.vgs_points
        if isinstance(cfg, OutputConfig):
            return cfg.vds_points * len(cfg.vgs_list_values)
        if isinstance(cfg, ResistorConfig):
            return cfg.v_points
        return 0

    def _selected_uid(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        cell = self._table.item(row, _COL_STATUS)
        return cell.data(Qt.ItemDataRole.UserRole) if cell else None

    def _remove_selected(self):
        row = self._table.currentRow()
        if row < 0:
            return
        status_cell = self._table.item(row, _COL_STATUS)
        label_cell  = self._table.item(row, _COL_LABEL)
        type_cell   = self._table.item(row, _COL_TYPE)
        if not status_cell:
            return
        uid = status_cell.data(Qt.ItemDataRole.UserRole)
        # Build a human-readable name for the status message
        label = label_cell.text() if label_cell else ""
        mtype = type_cell.text() if type_cell else "measurement"
        display = label if label and label != "—" else mtype
        self._queue.remove(uid)
        self.refresh()
        self.item_removed.emit(display)

    def _clear_queue(self):
        self._queue.clear()
        self._table.setRowCount(0)
        self._refresh_count()

    def check_all_export_public(self):
        """Public slot — called from the Queue menu action."""
        self._check_all_export()

    def _check_all_export(self):
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            cell = self._table.item(row, _COL_EXPORT)
            if cell:
                cell.setCheckState(Qt.CheckState.Checked)
        self._table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != _COL_EXPORT:
            return

    def _refresh_count(self):
        n = len(self._queue)
        self._count_lbl.setText(
            f"{n} item{'s' if n != 1 else ''} in queue" if n else "Queue empty"
        )
