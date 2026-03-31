"""Load measurement recipes from YAML or JSON files."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from .sweep_config import (
    MeasurementType,
    OutputConfig,
    ResistorConfig,
    TerminalAssignment,
    TerminalRole,
    TransferConfig,
)

log = logging.getLogger(__name__)

_TYPE_MAP = {
    "nmos_transfer": MeasurementType.NMOS_TRANSFER,
    "nmos_output": MeasurementType.NMOS_OUTPUT,
    "resistor_iv": MeasurementType.RESISTOR_IV,
}

_ROLE_MAP = {
    "gate": TerminalRole.GATE,
    "drain": TerminalRole.DRAIN,
    "source": TerminalRole.SOURCE,
    "terminal_1": TerminalRole.TERMINAL_1,
    "terminal_2": TerminalRole.TERMINAL_2,
    "ground": TerminalRole.GROUND,
}


def load_recipe(path: str | Path) -> list:
    """
    Parse a YAML or JSON recipe file and return a list of sweep config objects.

    Each entry in the returned list is a TransferConfig, OutputConfig, or ResistorConfig.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Recipe not found: {path}")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported recipe format: {path.suffix}")

    measurements = data.get("measurements", [data] if "type" in data else [])
    configs = []
    for entry in measurements:
        cfg = _parse_entry(entry)
        if cfg is not None:
            configs.append(cfg)
    log.info("Loaded %d measurement(s) from %s", len(configs), path.name)
    return configs


def _parse_entry(entry: dict[str, Any]):
    mtype_key = entry.get("type", "").lower()
    mtype = _TYPE_MAP.get(mtype_key)
    if mtype is None:
        log.warning("Unknown measurement type '%s', skipping", mtype_key)
        return None

    assignments = _parse_assignments(entry.get("assignments", {}))
    common = dict(
        label=entry.get("label", ""),
        compliance_gate_A=float(entry.get("compliance_gate_A", 0.01)),
        compliance_drain_A=float(entry.get("compliance_drain_A", 0.1)),
        nplc=float(entry.get("nplc", 1.0)),
        settling_delay_s=float(entry.get("settling_delay_s", 0.02)),
        assignments=assignments,
    )

    if mtype == MeasurementType.NMOS_TRANSFER:
        return TransferConfig(
            **common,
            vgs_start=float(entry.get("vgs_start", -1.0)),
            vgs_stop=float(entry.get("vgs_stop", 3.0)),
            vgs_step=float(entry.get("vgs_step", 0.05)),
            vds_fixed=float(entry.get("vds_fixed", 0.1)),
        )
    if mtype == MeasurementType.NMOS_OUTPUT:
        return OutputConfig(
            **common,
            vds_start=float(entry.get("vds_start", 0.0)),
            vds_stop=float(entry.get("vds_stop", 3.0)),
            vds_step=float(entry.get("vds_step", 0.05)),
            vgs_list_values=[float(v) for v in entry.get("vgs_list", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0])],
        )
    if mtype == MeasurementType.RESISTOR_IV:
        return ResistorConfig(
            **common,
            v_start=float(entry.get("v_start", -1.0)),
            v_stop=float(entry.get("v_stop", 1.0)),
            v_step=float(entry.get("v_step", 0.05)),
            compliance_A=float(entry.get("compliance_A", 0.1)),
        )
    return None


def _parse_assignments(raw: dict) -> list[TerminalAssignment]:
    result = []
    for role_key, spec in raw.items():
        role = _ROLE_MAP.get(role_key.lower())
        if role is None:
            continue
        if isinstance(spec, str) and spec.lower() == "gnd":
            result.append(TerminalAssignment(role=role, instrument_id="GND", grounded=True))
        elif isinstance(spec, dict):
            result.append(TerminalAssignment(
                role=role,
                instrument_id=str(spec.get("instrument", "")),
                channel=str(spec.get("channel", "")),
                grounded=bool(spec.get("grounded", False)),
            ))
    return result
