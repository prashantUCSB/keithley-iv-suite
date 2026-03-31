"""Dataclasses for sweep configuration and terminal assignment."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class MeasurementType(Enum):
    NMOS_TRANSFER = "nMOS Transfer (Id-Vgs)"
    NMOS_OUTPUT = "nMOS Output (Id-Vds)"
    RESISTOR_IV = "Resistor IV"


class TerminalRole(Enum):
    GATE = "Gate"
    DRAIN = "Drain"
    SOURCE = "Source"
    TERMINAL_1 = "Terminal 1"
    TERMINAL_2 = "Terminal 2"
    GROUND = "Ground"   # floating terminal tied to 0V


@dataclass
class TerminalAssignment:
    """Maps a terminal role to a specific SMU channel."""
    role: TerminalRole
    instrument_id: str       # e.g. "2400", "2614B"
    channel: str = ""        # "A", "B", or "" for single-channel
    grounded: bool = False   # True → skip SMU, terminal is tied to common ground

    @property
    def display(self) -> str:
        if self.grounded:
            return f"{self.role.value} → GND"
        ch = f" Ch{self.channel}" if self.channel else ""
        return f"{self.role.value} → {self.instrument_id}{ch}"


@dataclass
class SweepConfig:
    """Base sweep configuration."""
    measurement_type: MeasurementType
    label: str = ""                             # User-defined run label
    compliance_gate_A: float = 0.01             # 10 mA default gate compliance
    compliance_drain_A: float = 0.1             # 100 mA default drain compliance
    nplc: float = 1.0
    settling_delay_s: float = 0.02
    assignments: list[TerminalAssignment] = field(default_factory=list)

    def get_assignment(self, role: TerminalRole) -> Optional[TerminalAssignment]:
        for a in self.assignments:
            if a.role == role:
                return a
        return None


@dataclass
class TransferConfig(SweepConfig):
    """nMOS transfer curve: sweep Vgs, fixed Vds."""
    measurement_type: MeasurementType = MeasurementType.NMOS_TRANSFER
    vgs_start: float = -1.0
    vgs_stop: float = 3.0
    vgs_step: float = 0.05
    vds_fixed: float = 0.1

    @property
    def vgs_points(self) -> int:
        if self.vgs_step == 0:
            return 1
        return int(abs(self.vgs_stop - self.vgs_start) / abs(self.vgs_step)) + 1

    def vgs_list(self) -> list[float]:
        n = self.vgs_points
        return [
            round(self.vgs_start + i * self.vgs_step, 9)
            for i in range(n)
        ]


@dataclass
class OutputConfig(SweepConfig):
    """nMOS output curves: sweep Vds for a family of Vgs."""
    measurement_type: MeasurementType = MeasurementType.NMOS_OUTPUT
    vds_start: float = 0.0
    vds_stop: float = 3.0
    vds_step: float = 0.05
    vgs_list_values: list[float] = field(default_factory=lambda: [0.5, 1.0, 1.5, 2.0, 2.5, 3.0])

    @property
    def vds_points(self) -> int:
        if self.vds_step == 0:
            return 1
        return int(abs(self.vds_stop - self.vds_start) / abs(self.vds_step)) + 1

    def vds_list(self) -> list[float]:
        n = self.vds_points
        return [
            round(self.vds_start + i * self.vds_step, 9)
            for i in range(n)
        ]


@dataclass
class ResistorConfig(SweepConfig):
    """Resistor IV: two-terminal voltage sweep."""
    measurement_type: MeasurementType = MeasurementType.RESISTOR_IV
    v_start: float = -1.0
    v_stop: float = 1.0
    v_step: float = 0.05
    compliance_A: float = 0.1

    @property
    def v_points(self) -> int:
        if self.v_step == 0:
            return 1
        return int(abs(self.v_stop - self.v_start) / abs(self.v_step)) + 1

    def v_list(self) -> list[float]:
        n = self.v_points
        return [
            round(self.v_start + i * self.v_step, 9)
            for i in range(n)
        ]
