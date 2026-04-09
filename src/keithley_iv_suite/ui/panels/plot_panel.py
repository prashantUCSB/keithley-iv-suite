"""Live IV plot — single PlotWidget, Forced/Sensed toggle, log scale checkbox."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QRadioButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
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
    Single live IV plot.

    Controls
    --------
    - Forced V / Sensed V radio  — selects which voltage column drives the X axis.
      Can be toggled before or during a sweep.  Both datasets are always stored.
    - Log |I| checkbox           — switches Y axis to log scale live.

    Post-sweep a lightweight overlay is added to the same plot:
      Resistor  → dashed fit line + R / R² annotation
      Transfer  → Vth vertical marker + gm_pk / Vth annotation
      Output    → nothing extra (the family of curves is self-explanatory)
    """

    export_requested = pyqtSignal()
    params_updated   = pyqtSignal(dict)

    _MODE_FORCED = 0
    _MODE_SENSED = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_forced: dict[int, tuple[list, list]] = {}
        self._data_sensed: dict[int, tuple[list, list]] = {}
        self._curves:  dict[int, pg.PlotDataItem] = {}
        self._styles:  dict[int, CurveStyle] = {}

        self._config: SweepConfig | None = None
        self._total_pts = 0
        self._received_pts = 0
        self._view_mode = self._MODE_FORCED

        self._x_scale: float = 1.0
        self._x_unit:  str   = "V"
        self._y_scale: float = 1.0
        self._y_unit:  str   = "A"
        self._y_max_abs: float = 0.0
        self._x_name = "X"
        self._y_name = "Y"
        self._x_base = "V"
        self._y_base = "A"

        self._selected_cid: int | None = None

        # 25 Hz paint throttle — prevents UI freeze during fast sweeps
        self._dirty = False
        self._paint_timer = QTimer(self)
        self._paint_timer.setInterval(40)
        self._paint_timer.timeout.connect(self._flush_paint)

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(4)

        # ── header + controls row ─────────────────────────────────────
        ctrl_row = QHBoxLayout()

        hdr = QLabel("LIVE PLOT")
        hdr.setProperty("role", "section")
        ctrl_row.addWidget(hdr)
        ctrl_row.addSpacing(16)

        # Forced / Sensed V toggle
        axis_lbl = QLabel("X-axis:")
        axis_lbl.setProperty("role", "muted")
        ctrl_row.addWidget(axis_lbl)

        self._forced_rb = QRadioButton("Forced V")
        self._sensed_rb = QRadioButton("Sensed V")
        self._forced_rb.setChecked(True)
        self._forced_rb.setToolTip(
            "Plot commanded voltage on X axis (default for 2-wire measurements)"
        )
        self._sensed_rb.setToolTip(
            "Plot SMU voltage readback on X axis — differs from forced in 4-wire (Kelvin) mode"
        )
        grp = QButtonGroup(self)
        grp.addButton(self._forced_rb, self._MODE_FORCED)
        grp.addButton(self._sensed_rb, self._MODE_SENSED)
        grp.idToggled.connect(self._on_mode_changed)

        ctrl_row.addWidget(self._forced_rb)
        ctrl_row.addWidget(self._sensed_rb)
        ctrl_row.addSpacing(16)

        # Log scale checkbox
        self._log_chk = QCheckBox("Log |I|")
        self._log_chk.setToolTip("Switch Y axis to log scale (shows |current|)")
        self._log_chk.toggled.connect(self._on_log_toggled)
        ctrl_row.addWidget(self._log_chk)

        ctrl_row.addStretch()

        self._pts_lbl = QLabel("Ready")
        self._pts_lbl.setProperty("role", "muted")
        ctrl_row.addWidget(self._pts_lbl)

        root.addLayout(ctrl_row)

        # ── single PlotWidget ─────────────────────────────────────────
        self._pw = pg.PlotWidget()
        self._pw.setBackground(theme.PLOT_BG)
        self._pw.showGrid(x=True, y=True, alpha=0.15)
        axis_pen = pg.mkPen(color=theme.PLOT_AXIS, width=1)
        for side in ("bottom", "left"):
            ax = self._pw.getAxis(side)
            ax.setPen(axis_pen)
            ax.setTextPen(pg.mkPen(theme.TEXT_SECONDARY))
            ax.setStyle(tickLength=-8)
        self._pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._pw, stretch=1)

        # ── progress ─────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

        # ── equation / params label ───────────────────────────────────
        self._eq_lbl = QLabel("")
        self._eq_lbl.setStyleSheet(
            f"color:{theme.AMBER}; font-size:{theme.FONT_SIZE_SMALL}pt;"
            f" font-family:monospace; background:{theme.BG_DEEP}; padding:4px 6px;"
            f" border:1px solid {theme.BORDER}; border-radius:3px;"
        )
        self._eq_lbl.setWordWrap(True)
        self._eq_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._eq_lbl)

        # ── style toolbar ─────────────────────────────────────────────
        style_box = QGroupBox("Curve Style  (click a curve to select)")
        sl = QHBoxLayout(style_box)
        sl.setSpacing(6)
        sl.setContentsMargins(6, 4, 6, 4)

        self._color_btn = QPushButton("  Color  ")
        self._color_btn.setFixedHeight(24)
        self._color_btn.clicked.connect(self._pick_color)
        sl.addWidget(self._color_btn)

        sl.addWidget(QLabel("Line:"))
        self._line_combo = QComboBox()
        self._line_combo.addItems(list(_LINE_STYLES.keys()))
        self._line_combo.setFixedWidth(80)
        self._line_combo.currentTextChanged.connect(self._apply_style_line)
        sl.addWidget(self._line_combo)

        sl.addWidget(QLabel("Marker:"))
        self._marker_combo = QComboBox()
        self._marker_combo.addItems(list(_MARKERS.keys()))
        self._marker_combo.setFixedWidth(80)
        self._marker_combo.currentTextChanged.connect(self._apply_style_marker)
        sl.addWidget(self._marker_combo)

        sl.addWidget(QLabel("Size:"))
        self._marker_size = QSpinBox()
        self._marker_size.setRange(1, 20)
        self._marker_size.setValue(5)
        self._marker_size.setFixedWidth(50)
        self._marker_size.valueChanged.connect(self._apply_style_size)
        sl.addWidget(self._marker_size)

        sl.addStretch()
        root.addWidget(style_box)

        # ── action buttons ────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        for text, slot in (
            ("Export CSV",   self.export_requested.emit),
            ("Export PNG",   self._export_png),
            ("Clear",        self.clear),
            ("⤢ Autoscale", self._autoscale_all),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        root.addLayout(btn_row)

    # ── View mode / log toggle ────────────────────────────────────────────

    def _on_mode_changed(self, btn_id: int, checked: bool):
        if not checked:
            return
        self._view_mode = btn_id
        self._update_x_label()
        self._dirty = True
        self._flush_paint()

    def _on_log_toggled(self, checked: bool):
        self._pw.setLogMode(y=checked)
        if checked:
            self._pw.setLabel("left", f"|{self._y_name}| (A)")
        else:
            self._pw.setLabel("left", f"{self._y_name} ({self._y_unit})")
        self._dirty = True
        self._flush_paint()

    def _update_x_label(self):
        suffix = " (forced)" if self._view_mode == self._MODE_FORCED else " (sensed)"
        self._pw.setLabel("bottom", f"{self._x_name}{suffix} ({self._x_unit})")

    def _active_data(self) -> dict[int, tuple[list, list]]:
        return (self._data_forced if self._view_mode == self._MODE_FORCED
                else self._data_sensed)

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
        self._x_scale, self._x_unit = _select_si(x_max, x_base)
        y_est = self._compliance_estimate(config)
        self._y_scale, self._y_unit = _select_si(y_est, y_base)
        self._y_max_abs = 0.0

        lbl = config.label or config.measurement_type.value
        self._pw.setTitle(
            f'<span style="color:{theme.AMBER};font-weight:600;">{lbl}</span>',
            size="11pt",
        )
        self._update_x_label()
        self._pw.setLabel("left", f"{y_name} ({self._y_unit})")

        # Lock axes to sweep range — prevents pyqtgraph autoRange scroll loop
        # during the live 25 Hz setData calls.  autoRange() is called once in
        # mark_done() for a final fit after the sweep completes.
        vmin, vmax = self._config_v_range(config)
        x_lo = min(vmin, vmax) * self._x_scale
        x_hi = max(vmin, vmax) * self._x_scale
        i_range = y_est * self._y_scale
        self._pw.disableAutoRange()
        self._pw.setXRange(x_lo, x_hi, padding=0.08)
        self._pw.setYRange(-i_range, i_range, padding=0.10)

        if total_points > 0:
            self._progress.setRange(0, total_points)
            self._progress.setValue(0)
        self._pts_lbl.setText("0 pts")
        self._eq_lbl.setText("")

    def append_point(self, v_forced: float, i_meas: float, v_sensed: float,
                     curve_id: int = 0):
        """Store raw SI point; repaints are batched at 25 Hz."""
        if curve_id not in self._data_forced:
            self._data_forced[curve_id] = ([], [])
            self._data_sensed[curve_id] = ([], [])
            style = CurveStyle(
                color=theme.PLOT_COLORS[curve_id % len(theme.PLOT_COLORS)]
            )
            self._styles[curve_id] = style
            self._curves[curve_id] = self._make_curve(curve_id, style)

        self._data_forced[curve_id][0].append(v_forced)
        self._data_forced[curve_id][1].append(i_meas)
        self._data_sensed[curve_id][0].append(v_sensed)
        self._data_sensed[curve_id][1].append(i_meas)

        self._dirty = True
        self._tick()
        if not self._paint_timer.isActive():
            self._paint_timer.start()

    def _make_curve(self, cid: int, style: CurveStyle) -> pg.PlotDataItem:
        pen = self._make_pen(style)
        sym = _MARKERS.get(style.marker)
        c = self._pw.plot(
            [], [],
            pen=pen,
            symbol=sym,
            symbolSize=style.marker_size,
            symbolBrush=pg.mkBrush(style.color) if sym else None,
            symbolPen=None,
        )
        c.sigClicked.connect(lambda _c, _pts, _id=cid: self._on_curve_clicked(_id))
        return c

    def _make_pen(self, style: CurveStyle):
        ls = _LINE_STYLES.get(style.line_style)
        if ls is None:
            return None
        return pg.mkPen(color=style.color, width=style.line_width, style=ls)

    def _flush_paint(self):
        """Batch repaint — called by the 25 Hz timer."""
        if not self._dirty:
            self._paint_timer.stop()
            return
        self._dirty = False
        log_mode = self._log_chk.isChecked()
        for cid, (xs, ys) in self._active_data().items():
            if cid not in self._curves:
                continue
            x_arr = np.array(xs) * self._x_scale
            if log_mode:
                y_abs = np.abs(np.array(ys))
                mask  = y_abs > 0
                self._curves[cid].setData(
                    x_arr[mask]  if mask.any() else np.array([]),
                    y_abs[mask]  if mask.any() else np.array([]),
                )
            else:
                self._curves[cid].setData(x_arr, np.array(ys) * self._y_scale)

    def _tick(self):
        self._received_pts += 1
        self._pts_lbl.setText(f"{self._received_pts} pts")
        if self._total_pts > 0:
            self._progress.setValue(self._received_pts)

    def update_progress(self, step: int, total: int):
        self._progress.setRange(0, total)
        self._progress.setValue(step)
        self._pts_lbl.setText(f"{step}/{total} pts")

    def mark_done(self):
        self._flush_paint()
        self._paint_timer.stop()
        self._pts_lbl.setText(f"{self._received_pts} pts ✓")
        if self._total_pts > 0:
            self._progress.setValue(self._total_pts)
        if self._config and self._data_forced:
            try:
                self._add_overlay()
            except Exception as exc:
                import logging as _log
                _log.getLogger(__name__).warning("Post-sweep overlay failed: %s", exc)
        # One-shot fit to actual data now that the sweep is complete.
        # autoRange() in pyqtgraph does NOT re-enable continuous auto-rescaling —
        # it is a single fit call, so the axes stay stable afterward.
        self._pw.autoRange()

    def mark_error(self, msg: str):
        self._pts_lbl.setText(f"Error: {msg}")
        self._pts_lbl.setStyleSheet(f"color:{theme.ERROR};")

    def clear(self):
        self._paint_timer.stop()
        self._dirty = False
        self._pw.clear()
        self._pw.setLogMode(y=False)
        self._curves.clear()
        self._data_forced.clear()
        self._data_sensed.clear()
        self._styles.clear()
        self._received_pts = 0
        self._y_max_abs    = 0.0
        self._x_scale = 1.0
        self._y_scale = 1.0
        self._progress.setValue(0)
        self._pts_lbl.setText("Ready")
        self._pts_lbl.setStyleSheet("")
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

    # ── Post-sweep overlay (lightweight — no extra PlotWidgets) ───────────

    def _add_overlay(self):
        mt = self._config.measurement_type
        if mt == MeasurementType.RESISTOR_IV:
            self._overlay_resistor()
        elif mt == MeasurementType.NMOS_TRANSFER:
            self._overlay_transfer()
        # Output: family of curves needs no extra annotation

    def _overlay_resistor(self):
        active = self._active_data()
        v_all  = np.concatenate([np.array(xs) for xs, _ in active.values()])
        i_all  = np.concatenate([np.array(ys) for _, ys in active.values()])
        if len(v_all) < 2:
            return
        m, b = np.polyfit(v_all, i_all, 1)
        if abs(m) < 1e-30:
            return
        R      = 1.0 / m
        i_pred = m * v_all + b
        ss_res = float(np.sum((i_all - i_pred) ** 2))
        ss_tot = float(np.sum((i_all - i_all.mean()) ** 2))
        r_sq   = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        # Fit line
        pad   = (v_all.max() - v_all.min()) * 0.15
        v_ext = np.linspace(v_all.min() - pad, v_all.max() + pad, 200)
        self._pw.plot(
            v_ext * self._x_scale,
            (m * v_ext + b) * self._y_scale,
            pen=pg.mkPen(theme.AMBER, width=2, style=Qt.PenStyle.DashLine),
        )

        # Annotation
        ann = DraggableText(
            html=_annot(f"R = {_fmt_si(R, 'Ω')}<br>R² = {r_sq:.6f}"),
            anchor=(0.0, 1.0),
        )
        self._pw.addItem(ann)
        ann.setPos(float(v_ext[10]) * self._x_scale,
                   float((m * v_ext + b).max()) * self._y_scale)

        self._eq_lbl.setText(
            f"R = {_fmt_si(R, 'Ω')}     R² = {r_sq:.6f}"
            f"     σ = {_fmt_si(float(np.std(i_all - i_pred)), self._y_base)}"
        )
        self.params_updated.emit({"R": R, "R_sq": r_sq})

    def _overlay_transfer(self):
        # Always use forced-V for derivative calculations
        if 0 not in self._data_forced:
            return
        vgs_f = np.array(self._data_forced[0][0])
        id_f  = np.array(self._data_forced[0][1])
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

        # Vth vertical line
        if not np.isnan(Vth):
            self._pw.addItem(pg.InfiniteLine(
                pos=Vth * self._x_scale, angle=90,
                pen=pg.mkPen(theme.ERROR, width=1.5, style=Qt.PenStyle.DashLine),
                label=f"Vth ≈ {Vth:.3f} V",
                labelOpts={"color": theme.ERROR, "position": 0.85,
                           "font": QFont("monospace", 8)},
            ))

        # Annotation
        body = f"gm_pk = {_fmt_si(gm_pk, 'S')}<br>at Vgs = {vgs_gm:.3g} V"
        if not np.isnan(Vth):
            body += f"<br>Vth ≈ {Vth:.3f} V"
        ann = DraggableText(html=_annot(body), anchor=(0.0, 1.0))
        self._pw.addItem(ann)
        # Use the display-mode data for annotation position
        active = self._active_data()
        if 0 in active:
            vgs_d, id_d = active[0]
            ann.setPos(float(np.array(vgs_d)[0]) * self._x_scale,
                       float(np.array(id_d).max()) * self._y_scale)

        parts = [f"gm_pk = {_fmt_si(gm_pk, 'S')}"]
        if not np.isnan(Vth):
            parts.append(f"Vth ≈ {Vth:.3f} V")
        self._eq_lbl.setText("     ".join(parts))
        self.params_updated.emit({"gm_pk": gm_pk, "Vth": Vth, "vgs_at_gm_pk": vgs_gm})

    # ── Style toolbar ──────────────────────────────────────────────────────

    def _on_curve_clicked(self, cid: int | None):
        if cid is None:
            return
        self._selected_cid = cid
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
            f"background:{s.color};"
            f" color:{'#000' if QColor(s.color).lightness() > 128 else '#fff'};"
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
        if not style or cid not in self._curves:
            return
        c   = self._curves[cid]
        pen = self._make_pen(style)
        sym = _MARKERS.get(style.marker)
        c.setPen(pen)
        c.setSymbol(sym)
        c.setSymbolSize(style.marker_size)
        c.setSymbolBrush(pg.mkBrush(style.color) if sym else None)

    # ── PNG export ────────────────────────────────────────────────────────

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plot as PNG",
            str(Path.home() / "iv_plot.png"),
            "PNG Images (*.png);;All Files (*)",
        )
        if not path:
            return
        try:
            from pyqtgraph.exporters import ImageExporter
            ImageExporter(self._pw.plotItem).export(path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    # ── Autoscale (back-compat name kept for main_window menu action) ──────

    def _autoscale_all(self):
        self._pw.autoRange()

    @property
    def _plot_widget(self) -> pg.PlotWidget:
        return self._pw

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
    def _config_v_range(config: SweepConfig) -> tuple[float, float]:
        """Return (vmin, vmax) in raw SI (V) for the primary sweep axis."""
        if isinstance(config, TransferConfig):
            return config.vgs_start, config.vgs_stop
        if isinstance(config, OutputConfig):
            return config.vds_start, config.vds_stop
        if isinstance(config, ResistorConfig):
            return config.v_start, config.v_stop
        return -1.0, 1.0

    @staticmethod
    def _compliance_estimate(config: SweepConfig) -> float:
        if isinstance(config, ResistorConfig):
            return config.compliance_A
        return config.compliance_drain_A
