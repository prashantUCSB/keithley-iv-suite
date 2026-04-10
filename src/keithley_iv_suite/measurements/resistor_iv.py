"""Resistor IV sweep: two-terminal voltage sweep, measures I and computes R."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Optional

import numpy as np

from ..instruments.smu_base import SMUBase
from .sweep_config import ResistorConfig

log = logging.getLogger(__name__)

_EPSILON = 1e-15   # avoid division by zero


def run_resistor_sweep(
    config: ResistorConfig,
    smu: SMUBase,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """
    Execute a two-terminal resistor IV sweep.

    Parameters
    ----------
    config       : ResistorConfig
    smu          : SMU driving terminal 1 (terminal 2 grounded externally or inside the SMU)
    progress_cb  : Called with (step, total)
    data_cb      : Called with (v_forced, current_A, v_sensed) after each point
    abort_flag   : Mutable list; set abort_flag[0]=True to stop early

    Returns
    -------
    dict with keys: voltage, current, resistance, config
    """
    if abort_flag is None:
        abort_flag = [False]

    v_list = config.v_list()
    n_pts = len(v_list)

    smu.reset()
    smu.configure_voltage_source(
        compliance_current=config.compliance_A,
        voltage_range=config.source_range_V,
        sense_range_i=config.sense_range_A,
        nplc=config.nplc,
        source_delay_s=config.source_delay_s,
    )
    smu.set_voltage(v_list[0])
    smu.output_on()
    time.sleep(config.settling_delay_s * 2)

    v_f_data: list[float] = []   # forced setpoint
    v_s_data: list[float] = []   # sensed readback
    i_data:   list[float] = []
    r_data:   list[float] = []

    log.info(
        "Resistor sweep: V %.3f→%.3f V (%d pts), Ilim=%.3e A",
        config.v_start, config.v_stop, n_pts, config.compliance_A,
    )

    try:
        for idx, voltage in enumerate(v_list):
            if abort_flag[0]:
                log.info("Resistor sweep aborted at step %d/%d", idx, n_pts)
                break

            smu.set_voltage(voltage)
            time.sleep(config.settling_delay_s)

            current, v_meas = smu.measure_iv()
            resistance = v_meas / (current + _EPSILON) if abs(current) > 1e-14 else float("inf")

            v_f_data.append(voltage)
            v_s_data.append(v_meas)
            i_data.append(current)
            r_data.append(resistance)

            if data_cb:
                data_cb(voltage, current, v_meas)
            if progress_cb:
                progress_cb(idx + 1, n_pts)

    finally:
        smu.set_voltage(0.0)
        smu.output_off()

    return {
        "voltage":         np.array(v_f_data),
        "voltage_sensed":  np.array(v_s_data),
        "current":         np.array(i_data),
        "resistance":      np.array(r_data),
        "config":          config,
    }
