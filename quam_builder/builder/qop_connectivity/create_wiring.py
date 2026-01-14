"""
Wiring generation for quantum computing configurations.

This module provides functions for generating QUAM-compatible wiring configurations
from connectivity specifications. It uses a strategy pattern for handling different
element types (qubits, qubit pairs, global elements, readout).

The main entry point is create_wiring() which maintains backward compatibility
while using the new extensible architecture internally.
"""

from typing import List, Dict, Any, Optional
from functools import reduce
from qualang_tools.wirer import Connectivity
from qualang_tools.wirer.connectivity.element import (
    QubitPairReference,
    QubitReference,
    Reference,
    ElementId,
)
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from qualang_tools.wirer.instruments.instrument_channel import AnyInstrumentChannel

from quam_builder.builder.qop_connectivity.create_analog_ports import (
    create_octave_port,
    create_mw_fem_port,
    create_lf_opx_plus_port,
    create_external_mixer_reference,
)
from quam_builder.builder.qop_connectivity.create_digital_ports import (
    create_digital_output_port,
)
from quam_builder.builder.qop_connectivity.paths import *

# Import new architecture components
from quam_builder.builder.qop_connectivity.wiring_generator import WiringGenerator
from quam_builder.builder.qop_connectivity.line_type_registry import LineTypeRegistry
from quam_builder.builder.qop_connectivity.channel_port_factory import ChannelPortFactory
from quam_builder.builder.qop_connectivity.utils import set_nested_value_with_path


def create_wiring(
    connectivity: Connectivity,
    use_legacy: bool = False,
    custom_registry: Optional[LineTypeRegistry] = None,
    custom_port_factory: Optional[ChannelPortFactory] = None,
) -> dict:
    """Generates a dictionary containing QUAM-compatible JSON references.

    This is the main public API for wiring generation. It uses the new
    extensible architecture by default, with an option to fall back to
    the legacy implementation for compatibility testing.

    Args:
        connectivity: The connectivity configuration containing quantum elements
                     and their associated instrument channels
        use_legacy: If True, uses the old implementation (for testing/comparison).
                   Default is False (use new architecture).
        custom_registry: Optional custom LineTypeRegistry for extending/modifying
                        line type to element category mappings
        custom_port_factory: Optional custom ChannelPortFactory for adding
                            support for custom instrument types

    Returns:
        Dictionary containing QUAM-compatible JSON references organized by:
        - Element type (qubits, qubit_pairs, globals, readout)
        - Element ID (q0, q1_q2, etc.)
        - Line type (drive, flux, coupler, etc.)
        - Port keys (opx_output, opx_input, etc.)

    Raises:
        ValueError: If an unknown line type is encountered

    Example:
        # >>> connectivity = Connectivity(...)
        # >>> wiring = create_wiring(connectivity)
        # >>> # Result:
        # >>> # {
        # >>> #     "qubits": {
        # >>> #         "q0": {
        # >>> #             "drive": {"opx_output": "#/ports/port1"},
        # >>> #             "flux": {...}
        # >>> #         }
        # >>> #     },
        # >>> #     ...
        # >>> # }
    """
    if use_legacy:
        # Use legacy implementation for backward compatibility testing
        return _create_wiring_legacy(connectivity)

    # Use new architecture
    generator = WiringGenerator(custom_registry, custom_port_factory)
    return generator.generate(connectivity)


# ============================================================================
# LEGACY IMPLEMENTATION (kept for backward compatibility testing)
# ============================================================================


def _create_wiring_legacy(connectivity: Connectivity) -> dict:
    """Legacy implementation of create_wiring.

    This function is kept for backward compatibility testing and validation.
    It should produce identical results to the new implementation.

    Args:
        connectivity: The connectivity configuration

    Returns:
        Dictionary containing QUAM-compatible JSON references

    Raises:
        ValueError: If an unknown line type is encountered
    """
    wiring = {}
    for element_id, element in connectivity.elements.items():
        for line_type, channels in element.channels.items():
            # Get the string value for comparison (works with both WiringLineType)
            line_type_value = line_type.value if hasattr(line_type, "value") else line_type

            if line_type_value in [
                WiringLineType.RESONATOR.value,
                WiringLineType.DRIVE.value,
                WiringLineType.FLUX.value,
                WiringLineType.PLUNGER.value,
            ]:
                for k, v in qubit_wiring(channels, element_id, line_type).items():
                    set_nested_value_with_path(
                        wiring, f"qubits/{element_id}/{line_type_value}/{k}", v
                    )

            elif line_type_value in [
                WiringLineType.COUPLER.value,
                WiringLineType.CROSS_RESONANCE.value,
                WiringLineType.ZZ_DRIVE.value,
                WiringLineType.BARRIER.value,
            ]:
                for k, v in qubit_pair_wiring(channels, element_id).items():
                    set_nested_value_with_path(
                        wiring, f"qubit_pairs/{element_id}/{line_type_value}/{k}", v
                    )

            elif line_type_value in [
                WiringLineType.GLOBAL_GATE.value,
            ]:
                for k, v in global_element_wiring(channels, element_id, line_type).items():
                    set_nested_value_with_path(
                        wiring, f"globals/{element_id}/{line_type_value}/{k}", v
                    )
            elif line_type_value in [
                WiringLineType.SENSOR_GATE.value,
                WiringLineType.RF_RESONATOR.value,
            ]:
                for k, v in readout_wiring(channels, element_id, line_type).items():
                    set_nested_value_with_path(
                        wiring, f"readout/{element_id}/{line_type_value}/{k}", v
                    )
            else:
                raise ValueError(f"Unknown line type {line_type}")

    return wiring


def readout_wiring(
    channels: List[AnyInstrumentChannel],
    element_id: ElementId,
    line_type: WiringLineType,
) -> dict:
    qubit_line_wiring = {}
    for channel in channels:
        if channel.instrument_id == "external-mixer":
            key, reference = create_external_mixer_reference(channel, element_id, line_type)
            qubit_line_wiring[key] = reference
        elif not (channel.signal_type == "digital" and channel.io_type == "input"):
            key, reference = get_channel_port(channel, channels)
            qubit_line_wiring[key] = reference

    return qubit_line_wiring


def global_element_wiring(
    channels: List[AnyInstrumentChannel],
    element_id: ElementId,
    line_type: WiringLineType,
) -> dict:
    qubit_line_wiring = {}
    for channel in channels:
        if channel.instrument_id == "external-mixer":
            key, reference = create_external_mixer_reference(channel, element_id, line_type)
            qubit_line_wiring[key] = reference
        elif not (channel.signal_type == "digital" and channel.io_type == "input"):
            key, reference = get_channel_port(channel, channels)
            qubit_line_wiring[key] = reference

    return qubit_line_wiring


def qubit_wiring(
    channels: List[AnyInstrumentChannel],
    element_id: QubitReference,
    line_type: WiringLineType,
) -> dict:
    """Generates a dictionary containing QUAM-compatible JSON references for a list of channels from a single qubit and the same line type.

    Args:
        channels (List[AnyInstrumentChannel]): The list of instrument channels.
        element_id (QubitReference): The ID of the qubit element.
        line_type (WiringLineType): The type of wiring line.

    Returns:
        dict: A dictionary containing QUAM-compatible JSON references.
    """
    qubit_line_wiring = {}
    for channel in channels:
        if channel.instrument_id == "external-mixer":
            key, reference = create_external_mixer_reference(channel, element_id, line_type)
            qubit_line_wiring[key] = reference
        elif not (channel.signal_type == "digital" and channel.io_type == "input"):
            key, reference = get_channel_port(channel, channels)
            qubit_line_wiring[key] = reference

    return qubit_line_wiring


def qubit_pair_wiring(channels: List[AnyInstrumentChannel], element_id: QubitPairReference) -> dict:
    """Generates a dictionary containing QUAM-compatible JSON references for a list of channels from a single qubit pair and the same line type.

    Args:
        channels (List[AnyInstrumentChannel]): The list of instrument channels.
        element_id (QubitPairReference): The ID of the qubit pair element.

    Returns:
        dict: A dictionary containing QUAM-compatible JSON references.
    """
    qubit_pair_line_wiring = {
        "control_qubit": f"{QUBITS_BASE_JSON_PATH}/q{element_id.control_index}",
        "target_qubit": f"{QUBITS_BASE_JSON_PATH}/q{element_id.target_index}",
    }
    for channel in channels:
        if not (channel.signal_type == "digital" and channel.io_type == "input"):
            key, reference = get_channel_port(channel, channels)
            qubit_pair_line_wiring[key] = reference

    return qubit_pair_line_wiring


def get_channel_port(channel: AnyInstrumentChannel, channels: List[AnyInstrumentChannel]) -> tuple:
    """Determines the key and JSON reference for a given channel.

    Args:
        channel (AnyInstrumentChannel): The instrument channel for which the reference is created.
        channels (List[AnyInstrumentChannel]): A list of all instrument channels.

    Returns:
        tuple: A tuple containing the key and the JSON reference.

    Raises:
        ValueError: If the instrument type is unknown.
    """
    if channel.signal_type == "digital":
        key, reference = create_digital_output_port(channel)
    else:
        if channel.instrument_id == "octave":
            key, reference = create_octave_port(channel)
        elif channel.instrument_id == "mw-fem":
            key, reference = create_mw_fem_port(channel)
        elif channel.instrument_id in ["lf-fem", "opx+"]:
            key, reference = create_lf_opx_plus_port(channel, channels)
        else:
            raise ValueError(f"Unknown instrument type {channel.instrument_id}")

    return key, reference
