"""Utility functions and constants for building quantum dot QPU configurations.

This module provides helper functions for:
- Natural sorting of quantum element IDs
- Validation of wiring types and line types
- Creation of voltage gates, resonators, and sticky channels
- Grid layout calculations
- Virtual gate mapping
- Qubit pair ID parsing
"""

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

# Default configuration constants for quantum dot systems
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
    """Generate a sort key that handles numeric suffixes naturally.

    Enables sorting like ['q1', 'q2', 'q10'] instead of ['q1', 'q10', 'q2'].

    Args:
        value: String to generate sort key for.

    Returns:
        Tuple containing prefix string and numeric suffix for natural sorting.
    """
    match = re.match(r"(.*?)(\d+)$", value)
    if match:
        prefix, number = match.groups()
        return (prefix, int(number))
    return (value, 0)


def _sorted_items(mapping: Mapping[str, Any]) -> Iterable[Tuple[str, Any]]:
    """Iterate over mapping items in natural sort order.

    Args:
        mapping: Dictionary to iterate over.

    Yields:
        Key-value pairs in naturally sorted order by key.
    """
    for key in sorted(mapping, key=_natural_sort_key):
        yield key, mapping[key]


def _normalize_element_type(element_type: str) -> str:
    """Normalize element type aliases to canonical names.

    Maps various element type names (e.g., 'global_gates', 'sensor_dots') to their
    canonical forms ('globals', 'readout').

    Args:
        element_type: Element type string to normalize.

    Returns:
        Canonical element type name.

    Raises:
        ValueError: If element type is not recognized.
    """
    try:
        return _ELEMENT_TYPE_ALIASES[element_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported element type '{element_type}' in wiring") from exc


def _validate_line_type(element_type: str, line_type: str) -> None:
    """Validate that a line type is allowed for the given element type.

    Args:
        element_type: The element type (e.g., 'qubits', 'readout').
        line_type: The line type to validate (e.g., 'drive', 'sensor_gate').

    Raises:
        ValueError: If line type is not allowed for the element type.
    """
    allowed = _ALLOWED_LINE_TYPES.get(element_type)
    if allowed is not None and line_type not in allowed:
        raise ValueError(
            f"Unsupported line type '{line_type}' for element type '{element_type}'. "
            f"Allowed: {sorted(allowed)}"
        )


def _set_default_grid_location(qubit_number: int, total_number_of_qubits: int) -> str:
    """Calculate grid coordinates for qubit layout in square grid pattern.

    Arranges qubits in a square-like grid for visualization purposes.

    Args:
        qubit_number: Zero-indexed qubit number.
        total_number_of_qubits: Total number of qubits in the system.

    Returns:
        Grid location string in format "x,y".

    Raises:
        ValueError: If total_number_of_qubits is not positive.
    """
    if total_number_of_qubits <= 0:
        raise ValueError("total_number_of_qubits must be positive")

    number_of_rows = int(ceil(sqrt(total_number_of_qubits)))
    y = qubit_number % number_of_rows
    x = qubit_number // number_of_rows
    return f"{x},{y}"


def _make_sticky_channel() -> StickyChannelAddon:
    """Create a sticky channel addon with default duration.

    Returns:
        StickyChannelAddon configured with DEFAULT_STICKY_DURATION.
    """
    return StickyChannelAddon(duration=DEFAULT_STICKY_DURATION, digital=False)


def _make_voltage_gate(gate_id: str, wiring_path: str) -> VoltageGate:
    """Create a voltage gate component with sticky channel.

    Args:
        gate_id: Identifier for the gate.
        wiring_path: JSON path to wiring configuration.

    Returns:
        Configured VoltageGate instance.
    """
    return VoltageGate(
        id=gate_id,
        opx_output=f"{wiring_path}/opx_output",
        sticky=_make_sticky_channel(),
    )


def _make_resonator(sensor_id: str, wiring_path: str, resonator_cls: Any) -> ReadoutResonatorSingle:
    """Create a readout resonator with default configuration and readout pulse.

    Args:
        sensor_id: Identifier for the sensor dot.
        wiring_path: JSON path to wiring configuration.
        resonator_cls: Resonator class to instantiate.

    Returns:
        Configured resonator instance with default readout pulse.
    """
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
    """Validate qubit drive port configuration and determine drive type.

    Args:
        qubit_id: Identifier of the qubit being validated.
        ports: Port configuration mapping.

    Returns:
        Drive type string: "IQ" for IQ mixing or "MW" for microwave.

    Raises:
        ValueError: If port configuration is ambiguous or incomplete.
    """
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
    """Build bidirectional mapping between virtual names and physical channels.

    Args:
        prefix: Prefix for virtual channel names (e.g., 'virtual_dot').
        channels: Sequence of physical voltage gate channels.

    Returns:
        Tuple of (virtual_to_channel, physical_to_virtual) mappings.
    """
    virtual_to_channel: Dict[str, VoltageGate] = {}
    physical_to_virtual: Dict[str, str] = {}

    for index, channel in enumerate(channels, start=1):
        virtual_name = f"{prefix}_{index}"
        virtual_to_channel[virtual_name] = channel
        physical_to_virtual[channel.id] = virtual_name

    return virtual_to_channel, physical_to_virtual


def _parse_qubit_pair_ids(qubit_pair_id: str) -> Tuple[str, str]:
    """Parse qubit pair identifier into control and target qubit names.

    Accepts formats: 'q1_q2', 'q1-q2', '1_2', '1-2'.

    Args:
        qubit_pair_id: Pair identifier string.

    Returns:
        Tuple of (control_qubit_name, target_qubit_name) with 'q' prefix.

    Raises:
        ValueError: If pair ID format is invalid.
    """
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
