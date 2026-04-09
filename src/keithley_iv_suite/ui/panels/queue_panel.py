"""Right panel — measurement queue management."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
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


class QueuePanel(QWidget):
    """
    Right panel showing the measurement queue.

    Signals
    -------
    run_queue_requested()   — user clicked "Run All"
    stop_queue_requested()  — user clicked "Stop"
    """

    run_queue_requested  = pyqtSignal()
    stop_queue_requested = pyqtSignal()

    def __init__(self, queue: MeasurementQueue, parent=None):
        super().__init__(parent)
        self._queue = queue
        self._build_ui()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(180)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("QUEUE")
        title.setProperty("role", "section")
        root.addWidget(title)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["", "Type", "Label", "Pts"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setColumnWidth(_COL_STATUS, 20)
        self._table.setColumnWidth(_COL_TYPE,   80)
        self._table.setColumnWidth(_COL_LABEL,  80)
        self._table.setColumnWidth(_COL_NPTS,   40)
        self._table.setAlternatingRowColors(True)
        root.addWidget(self._table, stretch=1)

        # Row manipulation buttons
        row_btns = QHBoxLayout()
        self._up_btn   = QPushButton("↑")
        self._down_btn = QPushButton("↓")
        self._del_btn  = QPushButton("Remove")
        self._del_btn.setProperty("role", "danger")
        self._up_btn.setFixedWidth(32)
        self._down_btn.setFixedWidth(32)
        self._up_btn.clicked.connect(self._move_up)
        self._down_btn.clicked.connect(self._move_down)
        self._del_btn.clicked.connect(self._remove_selected)
        row_btns.addWidget(self._up_btn)
        row_btns.addWidget(self._down_btn)
        row_btns.addWidget(self._del_btn)
        root.addLayout(row_btns)

        # Queue actions
        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.clicked.connect(self._clear_queue)
        root.addWidget(self._clear_btn)

        self._run_all_btn = QPushButton("▶▶  Run Queue")
        self._run_all_btn.setProperty("role", "primary")
        self._run_all_btn.clicked.connect(self.run_queue_requested.emit)
        root.addWidget(self._run_all_btn)

        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setProperty("role", "stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_queue_requested.emit)
        root.addWidget(self._stop_btn)

        # Count label
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
            if self._table.item(row, _COL_STATUS) and \
               self._table.item(row, _COL_STATUS).data(Qt.ItemDataRole.UserRole) == uid:
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
                cell = self._table.item(row, _COL_STATUS)
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

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append_row(self, item: QueueItem):
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
        rows = self._table.selectedItems()
        if not rows:
            return None
        row = self._table.currentRow()
        cell = self._table.item(row, _COL_STATUS)
        return cell.data(Qt.ItemDataRole.UserRole) if cell else None

    def _move_up(self):
        uid = self._selected_uid()
        if uid:
            self._queue.move_up(uid)
            self.refresh()

    def _move_down(self):
        uid = self._selected_uid()
        if uid:
            self._queue.move_down(uid)
            self.refresh()

    def _remove_selected(self):
        uid = self._selected_uid()
        if uid:
            self._queue.remove(uid)
            self.refresh()

    def _clear_queue(self):
        self._queue.clear()
        self._table.setRowCount(0)
        self._refresh_count()

    def _refresh_count(self):
        n = len(self._queue)
        self._count_lbl.setText(f"{n} item{'s' if n != 1 else ''} in queue" if n else "Queue empty")
