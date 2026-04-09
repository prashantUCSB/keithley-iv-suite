"""Hall bar longitudinal + Hall resistance measurement.

i_smu sweeps current from i_start to i_stop.  v_smu acts as a voltmeter
on the transverse (Hall) contacts.

Two curves are emitted per measurement point:
  curve 0 — V_longitudinal (voltage at the current-source terminal) vs I
  curve 1 — V_Hall (voltage measured by the voltmeter SMU)       vs I

Post-sweep fits:
  R_xx  = slope of V_long vs I  (longitudinal, 2-probe, includes contacts)
  R_xy  = slope of V_Hall vs I  (Hall resistance, sign → carrier type)
  n_s   = 1 / (q × |R_xy| × B)   [sheet carrier density, m⁻²]
  µ_H   = |R_xy| / R_sheet         [Hall mobility, m²/Vs]
           where R_sheet is the separate VdP measurement result
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Optional

import numpy as np

from ..instruments.smu_base import SMUBase
from .sweep_config import HallBarConfig

log = logging.getLogger(__name__)

_Q_E = 1.602176634e-19   # elementary charge (C)
_EPSILON = 1e-30


def run_hall_sweep(
    config: HallBarConfig,
    i_smu: SMUBase,
    v_smu: SMUBase,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float, float, int], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """Execute a Hall bar current-sweep measurement.

    Parameters
    ----------
    config      : HallBarConfig
    i_smu       : current source (I+ / I- terminals)
    v_smu       : voltmeter on Hall contacts (V_Hall+ / V_Hall-)
    progress_cb : Called with (step, total); total = 2 × i_points
    data_cb     : Called twice per step:
                    (i_forced, v_long, v_long, 0)   ← longitudinal
                    (i_forced, v_hall, v_hall, 1)   ← Hall
    abort_flag  : list[bool]; set [0]=True to abort

    Returns
    -------
    dict with keys: i_forced, v_long, v_hall,
                    R_xx, R_xy, n_sheet, mu_H (NaN if B=0 or fit fails),
                    config
    """
    if abort_flag is None:
        abort_flag = [False]

    i_list = config.i_list()
    n_pts  = len(i_list)
    total  = n_pts * 2      # each point emits 2 data signals

    # Configure current source
    i_smu.reset()
    i_smu.configure_current_source(compliance_voltage=config.compliance_V)
    i_smu.set_current(i_list[0])
    i_smu.output_on()
    time.sleep(config.settling_delay_s * 2)

    # Configure voltmeter
    v_smu.reset()
    v_smu.configure_voltmeter(compliance_voltage=config.compliance_V)
    v_smu.output_on()
    time.sleep(config.settling_delay_s)

    i_f_data:    list[float] = []
    v_long_data: list[float] = []
    v_hall_data: list[float] = []
    step = 0

    log.info(
        "Hall sweep: I %.2e→%.2e A (%d pts), B=%.3f T, Vlim=%.1f V",
        config.i_start, config.i_stop, n_pts, config.b_field_T, config.compliance_V,
    )

    try:
        for idx, i_cmd in enumerate(i_list):
            if abort_flag[0]:
                log.info("Hall sweep aborted at step %d/%d", idx, n_pts)
                break

            i_smu.set_current(i_cmd)
            time.sleep(config.settling_delay_s)

            _i_meas, v_long = i_smu.measure_iv()   # (I_actual, V_longitudinal)
            _i_vm,   v_hall = v_smu.measure_iv()   # (~0 A,    V_Hall)

            i_f_data.append(i_cmd)
            v_long_data.append(v_long)
            v_hall_data.append(v_hall)

            if data_cb:
                data_cb(i_cmd, v_long, v_long, 0)
                data_cb(i_cmd, v_hall, v_hall, 1)

            step += 2
            if progress_cb:
                progress_cb(step, total)

    finally:
        i_smu.set_current(0.0)
        i_smu.output_off()
        v_smu.output_off()

    i_arr    = np.array(i_f_data)
    vl_arr   = np.array(v_long_data)
    vh_arr   = np.array(v_hall_data)

    # Fit slopes: V = slope * I
    R_xx = float("nan")
    R_xy = float("nan")
    if len(i_arr) >= 2 and np.ptp(i_arr) > 0:
        R_xx = float(np.polyfit(i_arr, vl_arr, 1)[0])
        R_xy = float(np.polyfit(i_arr, vh_arr, 1)[0])

    # Derived parameters (require B ≠ 0)
    n_sheet = float("nan")
    mu_H    = float("nan")
    if config.b_field_T != 0.0 and not np.isnan(R_xy):
        n_sheet = 1.0 / (_Q_E * abs(R_xy) * abs(config.b_field_T))
        # µ_H = |R_xy| / R_sheet  (R_sheet from separate VdP; use R_xx as proxy here)
        if not np.isnan(R_xx) and abs(R_xx) > 0:
            mu_H = abs(R_xy) / abs(R_xx)

    carrier_type = "n-type" if R_xy > 0 else "p-type" if R_xy < 0 else "unknown"

    return {
        "i_forced":    i_arr,
        "v_long":      vl_arr,
        "v_hall":      vh_arr,
        "R_xx":        R_xx,
        "R_xy":        R_xy,
        "n_sheet":     n_sheet,
        "mu_H":        mu_H,
        "carrier_type": carrier_type,
        "config":      config,
    }
