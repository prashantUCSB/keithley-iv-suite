"""Generic 4-port voltage sweep.

T1 is swept; T2 and T3 hold fixed bias voltages; T4 is grounded.
Measures I at T1.  Use for devices that do not fit the labelled MOSFET /
resistor / VdP / Hall tabs.
"""
from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from typing import Optional

from ..instruments.smu_base import SMUBase
from .sweep_config import Generic4PortConfig

log = logging.getLogger(__name__)


def run_generic_4port(
    config: Generic4PortConfig,
    t1_smu: SMUBase,
    t2_smu: Optional[SMUBase] = None,
    t3_smu: Optional[SMUBase] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float, float, int], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """Sweep V on T1, hold T2/T3 at fixed bias, measure I on T1.

    Parameters
    ----------
    config      : Generic4PortConfig
    t1_smu      : primary sweep terminal (forces V, measures I)
    t2_smu      : optional secondary terminal (holds v_t2_bias)
    t3_smu      : optional tertiary terminal (holds v_t3_bias)
    progress_cb : (step, total)
    data_cb     : (v_t1_forced, i_t1, v_t1_sensed, curve_id=0)
    abort_flag  : list[bool]

    Returns
    -------
    dict: v_forced, v_sensed, current, config
    """
    if abort_flag is None:
        abort_flag = [False]

    v_list = config.v_list()
    n_pts  = len(v_list)

    # Configure T1 as voltage source
    t1_smu.reset()
    t1_smu.configure_voltage_source(
        compliance_current=config.compliance_A,
        voltage_range=config.source_range_V,
        sense_range_i=config.sense_range_A,
        nplc=config.nplc,
        source_delay_s=config.source_delay_s,
    )
    t1_smu.set_voltage(v_list[0])
    t1_smu.output_on()
    time.sleep(config.settling_delay_s * 2)

    # Configure T2 at fixed bias if connected
    if t2_smu is not None and not math.isnan(config.v_t2_bias):
        t2_smu.reset()
        t2_smu.configure_voltage_source(compliance_current=config.comp_t2_A)
        t2_smu.set_voltage(config.v_t2_bias)
        t2_smu.output_on()
        time.sleep(config.settling_delay_s)

    # Configure T3 at fixed bias if connected
    if t3_smu is not None and not math.isnan(config.v_t3_bias):
        t3_smu.reset()
        t3_smu.configure_voltage_source(compliance_current=config.comp_t3_A)
        t3_smu.set_voltage(config.v_t3_bias)
        t3_smu.output_on()
        time.sleep(config.settling_delay_s)

    v_f_data: list[float] = []
    v_s_data: list[float] = []
    i_data:   list[float] = []

    log.info(
        "Generic 4-port sweep: V %.3f→%.3f V (%d pts), T2=%.3f V, T3=%.3f V",
        config.v_start, config.v_stop, n_pts,
        config.v_t2_bias, config.v_t3_bias,
    )

    try:
        for idx, voltage in enumerate(v_list):
            if abort_flag[0]:
                log.info("Generic sweep aborted at step %d/%d", idx, n_pts)
                break

            t1_smu.set_voltage(voltage)
            time.sleep(config.settling_delay_s)

            current, v_meas = t1_smu.measure_iv()

            v_f_data.append(voltage)
            v_s_data.append(v_meas)
            i_data.append(current)

            if data_cb:
                data_cb(voltage, current, v_meas, 0)
            if progress_cb:
                progress_cb(idx + 1, n_pts)

    finally:
        t1_smu.set_voltage(0.0)
        t1_smu.output_off()
        if t2_smu is not None:
            try:
                t2_smu.set_voltage(0.0)
                t2_smu.output_off()
            except Exception:
                pass
        if t3_smu is not None:
            try:
                t3_smu.set_voltage(0.0)
                t3_smu.output_off()
            except Exception:
                pass

    import numpy as np
    return {
        "v_forced":  np.array(v_f_data),
        "v_sensed":  np.array(v_s_data),
        "current":   np.array(i_data),
        "config":    config,
    }
