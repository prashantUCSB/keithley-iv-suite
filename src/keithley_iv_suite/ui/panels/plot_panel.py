"""3-tab IV plot with Forced/Sensed toggle, style toolbar, and draggable annotations."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QColorDialog, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from .. import theme
from ...measurements.sweep_config import (
    MeasurementType, OutputConfig, ResistorConfig, SweepConfig, TransferConfig,
)

pg.setConfigOptions(antialias=True, foreground=theme.TEXT_SECONDARY, background=theme.PLOT_BG)

# ── SI prefix helpers ────────────────────────────────────────────────────────

_SI_PREFIXES: list[tuple[float, str]] = [
    (1e15, "f"), (1e12, "p"), (1e9, "n"), (1e6, "µ"), (1e3, "m"),
    (1.0, ""), (1e-3, "k"),
]

_AXIS_CONFIG: dict[MeasurementType, tuple[str, str, str, str]] = {
    MeasurementType.NMOS_TRANSFER: ("Vgs", "V", "Id", "A"),
    MeasurementType.NMOS_OUTPUT:   ("Vds", "V", "Id", "A"),
    MeasurementType.RESISTOR_IV:   ("V",   "V", "I",  "A"),
}

_TAB3_TITLES = {
    MeasurementType.RESISTOR_IV:   "Residuals",
    MeasurementType.NMOS_TRANSFER: "gm",
    MeasurementType.NMOS_OUTPUT:   "gd",
}

_LINE_STYLES = {
    "Solid":   Qt.PenStyle.SolidLine,
    "Dash":    Qt.PenStyle.DashLine,
    "Dot":     Qt.PenStyle.DotLine,
    "DashDot": Qt.PenStyle.DashDotLine,
    "None":    None,
}

_MARKERS = {
    "Circle":   "o",
    "Square":   "s",
    "Triangle": "t",
    "Star":     "star",
    "Diamond":  "d",
    "None":     None,
}


def _select_si(mag: float, base_unit: str) -> tuple[float, str]:
    if mag > 0.0:
        for scale, prefix in _SI_PREFIXES:
            if 1.0 <= mag * scale < 1000.0:
                return scale, f"{prefix}{base_unit}"
    return 1.0, base_unit


def _fmt_si(value: float, base_unit: str) -> str:
    scale, unit = _select_si(abs(value), base_unit)
    return f"{value * scale:.4g} {unit}"


def _annot(html_body: str) -> str:
    return (
        f'<div style="background:rgba(0,0,0,0.65);padding:5px 7px;'
        f'border-radius:4px;border:1px solid {theme.BORDER};">'
        f'<span style="color:{theme.AMBER};font-size:9pt;font-family:monospace;">'
        f"{html_body}</span></div>"
    )


# ── Draggable annotation ─────────────────────────────────────────────────────

class DraggableText(pg.TextItem):
    """TextItem that can be click-dragged anywhere on the plot canvas."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable, True)
        self._drag_start = None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        ev.accept()
        # Move in parent (ViewBox) coordinates
        new_pos = self.mapToParent(ev.pos()) - self.mapToParent(ev.lastPos()) + self.pos()
        self.setPos(new_pos)

    def mouseReleaseEvent(self, ev):
        ev.accept()


# ── Per-curve style ──────────────────────────────────────────────────────────

@dataclass
class CurveStyle:
    color: str = theme.PLOT_COLORS[0]
    line_style: str = "Solid"    # key into _LINE_STYLES
    marker: str = "Circle"       # key into _MARKERS
    marker_size: int = 5
    line_width: int = 2


# ── Plot panel ───────────────────────────────────────────────────────────────

class PlotPanel(QWidget):
    """
    3-tab live IV plot with Forced / Sensed V / Readback toggle,
    always-visible style toolbar, and click-to-edit curve styling.

    Data stored internally
    ----------------------
    _data_forced   {curve_id: ([x_forced], [y])}   commanded setpoints
    _data_sensed   {curve_id: ([x_sensed], [y])}   SMU-readback voltages
    """

    export_requested = pyqtSignal()
    params_updated   = pyqtSignal(dict)

    # View modes
    _MODE_FORCED  = 0
    _MODE_SENSED  = 1
    _MODE_READBK  = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_forced: dict[int, tuple[list, list]] = {}
        self._data_sensed: dict[int, tuple[list, list]] = {}
        self._curves: dict[int, pg.PlotDataItem] = {}
        self._styles: dict[int, CurveStyle] = {}

        self._config: SweepConfig | None = None
        self._total_pts = 0
        self._received_pts = 0
        self._view_mode = self._MODE_FORCED

        self._x_scale: float = 1.0
        self._y_scale: float = 1.0
        self._y_max_abs: float = 0.0
        self._x_name = "X";  self._x_base = "V"
        self._y_name = "Y";  self._y_base = "A"

        self._selected_cid: int | None = None

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(4)

        # ── header + toggle row ──────────────────────────────────────────
        top_row = QHBoxLayout()
        hdr = QLabel("LIVE PLOT"); hdr.setProperty("role", "section")
        top_row.addWidget(hdr)
        top_row.addStretch()

        self._pts_lbl = QLabel("Ready"); self._pts_lbl.setProperty("role", "muted")
        top_row.addWidget(self._pts_lbl)
        root.addLayout(top_row)

        toggle_row = QHBoxLayout(); toggle_row.setSpacing(4)
        self._toggle_btns: list[QPushButton] = []
        for idx, lbl in enumerate(("Forced V", "Sensed V", "Readback")):
            b = QPushButton(lbl)
            b.setCheckable(True)
            b.setFixedHeight(24)
            b.clicked.connect(lambda checked, i=idx: self._set_view_mode(i))
            self._toggle_btns.append(b)
            toggle_row.addWidget(b)
        self._toggle_btns[0].setChecked(True)
        toggle_row.addStretch()
        root.addLayout(toggle_row)

        # ── 3-tab plot area ──────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._pw1 = self._make_pw()   # Tab 1 — live linear
        self._pw2 = self._make_pw()   # Tab 2 — log scale
        self._pw3 = self._make_pw()   # Tab 3 — analysis
        self._tabs.addTab(self._pw1, "Linear")
        self._tabs.addTab(self._pw2, "Log Scale")
        self._tabs.addTab(self._pw3, "Analysis")
        self._tabs.setMinimumHeight(260)
        self._tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._tabs, stretch=1)

        # ── progress ────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100); self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

        # ── equation / params text (never clips — lives outside the viewport)
        self._eq_lbl = QLabel("")
        self._eq_lbl.setStyleSheet(
            f"color:{theme.AMBER}; font-size:9pt; font-family:monospace;"
            f" background:{theme.BG_DEEP}; padding:4px 6px;"
            f" border:1px solid {theme.BORDER}; border-radius:3px;"
        )
        self._eq_lbl.setWordWrap(True)
        self._eq_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._eq_lbl)

        # ── style toolbar ────────────────────────────────────────────────
        style_box = QGroupBox("Curve Style  (click a curve to select)")
        style_layout = QHBoxLayout(style_box)
        style_layout.setSpacing(6)
        style_layout.setContentsMargins(6, 4, 6, 4)

        self._color_btn = QPushButton("  Color  ")
        self._color_btn.setFixedHeight(24)
        self._color_btn.clicked.connect(self._pick_color)
        style_layout.addWidget(self._color_btn)

        style_layout.addWidget(QLabel("Line:"))
        self._line_combo = QComboBox()
        self._line_combo.addItems(list(_LINE_STYLES.keys()))
        self._line_combo.setFixedWidth(80)
        self._line_combo.currentTextChanged.connect(self._apply_style_line)
        style_layout.addWidget(self._line_combo)

        style_layout.addWidget(QLabel("Marker:"))
        self._marker_combo = QComboBox()
        self._marker_combo.addItems(list(_MARKERS.keys()))
        self._marker_combo.setFixedWidth(80)
        self._marker_combo.currentTextChanged.connect(self._apply_style_marker)
        style_layout.addWidget(self._marker_combo)

        style_layout.addWidget(QLabel("Size:"))
        self._marker_size = QSpinBox()
        self._marker_size.setRange(1, 20); self._marker_size.setValue(5)
        self._marker_size.setFixedWidth(50)
        self._marker_size.valueChanged.connect(self._apply_style_size)
        style_layout.addWidget(self._marker_size)

        style_layout.addStretch()
        root.addWidget(style_box)

        # ── action buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        for text, slot in (
            ("Export CSV",   self.export_requested.emit),
            ("Export PNG",   self._export_png),
            ("Clear",        self.clear),
            ("⤢ Autoscale", self._autoscale_current),
        ):
            b = QPushButton(text); b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        root.addLayout(btn_row)

    def _make_pw(self) -> pg.PlotWidget:
        pw = pg.PlotWidget()
        pw.setBackground(theme.PLOT_BG)
        pw.showGrid(x=True, y=True, alpha=0.15)
        axis_pen = pg.mkPen(color=theme.PLOT_AXIS, width=1)
        for side in ("bottom", "left"):
            ax = pw.getAxis(side)
            ax.setPen(axis_pen)
            ax.setTextPen(pg.mkPen(theme.TEXT_SECONDARY))
            ax.setStyle(tickLength=-8)
        return pw

    def _autoscale_current(self):
        [self._pw1, self._pw2, self._pw3][self._tabs.currentIndex()].autoRange()

    # Back-compat for main_window menu action
    @property
    def _plot_widget(self) -> pg.PlotWidget:
        return self._pw1

    # ── View-mode toggle ─────────────────────────────────────────────────

    def _set_view_mode(self, mode: int):
        self._view_mode = mode
        for i, b in enumerate(self._toggle_btns):
            b.setChecked(i == mode)
        self._redraw_pw1()
        x_lbl = self._axis_x_label()
        self._pw1.setLabel("bottom", x_lbl)
        self._pw2.setLabel("bottom", x_lbl)

    def _active_data(self) -> dict[int, tuple[list, list]]:
        """Return the data dict for the current view mode."""
        if self._view_mode == self._MODE_FORCED:
            return self._data_forced
        return self._data_sensed   # both Sensed and Readback use sensed V

    def _axis_x_label(self) -> str:
        _, x_unit = _select_si(self._x_scale_inv(), self._x_base)
        suffix = {
            self._MODE_FORCED: "",
            self._MODE_SENSED: " (sensed)",
            self._MODE_READBK: " (readback)",
        }[self._view_mode]
        return f"{self._x_name}{suffix} ({x_unit})"

    def _x_scale_inv(self) -> float:
        """Return max |x| from active data, or 1.0 if no data."""
        all_x = [x for xs, _ in self._active_data().values() for x in xs]
        return max((abs(v) for v in all_x), default=1.0)

    # ── Public API ────────────────────────────────────────────────────────

    def prepare(self, config: SweepConfig, total_points: int = 0):
        self.clear()
        self._config = config
        self._total_pts = total_points

        x_name, x_base, y_name, y_base = _AXIS_CONFIG.get(
            config.measurement_type, ("X", "V", "Y", "A")
        )
        self._x_name, self._x_base = x_name, x_base
        self._y_name, self._y_base = y_name, y_base

        x_max = self._sweep_x_range(config)
        self._x_scale, x_unit = _select_si(x_max, x_base)
        y_est = self._compliance_estimate(config)
        self._y_scale, y_unit = _select_si(y_est, y_base)
        self._y_max_abs = 0.0

        for pw in (self._pw1, self._pw2, self._pw3):
            label = config.label or config.measurement_type.value
            pw.setTitle(
                f'<span style="color:{theme.AMBER};font-weight:600;">{label}</span>',
                size="11pt",
            )
        self._pw1.setLabel("bottom", f"{x_name} ({x_unit})")
        self._pw1.setLabel("left",   f"{y_name} ({y_unit})")
        self._pw2.setLabel("bottom", f"{x_name} ({x_unit})")
        self._pw2.setLabel("left",   f"|{y_name}| (A)")
        self._tabs.setTabText(2, _TAB3_TITLES.get(config.measurement_type, "Analysis"))

        if total_points > 0:
            self._progress.setRange(0, total_points)
            self._progress.setValue(0)
        self._pts_lbl.setText("0 pts")
        self._eq_lbl.setText("")

    def append_point(self, v_forced: float, i_meas: float, v_sensed: float, curve_id: int = 0):
        """Store raw SI point and update Tab 1 live."""
        # ── store both data sources ───────────────────────────────────
        if curve_id not in self._data_forced:
            self._data_forced[curve_id] = ([], [])
            self._data_sensed[curve_id] = ([], [])
            style = CurveStyle(
                color=theme.PLOT_COLORS[curve_id % len(theme.PLOT_COLORS)]
            )
            self._styles[curve_id] = style
            curve = self._make_curve(style)
            self._curves[curve_id] = curve

        self._data_forced[curve_id][0].append(v_forced)
        self._data_forced[curve_id][1].append(i_meas)
        self._data_sensed[curve_id][0].append(v_sensed)
        self._data_sensed[curve_id][1].append(i_meas)

        # ── update Y scale ────────────────────────────────────────────
        abs_y = abs(i_meas)
        if abs_y > self._y_max_abs:
            self._y_max_abs = abs_y
            new_scale, new_unit = _select_si(abs_y, self._y_base)
            if new_scale != self._y_scale:
                self._y_scale = new_scale
                self._pw1.setLabel("left", f"{self._y_name} ({new_unit})")
                self._redraw_pw1()
                self._tick(); return

        # ── update this curve on Tab 1 ────────────────────────────────
        active = self._active_data()
        xs, ys = active[curve_id]
        self._curves[curve_id].setData(
            np.array(xs) * self._x_scale,
            np.array(ys) * self._y_scale,
        )
        self._tick()

    def _make_curve(self, style: CurveStyle) -> pg.PlotDataItem:
        pen = self._make_pen(style)
        sym = _MARKERS.get(style.marker)
        curve = self._pw1.plot(
            [], [],
            pen=pen,
            symbol=sym,
            symbolSize=style.marker_size,
            symbolBrush=pg.mkBrush(style.color) if sym else None,
            symbolPen=None,
        )
        curve.sigClicked.connect(lambda c, pts: self._on_curve_clicked(
            next((cid for cid, cv in self._curves.items() if cv is c), None)
        ))
        return curve

    def _make_pen(self, style: CurveStyle) -> pg.mkPen | None:
        ls = _LINE_STYLES.get(style.line_style)
        if ls is None:
            return None
        return pg.mkPen(color=style.color, width=style.line_width, style=ls)

    def _redraw_pw1(self):
        active = self._active_data()
        for cid, (xs, ys) in active.items():
            if cid in self._curves:
                self._curves[cid].setData(
                    np.array(xs) * self._x_scale,
                    np.array(ys) * self._y_scale,
                )

    def _tick(self):
        self._received_pts += 1
        self._pts_lbl.setText(f"{self._received_pts} pts")
        if self._total_pts > 0:
            self._progress.setValue(self._received_pts)

    def update_progress(self, step: int, total: int):
        self._progress.setRange(0, total); self._progress.setValue(step)
        self._pts_lbl.setText(f"{step}/{total} pts")

    def mark_done(self):
        self._pts_lbl.setText(f"{self._received_pts} pts ✓")
        if self._total_pts > 0:
            self._progress.setValue(self._total_pts)
        if self._config and self._data_forced:
            try:
                self._compute_analysis()
            except Exception as exc:
                import logging as _log
                _log.getLogger(__name__).warning("Post-sweep analysis failed: %s", exc)

    def mark_error(self, msg: str):
        self._pts_lbl.setText(f"Error: {msg}")
        self._pts_lbl.setStyleSheet(f"color:{theme.ERROR};")

    def clear(self):
        for pw in (self._pw1, self._pw2, self._pw3):
            pw.clear(); pw.setLogMode(y=False)
        self._curves.clear()
        self._data_forced.clear(); self._data_sensed.clear()
        self._styles.clear()
        self._received_pts = 0; self._y_max_abs = 0.0
        self._x_scale = 1.0;    self._y_scale = 1.0
        self._progress.setValue(0)
        self._pts_lbl.setText("Ready"); self._pts_lbl.setStyleSheet("")
        self._eq_lbl.setText("")
        self._selected_cid = None
        self._update_toolbar_from_selection()

    @property
    def has_data(self) -> bool:
        return bool(self._data_forced)

    @property
    def current_result_data(self) -> dict[int, tuple[list, list]]:
        """Raw SI forced-V data (base units, A/V) — used by CSV exporter."""
        return {cid: (list(xs), list(ys))
                for cid, (xs, ys) in self._data_forced.items()}

    @property
    def current_sensed_data(self) -> dict[int, tuple[list, list]]:
        """Raw SI sensed-V data."""
        return {cid: (list(xs), list(ys))
                for cid, (xs, ys) in self._data_sensed.items()}

    # ── Style toolbar ─────────────────────────────────────────────────────

    def _on_curve_clicked(self, cid: int | None):
        if cid is None:
            return
        self._selected_cid = cid
        # Highlight selected curve
        for c_id, curve in self._curves.items():
            style = self._styles.get(c_id, CurveStyle())
            pen = self._make_pen(style)
            if pen and c_id == cid:
                pen.setWidth(style.line_width + 1)
            curve.setPen(pen)
        self._update_toolbar_from_selection()

    def _update_toolbar_from_selection(self):
        if self._selected_cid is None or self._selected_cid not in self._styles:
            self._color_btn.setStyleSheet("")
            return
        s = self._styles[self._selected_cid]
        self._color_btn.setStyleSheet(
            f"background:{s.color}; color:{'#000' if QColor(s.color).lightness() > 128 else '#fff'};"
        )
        self._line_combo.blockSignals(True)
        self._line_combo.setCurrentText(s.line_style)
        self._line_combo.blockSignals(False)
        self._marker_combo.blockSignals(True)
        self._marker_combo.setCurrentText(s.marker)
        self._marker_combo.blockSignals(False)
        self._marker_size.blockSignals(True)
        self._marker_size.setValue(s.marker_size)
        self._marker_size.blockSignals(False)

    def _pick_color(self):
        if self._selected_cid is None:
            return
        style = self._styles[self._selected_cid]
        initial = QColor(style.color)
        color = QColorDialog.getColor(initial, self, "Choose Curve Color")
        if color.isValid():
            style.color = color.name()
            self._apply_style_to_curve(self._selected_cid)
            self._update_toolbar_from_selection()

    def _apply_style_line(self, text: str):
        if self._selected_cid is None:
            return
        self._styles[self._selected_cid].line_style = text
        self._apply_style_to_curve(self._selected_cid)

    def _apply_style_marker(self, text: str):
        if self._selected_cid is None:
            return
        self._styles[self._selected_cid].marker = text
        self._apply_style_to_curve(self._selected_cid)

    def _apply_style_size(self, value: int):
        if self._selected_cid is None:
            return
        self._styles[self._selected_cid].marker_size = value
        self._apply_style_to_curve(self._selected_cid)

    def _apply_style_to_curve(self, cid: int):
        if cid not in self._curves:
            return
        style = self._styles[cid]
        curve = self._curves[cid]
        pen = self._make_pen(style)
        sym = _MARKERS.get(style.marker)
        curve.setPen(pen)
        curve.setSymbol(sym)
        curve.setSymbolSize(style.marker_size)
        curve.setSymbolBrush(pg.mkBrush(style.color) if sym else None)

    # ── Post-sweep analysis ───────────────────────────────────────────────

    def _compute_analysis(self):
        mt = self._config.measurement_type
        if   mt == MeasurementType.RESISTOR_IV:   self._resistor_analysis()
        elif mt == MeasurementType.NMOS_TRANSFER:  self._transfer_analysis()
        elif mt == MeasurementType.NMOS_OUTPUT:    self._output_analysis()

    # ── Resistor ─────────────────────────────────────────────────────────

    def _resistor_analysis(self):
        # Use active (Forced or Sensed) data for fit
        active = self._active_data()
        v_all = np.concatenate([np.array(xs) for xs, _ in active.values()])
        i_all = np.concatenate([np.array(ys) for _, ys in active.values()])
        if len(v_all) < 2:
            return

        m, b = np.polyfit(v_all, i_all, 1)
        if abs(m) < 1e-30:
            return
        R = 1.0 / m
        i_pred = m * v_all + b
        ss_res = float(np.sum((i_all - i_pred) ** 2))
        ss_tot = float(np.sum((i_all - i_all.mean()) ** 2))
        r_sq   = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        # ── extrapolated fit on Tab 1 ────────────────────────────────
        pad   = (v_all.max() - v_all.min()) * 0.20
        v_ext = np.linspace(v_all.min() - pad, v_all.max() + pad, 400)
        i_ext = m * v_ext + b
        fit_color = theme.AMBER
        self._pw1.plot(
            v_ext * self._x_scale, i_ext * self._y_scale,
            pen=pg.mkPen(fit_color, width=2, style=Qt.PenStyle.DashLine),
        )

        # ── equation as DraggableText on Tab 1 ───────────────────────
        _, x_unit = _select_si(float(np.abs(v_all).max()), self._x_base)
        _, y_unit = _select_si(float(np.abs(i_all).max()), self._y_base)
        m_disp = m * (1.0 / self._x_scale) * self._y_scale   # slope in display units
        b_disp = b * self._y_scale
        eq_html = (
            f"y = {m_disp:.4g} x"
            + (f" + {b_disp:.4g}" if b_disp >= 0 else f" − {abs(b_disp):.4g}")
            + f"<br>R = {_fmt_si(R, 'Ω')}"
            + f"<br>R² = {r_sq:.6f}"
        )
        ann = DraggableText(html=_annot(eq_html), anchor=(0.0, 1.0))
        self._pw1.addItem(ann)
        ann.setPos(float(v_ext[20]) * self._x_scale,
                   float(i_ext.max()) * self._y_scale)

        # Equation also shown in the text box below the plot (never clips)
        std_res = float(np.std(i_all - i_pred))
        self._eq_lbl.setText(
            f"I = V / {_fmt_si(R, 'Ω')}  +  {_fmt_si(b, self._y_base)}"
            f"     R = {_fmt_si(R, 'Ω')}"
            f"     R² = {r_sq:.6f}"
            f"     σ = {_fmt_si(std_res, self._y_base)}"
        )

        # ── Tab 2: log |I| ──────────────────────────────────────────
        self._pw2.setLogMode(y=True)
        self._pw2.setLabel("left", "|I| (A)")
        for cid, (xs, ys) in active.items():
            v = np.array(xs); i_abs = np.abs(np.array(ys))
            mask = i_abs > 0
            if not mask.any():
                continue
            color = self._styles.get(cid, CurveStyle()).color
            self._pw2.plot(v[mask] * self._x_scale, i_abs[mask],
                           pen=pg.mkPen(color, width=2))

        # ── Tab 3: residuals ────────────────────────────────────────
        residuals = i_all - i_pred
        res_scale, res_unit = _select_si(float(np.abs(residuals).max()), self._y_base)
        self._pw3.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw3.setLabel("left", f"ΔI ({res_unit})")
        self._pw3.addLine(y=0, pen=pg.mkPen(theme.TEXT_MUTED, width=1,
                                             style=Qt.PenStyle.DashLine))
        self._pw3.plot(
            v_all * self._x_scale, residuals * res_scale,
            pen=None, symbol="o", symbolSize=5,
            symbolBrush=pg.mkBrush(theme.PLOT_COLORS[0]), symbolPen=None,
        )
        res_ann = DraggableText(
            html=_annot(f"σ = {_fmt_si(std_res, self._y_base)}<br>R² = {r_sq:.6f}"),
            anchor=(0.0, 1.0),
        )
        self._pw3.addItem(res_ann)
        res_ann.setPos(float(v_all.min()) * self._x_scale,
                       float((residuals * res_scale).max()))

        self.params_updated.emit({
            "R": R, "R_sq": r_sq, "sigma_residual": std_res,
            "slope": float(m), "intercept": float(b),
        })

    # ── nMOS Transfer ─────────────────────────────────────────────────────

    def _transfer_analysis(self):
        if 0 not in self._data_forced:
            return
        active = self._active_data()
        vgs = np.array(active[0][0])
        id_ = np.array(active[0][1])
        if len(vgs) < 4:
            return

        gm     = np.gradient(id_, vgs)
        gm_pk  = float(gm.max())
        pk_idx = int(np.argmax(gm))
        vgs_gm = float(vgs[pk_idx])

        Vth = float("nan")
        try:
            hw = max(3, len(vgs) // 8)
            sl = slice(max(0, pk_idx - hw), min(len(vgs), pk_idx + hw + 1))
            cf = np.polyfit(vgs[sl], np.sqrt(np.maximum(id_[sl], 0.0)), 1)
            if abs(cf[0]) > 0:
                Vth = float(-cf[1] / cf[0])
        except Exception:
            pass

        _, x_unit = _select_si(float(np.abs(vgs).max()), self._x_base)

        # Tab 1 — Vth marker + annotation
        if not np.isnan(Vth):
            self._pw1.addItem(pg.InfiniteLine(
                pos=Vth * self._x_scale, angle=90,
                pen=pg.mkPen(theme.ERROR, width=1.5, style=Qt.PenStyle.DashLine),
                label=f"Vth ≈ {Vth:.3f} V",
                labelOpts={"color": theme.ERROR, "position": 0.85,
                           "font": QFont("monospace", 8)},
            ))
        body = f"gm_pk = {_fmt_si(gm_pk, 'S')}<br>at Vgs = {vgs_gm:.3g} V"
        if not np.isnan(Vth):
            body += f"<br>Vth ≈ {Vth:.3f} V"
        ann = DraggableText(html=_annot(body), anchor=(0.0, 1.0))
        self._pw1.addItem(ann)
        ann.setPos(float(vgs[0]) * self._x_scale, float(id_.max()) * self._y_scale)

        # Equation text box
        parts = [f"gm_pk = {_fmt_si(gm_pk, 'S')}"]
        if not np.isnan(Vth):
            parts.append(f"Vth ≈ {Vth:.3f} V")
        self._eq_lbl.setText("     ".join(parts))

        # Tab 2 — log |Id|
        self._pw2.setLogMode(y=True)
        self._pw2.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw2.setLabel("left",   "|Id| (A)")
        mask = id_ > 0
        if mask.any():
            color = self._styles.get(0, CurveStyle()).color
            self._pw2.plot(vgs[mask] * self._x_scale, id_[mask],
                           pen=pg.mkPen(color, width=2))
        if not np.isnan(Vth):
            self._pw2.addItem(pg.InfiniteLine(
                pos=Vth * self._x_scale, angle=90,
                pen=pg.mkPen(theme.ERROR, width=1.5, style=Qt.PenStyle.DashLine),
                label=f"Vth ≈ {Vth:.3f} V",
                labelOpts={"color": theme.ERROR, "position": 0.85,
                           "font": QFont("monospace", 8)},
            ))

        # Tab 3 — gm
        gm_scale, gm_unit = _select_si(float(np.abs(gm).max()), "S")
        self._pw3.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw3.setLabel("left",   f"gm ({gm_unit})")
        self._pw3.plot(vgs * self._x_scale, gm * gm_scale,
                       pen=pg.mkPen(theme.AMBER, width=2))
        gm_ann = DraggableText(
            html=_annot(f"gm_pk = {_fmt_si(gm_pk, 'S')}<br>"
                        f"at Vgs = {vgs_gm:.3g} V"),
            anchor=(0.0, 1.0),
        )
        self._pw3.addItem(gm_ann)
        gm_ann.setPos(float(vgs[0]) * self._x_scale, float((gm * gm_scale).max()))

        self.params_updated.emit({"gm_pk": gm_pk, "Vth": Vth, "vgs_at_gm_pk": vgs_gm})

    # ── nMOS Output ───────────────────────────────────────────────────────

    def _output_analysis(self):
        if not self._data_forced:
            return
        active = self._active_data()
        x_max = max(float(np.abs(np.array(xs)).max()) for xs, _ in active.values())
        _, x_unit = _select_si(x_max, self._x_base)

        # Tab 2 — log |Id|
        self._pw2.setLogMode(y=True)
        self._pw2.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw2.setLabel("left",   "|Id| (A)")
        for cid, (xs, ys) in active.items():
            vds = np.array(xs); i_abs = np.abs(np.array(ys))
            mask = i_abs > 0
            if not mask.any():
                continue
            color = self._styles.get(cid, CurveStyle()).color
            self._pw2.plot(vds[mask] * self._x_scale, i_abs[mask],
                           pen=pg.mkPen(color, width=2))

        # Tab 3 — gd per curve
        gd_data: list[tuple[np.ndarray, np.ndarray, int]] = []
        for cid, (xs, ys) in active.items():
            if len(xs) < 3:
                continue
            vds = np.array(xs); id_ = np.array(ys)
            gd_data.append((vds, np.gradient(id_, vds), cid))

        if not gd_data:
            return
        gd_max = max(float(np.abs(gd).max()) for _, gd, _ in gd_data)
        gd_scale, gd_unit = _select_si(gd_max, "S")
        self._pw3.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw3.setLabel("left",   f"gd ({gd_unit})")
        for vds, gd, cid in gd_data:
            color = self._styles.get(cid, CurveStyle()).color
            self._pw3.plot(vds * self._x_scale, gd * gd_scale,
                           pen=pg.mkPen(color, width=2))

        self._eq_lbl.setText(f"gd_max = {_fmt_si(gd_max, 'S')}")
        self.params_updated.emit({"gd_max": gd_max})

    # ── PNG export ────────────────────────────────────────────────────────

    def _export_png(self):
        idx      = self._tabs.currentIndex()
        pw       = [self._pw1, self._pw2, self._pw3][idx]
        tab_name = self._tabs.tabText(idx).replace(" ", "_").replace("/", "-")
        path, _  = QFileDialog.getSaveFileName(
            self, "Export Plot as PNG",
            str(Path.home() / f"iv_plot_{tab_name}.png"),
            "PNG Images (*.png);;All Files (*)",
        )
        if not path:
            return
        try:
            from pyqtgraph.exporters import ImageExporter
            ImageExporter(pw.plotItem).export(path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _sweep_x_range(config: SweepConfig) -> float:
        if isinstance(config, TransferConfig):
            return max(abs(config.vgs_start), abs(config.vgs_stop))
        if isinstance(config, OutputConfig):
            return max(abs(config.vds_start), abs(config.vds_stop))
        if isinstance(config, ResistorConfig):
            return max(abs(config.v_start), abs(config.v_stop))
        return 1.0

    @staticmethod
    def _compliance_estimate(config: SweepConfig) -> float:
        if isinstance(config, ResistorConfig):
            return config.compliance_A
        return config.compliance_drain_A
