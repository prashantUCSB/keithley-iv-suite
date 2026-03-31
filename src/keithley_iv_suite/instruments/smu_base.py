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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write(self, cmd: str) -> None:
        self._resource.write(cmd)

    def _query(self, cmd: str) -> str:
        return self._resource.query(cmd).strip()
