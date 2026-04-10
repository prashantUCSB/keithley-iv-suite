"""CSV export for all measurement result types."""
from __future__ import annotations

import csv
import dataclasses
from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np

from ..measurements.sweep_config import (
    SweepConfig,
    MeasurementType,
)


def default_filename(config: SweepConfig, output_dir: str) -> Path:
    """Return a timestamped default CSV path for *config* inside *output_dir*.

    Example: ``~/Documents/IV_Data/20260410_143522_RESISTOR_IV_run1.csv``
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Use the enum name — already filesystem-safe (e.g. NMOS_TRANSFER)
    mtype_safe = config.measurement_type.name
    if config.label:
        # Keep only alphanumeric, dash, and underscore from the label
        safe_label = "".join(
            c if c.isalnum() or c in ("-", "_") else "_"
            for c in config.label
        ).strip("_")
        filename = f"{ts}_{mtype_safe}_{safe_label}.csv"
    else:
        filename = f"{ts}_{mtype_safe}.csv"
    return Path(output_dir) / filename


def export_csv(
    result: dict,
    path: Union[str, Path],
    config: SweepConfig,
) -> None:
    """Write *result* to a CSV file at *path*.

    The file begins with ``#``-prefixed metadata lines (measurement type,
    timestamp, config parameters) followed by a column-header row and the
    numeric data.

    Parameters
    ----------
    result  : dict returned by the measurement function
    path    : destination file path (created with parents as needed)
    config  : SweepConfig that produced the measurement
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    mtype = config.measurement_type

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        _write_header(writer, config)

        if mtype == MeasurementType.NMOS_TRANSFER:
            _write_transfer(writer, result)
        elif mtype == MeasurementType.NMOS_OUTPUT:
            _write_output(writer, result)
        elif mtype == MeasurementType.RESISTOR_IV:
            _write_resistor(writer, result)
        elif mtype == MeasurementType.VAN_DER_PAUW:
            _write_vdp(writer, result)
        elif mtype == MeasurementType.HALL_BAR:
            _write_hall(writer, result)
        elif mtype == MeasurementType.FOUR_POINT_PROBE:
            _write_4pp(writer, result)
        elif mtype == MeasurementType.GENERIC_4PORT:
            _write_generic4(writer, result)
        else:
            _write_generic(writer, result)


# ── Private helpers ──────────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    return f"{v:.9g}"


def _write_header(writer: csv.writer, config: SweepConfig) -> None:
    """Emit #-prefixed metadata lines at the top of the file."""
    writer.writerow([f"# Keithley IV Suite — {config.measurement_type.value}"])
    writer.writerow([f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    if config.label:
        writer.writerow([f"# Label: {config.label}"])
    for f in dataclasses.fields(config):
        if f.name in ("measurement_type", "assignments"):
            continue
        writer.writerow([f"# {f.name}: {getattr(config, f.name)}"])
    writer.writerow(["#"])


def _write_transfer(writer: csv.writer, result: dict) -> None:
    vgs    = result["vgs"]
    vgs_s  = result.get("vgs_sensed", np.full_like(vgs, float("nan")))
    id_    = result["id"]
    ig     = result["ig"]
    vds    = result["vds_actual"]
    writer.writerow(["vgs_V", "vgs_sensed_V", "id_A", "ig_A", "vds_actual_V"])
    for row in zip(vgs, vgs_s, id_, ig, vds):
        writer.writerow([_fmt(v) for v in row])


def _write_output(writer: csv.writer, result: dict) -> None:
    writer.writerow(["curve_index", "vgs_V", "vds_forced_V", "vds_sensed_V", "id_A", "ig_A"])
    for ci, curve in enumerate(result["curves"]):
        vgs   = curve["vgs"]
        vds_f = curve["vds_forced"]
        vds_s = curve["vds"]
        id_   = curve["id"]
        ig    = curve["ig"]
        for vds_fi, vds_si, id_i, ig_i in zip(vds_f, vds_s, id_, ig):
            writer.writerow([ci, _fmt(vgs), _fmt(vds_fi), _fmt(vds_si), _fmt(id_i), _fmt(ig_i)])


def _write_resistor(writer: csv.writer, result: dict) -> None:
    vf = result["voltage"]
    vs = result.get("voltage_sensed", np.full_like(vf, float("nan")))
    i_ = result["current"]
    r_ = result["resistance"]
    writer.writerow(["voltage_forced_V", "voltage_sensed_V", "current_A", "resistance_ohm"])
    for row in zip(vf, vs, i_, r_):
        writer.writerow([_fmt(v) for v in row])


def _write_vdp(writer: csv.writer, result: dict) -> None:
    r_fit = result.get("R_fit", float("nan"))
    writer.writerow([f"# R_fit_ohm: {r_fit:.6g}"])
    i_ = result["i_forced"]
    v_ = result["v_sense"]
    r_ = result["resistance_per_pt"]
    writer.writerow(["i_forced_A", "v_sense_V", "resistance_per_pt_ohm"])
    for row in zip(i_, v_, r_):
        writer.writerow([_fmt(v) for v in row])


def _write_hall(writer: csv.writer, result: dict) -> None:
    for key in ("R_xx", "R_xy", "n_sheet", "mu_H", "carrier_type"):
        if key in result:
            writer.writerow([f"# {key}: {result[key]}"])
    i_  = result["i_forced"]
    vl  = result["v_long"]
    vh  = result["v_hall"]
    writer.writerow(["i_forced_A", "v_long_V", "v_hall_V"])
    for row in zip(i_, vl, vh):
        writer.writerow([_fmt(v) for v in row])


def _write_4pp(writer: csv.writer, result: dict) -> None:
    for key in ("R_transfer", "Rs", "rho", "R_sq"):
        if key in result:
            val = result[key]
            writer.writerow([f"# {key}: {val:.6g}" if isinstance(val, float) else f"# {key}: {val}"])
    i_forced = result["i_forced"]
    i_actual = result.get("i_actual", np.full_like(i_forced, float("nan")))
    v_ = result["v_sense"]
    writer.writerow(["i_forced_A", "i_actual_A", "v_sense_V"])
    for row in zip(i_forced, i_actual, v_):
        writer.writerow([_fmt(v) for v in row])


def _write_generic4(writer: csv.writer, result: dict) -> None:
    vf = result["v_forced"]
    vs = result["v_sensed"]
    i_ = result["current"]
    writer.writerow(["v_forced_V", "v_sensed_V", "current_A"])
    for row in zip(vf, vs, i_):
        writer.writerow([_fmt(v) for v in row])


def _write_generic(writer: csv.writer, result: dict) -> None:
    """Fallback: write all numpy arrays in the result side by side."""
    arrays = {k: v for k, v in result.items() if isinstance(v, np.ndarray)}
    if not arrays:
        return
    writer.writerow(list(arrays.keys()))
    for row in zip(*arrays.values()):
        writer.writerow([_fmt(v) for v in row])
