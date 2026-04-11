"""Collinear four-point probe sheet-resistance measurement.

Probe numbering (Valdes 1954 / Smits 1958 convention):
    [1]  outer  I+ probe
    [2]  inner  V+ probe
    [3]  inner  V− probe
    [4]  outer  I− probe

Two measurement modes are supported automatically:

Mode A — Two-SMU (recommended when a separate voltmeter instrument is available)
    i_smu forces current via its Force Hi/Lo (outer probes 1 & 4).
    v_smu is configured as a high-impedance voltmeter (0 A source) and
    connected to inner probes 2 & 3 via its Force Hi/Lo.
    No RSEN required.

        i_smu Force Hi → probe 1 (outer, I+)
        i_smu Force Lo → probe 4 (outer, I−)
        v_smu Force Hi → probe 2 (inner, V+)
        v_smu Force Lo → probe 3 (inner, V−)

Mode B — Single-SMU RSEN (when only one instrument is available)
    A SINGLE SMU is used with 4-wire remote sensing (SYST:RSEN ON).
    Force terminals carry current (outer probes); Sense terminals read
    voltage (inner probes).

        i_smu Force Hi → probe 1 (outer, I+)
        i_smu Sense Hi → probe 2 (inner, V+)
        i_smu Sense Lo → probe 3 (inner, V−)
        i_smu Force Lo → probe 4 (outer, I−)

    Mode B is selected when v_smu is None or the same object as i_smu.

Sheet resistance formula (Valdes 1954):
    Rs = (π / ln 2) × (V_sense / I_actual) × F_correction
       = 4.5324 × (V / I) × F_correction    [Ω/□]

Both modes compute Rs per-point using the ACTUAL measured current (not
the commanded setpoint) and then average, matching the working reference
algorithm.
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

_C4PP    = np.pi / np.log(2)   # ≈ 4.5324
_EPSILON = 1e-12                # minimum |I_actual| to compute V/I safely


def run_four_point_probe(
    config: FourPointProbeConfig,
    i_smu: SMUBase,
    v_smu: Optional[SMUBase] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float, float, int], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """Execute a four-point probe sheet-resistance measurement.

    Automatically selects two-SMU mode when *v_smu* is a different object
    from *i_smu*, otherwise falls back to single-SMU RSEN mode.

    Parameters
    ----------
    config      : FourPointProbeConfig
    i_smu       : current-source SMU (always required — outer probes).
    v_smu       : voltmeter SMU (inner probes).  Pass None or the same
                  object as i_smu to use single-SMU RSEN mode.
    progress_cb : called with (step, total)
    data_cb     : called with (i_actual, v_sense, v_sense, curve_id=0)
    abort_flag  : list[bool]; set [0]=True to abort early

    Returns
    -------
    dict with keys: i_forced, i_actual, v_sense, R_transfer, Rs, rho,
                    R_sq, config
    """
    if abort_flag is None:
        abort_flag = [False]

    _use_rsen = (v_smu is None or v_smu is i_smu)
    mode_label = "RSEN single-SMU" if _use_rsen else "two-SMU"

    i_list = config.i_list()
    n_pts  = len(i_list)

    log.info(
        "4PP sweep: %s mode, I %.2e→%.2e A (%d pts), F=%.4f, Vlim=%.1f V",
        mode_label, config.i_start, config.i_stop, n_pts,
        config.correction_F, config.compliance_V,
    )

    # ── Instrument setup ────────────────────────────────────────────────────
    if _use_rsen:
        # Mode B: single SMU, RSEN ON
        i_smu.reset()
        i_smu.set_sense_mode(remote=True)
        # Brief settle — some 2400 firmware performs an internal zeroing step
        # after SYST:RSEN ON that blocks the next VISA write if sent too quickly.
        time.sleep(0.5)
        # Use an explicit sense range instead of AUTO: auto-range on a freshly
        # enabled RSEN path can loop indefinitely and exhaust the VISA timeout.
        _sense_range = config.sense_range_V if config.sense_range_V is not None \
            else config.compliance_V
        i_smu.configure_current_source(
            compliance_voltage=config.compliance_V,
            current_range=config.source_range_A,
            sense_range_v=_sense_range,
            nplc=config.nplc,
            source_delay_s=config.source_delay_s,
        )
        i_smu.set_current(i_list[0])
        i_smu.output_on()
        time.sleep(config.settling_delay_s * 2)

    else:
        # Mode A: two separate SMUs
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

        v_smu.reset()
        v_smu.configure_voltmeter(
            compliance_voltage=config.compliance_V,
            sense_range_v=config.sense_range_V,
            nplc=config.nplc,
            source_delay_s=config.source_delay_s,
        )
        v_smu.output_on()
        time.sleep(config.settling_delay_s)

    # ── Sweep ────────────────────────────────────────────────────────────────
    i_f_data: list[float] = []
    i_a_data: list[float] = []
    v_s_data: list[float] = []

    try:
        for idx, i_cmd in enumerate(i_list):
            if abort_flag[0]:
                log.info("4PP sweep aborted at step %d/%d", idx, n_pts)
                break

            i_smu.set_current(i_cmd)
            time.sleep(config.settling_delay_s)

            if _use_rsen:
                # RSEN ON: measure_iv() returns (I_force_actual, V_sense_inner)
                i_actual, v_sense = i_smu.measure_iv()
            else:
                # Two-SMU: i_smu gives actual current, v_smu gives inner voltage
                i_actual, _v_ismu = i_smu.measure_iv()
                _i_vmeas, v_sense  = v_smu.measure_iv()

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
        if not _use_rsen:
            v_smu.output_off()

    # ── Post-processing ──────────────────────────────────────────────────────
    i_f_arr = np.array(i_f_data)
    i_a_arr = np.array(i_a_data)
    v_arr   = np.array(v_s_data)

    R_transfer = float("nan")
    Rs         = float("nan")
    R_sq       = float("nan")

    # Per-point Rs = (π/ln2) × (V_sense / I_actual) × F
    valid = np.abs(i_a_arr) > _EPSILON
    if np.any(valid):
        Rs_pts     = _C4PP * (v_arr[valid] / i_a_arr[valid]) * config.correction_F
        Rs         = float(np.mean(Rs_pts))
        R_transfer = float(np.mean(v_arr[valid] / i_a_arr[valid]))

    # R² from linear fit — quality/linearity metric
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
        "4PP result (%s): R_transfer=%.4e Ω  Rs=%.4e Ω/□  ρ=%s  R²=%.6f",
        mode_label, R_transfer, Rs,
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
