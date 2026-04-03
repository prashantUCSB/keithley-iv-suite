"""Live pyqtgraph plot panel with auto-scaling SI axis labels."""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from .. import theme
from ...measurements.sweep_config import (
    MeasurementType, OutputConfig, ResistorConfig, SweepConfig, TransferConfig,
)

pg.setConfigOptions(antialias=True, foreground=theme.TEXT_SECONDARY, background=theme.PLOT_BG)

# (x_name, x_base_unit, y_name, y_base_unit)
_AXIS_CONFIG: dict[MeasurementType, tuple[str, str, str, str]] = {
    MeasurementType.NMOS_TRANSFER: ("Vgs", "V",  "Id", "A"),
    MeasurementType.NMOS_OUTPUT:   ("Vds", "V",  "Id", "A"),
    MeasurementType.RESISTOR_IV:   ("V",   "V",  "I",  "A"),
}

# Ordered largest-scale-factor first so the loop finds the prefix where
# 1 ≤ |value| × scale < 1000 (displayed value is always in a human range).
_SI_PREFIXES: list[tuple[float, str]] = [
    (1e15, "f"),   # femto  — e.g. 500 fA
    (1e12, "p"),   # pico   — e.g.   5 pA
    (1e9,  "n"),   # nano   — e.g.  50 nA
    (1e6,  "µ"),   # micro  — e.g. 500 µA
    (1e3,  "m"),   # milli  — e.g.   3 mA
    (1.0,  ""),    # unity  — e.g. 1.5  A  /  2.0  V
    (1e-3, "k"),   # kilo   — e.g.   2 kΩ  (future)
]


def _select_si(mag: float, base_unit: str) -> tuple[float, str]:
    """Return ``(scale_factor, unit_string)`` for *mag* SI units.

    ``value_SI * scale_factor`` gives the display value;
    ``unit_string`` is the axis unit label (e.g. "mA", "µA", "V").

    Examples::

        _select_si(1.5e-3, "A")  →  (1e3,  "mA")
        _select_si(3.2e-9, "A")  →  (1e9,  "nA")
        _select_si(2.5,    "V")  →  (1.0,  "V" )
        _select_si(0.05,   "V")  →  (1e3,  "mV")
    """
    if mag > 0.0:
        for scale, prefix in _SI_PREFIXES:
            if 1.0 <= mag * scale < 1000.0:
                return scale, f"{prefix}{base_unit}"
    return 1.0, base_unit


class PlotPanel(QWidget):
    """
    Real-time IV plot panel with automatic SI prefix scaling.

    Raw SI values (Amps, Volts) are always stored internally.
    Axis labels and displayed data are rescaled to natural prefixes
    (mA, µA, nA, mV, …) so tick values always fall in a readable range.

    Call ``prepare(config)`` before a sweep starts, then call
    ``append_point(x, y, curve_id)`` for each new measurement point.
    """

    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: dict[int, pg.PlotDataItem] = {}
        self._data:   dict[int, tuple[list, list]] = {}   # raw SI
        self._config: SweepConfig | None = None
        self._total_pts = 0
        self._received_pts = 0

        # Current axis scaling state
        self._x_scale: float = 1.0
        self._y_scale: float = 1.0
        self._y_max_abs: float = 0.0   # largest |y| seen; triggers rescale
        self._x_name: str = "X"
        self._y_name: str = "Y"
        self._x_base: str = "V"
        self._y_base: str = "A"

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(6)

        header_row = QHBoxLayout()
        title = QLabel("LIVE PLOT")
        title.setProperty("role", "section")
        header_row.addWidget(title)
        header_row.addStretch()

        self._pts_lbl = QLabel("Ready")
        self._pts_lbl.setProperty("role", "muted")
        header_row.addWidget(self._pts_lbl)
        root.addLayout(header_row)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setMinimumHeight(280)
        self._plot_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._style_plot()
        root.addWidget(self._plot_widget, stretch=1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

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
        pw.showGrid(x=True, y=True, alpha=0.15)
        axis_pen = pg.mkPen(color=theme.PLOT_AXIS, width=1)
        for axis_name in ("bottom", "left"):
            ax = pw.getAxis(axis_name)
            ax.setPen(axis_pen)
            ax.setTextPen(pg.mkPen(theme.TEXT_SECONDARY))
            ax.setStyle(tickLength=-8)
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

        x_name, x_base, y_name, y_base = _AXIS_CONFIG.get(
            config.measurement_type, ("X", "V", "Y", "A")
        )
        self._x_name = x_name
        self._x_base = x_base
        self._y_name = y_name
        self._y_base = y_base

        # X scale: pre-computed from the known sweep voltage range
        x_max = self._sweep_x_range(config)
        self._x_scale, x_unit = _select_si(x_max, x_base)
        self._plot_widget.setLabel("bottom", f"{x_name} ({x_unit})")

        # Y scale: initial estimate from compliance; will refine as data arrives
        y_est = self._compliance_estimate(config)
        self._y_scale, y_unit = _select_si(y_est, y_base)
        self._y_max_abs = 0.0
        self._plot_widget.setLabel("left", f"{y_name} ({y_unit})")

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
        """Append a raw SI data point and update the live plot."""
        if curve_id not in self._data:
            self._data[curve_id] = ([], [])
            color = theme.PLOT_COLORS[curve_id % len(theme.PLOT_COLORS)]
            pen = pg.mkPen(color=color, width=2)
            self._curves[curve_id] = self._plot_widget.plot(
                [], [],
                pen=pen,
                symbol="o",
                symbolSize=5,
                symbolBrush=pg.mkBrush(color),
                symbolPen=None,
            )

        xs, ys = self._data[curve_id]
        xs.append(x)
        ys.append(y)

        # Rescale Y axis if a new maximum requires a different prefix
        abs_y = abs(y)
        if abs_y > self._y_max_abs:
            self._y_max_abs = abs_y
            new_scale, new_unit = _select_si(abs_y, self._y_base)
            if new_scale != self._y_scale:
                self._y_scale = new_scale
                self._plot_widget.setLabel("left", f"{self._y_name} ({new_unit})")
                self._redraw_all()   # redraw every curve with the new scale
                self._tick_progress()
                return               # _redraw_all already updated this curve

        self._curves[curve_id].setData(
            np.array(xs) * self._x_scale,
            np.array(ys) * self._y_scale,
        )
        self._tick_progress()

    def _redraw_all(self):
        """Redraw every curve with the current x/y scale factors."""
        for cid, (xs, ys) in self._data.items():
            if cid in self._curves:
                self._curves[cid].setData(
                    np.array(xs) * self._x_scale,
                    np.array(ys) * self._y_scale,
                )

    def _tick_progress(self):
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
        self._y_max_abs = 0.0
        self._x_scale = 1.0
        self._y_scale = 1.0
        self._progress.setValue(0)
        self._pts_lbl.setText("Ready")
        self._pts_lbl.setStyleSheet("")

    @property
    def has_data(self) -> bool:
        return bool(self._data)

    @property
    def current_result_data(self) -> dict[int, tuple[list, list]]:
        """Return {curve_id: (x_SI_list, y_SI_list)} — always raw SI units."""
        return {cid: (list(xs), list(ys)) for cid, (xs, ys) in self._data.items()}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sweep_x_range(config: SweepConfig) -> float:
        """Maximum absolute X value for the sweep (used to pre-select X prefix)."""
        if isinstance(config, TransferConfig):
            return max(abs(config.vgs_start), abs(config.vgs_stop))
        if isinstance(config, OutputConfig):
            return max(abs(config.vds_start), abs(config.vds_stop))
        if isinstance(config, ResistorConfig):
            return max(abs(config.v_start), abs(config.v_stop))
        return 1.0

    @staticmethod
    def _compliance_estimate(config: SweepConfig) -> float:
        """Initial Y-scale estimate from compliance (refined once real data arrives)."""
        if isinstance(config, ResistorConfig):
            return config.compliance_A
        return config.compliance_drain_A
