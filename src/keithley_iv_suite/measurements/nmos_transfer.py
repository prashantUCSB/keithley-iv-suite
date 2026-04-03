"""nMOS transfer curve measurement: sweep Vgs, fixed Vds, measure Id."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Optional

import numpy as np

from ..instruments.smu_base import SMUBase
from .sweep_config import TransferConfig, TerminalRole

log = logging.getLogger(__name__)


def run_transfer_sweep(
    config: TransferConfig,
    gate_smu: SMUBase,
    drain_smu: SMUBase,
    source_smu: Optional[SMUBase] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    data_cb: Optional[Callable[[float, float, float], None]] = None,
    abort_flag: Optional[list[bool]] = None,
) -> dict:
    """
    Execute an nMOS transfer curve sweep.

    Parameters
    ----------
    config       : TransferConfig
    gate_smu     : SMU driving the gate (sweeps Vgs)
    drain_smu    : SMU driving the drain (fixed Vds), measures Id
    source_smu   : Optional SMU for source (sets 0 V); if None, source is grounded externally
    progress_cb  : Called with (step, total) after each point
    data_cb      : Called with (vgs_forced, id_A, ig_A, vgs_sensed) after each point
    abort_flag   : Mutable list; set abort_flag[0]=True to stop early

    Returns
    -------
    dict with keys: vgs, id, ig, vds_actual, config
    """
    if abort_flag is None:
        abort_flag = [False]

    vgs_list = config.vgs_list()
    n_pts = len(vgs_list)

    # --- reset and configure all SMUs ---
    for smu, label in [(gate_smu, "Gate"), (drain_smu, "Drain")]:
        smu.reset()
        smu.configure_voltage_source(
            compliance_current=(
                config.compliance_gate_A if label == "Gate" else config.compliance_drain_A
            )
        )

    if source_smu is not None:
        source_smu.reset()
        source_smu.configure_voltage_source(compliance_current=0.1)
        source_smu.set_voltage(0.0)
        source_smu.output_on()

    # Set drain to fixed Vds
    drain_smu.set_voltage(config.vds_fixed)
    drain_smu.output_on()

    # Gate starts at first point
    gate_smu.set_voltage(vgs_list[0])
    gate_smu.output_on()
    time.sleep(config.settling_delay_s * 2)

    vgs_data:    list[float] = []
    vgs_s_data:  list[float] = []   # sensed gate voltage
    id_data:     list[float] = []
    ig_data:     list[float] = []
    vds_data:    list[float] = []

    log.info(
        "Transfer sweep: Vgs %.2f→%.2f V (%d pts), Vds=%.3f V",
        config.vgs_start, config.vgs_stop, n_pts, config.vds_fixed,
    )

    try:
        for i, vgs in enumerate(vgs_list):
            if abort_flag[0]:
                log.info("Transfer sweep aborted at step %d/%d", i, n_pts)
                break

            gate_smu.set_voltage(vgs)
            time.sleep(config.settling_delay_s)

            # Measure drain (Id and actual Vds)
            id_meas, vds_meas = drain_smu.measure_iv()
            # Measure gate (Ig and sensed Vgs)
            ig_meas, vgs_sensed = gate_smu.measure_iv()

            vgs_data.append(vgs)
            vgs_s_data.append(vgs_sensed)
            id_data.append(id_meas)
            ig_data.append(ig_meas)
            vds_data.append(vds_meas)

            if data_cb:
                data_cb(vgs, id_meas, ig_meas, vgs_sensed)
            if progress_cb:
                progress_cb(i + 1, n_pts)

    finally:
        gate_smu.output_off()
        drain_smu.output_off()
        if source_smu is not None:
            source_smu.output_off()

    return {
        "vgs":        np.array(vgs_data),
        "vgs_sensed": np.array(vgs_s_data),
        "id":         np.array(id_data),
        "ig":         np.array(ig_data),
        "vds_actual": np.array(vds_data),
        "config":     config,
    }
