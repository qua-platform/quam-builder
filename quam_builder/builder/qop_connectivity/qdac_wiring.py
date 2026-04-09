"""QDAC-II wiring helpers (quam-builder only; no QUAM fork).

QUAM resolves ``#/ports/...`` strings via :meth:`FEMPortsContainer.reference_to_port` /
:class:`OPXPlusPortsContainer`, which only understand OPX1000 / OPX+ layouts. QDAC outputs are
external to that graph, so we use a **parallel** reference root ``#/qdac/...`` plus explicit
``unit_index`` and ``port`` fields. That keeps ``wiring.json`` readable for multi-unit setups
without registering fake entries under ``machine.ports``.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from qualang_tools.wirer.instruments.instrument_channel import (
    InstrumentChannelQdac2DigitalInput,
    InstrumentChannelQdac2Output,
)

__all__ = [
    "QDAC_OUTPUT_KEY",
    "QDAC_TRIGGER_KEY",
    "qdac_analog_output_ref",
    "qdac_digital_input_ref",
    "qdac_output_wiring_entry",
    "qdac_trigger_wiring_entry",
    "extract_qdac_output_port",
    "extract_qdac_unit_index",
    "extract_qdac_trigger_port",
    "extract_qdac_trigger_unit_index",
]

QDAC_OUTPUT_KEY = "qdac_output"
QDAC_TRIGGER_KEY = "qdac_trigger"


def qdac_analog_output_ref(unit_index: int, port: int) -> str:
    """Stable JSON-pointer-style id for a QDAC DC output (not under ``#/ports``)."""
    return f"#/qdac/analog_outputs/qdac{int(unit_index)}/{int(port)}"


def qdac_digital_input_ref(unit_index: int, port: int) -> str:
    """Stable id for a QDAC external trigger input (not under ``#/ports``)."""
    return f"#/qdac/digital_inputs/qdac{int(unit_index)}/{int(port)}"


def qdac_output_wiring_entry(channel: InstrumentChannelQdac2Output) -> Dict[str, Any]:
    u, p = int(channel.con), int(channel.port)
    return {
        "unit_index": u,
        "port": p,
        "ref": qdac_analog_output_ref(u, p),
    }


def qdac_trigger_wiring_entry(channel: InstrumentChannelQdac2DigitalInput) -> Dict[str, Any]:
    u, p = int(channel.con), int(channel.port)
    return {
        "unit_index": u,
        "port": p,
        "ref": qdac_digital_input_ref(u, p),
    }


def extract_qdac_output_port(wiring_dict: Mapping[str, Any]) -> Optional[int]:
    """Analog output port (1–24) on the QDAC unit, or ``None``."""
    block = wiring_dict.get(QDAC_OUTPUT_KEY)
    if isinstance(block, Mapping):
        port = block.get("port")
        if port is not None:
            return int(port)
    legacy = wiring_dict.get("qdac_channel")
    if isinstance(legacy, int):
        return legacy
    if isinstance(legacy, Mapping) and legacy.get("port") is not None:
        return int(legacy["port"])
    return None


def extract_qdac_unit_index(wiring_dict: Mapping[str, Any]) -> Optional[int]:
    """Wirer ``con`` / QDAC unit index if present."""
    block = wiring_dict.get(QDAC_OUTPUT_KEY)
    if isinstance(block, Mapping):
        u = block.get("unit_index")
        if u is not None:
            return int(u)
    legacy = wiring_dict.get("qdac_channel")
    if isinstance(legacy, Mapping) and legacy.get("unit_index") is not None:
        return int(legacy["unit_index"])
    return None


def extract_qdac_trigger_port(wiring_dict: Mapping[str, Any]) -> Optional[int]:
    """External trigger input port (1–4), or ``None``."""
    block = wiring_dict.get(QDAC_TRIGGER_KEY)
    if isinstance(block, Mapping):
        port = block.get("port")
        if port is not None:
            return int(port)
    legacy = wiring_dict.get("qdac_trigger_in")
    if isinstance(legacy, int):
        return legacy
    return None


def extract_qdac_trigger_unit_index(wiring_dict: Mapping[str, Any]) -> Optional[int]:
    block = wiring_dict.get(QDAC_TRIGGER_KEY)
    if isinstance(block, Mapping):
        u = block.get("unit_index")
        if u is not None:
            return int(u)
    return None
