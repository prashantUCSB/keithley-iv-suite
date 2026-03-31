"""Live pyqtgraph plot panel with export and clear actions."""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from .. import theme
from ...measurements.sweep_config import MeasurementType, SweepConfig

# Configure pyqtgraph defaults once
pg.setConfigOptions(antialias=True, foreground=theme.TEXT_SECONDARY, background=theme.PLOT_BG)

_AXIS_LABELS = {
    MeasurementType.NMOS_TRANSFER: ("Vgs (V)",  "Id (A)"),
    MeasurementType.NMOS_OUTPUT:   ("Vds (V)",  "Id (A)"),
    MeasurementType.RESISTOR_IV:   ("Voltage (V)", "Current (A)"),
}


class PlotPanel(QWidget):
    """
    Real-time IV plot panel.

    Call ``prepare(config)`` before a sweep starts, then call
    ``append_point(x, y, curve_id)`` for each new measurement point.
    """

    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: dict[int, pg.PlotDataItem] = {}
        self._data:   dict[int, tuple[list, list]] = {}
        self._config: SweepConfig | None = None
        self._total_pts = 0
        self._received_pts = 0
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(6)

        # Header row
        header_row = QHBoxLayout()
        title = QLabel("LIVE PLOT")
        title.setProperty("role", "section")
        header_row.addWidget(title)
        header_row.addStretch()

        self._pts_lbl = QLabel("Ready")
        self._pts_lbl.setProperty("role", "muted")
        header_row.addWidget(self._pts_lbl)
        root.addLayout(header_row)

        # pyqtgraph plot widget
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setMinimumHeight(280)
        self._plot_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._style_plot()
        root.addWidget(self._plot_widget, stretch=1)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self.export_requested.emit)
        self._clear_btn = QPushButton("Clear Plot")
        self._clear_btn.clicked.connect(self.clear)
        self._autoscale_btn = QPushButton("⤢ Autoscale")
        self._autoscale_btn.clicked.connect(self._plot_widget.autoRange)

        btn_row.addWidget(self._export_btn)
        btn_row.addWidget(self._clear_btn)
        btn_row.addWidget(self._autoscale_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

    def _style_plot(self):
        pw = self._plot_widget
        pw.setBackground(theme.PLOT_BG)

        # Grid
        pw.showGrid(x=True, y=True, alpha=0.15)

        # Axis pens
        axis_pen = pg.mkPen(color=theme.PLOT_AXIS, width=1)
        for axis_name in ("bottom", "left"):
            ax = pw.getAxis(axis_name)
            ax.setPen(axis_pen)
            ax.setTextPen(pg.mkPen(theme.TEXT_SECONDARY))
            ax.setStyle(tickLength=-8)

        # Default labels
        pw.setLabel("bottom", "X")
        pw.setLabel("left",   "Y")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare(self, config: SweepConfig, total_points: int = 0):
        """Call before starting a new sweep — clears plot, sets axis labels."""
        self.clear()
        self._config = config
        self._total_pts = total_points
        self._received_pts = 0

        xlabel, ylabel = _AXIS_LABELS.get(
            config.measurement_type, ("X", "Y")
        )
        self._plot_widget.setLabel("bottom", xlabel)
        self._plot_widget.setLabel("left",   ylabel)

        # Title
        label = config.label or config.measurement_type.value
        self._plot_widget.setTitle(
            f'<span style="color:{theme.AMBER}; font-weight:600;">{label}</span>',
            size="11pt",
        )

        if total_points > 0:
            self._progress.setRange(0, total_points)
            self._progress.setValue(0)
        self._pts_lbl.setText("0 pts")

    def append_point(self, x: float, y: float, curve_id: int = 0):
        """Append a data point to curve `curve_id` and update the plot."""
        if curve_id not in self._data:
            self._data[curve_id] = ([], [])
            color = theme.PLOT_COLORS[curve_id % len(theme.PLOT_COLORS)]
            pen = pg.mkPen(color=color, width=2)
            symbol_brush = pg.mkBrush(color)
            curve = self._plot_widget.plot(
                [], [],
                pen=pen,
                symbol="o",
                symbolSize=5,
                symbolBrush=symbol_brush,
                symbolPen=None,
            )
            self._curves[curve_id] = curve

        xs, ys = self._data[curve_id]
        xs.append(x)
        ys.append(y)
        self._curves[curve_id].setData(np.array(xs), np.array(ys))

        self._received_pts += 1
        self._pts_lbl.setText(f"{self._received_pts} pts")
        if self._total_pts > 0:
            self._progress.setValue(self._received_pts)

    def update_progress(self, step: int, total: int):
        self._progress.setRange(0, total)
        self._progress.setValue(step)
        self._pts_lbl.setText(f"{step}/{total} pts")

    def mark_done(self):
        self._pts_lbl.setText(f"{self._received_pts} pts ✓")
        if self._total_pts > 0:
            self._progress.setValue(self._total_pts)

    def mark_error(self, msg: str):
        self._pts_lbl.setText(f"Error: {msg}")
        self._pts_lbl.setStyleSheet(f"color: {theme.ERROR};")

    def clear(self):
        self._plot_widget.clear()
        self._curves.clear()
        self._data.clear()
        self._received_pts = 0
        self._progress.setValue(0)
        self._pts_lbl.setText("Ready")
        self._pts_lbl.setStyleSheet("")

    @property
    def has_data(self) -> bool:
        return bool(self._data)

    @property
    def current_result_data(self) -> dict[int, tuple[list, list]]:
        """Return {curve_id: (x_list, y_list)} for all plotted curves."""
        return {cid: (list(xs), list(ys)) for cid, (xs, ys) in self._data.items()}
