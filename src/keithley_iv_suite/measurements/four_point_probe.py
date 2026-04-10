"""Collinear four-point probe sheet-resistance measurement.

Probe numbering (Valdes 1954 / Smits 1958 convention):
    [1]  I+  outer current probe
    [2]  V+  inner voltage probe
    [3]  V−  inner voltage probe
    [4]  I−  outer current probe

Wiring to SMUs:
    i_smu  — forces current:  Hi → probe 1 (I+),  Lo → probe 4 (I−)
    v_smu  — voltmeter:        Hi → probe 2 (V+),  Lo → probe 3 (V−)

Sheet resistance formula (Valdes 1954):
    Rs = (π / ln 2) × (V / I) × F_correction
       = 4.5324 × R_transfer × F_correction    [Ω/□]

where R_transfer = dV/dI is the transfer resistance obtained by linear
regression of the measured V vs I data, and F_correction accounts for
finite sample dimensions (Smits 1958).

Measurement procedure:
    1. Sweep current symmetrically (−I_max → +I_max).
    2. Record V_sense at each step.
    3. Fit V vs I → slope = R_transfer.
    4. Compute Rs from the formula above.
    5. If thickness is provided: ρ = Rs × t   [Ω·m]

The symmetric sweep cancels thermoelectric voltages (Seebeck offsets)
that would otherwise add a constant offset to V.  The linear fit also
provides an R² quality metric.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Optional

import numpy as np

from ..instruments.smu_base import SMUBase
from .sweep_config import FourPointProbeConfig

log = logging.getLogger(__name__)

# Rs = C4PP × R_transfer   (semi-infinite thin film, collinear equally-spaced probes)
_C4PP = np.pi / np.log(2)   # ≈ 4.5324

_EPSILON = 1e-30


def run_four_point_probe(
    config: FourPointProbeConfig,
    i_smu: SMUBase,
    v_smu: SMUBase,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float, float, int], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """Execute a four-point probe sheet-resistance measurement.

    Parameters
    ----------
    config      : FourPointProbeConfig
    i_smu       : current-source SMU  (Hi → probe 1 / I+,  Lo → probe 4 / I−)
    v_smu       : voltmeter SMU       (Hi → probe 2 / V+,  Lo → probe 3 / V−)
    progress_cb : called with (step, total)
    data_cb     : called with (i_forced, v_sense, v_sense, curve_id=0)
                  x-axis = forced current (A), y-axis = measured voltage (V)
    abort_flag  : list[bool]; set [0]=True to abort early

    Returns
    -------
    dict
        i_forced   : np.ndarray  — commanded current values (A)
        v_sense    : np.ndarray  — inner-probe voltage (V)
        R_transfer : float       — fitted slope dV/dI (Ω)
        Rs         : float       — sheet resistance (Ω/□)
        rho        : float | nan — resistivity ρ = Rs × t (Ω·m); NaN if no thickness
        R_sq       : float       — R² of the V vs I linear fit
        config     : FourPointProbeConfig
    """
    if abort_flag is None:
        abort_flag = [False]

    i_list = config.i_list()
    n_pts  = len(i_list)

    # ── Configure current source (outer probes) ────────────────────────────
    i_smu.reset()
    i_smu.configure_current_source(
        compliance_voltage=config.compliance_V,
        current_range=config.source_range_A,
        nplc=config.nplc,
        source_delay_s=config.source_delay_s,
    )
    i_smu.set_current(i_list[0])
    i_smu.output_on()
    time.sleep(config.settling_delay_s * 2)

    # ── Configure voltmeter (inner probes) ────────────────────────────────
    v_smu.reset()
    v_smu.configure_voltmeter(
        compliance_voltage=config.compliance_V,
        sense_range_v=config.sense_range_V,
        nplc=config.nplc,
        source_delay_s=config.source_delay_s,
    )
    v_smu.output_on()
    time.sleep(config.settling_delay_s)

    i_f_data: list[float] = []
    v_s_data: list[float] = []

    log.info(
        "4PP sweep: I %.2e→%.2e A (%d pts), s=%.3f mm, F=%.4f, Vlim=%.1f V",
        config.i_start, config.i_stop, n_pts,
        config.probe_spacing_m * 1e3, config.correction_F, config.compliance_V,
    )

    try:
        for idx, i_cmd in enumerate(i_list):
            if abort_flag[0]:
                log.info("4PP sweep aborted at step %d/%d", idx, n_pts)
                break

            i_smu.set_current(i_cmd)
            time.sleep(config.settling_delay_s)

            _i_actual, _v_ismu = i_smu.measure_iv()   # actual I (for reference)
            _i_vmeas,  v_sense = v_smu.measure_iv()   # ≈0 A, sensed voltage

            i_f_data.append(i_cmd)
            v_s_data.append(v_sense)

            if data_cb:
                data_cb(i_cmd, v_sense, v_sense, 0)
            if progress_cb:
                progress_cb(idx + 1, n_pts)

    finally:
        i_smu.set_current(0.0)
        i_smu.output_off()
        v_smu.output_off()

    # ── Post-processing ───────────────────────────────────────────────────
    i_arr = np.array(i_f_data)
    v_arr = np.array(v_s_data)

    R_transfer = float("nan")
    Rs         = float("nan")
    R_sq       = float("nan")

    if len(i_arr) >= 2 and np.ptp(i_arr) > 0:
        coeffs = np.polyfit(i_arr, v_arr, 1)
        m, b   = float(coeffs[0]), float(coeffs[1])
        R_transfer = m

        v_pred = m * i_arr + b
        ss_res = float(np.sum((v_arr - v_pred) ** 2))
        ss_tot = float(np.sum((v_arr - v_arr.mean()) ** 2))
        R_sq   = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        Rs = _C4PP * R_transfer * config.correction_F

    rho = (Rs * config.thickness_m
           if (config.thickness_m is not None and not np.isnan(Rs))
           else float("nan"))

    log.info(
        "4PP result: R_transfer=%.4e Ω  Rs=%.4e Ω/□  ρ=%s  R²=%.6f",
        R_transfer, Rs,
        f"{rho:.4e} Ω·m" if not np.isnan(rho) else "N/A",
        R_sq,
    )

    return {
        "i_forced":   i_arr,
        "v_sense":    v_arr,
        "R_transfer": R_transfer,
        "Rs":         Rs,
        "rho":        rho,
        "R_sq":       R_sq,
        "config":     config,
    }
