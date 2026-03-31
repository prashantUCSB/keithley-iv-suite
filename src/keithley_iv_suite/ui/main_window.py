"""Main application window."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QSizePolicy, QSplitter, QStatusBar, QVBoxLayout,
    QWidget,
)

from ..instruments.visa_manager import VISAManager
from ..measurements.queue_manager import MeasurementQueue, QueueItemStatus
from ..measurements.recipe_loader import load_recipe
from ..measurements.sweep_config import SweepConfig, TransferConfig, OutputConfig, ResistorConfig
from ..data.exporter import export_csv, default_filename
from .panels import InstrumentPanel, SweepPanel, PlotPanel, QueuePanel
from .workers import MeasurementWorker
from . import theme

log = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = str(Path.home() / "Documents" / "IV_Data")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._visa_manager: Optional[VISAManager] = None
        self._smu_map: dict = {}
        self._queue = MeasurementQueue()
        self._worker: Optional[MeasurementWorker] = None
        self._current_config: Optional[SweepConfig] = None
        self._last_result: Optional[dict] = None
        self._output_dir = _DEFAULT_OUTPUT_DIR
        self._queue_items_pending: list = []
        self._queue_running = False

        self._init_visa()
        self._build_ui()
        self._build_menu()
        self._apply_theme()
        self._post_init()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_visa(self):
        try:
            self._visa_manager = VISAManager()
        except RuntimeError as exc:
            log.error("VISA init failed: %s", exc)
            self._visa_manager = None

    def _build_ui(self):
        self.setWindowTitle("Keithley IV Suite")
        self.setMinimumSize(1200, 720)
        self.resize(1400, 860)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────
        top_bar = self._make_top_bar()
        main_layout.addWidget(top_bar)

        # ── Main splitter: [left panel | center | right panel] ───────────
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setChildrenCollapsible(False)

        # Left: instruments
        self._instr_panel = InstrumentPanel(
            self._visa_manager if self._visa_manager else self._dummy_visa()
        )
        self._instr_panel.instruments_changed.connect(self._on_instruments_changed)
        h_splitter.addWidget(self._instr_panel)

        # Center: config + plot (vertical splitter)
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setChildrenCollapsible(False)

        self._sweep_panel = SweepPanel()
        self._sweep_panel.run_requested.connect(self._run_single)
        self._sweep_panel.add_to_queue_requested.connect(self._add_to_queue)
        v_splitter.addWidget(self._sweep_panel)

        self._plot_panel = PlotPanel()
        self._plot_panel.export_requested.connect(self._export_last_result)
        v_splitter.addWidget(self._plot_panel)

        v_splitter.setSizes([380, 440])
        h_splitter.addWidget(v_splitter)

        # Right: queue
        self._queue_panel = QueuePanel(self._queue)
        self._queue_panel.run_queue_requested.connect(self._run_queue)
        self._queue_panel.stop_queue_requested.connect(self._stop_measurement)
        h_splitter.addWidget(self._queue_panel)

        h_splitter.setSizes([280, 860, 260])
        main_layout.addWidget(h_splitter, stretch=1)

        # ── Status bar ───────────────────────────────────────────────────
        self._build_status_bar()

    def _make_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(
            f"background: {theme.BG_DEEP}; border-bottom: 1px solid {theme.BORDER};"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Logo / title
        logo = QLabel("◈")
        logo.setStyleSheet(f"color: {theme.AMBER}; font-size: 18pt; font-weight: 700;")
        layout.addWidget(logo)

        title = QLabel("Keithley IV Suite")
        title.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(title)
        layout.addStretch()

        # Status indicator
        self._conn_status_lbl = QLabel("No VISA connection")
        self._conn_status_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
        layout.addWidget(self._conn_status_lbl)

        return bar

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_msg = QLabel("Ready")
        self._status_msg.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        sb.addWidget(self._status_msg, 1)

        self._status_progress = QProgressBar()
        self._status_progress.setFixedWidth(200)
        self._status_progress.setRange(0, 100)
        self._status_progress.setValue(0)
        self._status_progress.setVisible(False)
        sb.addPermanentWidget(self._status_progress)

    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("File")
        act_load_recipe = QAction("Load Recipe…", self)
        act_load_recipe.setShortcut(QKeySequence("Ctrl+O"))
        act_load_recipe.triggered.connect(self._load_recipe)
        file_menu.addAction(act_load_recipe)

        act_set_output = QAction("Set Output Directory…", self)
        act_set_output.triggered.connect(self._set_output_dir)
        file_menu.addAction(act_set_output)

        file_menu.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Measurement
        meas_menu = mb.addMenu("Measurement")
        act_run = QAction("Run Current", self)
        act_run.setShortcut(QKeySequence("F5"))
        act_run.triggered.connect(lambda: self._sweep_panel._on_run())
        meas_menu.addAction(act_run)

        act_stop = QAction("Stop", self)
        act_stop.setShortcut(QKeySequence("Escape"))
        act_stop.triggered.connect(self._stop_measurement)
        meas_menu.addAction(act_stop)

        act_export = QAction("Export Last Result…", self)
        act_export.setShortcut(QKeySequence("Ctrl+S"))
        act_export.triggered.connect(self._export_last_result)
        meas_menu.addAction(act_export)

        # View
        view_menu = mb.addMenu("View")
        act_clear = QAction("Clear Plot", self)
        act_clear.triggered.connect(self._plot_panel.clear)
        view_menu.addAction(act_clear)

        act_autoscale = QAction("Autoscale Plot", self)
        act_autoscale.setShortcut(QKeySequence("Ctrl+A"))
        act_autoscale.triggered.connect(self._plot_panel._plot_widget.autoRange)
        view_menu.addAction(act_autoscale)

        # Help
        help_menu = mb.addMenu("Help")
        act_about = QAction("About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _apply_theme(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(theme.stylesheet())

    def _post_init(self):
        if self._visa_manager is None:
            self._set_status(
                "⚠  VISA backend not found — install NI-VISA or Keysight IO Libraries",
                color=theme.WARNING,
            )
        else:
            self._set_status("VISA ready. Scan for instruments in the left panel.")

    # ------------------------------------------------------------------
    # Instrument updates
    # ------------------------------------------------------------------

    def _on_instruments_changed(self, smu_map: dict):
        self._smu_map = smu_map
        self._sweep_panel.update_instruments(smu_map)
        n = len(smu_map)
        names = ", ".join(smu_map.keys())
        self._conn_status_lbl.setText(
            f"{n} instrument{'s' if n != 1 else ''} connected: {names}" if n
            else "No instruments connected"
        )
        self._conn_status_lbl.setStyleSheet(
            f"color: {theme.SUCCESS}; font-size: 9pt;" if n
            else f"color: {theme.TEXT_MUTED}; font-size: 9pt;"
        )

    # ------------------------------------------------------------------
    # Single-run measurement
    # ------------------------------------------------------------------

    def _run_single(self, config: SweepConfig):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "A measurement is already running.")
            return
        if not self._smu_map:
            QMessageBox.warning(
                self, "No Instruments",
                "Connect at least one instrument before running a measurement.",
            )
            return
        self._start_worker(config)

    def _start_worker(self, config: SweepConfig):
        self._current_config = config
        total_pts = self._estimate_total_pts(config)
        self._plot_panel.prepare(config, total_pts)
        self._set_running(True)
        self._set_status(f"Running: {config.label or config.measurement_type.value}…")

        self._worker = MeasurementWorker(config, self._smu_map)
        self._worker.data_point.connect(self._on_data_point)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.aborted.connect(self._on_aborted)
        self._worker.start()

    def _stop_measurement(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._set_status("Stopping…", color=theme.WARNING)

    # ------------------------------------------------------------------
    # Worker signals
    # ------------------------------------------------------------------

    def _on_data_point(self, x: float, y: float, curve_id: int):
        self._plot_panel.append_point(x, y, curve_id)

    def _on_progress(self, step: int, total: int):
        self._status_progress.setRange(0, total)
        self._status_progress.setValue(step)
        self._plot_panel.update_progress(step, total)

    def _on_finished(self, result: dict):
        self._last_result = result
        self._plot_panel.mark_done()
        self._set_running(False)
        self._set_status(
            f"✓ Done — {self._current_config.measurement_type.value if self._current_config else 'Sweep'} complete",
            color=theme.SUCCESS,
        )
        # Update queue item if running queue
        if self._queue_running and self._queue_items_pending:
            finished_item = self._queue_items_pending.pop(0)
            finished_item.status = QueueItemStatus.DONE
            finished_item.result = result
            self._queue_panel.update_item_status(finished_item.uid, QueueItemStatus.DONE)
            self._auto_save(result, finished_item.config)
            self._run_next_in_queue()
        else:
            self._queue_running = False

    def _on_error(self, msg: str):
        self._plot_panel.mark_error(msg)
        self._set_running(False)
        self._set_status(f"✗ Error: {msg}", color=theme.ERROR)
        log.error("Measurement error: %s", msg)
        QMessageBox.critical(self, "Measurement Error", msg)
        if self._queue_running and self._queue_items_pending:
            failed_item = self._queue_items_pending.pop(0)
            failed_item.status = QueueItemStatus.ERROR
            failed_item.error_msg = msg
            self._queue_panel.update_item_status(failed_item.uid, QueueItemStatus.ERROR)
            self._run_next_in_queue()

    def _on_aborted(self):
        self._set_running(False)
        self._set_status("Measurement aborted", color=theme.WARNING)
        if self._queue_running and self._queue_items_pending:
            item = self._queue_items_pending.pop(0)
            item.status = QueueItemStatus.ABORTED
            self._queue_panel.update_item_status(item.uid, QueueItemStatus.ABORTED)
        self._queue_running = False
        self._queue_panel.set_running(False)

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def _add_to_queue(self, config: SweepConfig):
        self._queue_panel.add_config(config)
        self._set_status(
            f"Added '{config.label or config.measurement_type.value}' to queue "
            f"({len(self._queue)} items)"
        )

    def _run_queue(self):
        if not self._queue.items:
            QMessageBox.information(self, "Empty Queue", "Add measurements to the queue first.")
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "A measurement is already running.")
            return
        self._queue.reset_statuses()
        self._queue_panel.refresh()
        self._queue_items_pending = list(self._queue.pending_items())
        self._queue_running = True
        self._queue_panel.set_running(True)
        self._run_next_in_queue()

    def _run_next_in_queue(self):
        if not self._queue_items_pending:
            self._queue_running = False
            self._queue_panel.set_running(False)
            self._set_status(
                f"✓ Queue complete — {len(self._queue)} measurements done",
                color=theme.SUCCESS,
            )
            return
        item = self._queue_items_pending[0]
        item.status = QueueItemStatus.RUNNING
        self._queue_panel.update_item_status(item.uid, QueueItemStatus.RUNNING)
        self._start_worker(item.config)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_last_result(self):
        if self._last_result is None or self._current_config is None:
            QMessageBox.information(self, "No Data", "Run a measurement first.")
            return
        default = str(default_filename(self._current_config, self._output_dir))
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", default, "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            try:
                export_csv(self._last_result, path, self._current_config)
                self._set_status(f"Saved: {path}", color=theme.SUCCESS)
            except Exception as exc:
                QMessageBox.critical(self, "Export Error", str(exc))

    def _auto_save(self, result: dict, config: SweepConfig):
        try:
            os.makedirs(self._output_dir, exist_ok=True)
            path = default_filename(config, self._output_dir)
            export_csv(result, path, config)
            log.info("Auto-saved: %s", path)
        except Exception as exc:
            log.warning("Auto-save failed: %s", exc)

    # ------------------------------------------------------------------
    # Recipe loading
    # ------------------------------------------------------------------

    def _load_recipe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Recipe",
            str(Path.cwd() / "recipes"),
            "YAML / JSON (*.yaml *.yml *.json);;All Files (*)",
        )
        if not path:
            return
        try:
            configs = load_recipe(path)
            for cfg in configs:
                self._queue_panel.add_config(cfg)
            self._set_status(
                f"Recipe loaded: {len(configs)} measurement(s) added to queue"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Recipe Error", str(exc))

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _set_output_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self._output_dir
        )
        if d:
            self._output_dir = d
            self._set_status(f"Output directory: {d}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_running(self, running: bool):
        self._sweep_panel.set_running(running)
        self._status_progress.setVisible(running)
        if not running:
            self._status_progress.setValue(0)

    def _set_status(self, msg: str, color: str = theme.TEXT_SECONDARY):
        self._status_msg.setText(msg)
        self._status_msg.setStyleSheet(f"color: {color};")

    @staticmethod
    def _estimate_total_pts(config: SweepConfig) -> int:
        if isinstance(config, TransferConfig):
            return config.vgs_points
        if isinstance(config, OutputConfig):
            return config.vds_points * len(config.vgs_list_values)
        if isinstance(config, ResistorConfig):
            return config.v_points
        return 0

    def _show_about(self):
        from .dialogs.about_dialog import AboutDialog
        AboutDialog(self).exec()

    @staticmethod
    def _dummy_visa():
        """Return a VISAManager placeholder that silently uses pyvisa-py."""
        try:
            return VISAManager("@py")
        except Exception:
            return VISAManager.__new__(VISAManager)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        # Disconnect all instruments
        if self._instr_panel:
            for smu in self._instr_panel.smu_map.values():
                try:
                    smu.disconnect()
                except Exception:
                    pass
        super().closeEvent(event)
