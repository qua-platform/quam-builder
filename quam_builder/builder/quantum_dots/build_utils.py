import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from numpy import ceil, sqrt
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorSingle,
    VoltageGate,
)
from quam_builder.architecture.superconducting.qpu import AnyQuam
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_out_channel_ports,
    mw_out_channel_ports,
)
from quam.components import StickyChannelAddon, pulses

DEFAULT_GATE_SET_ID = "main_qpu"
DEFAULT_STICKY_DURATION = 16
DEFAULT_INTERMEDIATE_FREQUENCY = 500e6
DEFAULT_READOUT_LENGTH = 200
DEFAULT_READOUT_AMPLITUDE = 0.01

_ELEMENT_TYPE_ALIASES = {
    "globals": "globals",
    "global_gates": "globals",
    "readout": "readout",
    "sensor_dots": "readout",
    "qubits": "qubits",
    "qubit_pairs": "qubit_pairs",
}

_ALLOWED_LINE_TYPES = {
    "readout": {WiringLineType.SENSOR_GATE.value, WiringLineType.RF_RESONATOR.value},
    "qubits": {WiringLineType.DRIVE.value, WiringLineType.PLUNGER_GATE.value},
    "qubit_pairs": {WiringLineType.BARRIER_GATE.value},
}


def _natural_sort_key(value: str) -> Tuple[Any, ...]:
    match = re.match(r"(.*?)(\d+)$", value)
    if match:
        prefix, number = match.groups()
        return (prefix, int(number))
    return (value, 0)


def _sorted_items(mapping: Mapping[str, Any]) -> Iterable[Tuple[str, Any]]:
    for key in sorted(mapping, key=_natural_sort_key):
        yield key, mapping[key]


def _normalize_element_type(element_type: str) -> str:
    try:
        return _ELEMENT_TYPE_ALIASES[element_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported element type '{element_type}' in wiring") from exc


def _validate_line_type(element_type: str, line_type: str) -> None:
    allowed = _ALLOWED_LINE_TYPES.get(element_type)
    if allowed is not None and line_type not in allowed:
        raise ValueError(
            f"Unsupported line type '{line_type}' for element type '{element_type}'. "
            f"Allowed: {sorted(allowed)}"
        )


def _set_default_grid_location(qubit_number: int, total_number_of_qubits: int) -> str:
    """Sets a simple grid layout for visualization/placement."""

    if total_number_of_qubits <= 0:
        raise ValueError("total_number_of_qubits must be positive")

    number_of_rows = int(ceil(sqrt(total_number_of_qubits)))
    y = qubit_number % number_of_rows
    x = qubit_number // number_of_rows
    return f"{x},{y}"


def _make_sticky_channel() -> StickyChannelAddon:
    return StickyChannelAddon(duration=DEFAULT_STICKY_DURATION, digital=False)


def _make_voltage_gate(gate_id: str, wiring_path: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=f"{wiring_path}/opx_output",
        sticky=_make_sticky_channel(),
    )


def _make_resonator(sensor_id: str, wiring_path: str, resonator_cls: Any) -> ReadoutResonatorSingle:
    return resonator_cls(
        id=f"{sensor_id}_resonator",
        frequency_bare=0,
        intermediate_frequency=DEFAULT_INTERMEDIATE_FREQUENCY,
        operations={
            "readout": pulses.SquareReadoutPulse(
                length=DEFAULT_READOUT_LENGTH, id="readout", amplitude=DEFAULT_READOUT_AMPLITUDE
            )
        },
        opx_output=f"{wiring_path}/opx_output",
        opx_input=f"{wiring_path}/opx_input",
        sticky=_make_sticky_channel(),
    )


def _validate_drive_ports(qubit_id: str, ports: Mapping[str, Any]) -> str:
    has_iq = all(key in ports for key in iq_out_channel_ports)
    has_mw = all(key in ports for key in mw_out_channel_ports)

    if has_iq and has_mw:
        raise ValueError(f"Qubit {qubit_id} wiring is ambiguous: matches both IQ and MW drive ports")
    if not has_iq and not has_mw:
        raise ValueError(
            f"Qubit {qubit_id} wiring is incomplete: missing IQ ports {iq_out_channel_ports} "
            f"and MW ports {mw_out_channel_ports}"
        )
    return "IQ" if has_iq else "MW"


def _build_virtual_mapping(
    prefix: str, channels: Sequence[VoltageGate]
) -> Tuple[Dict[str, VoltageGate], Dict[str, str]]:
    virtual_to_channel: Dict[str, VoltageGate] = {}
    physical_to_virtual: Dict[str, str] = {}

    for index, channel in enumerate(channels, start=1):
        virtual_name = f"{prefix}_{index}"
        virtual_to_channel[virtual_name] = channel
        physical_to_virtual[channel.id] = virtual_name

    return virtual_to_channel, physical_to_virtual


def _parse_qubit_pair_ids(qubit_pair_id: str) -> Tuple[str, str]:
    if "-" in qubit_pair_id:
        control, target = qubit_pair_id.split("-", 1)
    elif "_" in qubit_pair_id:
        control, target = qubit_pair_id.split("_", 1)
    else:
        raise ValueError(
            f"Qubit pair id '{qubit_pair_id}' is invalid: expected '-' or '_' delimiter"
        )
    def _ensure_q_prefix(qubit_token: str) -> str:
        return qubit_token if qubit_token.startswith("q") else f"q{qubit_token}"

    control = _ensure_q_prefix(control)
    target = _ensure_q_prefix(target)
    return control, target


__all__ = [
    "DEFAULT_GATE_SET_ID",
    "DEFAULT_STICKY_DURATION",
    "DEFAULT_INTERMEDIATE_FREQUENCY",
    "DEFAULT_READOUT_LENGTH",
    "DEFAULT_READOUT_AMPLITUDE",
    "_natural_sort_key",
    "_sorted_items",
    "_normalize_element_type",
    "_validate_line_type",
    "_set_default_grid_location",
    "_make_sticky_channel",
    "_make_voltage_gate",
    "_make_resonator",
    "_validate_drive_ports",
    "_build_virtual_mapping",
    "_parse_qubit_pair_ids",
]
