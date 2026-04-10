"""Collinear four-point probe sheet-resistance measurement.

Probe numbering (Valdes 1954 / Smits 1958 convention):
    [1]  Force Hi  outer current probe
    [2]  Sense Hi  inner voltage probe
    [3]  Sense Lo  inner voltage probe
    [4]  Force Lo  outer current probe

Single-SMU algorithm (4-wire Kelvin / RSEN mode):
    A SINGLE current-source SMU is used with 4-wire remote sensing enabled.
    The Force terminals (Hi/Lo) carry current through the outer probes (1, 4).
    The Sense terminals (Hi/Lo) measure voltage at the inner probes (2, 3).

    Wiring to a single SMU (e.g. Keithley 2400 with SYST:RSEN ON):
        Force Hi → probe 1 (outer, I+)
        Sense Hi → probe 2 (inner, V+)
        Sense Lo → probe 3 (inner, V−)
        Force Lo → probe 4 (outer, I−)

Sheet resistance formula (Valdes 1954):
    Rs = (π / ln 2) × (V_sense / I_force) × F_correction
       = 4.5324 × (V / I) × F_correction    [Ω/□]

Measurement procedure:
    1. Enable 4-wire remote sensing on the SMU (SYST:RSEN ON).
    2. Sweep current symmetrically (−I_max → +I_max).
    3. Record V_sense (inner probe voltage) and I_actual at each step.
    4. Compute Rs per-point: Rs_i = (π/ln2) × (V_i / I_i) × F.
    5. Final Rs = mean(Rs_i) over all valid (non-zero I) points.

The symmetric sweep cancels thermoelectric offsets (Seebeck voltages): because
positive and negative current measurements both contribute to the mean, a
constant additive voltage offset cancels in the average.
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

# Rs = C4PP × (V/I)   (semi-infinite thin film, collinear equally-spaced probes)
_C4PP = np.pi / np.log(2)   # ≈ 4.5324

_EPSILON = 1e-12   # minimum |I_actual| to compute V/I ratio safely


def run_four_point_probe(
    config: FourPointProbeConfig,
    i_smu: SMUBase,
    v_smu: Optional[SMUBase] = None,   # not used — kept for API compatibility
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float, float, int], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """Execute a four-point probe sheet-resistance measurement.

    Uses a single SMU in 4-wire (Kelvin) remote-sense mode.  The SMU must
    be wired so that its Force terminals drive the outer probes and its Sense
    terminals are connected to the inner probes:

        Force Hi → probe 1,  Sense Hi → probe 2
        Force Lo → probe 4,  Sense Lo → probe 3

    Parameters
    ----------
    config      : FourPointProbeConfig
    i_smu       : current-source SMU with 4-wire remote sensing (RSEN ON).
    v_smu       : ignored (retained for backward compatibility).
    progress_cb : called with (step, total)
    data_cb     : called with (i_actual, v_sense, v_sense, curve_id=0)
    abort_flag  : list[bool]; set [0]=True to abort early

    Returns
    -------
    dict
        i_forced   : np.ndarray  — commanded current values (A)
        i_actual   : np.ndarray  — measured actual current values (A)
        v_sense    : np.ndarray  — inner-probe voltage (V)
        R_transfer : float       — mean V_sense / I_actual (Ω)
        Rs         : float       — mean sheet resistance (Ω/□)
        rho        : float | nan — resistivity ρ = Rs × t (Ω·m); NaN if no thickness
        R_sq       : float       — R² of the V vs I linear fit (quality metric)
        config     : FourPointProbeConfig
    """
    if abort_flag is None:
        abort_flag = [False]

    i_list = config.i_list()
    n_pts  = len(i_list)

    # ── Configure SMU in 4-wire Kelvin remote-sensing mode ─────────────────
    i_smu.reset()
    i_smu.set_sense_mode(remote=True)   # SYST:RSEN ON — Sense terminals read inner probes
    i_smu.configure_current_source(
        compliance_voltage=config.compliance_V,
        current_range=config.source_range_A,
        nplc=config.nplc,
        source_delay_s=config.source_delay_s,
    )
    i_smu.set_current(i_list[0])
    i_smu.output_on()
    time.sleep(config.settling_delay_s * 2)

    i_f_data: list[float] = []   # commanded current
    i_a_data: list[float] = []   # actual measured current
    v_s_data: list[float] = []   # sense voltage (inner probes via RSEN)

    log.info(
        "4PP sweep: I %.2e→%.2e A (%d pts), F=%.4f, Vlim=%.1f V (RSEN ON)",
        config.i_start, config.i_stop, n_pts,
        config.correction_F, config.compliance_V,
    )

    try:
        for idx, i_cmd in enumerate(i_list):
            if abort_flag[0]:
                log.info("4PP sweep aborted at step %d/%d", idx, n_pts)
                break

            i_smu.set_current(i_cmd)
            time.sleep(config.settling_delay_s)

            # With RSEN ON: measure_iv() → (I_force_actual, V_sense_inner)
            i_actual, v_sense = i_smu.measure_iv()

            i_f_data.append(i_cmd)
            i_a_data.append(i_actual)
            v_s_data.append(v_sense)

            if data_cb:
                data_cb(i_actual, v_sense, v_sense, 0)
            if progress_cb:
                progress_cb(idx + 1, n_pts)

    finally:
        i_smu.set_current(0.0)
        i_smu.output_off()

    # ── Post-processing ──────────────────────────────────────────────────────
    i_f_arr = np.array(i_f_data)
    i_a_arr = np.array(i_a_data)
    v_arr   = np.array(v_s_data)

    R_transfer = float("nan")
    Rs         = float("nan")
    R_sq       = float("nan")

    # Per-point Rs = (π/ln2) × (V_sense / I_actual) × F  — matches user's algorithm
    valid = np.abs(i_a_arr) > _EPSILON
    if np.any(valid):
        Rs_pts     = _C4PP * (v_arr[valid] / i_a_arr[valid]) * config.correction_F
        Rs         = float(np.mean(Rs_pts))
        R_transfer = float(np.mean(v_arr[valid] / i_a_arr[valid]))

    # R² from linear fit on (I_actual, V_sense) — quality/linearity metric
    if len(i_a_arr) >= 2 and np.ptp(i_a_arr) > 0:
        coeffs = np.polyfit(i_a_arr, v_arr, 1)
        m, b   = float(coeffs[0]), float(coeffs[1])
        v_pred = m * i_a_arr + b
        ss_res = float(np.sum((v_arr - v_pred) ** 2))
        ss_tot = float(np.sum((v_arr - v_arr.mean()) ** 2))
        R_sq   = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

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
        "i_forced":   i_f_arr,
        "i_actual":   i_a_arr,
        "v_sense":    v_arr,
        "R_transfer": R_transfer,
        "Rs":         Rs,
        "rho":        rho,
        "R_sq":       R_sq,
        "config":     config,
    }
