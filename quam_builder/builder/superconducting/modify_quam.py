"""Add and remove qubits and channels from an existing superconducting QUAM.

Reuses the same atomic component adders that ``build_quam()`` uses, so
incrementally-added objects are identical to batch-built ones.

Line type keys match ``WiringLineType`` enum values: ``"xy"`` (drive),
``"rr"`` (resonator), ``"z"`` (flux).

Example::

    from quam_builder.builder.superconducting.modify_quam import (
        add_qubit, remove_qubit, add_channel, remove_channel,
    )

    add_qubit(
        machine,
        qubit_id="q5",
        wiring={
            "xy": {"opx_output": "#/ports/mw_outputs/con1/1/5"},
            "rr": {"opx_output": "#/ports/mw_outputs/con1/2/5",
                    "opx_input":  "#/ports/mw_inputs/con1/2/1"},
        },
    )

    add_channel(machine, "q5", "z", {"opx_output": "#/ports/analog_outputs/con1/3/1"})

    remove_qubit(machine, "q5")
"""

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.core.quam_classes import QuamDict

from quam_builder.architecture.superconducting.qpu import AnyQuam
from quam_builder.architecture.superconducting.qubit import AnyTransmon
from quam_builder.builder.superconducting.add_default_pulses import (
    add_default_transmon_pulses,
)
from quam_builder.builder.superconducting.add_transmon_drive_component import (
    add_transmon_drive_component,
)
from quam_builder.builder.superconducting.add_transmon_flux_component import (
    add_transmon_flux_component,
)
from quam_builder.builder.superconducting.add_transmon_resonator_component import (
    add_transmon_resonator_component,
)

__all__ = ["add_qubit", "remove_qubit", "add_channel", "remove_channel"]

_LINE_TYPE_TO_ADDER = {
    WiringLineType.DRIVE.value: add_transmon_drive_component,
    WiringLineType.RESONATOR.value: add_transmon_resonator_component,
    WiringLineType.FLUX.value: add_transmon_flux_component,
}

_LINE_TYPE_TO_FIELD = {
    WiringLineType.DRIVE.value: "xy",
    WiringLineType.RESONATOR.value: "resonator",
    WiringLineType.FLUX.value: "z",
}


def _port_reference_values(ports: dict[str, str]):
    """Yield port reference strings without resolving through ``machine.wiring``.

    Wiring port dicts stored on the machine are ``QuamDict`` instances. Reading
    ``ports[key]`` resolves references, but the port objects may not exist yet.
    Use ``get_raw_value`` to read the stored reference string instead.
    """
    for key in ports:
        if isinstance(ports, QuamDict):
            ref = ports.get_raw_value(key)
        else:
            ref = ports[key]
        yield ref


def _create_ports(machine: AnyQuam, ports: dict[str, str]):
    """Ensure every port reference in *ports* exists in ``machine.ports``."""
    for ref in _port_reference_values(ports):
        if isinstance(ref, str) and "ports" in ref and machine.ports is not None:
            machine.ports.reference_to_port(ref, create=True)


def _get_referencing_qubit_pair_ids(machine: AnyQuam, qubit_id: str) -> list[str]:
    """Pair ids that reference ``qubit_id`` in ``machine.qubit_pairs`` or wiring."""
    found: set[str] = set()

    for pair_id, pair in machine.qubit_pairs.items():
        for ref in (pair.qubit_control, pair.qubit_target):
            if ref is None:
                continue
            if isinstance(ref, str):
                name = ref.rstrip("/").split("/")[-1]
            else:
                name = ref.name
            if name == qubit_id:
                found.add(pair_id)
                break

    for pair_id in machine.wiring.get("qubit_pairs", {}):
        qc, qt = pair_id.split("-", 1)
        qt = qt if str(qt).startswith("q") else f"q{qt}"
        if qubit_id in (qc, qt):
            found.add(pair_id)

    return sorted(found)


def add_qubit(
    machine: AnyQuam,
    qubit_id: str,
    wiring: dict[str, dict[str, str]] | None = None,
    add_default_pulses: bool = True,
) -> AnyTransmon:
    """Add a single qubit to an existing machine.

    Args:
        machine: The QUAM machine instance.
        qubit_id: Name for the qubit (e.g. ``"q5"``).
        wiring: Dict mapping line types (``"xy"``, ``"rr"``, ``"z"``) to port
            dicts, e.g.::

            {
                "xy": {"opx_output": "#/ports/mw_outputs/con1/1/5"},
                "rr": {"opx_output": "#/ports/...","opx_input": "#/ports/..."},
                "z":  {"opx_output": "#/ports/analog_outputs/con1/3/1"},
            }

            If ``None``, the wiring must already exist in
            ``machine.wiring["qubits"][qubit_id]``.
        add_default_pulses: Seed default pulse operations on the new channels.

    Returns:
        The newly created qubit, fully wired with channels and (optionally) pulses.

    Raises:
        KeyError: If a qubit with ``qubit_id`` already exists.
    """
    if qubit_id in machine.qubits:
        raise KeyError(f"Qubit '{qubit_id}' already exists")

    if wiring is not None:
        machine.wiring.setdefault("qubits", {})
        machine.wiring["qubits"][qubit_id] = wiring

    qubit_wiring = machine.wiring.get("qubits", {}).get(qubit_id, {})

    try:
        transmon = machine.qubit_type(id=qubit_id)
        machine.qubits[qubit_id] = transmon
    except AttributeError as e:
        raise TypeError(
            f"{type(machine).__name__} does not define qubit_type. "
            "Use FixedFrequencyQuam or FluxTunableQuam."
        ) from e

    for line_type, ports in qubit_wiring.items():
        _create_ports(machine, ports)
        wiring_path = f"#/wiring/qubits/{qubit_id}/{line_type}"
        adder = _LINE_TYPE_TO_ADDER.get(line_type)
        if adder is None:
            raise ValueError(f"Unknown line type: {line_type}")
        adder(transmon, wiring_path, ports)

    if add_default_pulses:
        add_default_transmon_pulses(transmon)

    if qubit_id not in machine.active_qubit_names:
        machine.active_qubit_names.append(transmon.name)

    return transmon


def remove_qubit(machine: AnyQuam, qubit_id: str) -> AnyTransmon:
    """Remove a qubit and its channels from the machine.

    The qubit is removed from ``machine.qubits`` and ``active_qubit_names``,
    and its wiring entry is cleaned up. The returned qubit has its parent
    cleared so it can be garbage-collected or re-attached elsewhere.

    Args:
        machine: The QUAM machine instance.
        qubit_id: The id of the qubit to remove.

    Returns:
        The detached qubit object.

    Raises:
        KeyError: If no qubit with ``qubit_id`` exists.
        ValueError: If the qubit participates in one or more qubit pairs.
    """
    if qubit_id not in machine.qubits:
        raise KeyError(f"Qubit '{qubit_id}' not found")

    pairs = _get_referencing_qubit_pair_ids(machine, qubit_id)
    if pairs:
        pair_list = ", ".join(pairs)
        raise ValueError(
            f"Cannot remove qubit '{qubit_id}': referenced by qubit pair(s): {pair_list}. "
            "Remove the qubit pair(s) first."
        )

    transmon = machine.qubits.pop(qubit_id)
    transmon.parent = None

    if transmon.name in machine.active_qubit_names:
        machine.active_qubit_names.remove(transmon.name)

    if "qubits" in machine.wiring and qubit_id in machine.wiring["qubits"]:
        del machine.wiring["qubits"][qubit_id]

    return transmon


def add_channel(
    machine: AnyQuam,
    qubit_id: str,
    line_type: str,
    ports: dict[str, str],
    add_default_pulses: bool = True,
) -> None:
    """Add a single channel to an existing qubit.

    Args:
        machine: The QUAM machine instance.
        qubit_id: The id of the target qubit.
        line_type: One of ``"xy"`` (drive), ``"rr"`` (resonator), or ``"z"`` (flux).
        ports: Dict with port references, e.g.
            ``{"opx_output": "#/ports/mw_outputs/con1/1/5"}``.
        add_default_pulses: Seed default pulse operations on the new channel.

    Raises:
        KeyError: If the qubit doesn't exist.
        ValueError: If the channel slot is already occupied.
    """
    if qubit_id not in machine.qubits:
        raise KeyError(f"Qubit '{qubit_id}' not found")

    transmon = machine.qubits[qubit_id]
    field_name = _LINE_TYPE_TO_FIELD.get(line_type)
    if field_name is None:
        raise ValueError(f"Unknown line type: {line_type}")

    if getattr(transmon, field_name, None) is not None:
        raise ValueError(
            f"Channel '{line_type}' (field '{field_name}') already exists on qubit '{qubit_id}'"
        )

    _create_ports(machine, ports)

    machine.wiring.setdefault("qubits", {})
    machine.wiring["qubits"].setdefault(qubit_id, {})
    machine.wiring["qubits"][qubit_id][line_type] = ports

    wiring_path = f"#/wiring/qubits/{qubit_id}/{line_type}"
    adder = _LINE_TYPE_TO_ADDER[line_type]
    adder(transmon, wiring_path, ports)

    if add_default_pulses:
        add_default_transmon_pulses(transmon)


def remove_channel(machine: AnyQuam, qubit_id: str, line_type: str) -> None:
    """Remove a single channel from an existing qubit.

    Args:
        machine: The QUAM machine instance.
        qubit_id: The id of the target qubit.
        line_type: One of ``"xy"`` (drive), ``"rr"`` (resonator), or ``"z"`` (flux).

    Raises:
        KeyError: If the qubit doesn't exist.
        ValueError: If the channel slot is already empty.
    """
    if qubit_id not in machine.qubits:
        raise KeyError(f"Qubit '{qubit_id}' not found")

    transmon = machine.qubits[qubit_id]
    field_name = _LINE_TYPE_TO_FIELD.get(line_type)
    if field_name is None:
        raise ValueError(f"Unknown line type: {line_type}")

    channel = getattr(transmon, field_name, None)
    if channel is None:
        raise ValueError(
            f"Channel '{line_type}' (field '{field_name}') does not exist on qubit '{qubit_id}'"
        )

    channel.parent = None
    setattr(transmon, field_name, None)

    if "qubits" in machine.wiring:
        qubit_wiring = machine.wiring["qubits"].get(qubit_id, {})
        if line_type in qubit_wiring:
            del qubit_wiring[line_type]
