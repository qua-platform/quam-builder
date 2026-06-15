"""Add and remove qubits and channels from an existing superconducting QUAM.

Reuses the same atomic component adders that ``build_quam()`` uses, so
incrementally-added objects are identical to batch-built ones.

Line type keys match ``WiringLineType`` enum values: ``"xy"`` (drive),
``"rr"`` (resonator), ``"z"`` (flux).

``add_qubit`` and ``add_channel`` validate wiring and port mappings before
mutating the machine, so invalid input raises without changing state.
Port dicts may reference ``#/ports/...``, ``#/octaves/...``, and
``#/mixers/...``; the latter two are created on the machine when missing.

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

from pathlib import Path

from qualang_tools.units import unit
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components import FrequencyConverter, LocalOscillator, Octave
from quam.components.pulses import SquarePulse, SquareReadoutPulse
from quam.core.quam_classes import QuamDict

from quam_builder.architecture.superconducting.components.mixer import StandaloneMixer
from quam_builder.architecture.superconducting.qpu import AnyQuam
from quam_builder.architecture.superconducting.qubit import AnyTransmon
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_in_out_channel_ports,
    iq_out_channel_ports,
    mw_in_out_channel_ports,
    mw_out_channel_ports,
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

_u = unit(coerce_to_integer=True)

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

_MIXER_CHANNEL_FIELD = {
    WiringLineType.DRIVE.value: "xy",
    WiringLineType.RESONATOR.value: "resonator",
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


def _calibration_db_path(machine: AnyQuam, calibration_db_path: Path | str | None) -> Path:
    if calibration_db_path is None:
        calibration_db_path = machine.get_serialiser()._get_state_path().parent
    if isinstance(calibration_db_path, str):
        calibration_db_path = Path(calibration_db_path)
    return calibration_db_path


def _create_line_refs(
    machine: AnyQuam,
    ports: dict[str, str],
    qubit_id: str,
    line_type: str,
    calibration_db_path: Path | str | None = None,
) -> None:
    """Create ports, octaves, and mixers referenced by a wiring port dict if missing."""

    for ref in _port_reference_values(ports):
        if not isinstance(ref, str):
            continue
        if "ports" in ref and machine.ports is not None:
            machine.ports.reference_to_port(ref, create=True)
        elif "octaves" in ref:
            db_path = _calibration_db_path(machine, calibration_db_path)
            octave_name = ref.split("/")[2]
            if octave_name not in machine.octaves:
                octave = Octave(
                    name=octave_name,
                    calibration_db_path=str(db_path),
                )
                machine.octaves[octave_name] = octave
                octave.initialize_frequency_converters()
        elif "mixers" in ref:
            channel_field = _MIXER_CHANNEL_FIELD.get(line_type)
            if channel_field is None:
                raise ValueError(
                    f"Cannot create mixer for line type '{line_type}' on qubit '{qubit_id}'"
                )
            mixer_name = ref.split("/")[2]
            if mixer_name not in machine.mixers:
                machine.mixers[mixer_name] = FrequencyConverter(
                    local_oscillator=LocalOscillator(),
                    mixer=StandaloneMixer(
                        intermediate_frequency=(
                            f"#/qubits/{qubit_id}/{channel_field}/intermediate_frequency"
                        ),
                    ),
                )


def _validate_port_mapping(line_type: str, ports: dict[str, str]) -> None:
    keys = set(ports.keys())
    if line_type == WiringLineType.FLUX.value:
        if "opx_output" in keys:
            return
    elif line_type == WiringLineType.DRIVE.value:
        if all(key in keys for key in iq_out_channel_ports) or all(
            key in keys for key in mw_out_channel_ports
        ):
            return
    elif line_type == WiringLineType.RESONATOR.value:
        if all(key in keys for key in iq_in_out_channel_ports) or all(
            key in keys for key in mw_in_out_channel_ports
        ):
            return
    raise ValueError(f"Unimplemented mapping of port keys to channel for ports: {ports}")


def _validate_qubit_wiring(qubit_wiring: dict[str, dict[str, str]]) -> None:
    if not qubit_wiring:
        raise ValueError("Qubit wiring cannot be empty")
    for line_type, ports in qubit_wiring.items():
        if line_type not in _LINE_TYPE_TO_ADDER:
            raise ValueError(
                f"Unknown line type: {line_type}. Valid line types are: {_LINE_TYPE_TO_ADDER.keys()}"
            )
        _validate_port_mapping(line_type, ports)


def _seed_default_pulses_for_line(transmon: AnyTransmon, line_type: str) -> None:
    """Map wiring line type to a transmon channel and seed missing default pulses."""
    field_name = _LINE_TYPE_TO_FIELD.get(line_type)
    if field_name is None:
        return
    channel = getattr(transmon, field_name, None)
    if channel is None:
        return

    if field_name == "xy":
        if "saturation" not in channel.operations:
            channel.operations["saturation"] = SquarePulse(
                amplitude=0.25, length=20 * _u.us, axis_angle=0
            )
    elif field_name == "z":
        if "const" not in channel.operations:
            channel.operations["const"] = SquarePulse(amplitude=0.1, length=100)
    elif field_name == "resonator":
        if "readout" not in channel.operations:
            channel.operations["readout"] = SquareReadoutPulse(
                length=2000, amplitude=0.01, threshold=0.0, digital_marker="ON"
            )
        if "readout_GEF" not in channel.operations:
            channel.operations["readout_GEF"] = SquareReadoutPulse(
                length=2000, amplitude=0.01, threshold=0.0, digital_marker="ON"
            )


def _wire_qubit_channels(
    machine: AnyQuam,
    transmon: AnyTransmon,
    qubit_id: str,
    qubit_wiring: dict[str, dict[str, str]],
    calibration_db_path: Path | str | None = None,
) -> None:
    for line_type, ports in qubit_wiring.items():
        _create_line_refs(machine, ports, qubit_id, line_type, calibration_db_path)
        wiring_path = f"#/wiring/qubits/{qubit_id}/{line_type}"
        _LINE_TYPE_TO_ADDER[line_type](transmon, wiring_path, ports)


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
    calibration_db_path: Path | str | None = None,
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
        add_default_pulses: Seed default pulse operations on the new channels only.
        calibration_db_path: Path to the Octave calibration database. Defaults to
            the machine state directory.

    Returns:
        The newly created qubit, fully wired with channels and (optionally) pulses.

    Raises:
        KeyError: If a qubit with ``qubit_id`` already exists.
        ValueError: If wiring is invalid.
    """
    if qubit_id in machine.qubits:
        raise KeyError(f"Qubit '{qubit_id}' already exists")

    qubit_wiring = (
        wiring if wiring is not None else machine.wiring.get("qubits", {}).get(qubit_id, {})
    )
    _validate_qubit_wiring(qubit_wiring)

    try:
        transmon = machine.qubit_type(id=qubit_id)
    except AttributeError as e:
        raise TypeError(
            f"{type(machine).__name__} does not define qubit_type. "
            "Use FixedFrequencyQuam or FluxTunableQuam."
        ) from e

    if wiring is not None:
        machine.wiring.setdefault("qubits", {})
        machine.wiring["qubits"][qubit_id] = wiring

    machine.qubits[qubit_id] = transmon

    _wire_qubit_channels(machine, transmon, qubit_id, qubit_wiring, calibration_db_path)

    if add_default_pulses:
        for line_type in qubit_wiring:
            _seed_default_pulses_for_line(transmon, line_type)

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
    calibration_db_path: Path | str | None = None,
) -> None:
    """Add a single channel to an existing qubit.

    Args:
        machine: The QUAM machine instance.
        qubit_id: The id of the target qubit.
        line_type: One of ``"xy"`` (drive), ``"rr"`` (resonator), or ``"z"`` (flux).
        ports: Dict with port references, e.g.
            ``{"opx_output": "#/ports/mw_outputs/con1/1/5"}``.
        add_default_pulses: Seed default pulse operations on the new channel only.
        calibration_db_path: Path to the Octave calibration database. Defaults to
            the machine state directory.

    Raises:
        KeyError: If the qubit doesn't exist.
        ValueError: If the channel slot is already occupied or ports are invalid.
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

    _validate_port_mapping(line_type, ports)

    machine.wiring.setdefault("qubits", {})
    machine.wiring["qubits"].setdefault(qubit_id, {})
    machine.wiring["qubits"][qubit_id][line_type] = ports

    wiring_path = f"#/wiring/qubits/{qubit_id}/{line_type}"
    _create_line_refs(machine, ports, qubit_id, line_type, calibration_db_path)
    _LINE_TYPE_TO_ADDER[line_type](transmon, wiring_path, ports)

    if add_default_pulses:
        _seed_default_pulses_for_line(transmon, line_type)


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
