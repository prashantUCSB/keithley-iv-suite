"""Keithley 2602 / 2614B TSP (Lua) driver."""
from __future__ import annotations

import logging
import time
from typing import Optional

import pyvisa

from .smu_base import SMUBase

log = logging.getLogger(__name__)


class SMU2600(SMUBase):
    """
    Drives one channel (A or B) of a Keithley 2602 or 2614B via TSP (Lua).

    The 2600-series instruments use the Test Script Processor instead of SCPI.
    Commands are Lua statements sent over the VISA connection.

    Channel selection: pass channel='A' or channel='B'.
    The TSP object for channel A is ``smua``, for B it is ``smub``.
    """

    MODEL_IDS = ("2602", "2602A", "2614B", "2614")

    def __init__(
        self,
        resource: pyvisa.resources.Resource,
        channel: str = "A",
        nplc: float = 1.0,
        delay_s: float = 0.02,
    ) -> None:
        if channel.upper() not in ("A", "B"):
            raise ValueError(f"Channel must be 'A' or 'B', got '{channel}'")
        super().__init__(resource, channel=channel.upper())
        self._smu = f"smu{channel.lower()}"   # "smua" or "smub"
        self._nplc = nplc
        self._delay_s = delay_s
        self._compliance = 0.1
        self._output_on = False

    # ------------------------------------------------------------------
    # Private TSP helpers
    # ------------------------------------------------------------------

    def _tsp(self, cmd: str) -> None:
        """Write a TSP (Lua) command."""
        self._write(cmd)

    def _tsp_query(self, expr: str) -> str:
        """Evaluate a TSP expression and return the printed result."""
        self._write(f"print({expr})")
        return self._resource.read().strip()

    # ------------------------------------------------------------------
    # SMUBase implementation
    # ------------------------------------------------------------------

    def identify(self) -> str:
        return self._query("*IDN?")

    def reset(self) -> None:
        self._tsp(f"{self._smu}.reset()")
        time.sleep(0.1)
        self._tsp(f"{self._smu}.measure.nplc = {self._nplc}")
        # Use literal 2 (AUTOZERO_AUTO) — the symbolic constant smua.AUTOZERO_AUTO
        # is nil on some firmware builds and assigning nil to a protected TSP
        # attribute raises "cannot modify table".
        self._tsp(f"{self._smu}.measure.autozero = 2")
        log.debug("SMU2600 channel %s reset complete", self._channel)

    def configure_voltage_source(
        self,
        compliance_current: float,
        voltage_range: Optional[float] = None,
        sense_range_i: Optional[float] = None,
        nplc: float = 1.0,
        source_delay_s: float = 0.0,
    ) -> None:
        self._compliance = compliance_current
        smu = self._smu
        self._tsp(f"{smu}.source.func = {smu}.OUTPUT_DCVOLTS")
        if voltage_range is not None:
            self._tsp(f"{smu}.source.rangev = {voltage_range:.6g}")
        else:
            self._tsp(f"{smu}.source.autorangev = 1")   # 1 = AUTORANGE_ON
        self._tsp(f"{smu}.source.limiti = {compliance_current:.6g}")
        if sense_range_i is not None:
            self._tsp(f"{smu}.measure.autorangei = 0")  # 0 = AUTORANGE_OFF
            self._tsp(f"{smu}.measure.rangei = {sense_range_i:.6g}")
        else:
            self._tsp(f"{smu}.measure.autorangei = 1")  # 1 = AUTORANGE_ON
        self._tsp(f"{smu}.measure.nplc = {nplc:.6g}")
        self._nplc = nplc
        if source_delay_s > 0:
            self._tsp(f"{smu}.source.delay = {source_delay_s:.6g}")
        self._tsp(f"{smu}.source.output = {smu}.OUTPUT_OFF")
        log.debug(
            "SMU2600 Ch%s configured: Vsource, Ilim=%.3e A, sense_range=%s, nplc=%.2f",
            self._channel, compliance_current,
            f"{sense_range_i:.2e} A" if sense_range_i else "auto",
            nplc,
        )

    def set_voltage(self, voltage: float) -> None:
        self._tsp(f"{self._smu}.source.levelv = {voltage:.6g}")

    def configure_current_source(
        self,
        compliance_voltage: float,
        current_range=None,
        sense_range_v: Optional[float] = None,
        nplc: float = 1.0,
        source_delay_s: float = 0.0,
    ) -> None:
        smu = self._smu
        self._tsp(f"{smu}.source.func = {smu}.OUTPUT_DCAMPS")
        if current_range is not None:
            self._tsp(f"{smu}.source.rangei = {current_range:.6g}")
        else:
            self._tsp(f"{smu}.source.autorangei = 1")
        self._tsp(f"{smu}.source.limitv = {compliance_voltage:.6g}")
        if sense_range_v is not None:
            self._tsp(f"{smu}.measure.autorangev = 0")  # 0 = AUTORANGE_OFF
            self._tsp(f"{smu}.measure.rangev = {sense_range_v:.6g}")
        else:
            self._tsp(f"{smu}.measure.autorangev = 1")
        self._tsp(f"{smu}.measure.nplc = {nplc:.6g}")
        self._nplc = nplc
        if source_delay_s > 0:
            self._tsp(f"{smu}.source.delay = {source_delay_s:.6g}")
        self._tsp(f"{smu}.source.output = {smu}.OUTPUT_OFF")
        log.debug(
            "SMU2600 Ch%s configured: Isource, Vlim=%.3g V, sense_range=%s, nplc=%.2f",
            self._channel, compliance_voltage,
            f"{sense_range_v:.2e} V" if sense_range_v else "auto",
            nplc,
        )

    def set_current(self, current: float) -> None:
        self._tsp(f"{self._smu}.source.leveli = {current:.6g}")

    def output_on(self) -> None:
        self._tsp(f"{self._smu}.source.output = {self._smu}.OUTPUT_ON")
        self._output_on = True
        time.sleep(self._delay_s)

    def output_off(self) -> None:
        self._tsp(f"{self._smu}.source.output = {self._smu}.OUTPUT_OFF")
        self._output_on = False

    @staticmethod
    def _extract_floats(raw: str) -> list[float]:
        """Return all parseable float tokens from a TSP response string."""
        result: list[float] = []
        for token in raw.strip().split():
            try:
                result.append(float(token))
            except ValueError:
                pass
        return result

    def measure_iv(self) -> tuple[float, float]:
        """Return (current_A, voltage_V).

        TSP print() separates Lua multiple-return values with tabs, but
        firmware versions vary — some append status tokens, others return
        both I and V even from single-quantity calls (measure.i(), measure.v()).
        All paths parse defensively.
        """
        raw = self._tsp_query(f"{self._smu}.measure.iv()")
        floats = self._extract_floats(raw)
        if len(floats) >= 2:
            return floats[0], floats[1]

        log.warning(
            "measure.iv() response not parseable (%r); "
            "falling back to separate i/v queries",
            raw,
        )
        raw_i = self._tsp_query(f"{self._smu}.measure.i()")
        fi = self._extract_floats(raw_i)
        if len(fi) >= 2:
            # Firmware returns "current\tvoltage" even from measure.i()
            return fi[0], fi[1]
        if len(fi) == 1:
            raw_v = self._tsp_query(f"{self._smu}.measure.v()")
            fv = self._extract_floats(raw_v)
            return fi[0], fv[0] if fv else 0.0

        raise RuntimeError(
            f"Cannot parse any float from measure.i() response: {raw_i!r}"
        )

    # ------------------------------------------------------------------
    # Extras
    # ------------------------------------------------------------------

    def set_nplc(self, nplc: float) -> None:
        self._nplc = nplc
        self._tsp(f"{self._smu}.measure.nplc = {nplc}")

    def set_delay(self, delay_s: float) -> None:
        self._delay_s = delay_s

    def set_sense_mode(self, remote: bool) -> None:
        """Enable 4-wire (SENSE_REMOTE) or 2-wire (SENSE_LOCAL) sense."""
        mode = f"{self._smu}.SENSE_REMOTE" if remote else f"{self._smu}.SENSE_LOCAL"
        self._tsp(f"{self._smu}.sense = {mode}")
        log.debug("SMU2600 Ch%s sense mode: %s", self._channel, "4-wire" if remote else "2-wire")

    @property
    def compliance_current(self) -> float:
        return self._compliance

    def in_compliance(self) -> bool:
        raw = self._tsp_query(f"{self._smu}.source.compliance")
        return raw.strip().lower() in ("true", "1")
