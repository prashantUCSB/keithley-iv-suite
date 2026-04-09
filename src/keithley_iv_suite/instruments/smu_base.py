"""Abstract base class for all SMU channels."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import pyvisa


class SourceMode(Enum):
    VOLTAGE = auto()
    CURRENT = auto()


@dataclass
class MeasurementPoint:
    voltage: float
    current: float
    timestamp: float = 0.0


@dataclass
class SMUChannel:
    """Identifies a single source-measure channel (e.g. '2614B:A')."""
    instrument_id: str          # e.g. "2614B", "2400"
    channel: str = "A"          # "A", "B", or "" for single-channel instruments
    resource_string: str = ""   # VISA resource string

    @property
    def display_name(self) -> str:
        if self.channel and self.channel not in ("", "--"):
            return f"{self.instrument_id} Ch{self.channel}"
        return self.instrument_id

    def __str__(self) -> str:
        return self.display_name


class SMUBase(ABC):
    """Abstract base for a single SMU channel."""

    def __init__(self, resource: pyvisa.resources.Resource, channel: str = "") -> None:
        self._resource = resource
        self._channel = channel.upper() if channel else ""
        self._connected = True

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    def disconnect(self) -> None:
        try:
            self.output_off()
        except Exception:
            pass
        try:
            self._resource.close()
        except Exception:
            pass
        self._connected = False

    # ------------------------------------------------------------------
    # Required interface
    # ------------------------------------------------------------------

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def configure_voltage_source(
        self,
        compliance_current: float,
        voltage_range: Optional[float] = None,
    ) -> None: ...

    @abstractmethod
    def set_voltage(self, voltage: float) -> None: ...

    @abstractmethod
    def configure_current_source(
        self,
        compliance_voltage: float,
        current_range: Optional[float] = None,
    ) -> None:
        """Configure as a DC current source.

        Parameters
        ----------
        compliance_voltage : voltage compliance limit (V)
        current_range      : explicit range (A); None = autorange
        """
        ...

    @abstractmethod
    def set_current(self, current: float) -> None:
        """Set the DC current level (A).  Must call configure_current_source first."""
        ...

    def configure_voltmeter(self, compliance_voltage: float = 10.0) -> None:
        """Configure as a high-impedance voltmeter (force 0 A, measure V).

        Default implementation re-uses configure_current_source + set_current(0).
        Subclasses may override if the hardware has a dedicated voltmeter mode.
        """
        self.configure_current_source(compliance_voltage=compliance_voltage)
        self.set_current(0.0)

    @abstractmethod
    def output_on(self) -> None: ...

    @abstractmethod
    def output_off(self) -> None: ...

    @abstractmethod
    def measure_iv(self) -> tuple[float, float]:
        """Return (current_A, voltage_V) at current source level."""
        ...

    @abstractmethod
    def identify(self) -> str:
        """Return *IDN? string."""
        ...

    def set_sense_mode(self, remote: bool) -> None:
        """Enable (True) or disable (False) 4-wire remote sensing.

        Default implementation is a no-op — subclasses override if the
        hardware supports remote sensing.
        """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write(self, cmd: str) -> None:
        self._resource.write(cmd)

    def _query(self, cmd: str) -> str:
        return self._resource.query(cmd).strip()
