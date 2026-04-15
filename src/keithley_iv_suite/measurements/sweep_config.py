"""Dataclasses for sweep configuration and terminal assignment."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class MeasurementType(Enum):
    NMOS_TRANSFER    = "nMOS Transfer (Id-Vgs)"
    NMOS_OUTPUT      = "nMOS Output (Id-Vds)"
    RESISTOR_IV      = "Resistor IV"
    VAN_DER_PAUW     = "Van der Pauw (Rs)"
    HALL_BAR         = "Hall Bar (Rxy, n, µ)"
    GENERIC_4PORT    = "Generic 4-Port"
    FOUR_POINT_PROBE = "Four-Point Probe (Rs)"
    PHOTODIODE_IV    = "Photodiode IV"


class TerminalRole(Enum):
    # MOSFET
    GATE       = "Gate"
    DRAIN      = "Drain"
    SOURCE     = "Source"
    # Resistor / 2-terminal
    TERMINAL_1 = "Terminal 1"
    TERMINAL_2 = "Terminal 2"
    # Van der Pauw / Hall bar current path
    I_PLUS     = "I+"
    I_MINUS    = "I-"
    # Van der Pauw / Hall bar voltage sense
    V_PLUS     = "V+"
    V_MINUS    = "V-"
    # Hall bar extra sense pair
    V_HALL_PLUS  = "V_Hall+"
    V_HALL_MINUS = "V_Hall-"
    # Generic 4-port
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    # Common
    GROUND = "Ground"


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
    source_delay_s: float = 0.0          # hardware-side source delay (s); 0 = use auto/default
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
    # Range controls — None means hardware auto-range
    drain_sense_range_A: Optional[float] = None   # drain current measurement range
    gate_sense_range_A: Optional[float] = None    # gate current measurement range
    source_range_V: Optional[float] = None        # voltage source range (gate + drain)

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
    # Range controls
    drain_sense_range_A: Optional[float] = None
    gate_sense_range_A: Optional[float] = None
    source_range_V: Optional[float] = None

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
    # Range controls
    sense_range_A: Optional[float] = None
    source_range_V: Optional[float] = None

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


@dataclass
class VanDerPauwConfig(SweepConfig):
    """Van der Pauw sheet-resistance measurement.

    One SMU sweeps current (I+ → I−), a second SMU acts as voltmeter (V+/V−).
    Run twice (use 'Overlay runs') for the two reciprocal probe configurations,
    then compute Rs via the van der Pauw equation.
    """
    measurement_type: MeasurementType = MeasurementType.VAN_DER_PAUW
    i_start: float = -1e-5      # A  (−10 µA)
    i_stop:  float =  1e-5      # A  (+10 µA)
    i_step:  float =  1e-6      # A  (1 µA)
    compliance_V: float = 10.0
    thickness_m: Optional[float] = None   # sample thickness for ρ calculation
    # Range controls
    source_range_A: Optional[float] = None   # current source range
    sense_range_V: Optional[float] = None    # voltage measurement range

    @property
    def i_points(self) -> int:
        if self.i_step == 0:
            return 1
        return int(abs(self.i_stop - self.i_start) / abs(self.i_step)) + 1

    def i_list(self) -> list[float]:
        n = self.i_points
        return [round(self.i_start + k * self.i_step, 15) for k in range(n)]


@dataclass
class HallBarConfig(SweepConfig):
    """Hall bar longitudinal + Hall resistance measurement.

    SMU_I sweeps current (−I_max → +I_max); SMU_V acts as voltmeter on the
    transverse (Hall) contacts.  The current-source channel's own voltage
    readback gives the longitudinal (2-probe) resistance.

    Both R_xx (longitudinal) and R_xy (Hall) are plotted as two curves.
    R_H, sheet carrier density n_s, and Hall mobility µ_H are computed
    post-sweep from the fitted slopes.
    """
    measurement_type: MeasurementType = MeasurementType.HALL_BAR
    i_start: float = -1e-5      # A
    i_stop:  float =  1e-5      # A
    i_step:  float =  1e-6      # A
    compliance_V: float = 10.0
    b_field_T: float = 0.0      # magnetic field (T) — set manually on magnet
    thickness_m: Optional[float] = None   # for ρ calculation
    # Range controls
    source_range_A: Optional[float] = None
    sense_range_V: Optional[float] = None

    @property
    def i_points(self) -> int:
        if self.i_step == 0:
            return 1
        return int(abs(self.i_stop - self.i_start) / abs(self.i_step)) + 1

    def i_list(self) -> list[float]:
        n = self.i_points
        return [round(self.i_start + k * self.i_step, 15) for k in range(n)]


@dataclass
class Generic4PortConfig(SweepConfig):
    """Generic 4-terminal voltage sweep.

    T1 is swept; T2, T3 are held at fixed bias; T4 is grounded.
    Measures I at T1.  Use for any device whose port semantics don't
    match the labelled MOSFET / resistor / VdP tabs.
    """
    measurement_type: MeasurementType = MeasurementType.GENERIC_4PORT
    v_start: float = 0.0
    v_stop:  float = 1.0
    v_step:  float = 0.05
    compliance_A: float = 0.1
    # Fixed biases on secondary terminals (NaN = leave floating / unconnected)
    v_t2_bias: float = 0.0
    v_t3_bias: float = 0.0
    comp_t2_A: float = 0.01
    comp_t3_A: float = 0.01
    # Range controls
    sense_range_A: Optional[float] = None
    source_range_V: Optional[float] = None

    @property
    def v_points(self) -> int:
        if self.v_step == 0:
            return 1
        return int(abs(self.v_stop - self.v_start) / abs(self.v_step)) + 1

    def v_list(self) -> list[float]:
        n = self.v_points
        return [round(self.v_start + k * self.v_step, 9) for k in range(n)]


@dataclass
class FourPointProbeConfig(SweepConfig):
    """Collinear four-point probe sheet-resistance measurement.

    Probe layout (Valdes / Smits geometry):
        [1] → I+    outer probe, sources current
        [2] → V+    inner probe, senses voltage
        [3] → V−    inner probe, senses voltage
        [4] → I−    outer probe, sinks current

    Sheet resistance  Rs = (π / ln 2) × (V / I) × F_correction  [Ω/□]
    Resistivity       ρ  = Rs × thickness_m                       [Ω·m]

    Measurement:  current is swept symmetrically (−I_max → +I_max) and V
    is recorded by a second SMU acting as voltmeter (forces 0 A).  A linear
    fit to V vs I gives R_transfer = slope; Rs is then computed from the
    formula above.  The swept approach gives a reliable R² quality indicator
    and is robust against thermoelectric offsets.

    Probe and geometry notes
    -------------------------
    Signatone SP4 (standard collinear head):
        s = 1.016 mm  (40 mil / 1.016 mm equally-spaced probes)

    Correction factor F:
        F = 1.000   semi-infinite plane  (sample ≫ probe spacing)
        F < 1.000   finite sample        (use Smits 1958 table or enter manually)
        For a 150 mm wafer with s = 1.016 mm: d/s ≈ 148 → F ≈ 1.000
        For a  10 mm square chip with s = 1.016 mm: d/s ≈ 9.8 → F ≈ 0.98

    Suggested current ranges by expected Rs:
        Rs < 10 Ω/□      (metals, silicides)      →  I = 10–100 mA
        Rs 10–1000 Ω/□   (ITO, doped Si, TCO)     →  I = 1–10 mA
        Rs 1–100 kΩ/□    (lightly doped Si, SiC)  →  I = 100 µA – 1 mA
        Rs > 100 kΩ/□    (semi-insulating)         →  I = 1–100 µA
    """
    measurement_type: MeasurementType = MeasurementType.FOUR_POINT_PROBE

    # Current sweep — default ±10 µA (safe for most thin films / doped wafers)
    i_start: float = -1e-5      # A  (−10 µA)
    i_stop:  float =  1e-5      # A  (+10 µA)
    i_step:  float =  1e-6      # A  (1 µA step → 21 points)
    compliance_V: float = 10.0  # V  (voltage compliance on both SMUs)
    # Range controls
    source_range_A: Optional[float] = None
    sense_range_V: Optional[float] = None

    # Probe geometry
    probe_spacing_m: float = 1.016e-3   # m  (SP4 standard: 40 mil = 1.016 mm)

    # Geometric correction factor F (Smits 1958)
    #   1.0 → semi-infinite plane (default, valid when sample ≫ s)
    correction_F: float = 1.0

    # Sample thickness (optional) — used only to compute ρ = Rs × t
    thickness_m: Optional[float] = None

    @property
    def i_points(self) -> int:
        if self.i_step == 0:
            return 1
        return int(abs(self.i_stop - self.i_start) / abs(self.i_step)) + 1

    def i_list(self) -> list[float]:
        n = self.i_points
        return [round(self.i_start + k * self.i_step, 15) for k in range(n)]


@dataclass
class PhotodiodeConfig(SweepConfig):
    """Photodiode IV: two-terminal voltage sweep from reverse to forward bias.

    Anode is driven by the SMU; cathode is grounded.
    Reverse bias reveals dark current / leakage; forward bias shows
    the exponential diode turn-on and allows ideality-factor extraction.
    """
    measurement_type: MeasurementType = MeasurementType.PHOTODIODE_IV
    v_start: float = -5.0       # V  (reverse bias)
    v_stop:  float = 1.5        # V  (past forward turn-on ~0.6–1.2 V)
    v_step:  float = 0.05       # V
    compliance_A: float = 0.1   # A  (protect device in forward bias)
    # Range controls
    sense_range_A: Optional[float] = None
    source_range_V: Optional[float] = None

    @property
    def v_points(self) -> int:
        if self.v_step == 0:
            return 1
        return int(abs(self.v_stop - self.v_start) / abs(self.v_step)) + 1

    def v_list(self) -> list[float]:
        n = self.v_points
        return [round(self.v_start + i * self.v_step, 9) for i in range(n)]
