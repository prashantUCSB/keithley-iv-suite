"""QThread worker that runs measurements and emits signals for live UI updates."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ...instruments.smu_base import SMUBase
from ...measurements.sweep_config import (
    FourPointProbeConfig, Generic4PortConfig, HallBarConfig, MeasurementType,
    OutputConfig, ResistorConfig, SweepConfig, TransferConfig, VanDerPauwConfig,
)
from ...measurements.nmos_transfer import run_transfer_sweep
from ...measurements.nmos_output import run_output_sweep
from ...measurements.resistor_iv import run_resistor_sweep
from ...measurements.van_der_pauw import run_vdp_sweep
from ...measurements.hall_bar import run_hall_sweep
from ...measurements.four_point_probe import run_four_point_probe
from ...measurements.generic_4port import run_generic_4port

log = logging.getLogger(__name__)


class MeasurementWorker(QThread):
    """
    Runs a single sweep config in a background QThread.

    Signals
    -------
    progress(step, total)
    data_point(v_forced, i_meas, v_sensed, curve_id)
        v_forced  — commanded setpoint (V)
        i_meas    — measured current (A)
        v_sensed  — voltage read back by the SMU (V); equals v_forced in
                    2-wire mode, differs in 4-wire (Kelvin) mode
        curve_id  — index into the family (0 for single-curve measurements)
    finished(result_dict)
    error(message)
    aborted()
    """

    progress   = pyqtSignal(int, int)
    data_point = pyqtSignal(float, float, float, int)   # v_forced, i, v_sensed, curve_id
    finished   = pyqtSignal(dict)
    error      = pyqtSignal(str)
    aborted    = pyqtSignal()

    def __init__(
        self,
        config: SweepConfig,
        smu_map: dict[str, SMUBase],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._smu_map = smu_map
        self._abort_flag: list[bool] = [False]

    def stop(self) -> None:
        self._abort_flag[0] = True

    def run(self) -> None:
        try:
            result = self._dispatch()
            if self._abort_flag[0]:
                self.aborted.emit()
            else:
                self.finished.emit(result)
        except Exception as exc:
            log.exception("Measurement worker error")
            self.error.emit(str(exc))

    def _dispatch(self) -> dict:
        cfg = self._config
        mtype = cfg.measurement_type

        if mtype == MeasurementType.NMOS_TRANSFER:
            assert isinstance(cfg, TransferConfig)
            gate_smu  = self._resolve("gate",  cfg)
            drain_smu = self._resolve("drain", cfg)
            src_smu   = self._resolve_optional("source", cfg)
            return run_transfer_sweep(
                config=cfg,
                gate_smu=gate_smu,
                drain_smu=drain_smu,
                source_smu=src_smu,
                progress_cb=lambda s, t: self.progress.emit(s, t),
                data_cb=lambda vf, i, ig, vs: self.data_point.emit(vf, i, vs, 0),
                abort_flag=self._abort_flag,
            )

        if mtype == MeasurementType.NMOS_OUTPUT:
            assert isinstance(cfg, OutputConfig)
            gate_smu  = self._resolve("gate",  cfg)
            drain_smu = self._resolve("drain", cfg)
            src_smu   = self._resolve_optional("source", cfg)
            return run_output_sweep(
                config=cfg,
                gate_smu=gate_smu,
                drain_smu=drain_smu,
                source_smu=src_smu,
                progress_cb=lambda s, t: self.progress.emit(s, t),
                data_cb=lambda vf, i, ig, vs, ci: self.data_point.emit(vf, i, vs, ci),
                abort_flag=self._abort_flag,
            )

        if mtype == MeasurementType.RESISTOR_IV:
            assert isinstance(cfg, ResistorConfig)
            smu = self._resolve("terminal_1", cfg)
            return run_resistor_sweep(
                config=cfg,
                smu=smu,
                progress_cb=lambda s, t: self.progress.emit(s, t),
                data_cb=lambda vf, i, vs: self.data_point.emit(vf, i, vs, 0),
                abort_flag=self._abort_flag,
            )

        if mtype == MeasurementType.VAN_DER_PAUW:
            assert isinstance(cfg, VanDerPauwConfig)
            i_smu = self._resolve("i_plus", cfg)
            v_smu = self._resolve("v_plus", cfg)
            return run_vdp_sweep(
                config=cfg,
                i_smu=i_smu,
                v_smu=v_smu,
                progress_cb=lambda s, t: self.progress.emit(s, t),
                data_cb=lambda i, v, vs, ci: self.data_point.emit(i, v, vs, ci),
                abort_flag=self._abort_flag,
            )

        if mtype == MeasurementType.HALL_BAR:
            assert isinstance(cfg, HallBarConfig)
            i_smu = self._resolve("i_plus", cfg)
            v_smu = self._resolve("v_hall_plus", cfg)
            return run_hall_sweep(
                config=cfg,
                i_smu=i_smu,
                v_smu=v_smu,
                progress_cb=lambda s, t: self.progress.emit(s, t),
                data_cb=lambda i, v, vs, ci: self.data_point.emit(i, v, vs, ci),
                abort_flag=self._abort_flag,
            )

        if mtype == MeasurementType.GENERIC_4PORT:
            assert isinstance(cfg, Generic4PortConfig)
            t1 = self._resolve("t1", cfg)
            t2 = self._resolve_optional("t2", cfg)
            t3 = self._resolve_optional("t3", cfg)
            return run_generic_4port(
                config=cfg,
                t1_smu=t1,
                t2_smu=t2,
                t3_smu=t3,
                progress_cb=lambda s, t: self.progress.emit(s, t),
                data_cb=lambda vf, i, vs, ci: self.data_point.emit(vf, i, vs, ci),
                abort_flag=self._abort_flag,
            )

        if mtype == MeasurementType.FOUR_POINT_PROBE:
            assert isinstance(cfg, FourPointProbeConfig)
            i_smu = self._resolve("i_plus", cfg)
            v_smu = self._resolve("v_plus", cfg)
            return run_four_point_probe(
                config=cfg,
                i_smu=i_smu,
                v_smu=v_smu,
                progress_cb=lambda s, t: self.progress.emit(s, t),
                data_cb=lambda i, v, vs, ci: self.data_point.emit(i, v, vs, ci),
                abort_flag=self._abort_flag,
            )

        raise ValueError(f"Unknown measurement type: {mtype}")

    def _resolve(self, role_key: str, cfg: SweepConfig) -> SMUBase:
        from ...measurements.sweep_config import TerminalRole
        role_map = {
            "gate":         TerminalRole.GATE,
            "drain":        TerminalRole.DRAIN,
            "source":       TerminalRole.SOURCE,
            "terminal_1":   TerminalRole.TERMINAL_1,
            "terminal_2":   TerminalRole.TERMINAL_2,
            "i_plus":       TerminalRole.I_PLUS,
            "i_minus":      TerminalRole.I_MINUS,
            "v_plus":       TerminalRole.V_PLUS,
            "v_minus":      TerminalRole.V_MINUS,
            "v_hall_plus":  TerminalRole.V_HALL_PLUS,
            "v_hall_minus": TerminalRole.V_HALL_MINUS,
            "t1":           TerminalRole.T1,
            "t2":           TerminalRole.T2,
            "t3":           TerminalRole.T3,
            "t4":           TerminalRole.T4,
        }
        role = role_map[role_key]
        assignment = cfg.get_assignment(role)
        if assignment is None or assignment.grounded:
            raise ValueError(f"No SMU assignment found for role '{role_key}'")
        key = assignment.instrument_id
        if key not in self._smu_map:
            raise ValueError(
                f"Instrument '{key}' assigned to {role_key} is not connected. "
                f"Available: {list(self._smu_map.keys())}"
            )
        return self._smu_map[key]

    def _resolve_optional(self, role_key: str, cfg: SweepConfig) -> Optional[SMUBase]:
        from ...measurements.sweep_config import TerminalRole
        role_map = {
            "source":  TerminalRole.SOURCE,
            "t2":      TerminalRole.T2,
            "t3":      TerminalRole.T3,
        }
        role = role_map.get(role_key)
        if role is None:
            return None
        assignment = cfg.get_assignment(role)
        if assignment is None or assignment.grounded:
            return None
        return self._smu_map.get(assignment.instrument_id)
