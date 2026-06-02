"""Add and remove ports from any QUAM machine with a ports container.

Wraps ``FEMPortsContainer`` and ``OPXPlusPortsContainer`` methods into a
uniform interface that works across all modalities (superconducting,
quantum dots, NV centers).

Example::

    from quam_builder.builder.qop_connectivity.modify_ports import add_port, remove_port

    port = add_port(machine, "mw_output", "con1", fem_id=1, port_id=3, band=1)
    remove_port(machine, "mw_output", "con1", fem_id=1, port_id=3)
"""

from typing import Optional, Protocol, Union

from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer
from quam.components.ports.base_ports import BasePort

__all__ = ["add_port", "remove_port"]

_PortsContainer = Union[FEMPortsContainer, OPXPlusPortsContainer]

_FEM_PORT_TYPES = ("mw_output", "mw_input", "analog_output", "analog_input", "digital_output")
_OPXPLUS_PORT_TYPES = ("analog_output", "analog_input", "digital_output", "digital_input")


class _HasPorts(Protocol):
    ports: Union[FEMPortsContainer, OPXPlusPortsContainer]


def _get_ports_container(machine: _HasPorts) -> _PortsContainer:
    ports = getattr(machine, "ports", None)
    if ports is None:
        raise TypeError(f"{type(machine).__name__} does not have a 'ports' attribute")
    if not isinstance(ports, (FEMPortsContainer, OPXPlusPortsContainer)):
        raise TypeError(
            f"Expected FEMPortsContainer or OPXPlusPortsContainer, " f"got {type(ports).__name__}"
        )
    return ports


def _add_fem_port(
    container: FEMPortsContainer,
    port_type: str,
    controller_id: Union[str, int],
    fem_id: int,
    port_id: int,
    **kwargs,
) -> BasePort:
    if port_type == "mw_output":
        return container.get_mw_output(controller_id, fem_id, port_id, create=True, **kwargs)
    elif port_type == "mw_input":
        return container.get_mw_input(controller_id, fem_id, port_id, create=True, **kwargs)
    elif port_type == "analog_output":
        return container.get_analog_output(controller_id, fem_id, port_id, create=True, **kwargs)
    elif port_type == "analog_input":
        return container.get_analog_input(controller_id, fem_id, port_id, create=True, **kwargs)
    elif port_type == "digital_output":
        return container.get_digital_output(controller_id, fem_id, port_id, create=True, **kwargs)
    else:
        raise ValueError(
            f"Unsupported FEM port type '{port_type}'. Expected one of: {_FEM_PORT_TYPES}"
        )


def _add_opxplus_port(
    container: OPXPlusPortsContainer,
    port_type: str,
    controller_id: Union[str, int],
    port_id: int,
    **kwargs,
) -> BasePort:
    if port_type == "analog_output":
        return container.get_analog_output(controller_id, port_id, create=True, **kwargs)
    elif port_type == "analog_input":
        return container.get_analog_input(controller_id, port_id, create=True, **kwargs)
    elif port_type == "digital_output":
        return container.get_digital_output(controller_id, port_id, create=True, **kwargs)
    elif port_type == "digital_input":
        return container.get_digital_input(controller_id, port_id, create=True, **kwargs)
    else:
        raise ValueError(
            f"Unsupported OPX+ port type '{port_type}'. Expected one of: {_OPXPLUS_PORT_TYPES}"
        )


def _remove_fem_port(
    container: FEMPortsContainer,
    port_type: str,
    controller_id: Union[str, int],
    fem_id: int,
    port_id: int,
) -> BasePort:
    if port_type == "mw_output":
        return container.mw_outputs[controller_id][fem_id].pop(port_id)
    elif port_type == "mw_input":
        return container.mw_inputs[controller_id][fem_id].pop(port_id)
    elif port_type == "analog_output":
        return container.analog_outputs[controller_id][fem_id].pop(port_id)
    elif port_type == "analog_input":
        return container.analog_inputs[controller_id][fem_id].pop(port_id)
    elif port_type == "digital_output":
        return container.digital_outputs[controller_id][fem_id].pop(port_id)
    else:
        raise ValueError(
            f"Unsupported FEM port type '{port_type}'. Expected one of: {_FEM_PORT_TYPES}"
        )


def _remove_opxplus_port(
    container: OPXPlusPortsContainer,
    port_type: str,
    controller_id: Union[str, int],
    port_id: int,
) -> BasePort:
    if port_type == "analog_output":
        return container.analog_outputs[controller_id].pop(port_id)
    elif port_type == "analog_input":
        return container.analog_inputs[controller_id].pop(port_id)
    elif port_type == "digital_output":
        return container.digital_outputs[controller_id].pop(port_id)
    elif port_type == "digital_input":
        return container.digital_inputs[controller_id].pop(port_id)
    else:
        raise ValueError(
            f"Unsupported OPX+ port type '{port_type}'. Expected one of: {_OPXPLUS_PORT_TYPES}"
        )


def add_port(
    machine: _HasPorts,
    port_type: str,
    controller_id: Union[str, int],
    fem_id: Optional[int] = None,
    port_id: Optional[int] = None,
    **kwargs,
) -> BasePort:
    """Create a port and register it in the machine's ports container.

    For FEM-based machines, ``fem_id`` and ``port_id`` are both required.
    For OPX+-based machines, only ``port_id`` is required.

    FEM port types: ("mw_output", "mw_input", "analog_output", "analog_input", "digital_output")
    OPX+ port types: ("analog_output", "analog_input", "digital_output", "digital_input")

    Args:
        machine: A QUAM machine with a ``ports`` attribute (``FEMPortsContainer``
            or ``OPXPlusPortsContainer``).
        port_type: Port kind e.g. ``"mw_output"``, ``"analog_input"``.
        controller_id: Controller identifier (e.g. ``"con1"``).
        fem_id: FEM slot number. Required for FEM containers.
        port_id: Port number on the FEM or controller.
        **kwargs: Forwarded to the port constructor (e.g. ``band=1``).

    Returns:
        The newly created (or already existing) port.

    Raises:
        TypeError: If ``machine`` has no supported ports container.
        ValueError: If required identifiers are missing or ``port_type``
            is not recognised by the container.
    """
    container = _get_ports_container(machine)

    if isinstance(container, FEMPortsContainer):
        if fem_id is None or port_id is None:
            raise ValueError("FEM ports require both fem_id and port_id")
        return _add_fem_port(container, port_type, controller_id, fem_id, port_id, **kwargs)
    else:
        if port_id is None:
            raise ValueError("OPX+ ports require port_id")
        return _add_opxplus_port(container, port_type, controller_id, port_id, **kwargs)


def remove_port(
    machine: _HasPorts,
    port_type: str,
    controller_id: Union[str, int],
    fem_id: Optional[int] = None,
    port_id: Optional[int] = None,
) -> BasePort:
    """Remove a port from the machine's ports container.

    FEM port types: ("mw_output", "mw_input", "analog_output", "analog_input", "digital_output")
    OPX+ port types: ("analog_output", "analog_input", "digital_output", "digital_input")

    Args:
        machine: A QUAM machine with a ``ports`` attribute.
        port_type: Port kind e.g. ``"mw_output"``, ``"analog_input"``.
        controller_id: Controller identifier.
        fem_id: FEM slot number. Required for FEM containers.
        port_id: Port number.

    Returns:
        The removed port.

    Raises:
        TypeError: If ``machine`` has no supported ports container.
        KeyError: If the specified port does not exist.
        ValueError: If required identifiers are missing or ``port_type``
            is not recognised by the container.
    """
    container = _get_ports_container(machine)

    if isinstance(container, FEMPortsContainer):
        if fem_id is None or port_id is None:
            raise ValueError("FEM ports require both fem_id and port_id")
        removed = _remove_fem_port(container, port_type, controller_id, fem_id, port_id)
    else:
        if port_id is None:
            raise ValueError("OPX+ ports require port_id")
        removed = _remove_opxplus_port(container, port_type, controller_id, port_id)

    removed.parent = None
    return removed
