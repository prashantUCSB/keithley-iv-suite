"""3-tab IV plot panel: live linear | log scale | analysis (fit/gm/gd)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
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

_TAB3_TITLES = {
    MeasurementType.RESISTOR_IV:   "Residuals",
    MeasurementType.NMOS_TRANSFER: "gm",
    MeasurementType.NMOS_OUTPUT:   "gd",
}

# Ordered largest-scale-factor first; loop finds the first where 1 ≤ |v|×scale < 1000
_SI_PREFIXES: list[tuple[float, str]] = [
    (1e15, "f"),
    (1e12, "p"),
    (1e9,  "n"),
    (1e6,  "µ"),
    (1e3,  "m"),
    (1.0,  ""),
    (1e-3, "k"),
]


def _select_si(mag: float, base_unit: str) -> tuple[float, str]:
    """Return ``(scale, unit_string)`` so that ``|value| * scale`` ∈ [1, 1000).

    Examples::
        _select_si(1.5e-3, "A") → (1e3,  "mA")
        _select_si(3.2e-9, "A") → (1e9,  "nA")
        _select_si(2.5,    "V") → (1.0,  "V" )
        _select_si(0.04,   "V") → (1e3,  "mV")
    """
    if mag > 0.0:
        for scale, prefix in _SI_PREFIXES:
            if 1.0 <= mag * scale < 1000.0:
                return scale, f"{prefix}{base_unit}"
    return 1.0, base_unit


def _fmt_si(value: float, base_unit: str) -> str:
    """Format *value* with SI prefix. E.g. ``(1.23e-3, 'A')`` → ``'1.23 mA'``."""
    scale, unit = _select_si(abs(value), base_unit)
    return f"{value * scale:.4g} {unit}"


def _annot(html_body: str) -> str:
    """Wrap annotation text in a semi-transparent dark box."""
    return (
        f'<div style="background:rgba(0,0,0,0.60);padding:4px;border-radius:3px;">'
        f'<span style="color:{theme.AMBER};font-size:9pt;font-family:monospace;">'
        f"{html_body}</span></div>"
    )


class PlotPanel(QWidget):
    """
    3-tab live IV plot.

    Tab 1 — "Linear"   : live linear-scale plot; fit overlay added at sweep end.
    Tab 2 — "Log Scale": log-Y plot, populated at sweep end.
    Tab 3 — analysis tab (label varies):
              Resistor  → "Residuals"  (measured − fit)
              Transfer  → "gm"         (transconductance vs Vgs)
              Output    → "gd"         (output conductance vs Vds)
    """

    export_requested = pyqtSignal()
    params_updated   = pyqtSignal(dict)   # emitted after mark_done with fit results

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: dict[int, pg.PlotDataItem] = {}
        self._data:   dict[int, tuple[list, list]] = {}   # always raw SI
        self._config: SweepConfig | None = None
        self._total_pts = 0
        self._received_pts = 0

        self._x_scale: float = 1.0
        self._y_scale: float = 1.0
        self._y_max_abs: float = 0.0
        self._x_name = "X";  self._x_base = "V"
        self._y_name = "Y";  self._y_base = "A"

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(4)

        # ── header ──────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl = QLabel("LIVE PLOT"); lbl.setProperty("role", "section")
        hdr.addWidget(lbl); hdr.addStretch()
        self._pts_lbl = QLabel("Ready"); self._pts_lbl.setProperty("role", "muted")
        hdr.addWidget(self._pts_lbl)
        root.addLayout(hdr)

        # ── 3-tab plot area ─────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._pw1 = self._make_pw()   # Tab 1: live linear
        self._pw2 = self._make_pw()   # Tab 2: log scale
        self._pw3 = self._make_pw()   # Tab 3: analysis

        self._tabs.addTab(self._pw1, "Linear")
        self._tabs.addTab(self._pw2, "Log Scale")
        self._tabs.addTab(self._pw3, "Analysis")
        self._tabs.setMinimumHeight(280)
        self._tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._tabs, stretch=1)

        # ── progress ────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100); self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

        # ── extracted params label ───────────────────────────────────────
        self._params_lbl = QLabel("")
        self._params_lbl.setStyleSheet(
            f"color:{theme.AMBER}; font-size:9pt; font-family:monospace;"
        )
        self._params_lbl.setWordWrap(True)
        root.addWidget(self._params_lbl)

        # ── buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        for text, slot in (
            ("Export CSV",      self.export_requested.emit),
            ("Export PNG",      self._export_png),
            ("Clear",           self.clear),
            ("⤢ Autoscale",    self._autoscale_current),
        ):
            b = QPushButton(text); b.clicked.connect(slot); btn_row.addWidget(b)
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

    # Backward-compat: main_window references _plot_widget for autoRange in menu
    @property
    def _plot_widget(self) -> pg.PlotWidget:
        return self._pw1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

        # Tab 1 labels
        self._pw1.setLabel("bottom", f"{x_name} ({x_unit})")
        self._pw1.setLabel("left",   f"{y_name} ({y_unit})")
        # Tab 2 labels (log; y always SI until computed)
        self._pw2.setLabel("bottom", f"{x_name} ({x_unit})")
        self._pw2.setLabel("left",   f"|{y_name}| (A)")
        # Tab 3 label
        tab3 = _TAB3_TITLES.get(config.measurement_type, "Analysis")
        self._tabs.setTabText(2, tab3)

        label = config.label or config.measurement_type.value
        title = f'<span style="color:{theme.AMBER};font-weight:600;">{label}</span>'
        for pw in (self._pw1, self._pw2, self._pw3):
            pw.setTitle(title, size="11pt")

        if total_points > 0:
            self._progress.setRange(0, total_points)
            self._progress.setValue(0)
        self._pts_lbl.setText("0 pts")
        self._params_lbl.setText("")

    def append_point(self, x: float, y: float, curve_id: int = 0):
        if curve_id not in self._data:
            self._data[curve_id] = ([], [])
            color = theme.PLOT_COLORS[curve_id % len(theme.PLOT_COLORS)]
            self._curves[curve_id] = self._pw1.plot(
                [], [], pen=pg.mkPen(color, width=2),
                symbol="o", symbolSize=5,
                symbolBrush=pg.mkBrush(color), symbolPen=None,
            )

        xs, ys = self._data[curve_id]
        xs.append(x); ys.append(y)

        abs_y = abs(y)
        if abs_y > self._y_max_abs:
            self._y_max_abs = abs_y
            new_scale, new_unit = _select_si(abs_y, self._y_base)
            if new_scale != self._y_scale:
                self._y_scale = new_scale
                self._pw1.setLabel("left", f"{self._y_name} ({new_unit})")
                self._redraw_pw1()
                self._tick(); return

        self._curves[curve_id].setData(
            np.array(xs) * self._x_scale,
            np.array(ys) * self._y_scale,
        )
        self._tick()

    def _redraw_pw1(self):
        for cid, (xs, ys) in self._data.items():
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
        if self._config and self._data:
            try:
                self._compute_analysis()
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Post-sweep analysis failed: %s", exc)

    def mark_error(self, msg: str):
        self._pts_lbl.setText(f"Error: {msg}")
        self._pts_lbl.setStyleSheet(f"color:{theme.ERROR};")

    def clear(self):
        for pw in (self._pw1, self._pw2, self._pw3):
            pw.clear()
            pw.setLogMode(y=False)
        self._curves.clear(); self._data.clear()
        self._received_pts = 0; self._y_max_abs = 0.0
        self._x_scale = 1.0;   self._y_scale = 1.0
        self._progress.setValue(0)
        self._pts_lbl.setText("Ready"); self._pts_lbl.setStyleSheet("")
        self._params_lbl.setText("")

    @property
    def has_data(self) -> bool:
        return bool(self._data)

    @property
    def current_result_data(self) -> dict[int, tuple[list, list]]:
        """Raw SI values — always in base units (A, V) regardless of display scale."""
        return {cid: (list(xs), list(ys)) for cid, (xs, ys) in self._data.items()}

    # ------------------------------------------------------------------
    # Post-sweep analysis
    # ------------------------------------------------------------------

    def _compute_analysis(self):
        mt = self._config.measurement_type
        if   mt == MeasurementType.RESISTOR_IV:   self._resistor_analysis()
        elif mt == MeasurementType.NMOS_TRANSFER:  self._transfer_analysis()
        elif mt == MeasurementType.NMOS_OUTPUT:    self._output_analysis()

    # ── Resistor ────────────────────────────────────────────────────────

    def _resistor_analysis(self):
        v_all = np.concatenate([np.array(xs) for xs, _ in self._data.values()])
        i_all = np.concatenate([np.array(ys) for _, ys in self._data.values()])
        if len(v_all) < 2:
            return

        # Unconstrained linear fit  I = m·V + b
        m, b = np.polyfit(v_all, i_all, 1)
        if abs(m) < 1e-30:
            return
        R = 1.0 / m

        i_pred = m * v_all + b
        ss_res = float(np.sum((i_all - i_pred) ** 2))
        ss_tot = float(np.sum((i_all - i_all.mean()) ** 2))
        r_sq   = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        # ── extrapolated fit line (±20% beyond data) ──────────────────
        pad   = (v_all.max() - v_all.min()) * 0.2
        v_ext = np.linspace(v_all.min() - pad, v_all.max() + pad, 400)
        i_ext = m * v_ext + b

        # ── Tab 1: dashed fit line + equation annotation ───────────────
        self._pw1.plot(
            v_ext * self._x_scale, i_ext * self._y_scale,
            pen=pg.mkPen(theme.AMBER, width=2,
                         style=pg.QtCore.Qt.PenStyle.DashLine),
        )
        eq_lines = (
            f"I = V / {_fmt_si(R, 'Ω')}  +  {_fmt_si(b, self._y_base)}"
            f"<br>R = {_fmt_si(R, 'Ω')}"
            f"<br>R² = {r_sq:.6f}"
        )
        ann = pg.TextItem(html=_annot(eq_lines), anchor=(0.0, 1.0))
        self._pw1.addItem(ann)
        ann.setPos(v_ext[10] * self._x_scale,
                   float(i_ext.max()) * self._y_scale)

        # ── Tab 2: log |I| vs V ────────────────────────────────────────
        self._pw2.setLogMode(y=True)
        self._pw2.setLabel("left", "|I| (A)")
        for cid, (xs, ys) in self._data.items():
            v = np.array(xs); i_abs = np.abs(np.array(ys))
            mask = i_abs > 0
            if not mask.any():
                continue
            color = theme.PLOT_COLORS[cid % len(theme.PLOT_COLORS)]
            self._pw2.plot(v[mask] * self._x_scale, i_abs[mask],
                           pen=pg.mkPen(color, width=2))

        # ── Tab 3: residuals ──────────────────────────────────────────
        residuals  = i_all - i_pred
        res_scale, res_unit = _select_si(float(np.abs(residuals).max()), self._y_base)
        _, x_unit  = _select_si(float(np.abs(v_all).max()), self._x_base)
        self._pw3.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw3.setLabel("left",   f"ΔI ({res_unit})")
        self._pw3.addLine(
            y=0,
            pen=pg.mkPen(theme.TEXT_MUTED, width=1,
                         style=pg.QtCore.Qt.PenStyle.DashLine),
        )
        self._pw3.plot(
            v_all * self._x_scale, residuals * res_scale,
            pen=None, symbol="o", symbolSize=5,
            symbolBrush=pg.mkBrush(theme.PLOT_COLORS[0]), symbolPen=None,
        )
        std_res = float(np.std(residuals))
        res_ann = pg.TextItem(
            html=_annot(f"σ = {_fmt_si(std_res, self._y_base)}<br>R² = {r_sq:.6f}"),
            anchor=(0.0, 1.0),
        )
        self._pw3.addItem(res_ann)
        res_ann.setPos(float(v_all.min()) * self._x_scale,
                       float((residuals * res_scale).max()))

        # ── params label + signal ─────────────────────────────────────
        summary = (f"R = {_fmt_si(R, 'Ω')}    "
                   f"R² = {r_sq:.6f}    "
                   f"σ = {_fmt_si(std_res, self._y_base)}")
        self._params_lbl.setText(summary)
        self.params_updated.emit({
            "R": R, "R_sq": r_sq, "sigma_residual": std_res,
            "slope": float(m), "intercept": float(b),
        })

    # ── nMOS Transfer ───────────────────────────────────────────────────

    def _transfer_analysis(self):
        if 0 not in self._data:
            return
        vgs = np.array(self._data[0][0])
        id_ = np.array(self._data[0][1])
        if len(vgs) < 4:
            return

        # gm = dId / dVgs
        gm      = np.gradient(id_, vgs)
        gm_pk   = float(gm.max())
        pk_idx  = int(np.argmax(gm))
        vgs_gm  = float(vgs[pk_idx])

        # Vth via √Id linear extrapolation near gm peak
        Vth = float("nan")
        try:
            hw  = max(3, len(vgs) // 8)
            sl  = slice(max(0, pk_idx - hw), min(len(vgs), pk_idx + hw + 1))
            cf  = np.polyfit(vgs[sl], np.sqrt(np.maximum(id_[sl], 0.0)), 1)
            if abs(cf[0]) > 0:
                Vth = float(-cf[1] / cf[0])
        except Exception:
            pass

        _, x_unit = _select_si(float(np.abs(vgs).max()), self._x_base)

        # ── Tab 1: Vth marker + annotation ────────────────────────────
        if not np.isnan(Vth):
            vth_line = pg.InfiniteLine(
                pos=Vth * self._x_scale, angle=90,
                pen=pg.mkPen(theme.ERROR, width=1.5,
                             style=pg.QtCore.Qt.PenStyle.DashLine),
                label=f"Vth ≈ {Vth:.3f} V",
                labelOpts={"color": theme.ERROR, "position": 0.85,
                           "font": QFont("monospace", 8)},
            )
            self._pw1.addItem(vth_line)

        body = (f"gm_pk = {_fmt_si(gm_pk, 'S')}<br>"
                f"at Vgs = {vgs_gm * self._x_scale:.3g} {x_unit}")
        if not np.isnan(Vth):
            body += f"<br>Vth ≈ {Vth:.3f} V"
        ann = pg.TextItem(html=_annot(body), anchor=(0.0, 1.0))
        self._pw1.addItem(ann)
        ann.setPos(float(vgs[0]) * self._x_scale,
                   float(id_.max()) * self._y_scale)

        # ── Tab 2: log |Id| vs Vgs ────────────────────────────────────
        self._pw2.setLogMode(y=True)
        self._pw2.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw2.setLabel("left",   "|Id| (A)")
        mask = id_ > 0
        if mask.any():
            self._pw2.plot(vgs[mask] * self._x_scale, id_[mask],
                           pen=pg.mkPen(theme.PLOT_COLORS[0], width=2))
        if not np.isnan(Vth):
            self._pw2.addItem(pg.InfiniteLine(
                pos=Vth * self._x_scale, angle=90,
                pen=pg.mkPen(theme.ERROR, width=1.5,
                             style=pg.QtCore.Qt.PenStyle.DashLine),
                label=f"Vth ≈ {Vth:.3f} V",
                labelOpts={"color": theme.ERROR, "position": 0.85,
                           "font": QFont("monospace", 8)},
            ))

        # ── Tab 3: gm vs Vgs ─────────────────────────────────────────
        gm_scale, gm_unit = _select_si(float(np.abs(gm).max()), "S")
        self._pw3.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw3.setLabel("left",   f"gm ({gm_unit})")
        self._pw3.plot(vgs * self._x_scale, gm * gm_scale,
                       pen=pg.mkPen(theme.AMBER, width=2))
        gm_ann = pg.TextItem(
            html=_annot(f"gm_pk = {_fmt_si(gm_pk, 'S')}<br>"
                        f"at Vgs = {vgs_gm * self._x_scale:.3g} {x_unit}"),
            anchor=(0.0, 1.0),
        )
        self._pw3.addItem(gm_ann)
        gm_ann.setPos(float(vgs[0]) * self._x_scale,
                      float((gm * gm_scale).max()))

        # ── params label + signal ─────────────────────────────────────
        parts = [f"gm_pk = {_fmt_si(gm_pk, 'S')}"]
        if not np.isnan(Vth):
            parts.append(f"Vth ≈ {Vth:.3f} V")
        self._params_lbl.setText("    ".join(parts))
        self.params_updated.emit({"gm_pk": gm_pk, "Vth": Vth,
                                   "vgs_at_gm_pk": vgs_gm})

    # ── nMOS Output ─────────────────────────────────────────────────────

    def _output_analysis(self):
        if not self._data:
            return

        _, x_unit = _select_si(
            max(float(np.abs(np.array(xs)).max()) for xs, _ in self._data.values()),
            self._x_base,
        )

        # ── Tab 2: log |Id| vs Vds, all curves ───────────────────────
        self._pw2.setLogMode(y=True)
        self._pw2.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw2.setLabel("left",   "|Id| (A)")
        for cid, (xs, ys) in self._data.items():
            vds = np.array(xs); i_abs = np.abs(np.array(ys))
            mask = i_abs > 0
            if not mask.any():
                continue
            color = theme.PLOT_COLORS[cid % len(theme.PLOT_COLORS)]
            self._pw2.plot(vds[mask] * self._x_scale, i_abs[mask],
                           pen=pg.mkPen(color, width=2))

        # ── Tab 3: gd = dId/dVds per curve ───────────────────────────
        gd_data: list[tuple[np.ndarray, np.ndarray]] = []
        for xs, ys in self._data.values():
            if len(xs) < 3:
                continue
            vds = np.array(xs); id_ = np.array(ys)
            gd_data.append((vds, np.gradient(id_, vds)))

        if not gd_data:
            return

        gd_max = max(float(np.abs(gd).max()) for _, gd in gd_data)
        gd_scale, gd_unit = _select_si(gd_max, "S")
        self._pw3.setLabel("bottom", f"{self._x_name} ({x_unit})")
        self._pw3.setLabel("left",   f"gd ({gd_unit})")

        for cid, (vds, gd) in enumerate(gd_data):
            color = theme.PLOT_COLORS[cid % len(theme.PLOT_COLORS)]
            self._pw3.plot(vds * self._x_scale, gd * gd_scale,
                           pen=pg.mkPen(color, width=2))

        self._params_lbl.setText(f"gd_max = {_fmt_si(gd_max, 'S')}")
        self.params_updated.emit({"gd_max": gd_max})

    # ------------------------------------------------------------------
    # PNG export
    # ------------------------------------------------------------------

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
            exp = ImageExporter(pw.plotItem)
            exp.export(path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
