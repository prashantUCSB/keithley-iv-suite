"""Keithley 2400 / 2401 SCPI driver."""
from __future__ import annotations

import logging
import time
from typing import Optional

import pyvisa

from .smu_base import SMUBase

log = logging.getLogger(__name__)

# SCPI response indices when :FORM:ELEM VOLT,CURR is set
_IDX_VOLT = 0
_IDX_CURR = 1


class SMU2400(SMUBase):
    """
    Drives the Keithley 2400 or 2401 via standard SCPI.

    Both models share identical command sets.  This driver forces voltage
    and measures current; compliance, range, and NPLC are all configurable.
    """

    MODEL_IDS = ("2400", "2401")

    def __init__(
        self,
        resource: pyvisa.resources.Resource,
        nplc: float = 1.0,
        delay_s: float = 0.02,
    ) -> None:
        super().__init__(resource, channel="")
        self._nplc = nplc
        self._delay_s = delay_s
        self._compliance = 0.1
        self._output_on = False
        # 10 s covers *RST + long NPLC reads (NPLC=25 @ 50 Hz = 500 ms/pt)
        # with plenty of margin for USB-TMC round-trip overhead.
        resource.timeout = 10_000

    # ------------------------------------------------------------------
    # SMUBase implementation
    # ------------------------------------------------------------------

    def identify(self) -> str:
        return self._query("*IDN?")

    def reset(self) -> None:
        # :ABORt returns the 2400 to the trigger-idle state regardless of
        # what it was doing (mid-sweep, waiting for trigger, output ON).
        # Ignore errors — instrument may already be idle.
        try:
            self._write(":ABOR")
        except Exception:
            pass
        # *RST performs a full hardware reset.  Do NOT call resource.clear()
        # here — it may already have been called by the connect sequence, and a
        # back-to-back INITIATE_CLEAR causes USB-TMC to desync, making the next
        # viWrite fail with VI_ERROR_TMO.  Do NOT use *OPC? immediately after
        # *RST — the 2400 cannot accept a query for ~500 ms post-reset; a plain
        # sleep is more reliable for this model.
        self._write("*RST")
        time.sleep(1.0)
        self._write("*CLS")
        self._write(":SYST:BEEP:STAT OFF")
        self._write(":FORM:ELEM VOLT,CURR")
        self._write(f":SENS:CURR:NPLC {self._nplc}")
        self._write(":SENS:VOLT:NPLC 1.0")
        self._write(":DISP:ENAB ON")
        log.debug("SMU2400 reset complete")

    def configure_voltage_source(
        self,
        compliance_current: float,
        voltage_range: Optional[float] = None,
        sense_range_i: Optional[float] = None,
        nplc: float = 1.0,
        source_delay_s: float = 0.0,
    ) -> None:
        self._compliance = compliance_current
        self._write(":SOUR:FUNC VOLT")
        if voltage_range is not None:
            self._write(f":SOUR:VOLT:RANG {voltage_range:.6g}")
        else:
            self._write(":SOUR:VOLT:RANG:AUTO ON")
        self._write(":SENS:FUNC \"CURR:DC\"")
        if sense_range_i is not None:
            self._write(":SENS:CURR:RANG:AUTO OFF")
            self._write(f":SENS:CURR:RANG {sense_range_i:.6g}")
        else:
            self._write(":SENS:CURR:RANG:AUTO ON")
        self._write(f":SENS:CURR:PROT {compliance_current:.6g}")
        self._write(f":SENS:CURR:NPLC {nplc:.6g}")
        self._nplc = nplc
        if source_delay_s > 0:
            self._write(":SOUR:DEL:AUTO OFF")
            self._write(f":SOUR:DEL {max(0.001, source_delay_s):.6g}")
        self._write(":FORM:ELEM VOLT,CURR")
        log.debug(
            "SMU2400 configured: Vsource, Ilim=%.3e A, sense_range=%s, nplc=%.2f",
            compliance_current,
            f"{sense_range_i:.2e} A" if sense_range_i else "auto",
            nplc,
        )

    def set_voltage(self, voltage: float) -> None:
        self._write(f":SOUR:VOLT:LEV {voltage:.6g}")

    def configure_current_source(
        self,
        compliance_voltage: float,
        current_range=None,
        sense_range_v: Optional[float] = None,
        nplc: float = 1.0,
        source_delay_s: float = 0.0,
    ) -> None:
        self._write(":SOUR:FUNC CURR")
        if current_range is not None:
            self._write(f":SOUR:CURR:RANG {current_range:.6g}")
        else:
            self._write(":SOUR:CURR:RANG:AUTO ON")
        self._write(":SENS:FUNC \"VOLT:DC\"")
        if sense_range_v is not None:
            self._write(":SENS:VOLT:RANG:AUTO OFF")
            self._write(f":SENS:VOLT:RANG {sense_range_v:.6g}")
        else:
            self._write(":SENS:VOLT:RANG:AUTO ON")
        self._write(f":SENS:VOLT:PROT {compliance_voltage:.6g}")
        self._write(f":SENS:VOLT:NPLC {nplc:.6g}")
        self._nplc = nplc
        if source_delay_s > 0:
            self._write(":SOUR:DEL:AUTO OFF")
            self._write(f":SOUR:DEL {max(0.001, source_delay_s):.6g}")
        self._write(":FORM:ELEM VOLT,CURR")
        log.debug(
            "SMU2400 configured: Isource, Vlim=%.3g V, sense_range=%s, nplc=%.2f",
            compliance_voltage,
            f"{sense_range_v:.2e} V" if sense_range_v else "auto",
            nplc,
        )

    def set_current(self, current: float) -> None:
        self._write(f":SOUR:CURR:LEV {current:.6g}")

    def output_on(self) -> None:
        self._write(":OUTP ON")
        self._output_on = True
        time.sleep(self._delay_s)

    def output_off(self) -> None:
        self._write(":OUTP OFF")
        self._output_on = False

    def measure_iv(self) -> tuple[float, float]:
        """Return (current_A, voltage_V)."""
        raw = self._query(":READ?")
        values = [float(x) for x in raw.split(",")]
        voltage = values[_IDX_VOLT]
        current = values[_IDX_CURR]
        return current, voltage

    # ------------------------------------------------------------------
    # Extras
    # ------------------------------------------------------------------

    def set_nplc(self, nplc: float) -> None:
        self._nplc = nplc
        self._write(f":SENS:CURR:NPLC {nplc}")

    def set_delay(self, delay_s: float) -> None:
        self._delay_s = delay_s

    def set_sense_mode(self, remote: bool) -> None:
        """Enable 4-wire (remote) or 2-wire (local) sense."""
        self._write(":SYST:RSEN ON" if remote else ":SYST:RSEN OFF")
        log.debug("SMU2400 sense mode: %s", "4-wire" if remote else "2-wire")

    @property
    def compliance_current(self) -> float:
        return self._compliance

    def in_compliance(self) -> bool:
        """Return True if the instrument is at its compliance limit."""
        raw = self._query(":READ?")
        values = [float(x) for x in raw.split(",")]
        # Status word is the 5th element when :FORM:ELEM is VOLT,CURR (not present)
        # Check by comparing |I| to compliance threshold
        current = abs(values[_IDX_CURR])
        return current >= self._compliance * 0.999
