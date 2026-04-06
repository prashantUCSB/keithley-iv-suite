"""Three side-by-side live IV plots: Forced V | Sensed V | Analysis."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QColorDialog, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
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

_ANALYSIS_TITLES = {
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

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        ev.accept()
        new_pos = self.mapToParent(ev.pos()) - self.mapToParent(ev.lastPos()) + self.pos()
        self.setPos(new_pos)

    def mouseReleaseEvent(self, ev):
        ev.accept()


# ── Per-curve style ──────────────────────────────────────────────────────────

@dataclass
class CurveStyle:
    color: str = theme.PLOT_COLORS[0]
    line_style: str = "Solid"
    marker: str = "Circle"
    marker_size: int = 5
    line_width: int = 2


# ── Plot panel ───────────────────────────────────────────────────────────────

class PlotPanel(QWidget):
    """
    Three side-by-side live IV plots:
      Left   — I vs V_forced  (live linear)
      Center — I vs V_sensed  (live linear)
      Right  — log |I| live → post-sweep analysis (Residuals / gm / gd)

    All three update in real time as data arrives.  At sweep completion the
    right pane is replaced with the derived analysis for the measurement type.
    """

    export_requested = pyqtSignal()
    params_updated   = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_forced: dict[int, tuple[list, list]] = {}
        self._data_sensed: dict[int, tuple[list, list]] = {}
        self._curves_forced: dict[int, pg.PlotDataItem] = {}
        self._curves_sensed: dict[int, pg.PlotDataItem] = {}
        self._curves_log:    dict[int, pg.PlotDataItem] = {}
        self._styles: dict[int, CurveStyle] = {}

        self._config: SweepConfig | None = None
        self._total_pts = 0
        self._received_pts = 0

        self._x_scale: float = 1.0
        self._y_scale: float = 1.0
        self._y_max_abs: float = 0.0
        self._x_name = "X";  self._x_base = "V"
        self._y_name = "Y";  self._y_base = "A"

        self._selected_cid: int | None = None

        # ── paint throttle (25 Hz max) ────────────────────────────────
        self._dirty = False
        self._paint_timer = QTimer(self)
        self._paint_timer.setInterval(40)          # ms → 25 Hz
        self._paint_timer.timeout.connect(self._flush_paint)

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(4)

        # ── header ───────────────────────────────────────────────────────
        top_row = QHBoxLayout()
        hdr = QLabel("LIVE PLOT"); hdr.setProperty("role", "section")
        top_row.addWidget(hdr)
        top_row.addStretch()
        self._pts_lbl = QLabel("Ready"); self._pts_lbl.setProperty("role", "muted")
        top_row.addWidget(self._pts_lbl)
        root.addLayout(top_row)

        # ── three side-by-side plot widgets ──────────────────────────────
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.setChildrenCollapsible(False)

        self._pw_forced   = self._make_pw()
        self._pw_sensed   = self._make_pw()
        self._pw_analysis = self._make_pw()

        for pw in (self._pw_forced, self._pw_sensed, self._pw_analysis):
            pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._h_splitter.addWidget(pw)

        # Analysis pane starts in log mode showing |I| live
        self._pw_analysis.setLogMode(y=True)
        self._pw_analysis.setLabel("left", "|I| (A)")

        root.addWidget(self._h_splitter, stretch=1)

        # ── progress ─────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100); self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

        # ── equation / params text ────────────────────────────────────────
        self._eq_lbl = QLabel("")
        self._eq_lbl.setStyleSheet(
            f"color:{theme.AMBER}; font-size:{theme.FONT_SIZE_SMALL}pt;"
            f" font-family:monospace; background:{theme.BG_DEEP}; padding:4px 6px;"
            f" border:1px solid {theme.BORDER}; border-radius:3px;"
        )
        self._eq_lbl.setWordWrap(True)
        self._eq_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._eq_lbl)

        # ── style toolbar ─────────────────────────────────────────────────
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

        # ── action buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        for text, slot in (
            ("Export CSV",   self.export_requested.emit),
            ("Export PNG",   self._export_png),
            ("Clear",        self.clear),
            ("⤢ Autoscale", self._autoscale_all),
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

    def _autoscale_all(self):
        for pw in (self._pw_forced, self._pw_sensed, self._pw_analysis):
            pw.autoRange()

    # Back-compat for main_window menu action
    @property
    def _plot_widget(self) -> pg.PlotWidget:
        return self._pw_forced

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

        lbl = config.label or config.measurement_type.value
        title_html = f'<span style="color:{theme.AMBER};font-weight:600;">{lbl}</span>'
        for pw, suffix in (
            (self._pw_forced,   " · Forced V"),
            (self._pw_sensed,   " · Sensed V"),
            (self._pw_analysis, " · log |I|"),
        ):
            pw.setTitle(
                title_html
                + f'<span style="color:{theme.TEXT_MUTED};font-size:9pt;">{suffix}</span>',
                size="10pt",
            )

        self._pw_forced.setLabel("bottom", f"{x_name} forced ({x_unit})")
        self._pw_forced.setLabel("left",   f"{y_name} ({y_unit})")
        self._pw_sensed.setLabel("bottom", f"{x_name} sensed ({x_unit})")
        self._pw_sensed.setLabel("left",   f"{y_name} ({y_unit})")
        self._pw_analysis.setLabel("bottom", f"{x_name} sensed ({x_unit})")
        self._pw_analysis.setLabel("left",   f"|{y_name}| (A)")
        self._pw_analysis.setLogMode(y=True)

        if total_points > 0:
            self._progress.setRange(0, total_points)
            self._progress.setValue(0)
        self._pts_lbl.setText("0 pts")
        self._eq_lbl.setText("")

    def append_point(self, v_forced: float, i_meas: float, v_sensed: float, curve_id: int = 0):
        """Store raw SI point; actual repaints are batched at 25 Hz by _flush_paint."""
        # ── allocate new curve set ────────────────────────────────────
        if curve_id not in self._data_forced:
            self._data_forced[curve_id] = ([], [])
            self._data_sensed[curve_id] = ([], [])
            style = CurveStyle(
                color=theme.PLOT_COLORS[curve_id % len(theme.PLOT_COLORS)]
            )
            self._styles[curve_id] = style
            self._make_curves(curve_id, style)

        self._data_forced[curve_id][0].append(v_forced)
        self._data_forced[curve_id][1].append(i_meas)
        self._data_sensed[curve_id][0].append(v_sensed)
        self._data_sensed[curve_id][1].append(i_meas)

        # ── track Y scale — update axis label only, no repaint ───────
        abs_y = abs(i_meas)
        if abs_y > self._y_max_abs:
            self._y_max_abs = abs_y
            new_scale, new_unit = _select_si(abs_y, self._y_base)
            if new_scale != self._y_scale:
                self._y_scale = new_scale
                self._pw_forced.setLabel("left", f"{self._y_name} ({new_unit})")
                self._pw_sensed.setLabel("left", f"{self._y_name} ({new_unit})")

        self._dirty = True
        self._tick()
        if not self._paint_timer.isActive():
            self._paint_timer.start()

    def _flush_paint(self):
        """Repaint all three live plots — called by the 25 Hz timer."""
        if not self._dirty:
            self._paint_timer.stop()
            return
        self._dirty = False

        for cid, (xf, yf) in self._data_forced.items():
            if cid in self._curves_forced:
                self._curves_forced[cid].setData(
                    np.array(xf) * self._x_scale,
                    np.array(yf) * self._y_scale,
                )
        for cid, (xs, ys) in self._data_sensed.items():
            if cid in self._curves_sensed:
                self._curves_sensed[cid].setData(
                    np.array(xs) * self._x_scale,
                    np.array(ys) * self._y_scale,
                )
            if cid in self._curves_log:
                i_abs = np.abs(np.array(ys))
                mask = i_abs > 0
                if mask.any():
                    self._curves_log[cid].setData(
                        np.array(xs)[mask] * self._x_scale,
                        i_abs[mask],
                    )

    def _make_curves(self, cid: int, style: CurveStyle):
        """Create linear curves on pw_forced / pw_sensed and log curve on pw_analysis."""
        pen = self._make_pen(style)
        sym = _MARKERS.get(style.marker)
        brush = pg.mkBrush(style.color) if sym else None

        for curves_dict, pw in (
            (self._curves_forced, self._pw_forced),
            (self._curves_sensed, self._pw_sensed),
        ):
            c = pw.plot([], [], pen=pen, symbol=sym,
                        symbolSize=style.marker_size,
                        symbolBrush=brush, symbolPen=None)
            c.sigClicked.connect(lambda _c, _pts, _id=cid: self._on_curve_clicked(_id))
            curves_dict[cid] = c

        lc = self._pw_analysis.plot([], [], pen=pg.mkPen(style.color, width=2))
        self._curves_log[cid] = lc

    def _make_pen(self, style: CurveStyle):
        ls = _LINE_STYLES.get(style.line_style)
        if ls is None:
            return None
        return pg.mkPen(color=style.color, width=style.line_width, style=ls)

    def _tick(self):
        self._received_pts += 1
        self._pts_lbl.setText(f"{self._received_pts} pts")
        if self._total_pts > 0:
            self._progress.setValue(self._received_pts)

    def update_progress(self, step: int, total: int):
        self._progress.setRange(0, total); self._progress.setValue(step)
        self._pts_lbl.setText(f"{step}/{total} pts")

    def mark_done(self):
        self._flush_paint()          # ensure every point is drawn before analysis
        self._paint_timer.stop()
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
        self._paint_timer.stop()
        self._dirty = False
        for pw in (self._pw_forced, self._pw_sensed, self._pw_analysis):
            pw.clear(); pw.setLogMode(y=False)
        self._curves_forced.clear()
        self._curves_sensed.clear()
        self._curves_log.clear()
        self._data_forced.clear()
        self._data_sensed.clear()
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
        """Raw SI forced-V data — used by CSV exporter."""
        return {cid: (list(xs), list(ys))
                for cid, (xs, ys) in self._data_forced.items()}

    @property
    def current_sensed_data(self) -> dict[int, tuple[list, list]]:
        """Raw SI sensed-V data."""
        return {cid: (list(xs), list(ys))
                for cid, (xs, ys) in self._data_sensed.items()}

    # ── Style toolbar ──────────────────────────────────────────────────────

    def _on_curve_clicked(self, cid: int | None):
        if cid is None:
            return
        self._selected_cid = cid
        for curves_dict in (self._curves_forced, self._curves_sensed):
            for c_id, curve in curves_dict.items():
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
        color = QColorDialog.getColor(QColor(style.color), self, "Choose Curve Color")
        if color.isValid():
            style.color = color.name()
            self._apply_style_to_curve(self._selected_cid)
            self._update_toolbar_from_selection()

    def _apply_style_line(self, text: str):
        if self._selected_cid is None: return
        self._styles[self._selected_cid].line_style = text
        self._apply_style_to_curve(self._selected_cid)

    def _apply_style_marker(self, text: str):
        if self._selected_cid is None: return
        self._styles[self._selected_cid].marker = text
        self._apply_style_to_curve(self._selected_cid)

    def _apply_style_size(self, value: int):
        if self._selected_cid is None: return
        self._styles[self._selected_cid].marker_size = value
        self._apply_style_to_curve(self._selected_cid)

    def _apply_style_to_curve(self, cid: int):
        style = self._styles.get(cid)
        if not style:
            return
        pen = self._make_pen(style)
        sym = _MARKERS.get(style.marker)
        brush = pg.mkBrush(style.color) if sym else None
        for curves_dict in (self._curves_forced, self._curves_sensed):
            if cid in curves_dict:
                c = curves_dict[cid]
                c.setPen(pen)
                c.setSymbol(sym)
                c.setSymbolSize(style.marker_size)
                c.setSymbolBrush(brush)
        if cid in self._curves_log:
            self._curves_log[cid].setPen(pg.mkPen(style.color, width=2))

    # ── Post-sweep analysis ────────────────────────────────────────────────

    def _compute_analysis(self):
        """Replace log|I| live view with the measurement-type-specific analysis."""
        self._pw_analysis.clear()
        self._pw_analysis.setLogMode(y=False)
        self._curves_log.clear()
        mt = self._config.measurement_type
        if   mt == MeasurementType.RESISTOR_IV:   self._resistor_analysis()
        elif mt == MeasurementType.NMOS_TRANSFER:  self._transfer_analysis()
        elif mt == MeasurementType.NMOS_OUTPUT:    self._output_analysis()
        title_str = _ANALYSIS_TITLES.get(mt, "Analysis")
        lbl = self._config.label or mt.value
        self._pw_analysis.setTitle(
            f'<span style="color:{theme.AMBER};font-weight:600;">{lbl}</span>'
            f'<span style="color:{theme.TEXT_MUTED};font-size:9pt;"> · {title_str}</span>',
            size="10pt",
        )

    # ── Resistor ──────────────────────────────────────────────────────────

    def _resistor_analysis(self):
        v_f_all = np.concatenate([np.array(xs) for xs, _ in self._data_forced.values()])
        i_all   = np.concatenate([np.array(ys) for _, ys in self._data_forced.values()])
        if len(v_f_all) < 2:
            return

        m, b = np.polyfit(v_f_all, i_all, 1)
        if abs(m) < 1e-30:
            return
        R = 1.0 / m
        i_pred  = m * v_f_all + b
        ss_res  = float(np.sum((i_all - i_pred) ** 2))
        ss_tot  = float(np.sum((i_all - i_all.mean()) ** 2))
        r_sq    = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        std_res = float(np.std(i_all - i_pred))

        pad     = (v_f_all.max() - v_f_all.min()) * 0.20
        fit_pen = pg.mkPen(theme.AMBER, width=2, style=Qt.PenStyle.DashLine)

        # Fit line on both linear panes (using their respective X data)
        for pw, data_dict in (
            (self._pw_forced, self._data_forced),
            (self._pw_sensed, self._data_sensed),
        ):
            v_d = np.concatenate([np.array(xs) for xs, _ in data_dict.values()])
            i_d = np.concatenate([np.array(ys) for _, ys in data_dict.values()])
            if len(v_d) < 2:
                continue
            m_d, b_d = np.polyfit(v_d, i_d, 1)
            v_e = np.linspace(v_d.min() - pad, v_d.max() + pad, 400)
            pw.plot(v_e * self._x_scale, (m_d * v_e + b_d) * self._y_scale, pen=fit_pen)

        # Annotation on forced pane
        v_ext  = np.linspace(v_f_all.min() - pad, v_f_all.max() + pad, 400)
        i_ext  = m * v_ext + b
        m_disp = m * (1.0 / self._x_scale) * self._y_scale
        b_disp = b * self._y_scale
        eq_html = (
            f"y = {m_disp:.4g} x"
            + (f" + {b_disp:.4g}" if b_disp >= 0 else f" − {abs(b_disp):.4g}")
            + f"<br>R = {_fmt_si(R, 'Ω')}"
            + f"<br>R² = {r_sq:.6f}"
        )
        ann = DraggableText(html=_annot(eq_html), anchor=(0.0, 1.0))
        self._pw_forced.addItem(ann)
        ann.setPos(float(v_ext[20]) * self._x_scale, float(i_ext.max()) * self._y_scale)

        # Analysis pane: residuals
        residuals = i_all - i_pred
        res_max   = float(np.abs(residuals).max()) if len(residuals) else 1.0
        res_scale, res_unit = _select_si(res_max, self._y_base)
        _, x_unit = _select_si(float(np.abs(v_f_all).max()), self._x_base)
        self._pw_analysis.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw_analysis.setLabel("left",   f"ΔI ({res_unit})")
        self._pw_analysis.addLine(y=0, pen=pg.mkPen(theme.TEXT_MUTED, width=1,
                                                     style=Qt.PenStyle.DashLine))
        self._pw_analysis.plot(
            v_f_all * self._x_scale, residuals * res_scale,
            pen=None, symbol="o", symbolSize=5,
            symbolBrush=pg.mkBrush(theme.PLOT_COLORS[0]), symbolPen=None,
        )
        res_ann = DraggableText(
            html=_annot(f"σ = {_fmt_si(std_res, self._y_base)}<br>R² = {r_sq:.6f}"),
            anchor=(0.0, 1.0),
        )
        self._pw_analysis.addItem(res_ann)
        if len(residuals):
            res_ann.setPos(float(v_f_all.min()) * self._x_scale,
                           float((residuals * res_scale).max()))

        self._eq_lbl.setText(
            f"I = V / {_fmt_si(R, 'Ω')}  +  {_fmt_si(b, self._y_base)}"
            f"     R = {_fmt_si(R, 'Ω')}"
            f"     R² = {r_sq:.6f}"
            f"     σ = {_fmt_si(std_res, self._y_base)}"
        )
        self.params_updated.emit({
            "R": R, "R_sq": r_sq, "sigma_residual": std_res,
            "slope": float(m), "intercept": float(b),
        })

    # ── nMOS Transfer ─────────────────────────────────────────────────────

    def _transfer_analysis(self):
        if 0 not in self._data_forced:
            return
        vgs_f = np.array(self._data_forced[0][0])
        id_f  = np.array(self._data_forced[0][1])
        vgs_s = np.array(self._data_sensed[0][0])
        if len(vgs_f) < 4:
            return

        gm     = np.gradient(id_f, vgs_f)
        gm_pk  = float(gm.max())
        pk_idx = int(np.argmax(gm))
        vgs_gm = float(vgs_f[pk_idx])

        Vth = float("nan")
        try:
            hw = max(3, len(vgs_f) // 8)
            sl = slice(max(0, pk_idx - hw), min(len(vgs_f), pk_idx + hw + 1))
            cf = np.polyfit(vgs_f[sl], np.sqrt(np.maximum(id_f[sl], 0.0)), 1)
            if abs(cf[0]) > 0:
                Vth = float(-cf[1] / cf[0])
        except Exception:
            pass

        _, x_unit = _select_si(float(np.abs(vgs_f).max()), self._x_base)
        vth_pen = pg.mkPen(theme.ERROR, width=1.5, style=Qt.PenStyle.DashLine)
        body = f"gm_pk = {_fmt_si(gm_pk, 'S')}<br>at Vgs = {vgs_gm:.3g} V"
        if not np.isnan(Vth):
            body += f"<br>Vth ≈ {Vth:.3f} V"

        # Vth markers on both linear panes
        for pw in (self._pw_forced, self._pw_sensed):
            if not np.isnan(Vth):
                pw.addItem(pg.InfiniteLine(
                    pos=Vth * self._x_scale, angle=90, pen=vth_pen,
                    label=f"Vth ≈ {Vth:.3f} V",
                    labelOpts={"color": theme.ERROR, "position": 0.85,
                               "font": QFont("monospace", 8)},
                ))
        ann = DraggableText(html=_annot(body), anchor=(0.0, 1.0))
        self._pw_forced.addItem(ann)
        ann.setPos(float(vgs_f[0]) * self._x_scale, float(id_f.max()) * self._y_scale)

        # Analysis pane: gm vs Vgs
        gm_scale, gm_unit = _select_si(float(np.abs(gm).max()), "S")
        self._pw_analysis.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw_analysis.setLabel("left",   f"gm ({gm_unit})")
        self._pw_analysis.plot(vgs_f * self._x_scale, gm * gm_scale,
                               pen=pg.mkPen(theme.AMBER, width=2))
        if not np.isnan(Vth):
            self._pw_analysis.addItem(pg.InfiniteLine(
                pos=Vth * self._x_scale, angle=90, pen=vth_pen,
                label=f"Vth ≈ {Vth:.3f} V",
                labelOpts={"color": theme.ERROR, "position": 0.85,
                           "font": QFont("monospace", 8)},
            ))
        gm_ann = DraggableText(
            html=_annot(f"gm_pk = {_fmt_si(gm_pk, 'S')}<br>at Vgs = {vgs_gm:.3g} V"),
            anchor=(0.0, 1.0),
        )
        self._pw_analysis.addItem(gm_ann)
        gm_ann.setPos(float(vgs_f[0]) * self._x_scale, float((gm * gm_scale).max()))

        parts = [f"gm_pk = {_fmt_si(gm_pk, 'S')}"]
        if not np.isnan(Vth):
            parts.append(f"Vth ≈ {Vth:.3f} V")
        self._eq_lbl.setText("     ".join(parts))
        self.params_updated.emit({"gm_pk": gm_pk, "Vth": Vth, "vgs_at_gm_pk": vgs_gm})

    # ── nMOS Output ───────────────────────────────────────────────────────

    def _output_analysis(self):
        if not self._data_forced:
            return
        x_max = max(float(np.abs(np.array(xs)).max()) for xs, _ in self._data_forced.values())
        _, x_unit = _select_si(x_max, self._x_base)

        gd_data: list[tuple[np.ndarray, np.ndarray, int]] = []
        for cid, (xs, ys) in self._data_forced.items():
            if len(xs) < 3:
                continue
            vds = np.array(xs); id_ = np.array(ys)
            gd_data.append((vds, np.gradient(id_, vds), cid))

        if not gd_data:
            return
        gd_max   = max(float(np.abs(gd).max()) for _, gd, _ in gd_data)
        gd_scale, gd_unit = _select_si(gd_max, "S")
        self._pw_analysis.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw_analysis.setLabel("left",   f"gd ({gd_unit})")
        for vds, gd, cid in gd_data:
            color = self._styles.get(cid, CurveStyle()).color
            self._pw_analysis.plot(vds * self._x_scale, gd * gd_scale,
                                   pen=pg.mkPen(color, width=2))

        self._eq_lbl.setText(f"gd_max = {_fmt_si(gd_max, 'S')}")
        self.params_updated.emit({"gd_max": gd_max})

    # ── PNG export ────────────────────────────────────────────────────────

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plot as PNG",
            str(Path.home() / "iv_plot_forced.png"),
            "PNG Images (*.png);;All Files (*)",
        )
        if not path:
            return
        try:
            from pyqtgraph.exporters import ImageExporter
            ImageExporter(self._pw_forced.plotItem).export(path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _sweep_x_range(config: SweepConfig) -> float:
        if isinstance(config, TransferConfig):
            return max(abs(config.vgs_start), abs(config.vgs_stop), 0.01)
        if isinstance(config, OutputConfig):
            return max(abs(config.vds_start), abs(config.vds_stop), 0.01)
        if isinstance(config, ResistorConfig):
            return max(abs(config.v_start), abs(config.v_stop), 0.01)
        return 1.0

    @staticmethod
    def _compliance_estimate(config: SweepConfig) -> float:
        if isinstance(config, ResistorConfig):
            return config.compliance_A
        return config.compliance_drain_A
