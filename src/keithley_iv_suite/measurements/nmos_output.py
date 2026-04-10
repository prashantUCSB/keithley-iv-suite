"""nMOS output characteristics: sweep Vds for a family of Vgs values."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Optional

import numpy as np

from ..instruments.smu_base import SMUBase
from .sweep_config import OutputConfig, TerminalRole

log = logging.getLogger(__name__)


def run_output_sweep(
    config: OutputConfig,
    gate_smu: SMUBase,
    drain_smu: SMUBase,
    source_smu: Optional[SMUBase] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float, float, int], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """
    Execute nMOS output curves (family of Id-Vds at multiple Vgs).

    Parameters
    ----------
    config       : OutputConfig
    gate_smu     : SMU driving the gate (fixed at each Vgs in the family)
    drain_smu    : SMU driving/measuring drain (sweeps Vds)
    source_smu   : Optional source SMU (0 V); if None, externally grounded
    progress_cb  : Called with (step, total_steps_across_all_curves)
    data_cb      : Called with (vds_forced, id_A, ig_A, vds_sensed, curve_index)
    abort_flag   : Mutable list; set abort_flag[0]=True to stop early

    Returns
    -------
    dict with keys: curves (list of dicts per Vgs), vgs_list, config
    """
    if abort_flag is None:
        abort_flag = [False]

    vds_list = config.vds_list()
    vgs_family = config.vgs_list_values
    n_curves = len(vgs_family)
    n_pts_per_curve = len(vds_list)
    total_pts = n_curves * n_pts_per_curve
    step = 0

    # --- configure SMUs ---
    gate_smu.reset()
    gate_smu.configure_voltage_source(
        compliance_current=config.compliance_gate_A,
        voltage_range=config.source_range_V,
        sense_range_i=config.gate_sense_range_A,
        nplc=config.nplc,
        source_delay_s=config.source_delay_s,
    )
    drain_smu.reset()
    drain_smu.configure_voltage_source(
        compliance_current=config.compliance_drain_A,
        voltage_range=config.source_range_V,
        sense_range_i=config.drain_sense_range_A,
        nplc=config.nplc,
        source_delay_s=config.source_delay_s,
    )

    if source_smu is not None:
        source_smu.reset()
        source_smu.configure_voltage_source(compliance_current=0.1)
        source_smu.set_voltage(0.0)
        source_smu.output_on()

    curves: list[dict] = []

    log.info(
        "Output sweep: Vds %.2f→%.2f V (%d pts), Vgs family: %s",
        config.vds_start, config.vds_stop, n_pts_per_curve,
        [f"{v:.2f}" for v in vgs_family],
    )

    try:
        for curve_idx, vgs in enumerate(vgs_family):
            if abort_flag[0]:
                break

            gate_smu.set_voltage(vgs)
            gate_smu.output_on()
            drain_smu.set_voltage(vds_list[0])
            drain_smu.output_on()
            time.sleep(config.settling_delay_s * 2)

            vds_f_data: list[float] = []   # forced setpoint
            vds_s_data: list[float] = []   # sensed readback
            id_data:    list[float] = []
            ig_data:    list[float] = []

            for vds in vds_list:
                if abort_flag[0]:
                    break
                drain_smu.set_voltage(vds)
                time.sleep(config.settling_delay_s)

                id_meas, vds_meas = drain_smu.measure_iv()
                ig_meas, _ = gate_smu.measure_iv()

                vds_f_data.append(vds)
                vds_s_data.append(vds_meas)
                id_data.append(id_meas)
                ig_data.append(ig_meas)

                step += 1
                if data_cb:
                    data_cb(vds, id_meas, ig_meas, vds_meas, curve_idx)
                if progress_cb:
                    progress_cb(step, total_pts)

            gate_smu.output_off()
            drain_smu.output_off()

            curves.append({
                "vgs":        vgs,
                "vds_forced": np.array(vds_f_data),
                "vds":        np.array(vds_s_data),   # sensed; backward-compat key
                "id":         np.array(id_data),
                "ig":         np.array(ig_data),
            })

    finally:
        gate_smu.output_off()
        drain_smu.output_off()
        if source_smu is not None:
            source_smu.output_off()

    return {
        "curves": curves,
        "vgs_list": vgs_family,
        "config": config,
    }
