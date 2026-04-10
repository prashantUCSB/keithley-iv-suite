"""Van der Pauw sheet-resistance measurement.

One SMU channel sources current (swept from i_start to i_stop); a second
channel acts as a high-impedance voltmeter (forces 0 A, measures V).

Run two probe configurations with 'Overlay runs' enabled:
  Config 1: current through contacts A–B, voltage across C–D  → R₁
  Config 2: current through contacts B–C, voltage across D–A  → R₂

Post-sweep the panel solves the van der Pauw equation
    exp(−π R₁ / Rs) + exp(−π R₂ / Rs) = 1
numerically to yield the sheet resistance Rs.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Optional

import numpy as np

from ..instruments.smu_base import SMUBase
from .sweep_config import VanDerPauwConfig

log = logging.getLogger(__name__)

_EPSILON = 1e-30


def run_vdp_sweep(
    config: VanDerPauwConfig,
    i_smu: SMUBase,
    v_smu: SMUBase,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float, float, int], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """Execute a Van der Pauw current-sweep resistance measurement.

    Parameters
    ----------
    config      : VanDerPauwConfig
    i_smu       : SMU used as current source (I+ terminal)
    v_smu       : SMU used as voltmeter (V+ terminal, force 0 A)
    progress_cb : Called with (step, total)
    data_cb     : Called with (i_forced, v_sense, v_sense, curve_id=0)
                  x = forced current (A); y = sensed voltage (V)
    abort_flag  : list[bool]; set [0]=True to abort

    Returns
    -------
    dict: i_forced, v_sense, resistance_per_point, R_fit, config
    """
    if abort_flag is None:
        abort_flag = [False]

    i_list = config.i_list()
    n_pts = len(i_list)

    # --- Configure current source ---
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

    # --- Configure voltmeter ---
    v_smu.reset()
    v_smu.configure_voltmeter(
        compliance_voltage=config.compliance_V,
        sense_range_v=config.sense_range_V,
        nplc=config.nplc,
        source_delay_s=config.source_delay_s,
    )
    v_smu.output_on()
    time.sleep(config.settling_delay_s)

    i_f_data:  list[float] = []
    v_s_data:  list[float] = []
    r_pt_data: list[float] = []

    log.info(
        "VdP sweep: I %.2e→%.2e A (%d pts), Vlim=%.1f V",
        config.i_start, config.i_stop, n_pts, config.compliance_V,
    )

    try:
        for idx, i_cmd in enumerate(i_list):
            if abort_flag[0]:
                log.info("VdP sweep aborted at step %d/%d", idx, n_pts)
                break

            i_smu.set_current(i_cmd)
            time.sleep(config.settling_delay_s)

            _i_meas, _v_ismu = i_smu.measure_iv()   # actual I, V at source terminal
            _i_vmeas, v_sense = v_smu.measure_iv()  # ~0 A, sensed voltage

            r_pt = v_sense / (_i_meas + _EPSILON) if abs(_i_meas) > 1e-18 else float("inf")

            i_f_data.append(i_cmd)
            v_s_data.append(v_sense)
            r_pt_data.append(r_pt)

            if data_cb:
                data_cb(i_cmd, v_sense, v_sense, 0)
            if progress_cb:
                progress_cb(idx + 1, n_pts)

    finally:
        i_smu.set_current(0.0)
        i_smu.output_off()
        v_smu.output_off()

    # Linear fit: V = R * I  →  R_fit = slope (Ω)
    i_arr = np.array(i_f_data)
    v_arr = np.array(v_s_data)
    R_fit = float("nan")
    if len(i_arr) >= 2 and np.ptp(i_arr) > 0:
        m, _ = np.polyfit(i_arr, v_arr, 1)
        R_fit = float(m)

    return {
        "i_forced":           np.array(i_f_data),
        "v_sense":            np.array(v_s_data),
        "resistance_per_pt":  np.array(r_pt_data),
        "R_fit":              R_fit,
        "config":             config,
    }
