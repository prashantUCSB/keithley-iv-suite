"""Main application window."""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy, QSplitter, QStatusBar,
    QVBoxLayout, QWidget,
)

from ..instruments.visa_manager import VISAManager
from ..measurements.queue_manager import MeasurementQueue, QueueItemStatus
from ..measurements.recipe_loader import load_recipe
from ..measurements.sweep_config import (
    FourPointProbeConfig, Generic4PortConfig, HallBarConfig, OutputConfig,
    ResistorConfig, SweepConfig, TransferConfig, VanDerPauwConfig,
)
from ..data.exporter import export_csv, default_filename
from .panels import InstrumentPanel, SweepPanel, PlotPanel, QueuePanel
from .workers import MeasurementWorker, ExportWorker
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
        # Export state — reset at each queue run
        self._export_workers: list[ExportWorker] = []
        self._excel_lock = threading.Lock()
        self._current_excel_path: str = ""

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
        self.setMinimumSize(1100, 700)
        self.resize(1500, 960)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────
        top_bar = self._make_top_bar()
        main_layout.addWidget(top_bar)

        # ── Layout: [instruments | [sweep+queue vertical] | plot] ────────
        #
        # h_splitter
        #   ├── _instr_panel       (left,  ~300 px, min-resizable)
        #   └── right_h_split      (expands horizontally)
        #         ├── left_v_split (~370 px, min-resizable)
        #         │     ├── _sweep_panel  (top, fixed height)
        #         │     └── _queue_panel  (bottom, expands vertically)
        #         └── _plot_panel  (expands — takes all remaining width)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setChildrenCollapsible(False)
        h_splitter.setHandleWidth(4)

        # ── Left: instruments ─────────────────────────────────────────────
        self._instr_panel = InstrumentPanel(
            self._visa_manager if self._visa_manager else self._dummy_visa()
        )
        self._instr_panel.instruments_changed.connect(self._on_instruments_changed)
        h_splitter.addWidget(self._instr_panel)

        # ── Right: sweep panel  |  plot ─────────────────────────────────
        right_h_split = QSplitter(Qt.Orientation.Horizontal)
        right_h_split.setChildrenCollapsible(False)
        right_h_split.setHandleWidth(4)

        self._sweep_panel = SweepPanel()
        self._sweep_panel.run_requested.connect(self._run_single)
        self._sweep_panel.add_to_queue_requested.connect(self._add_to_queue)

        # Plot panel: occupies the bulk of the horizontal space.
        self._plot_panel = PlotPanel()
        self._plot_panel.export_requested.connect(self._export_last_result)
        self._plot_panel.params_updated.connect(self._on_params_updated)

        right_h_split.addWidget(self._sweep_panel)
        right_h_split.addWidget(self._plot_panel)
        right_h_split.setSizes([370, 830])
        right_h_split.setStretchFactor(0, 0)   # sweep — doesn't grow
        right_h_split.setStretchFactor(1, 1)   # plot  — expands

        h_splitter.addWidget(right_h_split)
        h_splitter.setSizes([300, 1200])
        h_splitter.setStretchFactor(0, 0)   # instruments — doesn't grow
        h_splitter.setStretchFactor(1, 1)   # right area  — expands
        main_layout.addWidget(h_splitter, stretch=1)

        # ── Queue dock widget (floating by default) ──────────────────────
        self._queue_panel = QueuePanel(self._queue)
        self._queue_panel.run_queue_requested.connect(self._run_queue)
        self._queue_panel.stop_queue_requested.connect(self._stop_measurement)
        self._queue_panel.item_removed.connect(
            lambda name: self._set_status(f"Removed '{name}' from queue")
        )

        self._queue_dock = QDockWidget("Measurement Queue", self)
        self._queue_dock.setWidget(self._queue_panel)
        self._queue_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._queue_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        # Register with main window so docking is possible, then float it
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._queue_dock)
        self._queue_dock.setFloating(True)
        self._queue_dock.resize(300, 520)

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
        logo.setStyleSheet(
            f"color: {theme.AMBER}; font-size: {theme.FONT_SIZE_TITLE + 4}pt; font-weight: 700;"
        )
        layout.addWidget(logo)

        title = QLabel("Keithley IV Suite")
        title.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: {theme.FONT_SIZE_TITLE}pt; font-weight: 700;"
        )
        layout.addWidget(title)

        # Developer credit + version — always visible in the top bar
        layout.addSpacing(16)
        dev_lbl = QLabel(theme.DEVELOPER)
        dev_lbl.setStyleSheet(
            f"color: {theme.TEXT_CREDIT}; font-size: {theme.FONT_SIZE_SMALL}pt;"
        )
        layout.addWidget(dev_lbl)

        ver_lbl = QLabel(f"v{theme.VERSION}")
        ver_lbl.setStyleSheet(
            f"color: {theme.GREEN_BRIGHT}; font-size: {theme.FONT_SIZE_SMALL}pt;"
            " font-weight: 700; letter-spacing: 0.04em;"
        )
        layout.addWidget(ver_lbl)

        layout.addStretch()

        # Output directory path bar — shows current dir; click to change
        self._path_btn = QPushButton()
        self._path_btn.setFlat(True)
        self._path_btn.setToolTip("Output directory (click to change)")
        self._path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._path_btn.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_SIZE_SMALL}pt;"
            "background: transparent; border: none; padding: 2px 6px;"
        )
        self._path_btn.clicked.connect(self._set_output_dir)
        layout.addWidget(self._path_btn)
        self._refresh_path_btn()

        # Vertical separator
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {theme.BORDER}; padding: 0 4px;")
        layout.addWidget(sep)

        # Status indicator
        self._conn_status_lbl = QLabel("No VISA connection")
        self._conn_status_lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_SIZE_SMALL}pt;"
        )
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
        act_exit.setShortcut(QKeySequence("Ctrl+W"))
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Measurement
        meas_menu = mb.addMenu("Measurement")
        act_run = QAction("Run Current", self)
        act_run.setShortcut(QKeySequence("F5"))
        act_run.triggered.connect(lambda: self._sweep_panel._on_run())
        meas_menu.addAction(act_run)

        act_stop = QAction("Stop", self)
        act_stop.triggered.connect(self._stop_measurement)
        meas_menu.addAction(act_stop)

        act_export = QAction("Export Last Result…", self)
        act_export.setShortcut(QKeySequence("Ctrl+S"))
        act_export.triggered.connect(self._export_last_result)
        meas_menu.addAction(act_export)

        # Queue
        queue_menu = mb.addMenu("Queue")

        self._act_show_queue = QAction("Show Queue", self)
        self._act_show_queue.setCheckable(True)
        self._act_show_queue.setChecked(True)
        self._act_show_queue.setShortcut(QKeySequence("Ctrl+Shift+Q"))
        self._act_show_queue.triggered.connect(
            lambda checked: self._queue_dock.setVisible(checked)
        )
        queue_menu.addAction(self._act_show_queue)
        # Keep checkmark in sync when user closes the dock via its own X button
        # (connect after _build_ui so _queue_dock already exists)
        queue_menu.addSeparator()

        act_run_q = QAction("Run Queue", self)
        act_run_q.setShortcut(QKeySequence("F6"))
        act_run_q.triggered.connect(self._run_queue)
        queue_menu.addAction(act_run_q)

        act_stop_q = QAction("Stop", self)
        act_stop_q.setShortcut(QKeySequence("Escape"))
        act_stop_q.triggered.connect(self._stop_measurement)
        queue_menu.addAction(act_stop_q)

        queue_menu.addSeparator()

        act_check_all = QAction("Check All for Export", self)
        act_check_all.triggered.connect(self._queue_panel.check_all_export_public)
        queue_menu.addAction(act_check_all)

        # View
        view_menu = mb.addMenu("View")
        act_clear = QAction("Clear Plot", self)
        act_clear.triggered.connect(self._plot_panel.clear)
        view_menu.addAction(act_clear)

        act_autoscale = QAction("Autoscale Plot", self)
        act_autoscale.setShortcut(QKeySequence("Ctrl+A"))
        act_autoscale.triggered.connect(self._plot_panel._autoscale_all)
        view_menu.addAction(act_autoscale)

        act_export_png = QAction("Export Plot as PNG…", self)
        act_export_png.setShortcut(QKeySequence("Ctrl+P"))
        act_export_png.triggered.connect(self._plot_panel._export_png)
        view_menu.addAction(act_export_png)

        # Help
        help_menu = mb.addMenu("Help")
        act_wiring = QAction("Wiring Guide…", self)
        act_wiring.setShortcut(QKeySequence("F1"))
        act_wiring.triggered.connect(self._show_wiring_guide)
        help_menu.addAction(act_wiring)
        help_menu.addSeparator()
        act_about = QAction("About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _apply_theme(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(theme.stylesheet())

    def _post_init(self):
        # Keep the Queue menu checkmark in sync with the dock's own close button
        self._queue_dock.visibilityChanged.connect(self._act_show_queue.setChecked)

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
            f"color: {theme.SUCCESS}; font-size: {theme.FONT_SIZE_SMALL}pt;" if n
            else f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_SIZE_SMALL}pt;"
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

    def _on_data_point(self, v_forced: float, i_meas: float, v_sensed: float, curve_id: int):
        self._plot_panel.append_point(v_forced, i_meas, v_sensed, curve_id)

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
            if self._queue_panel.is_export_checked(finished_item.uid):
                self._trigger_export(result, finished_item.config)
            self._run_next_in_queue()
        else:
            self._queue_running = False

    def _on_params_updated(self, params: dict):
        """Show extracted parameters in the status bar."""
        from .panels.plot_panel import _fmt_si
        parts = []
        if "R" in params:
            parts.append(f"R = {_fmt_si(params['R'], 'Ω')}")
            parts.append(f"R² = {params['R_sq']:.6f}")
        if "gm_pk" in params:
            parts.append(f"gm_pk = {_fmt_si(params['gm_pk'], 'S')}")
        if "Vth" in params and not (isinstance(params["Vth"], float)
                                    and params["Vth"] != params["Vth"]):
            parts.append(f"Vth = {params['Vth']:.3f} V")
        if "gd_max" in params:
            parts.append(f"gd_max = {_fmt_si(params['gd_max'], 'S')}")
        if parts:
            self._set_status("  |  ".join(parts), color=theme.AMBER)

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
        # Prepare a fresh Excel workbook path for this queue run
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(self._output_dir, exist_ok=True)
        self._current_excel_path = str(Path(self._output_dir) / f"IV_Data_{ts}.xlsx")
        self._excel_lock = threading.Lock()
        self._export_workers.clear()
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

    def _trigger_export(self, result: dict, config: SweepConfig) -> None:
        """Capture the plot PNG in the UI thread, then launch a background export."""
        png_bytes = self._capture_plot_png()
        fmt = self._queue_panel.export_format
        worker = ExportWorker(
            result=result,
            config=config,
            output_dir=self._output_dir,
            export_format=fmt,
            png_bytes=png_bytes,
            excel_path=self._current_excel_path if fmt in ("excel", "both") else None,
            excel_lock=self._excel_lock,
            parent=None,
        )
        worker.export_done.connect(
            lambda p: self._set_status(f"Saved → {p}", color=theme.SUCCESS)
        )
        worker.export_error.connect(
            lambda e: log.warning("Export error: %s", e)
        )
        # Keep reference so GC doesn't collect it before it finishes
        self._export_workers.append(worker)
        worker.finished.connect(lambda: self._export_workers.remove(worker)
                                if worker in self._export_workers else None)
        worker.start()

    def _capture_plot_png(self) -> bytes:
        """Grab the plot panel as PNG bytes (must be called from the UI thread)."""
        from PyQt6.QtCore import QBuffer, QIODevice
        pixmap = self._plot_panel.grab()
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buf, "PNG")
        data = bytes(buf.data())
        buf.close()
        return data

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
            self._refresh_path_btn()
            self._set_status(f"Output directory: {d}")

    def _refresh_path_btn(self):
        """Update the top-bar path button label to show the current output dir."""
        p = Path(self._output_dir)
        # Show last two path components to keep the label compact
        try:
            parts = p.parts
            label = str(Path(*parts[-2:])) if len(parts) >= 2 else str(p)
        except Exception:
            label = str(p)
        self._path_btn.setText(f"📁 {label}")
        self._path_btn.setToolTip(f"Output: {self._output_dir}\n(click to change)")

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
        if isinstance(config, (VanDerPauwConfig, HallBarConfig)):
            return config.i_points
        if isinstance(config, Generic4PortConfig):
            return config.v_points
        if isinstance(config, FourPointProbeConfig):
            return config.i_points
        return 0

    def _show_wiring_guide(self):
        from .dialogs.wiring_guide_dialog import WiringGuideDialog
        WiringGuideDialog(self).exec()

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
