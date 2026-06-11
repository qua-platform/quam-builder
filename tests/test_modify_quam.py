"""Tests for the machine add/remove helpers.

Validates that added qubits, channels, and ports produce the
same results as the batch ``build_quam()`` flow:
  - Config generation
  - Serialization
  - iterate_components visibility
  - Parent chain integrity
  - Active qubit tracking
"""

import pytest

from quam.config.models.quam import QuamConfig
from quam.config.resolvers import get_quam_config
from quam.config.vars import CONFIG_PATH_ENV_NAME

from quam.components.pulses import SquarePulse
from quam.components.ports import (
    FEMPortsContainer,
    MWFEMAnalogOutputPort,
    MWFEMAnalogInputPort,
    LFFEMAnalogOutputPort,
)

from quam_builder.architecture.superconducting.qpu import (
    FixedFrequencyQuam,
    FluxTunableQuam,
)
from quam_builder.architecture.superconducting.qubit import (
    FixedFrequencyTransmon,
)
from quam_builder.architecture.superconducting.components.xy_drive import XYDriveMW
from quam_builder.architecture.superconducting.components.readout_resonator import (
    ReadoutResonatorMW,
)
from quam_builder.architecture.superconducting.components.flux_line import FluxLine
from quam_builder.architecture.superconducting.qubit_pair import FixedFrequencyTransmonPair

from quam_builder.builder.superconducting.modify_quam import (
    add_qubit,
    remove_qubit,
    add_channel,
    remove_channel,
)
from quam_builder.builder.qop_connectivity.modify_ports import (
    add_port,
    remove_port,
)

##############################################################################
##############################################################################
#                                Fixtures
##############################################################################
##############################################################################


@pytest.fixture(autouse=True)
def compatible_quam_config(tmp_path, monkeypatch):
    """Use a qualibrate config that matches the installed quam package version."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(f"[quam]\nversion = {QuamConfig.version}\n")
    monkeypatch.setenv(CONFIG_PATH_ENV_NAME, str(config_file))
    get_quam_config.cache_clear()


@pytest.fixture
def empty_ff_machine() -> FixedFrequencyQuam:
    machine = FixedFrequencyQuam(
        ports=FEMPortsContainer(),
    )
    return machine


@pytest.fixture
def mw_wiring() -> dict[str, str]:
    """MW-FEM wiring dict for a single qubit with drive + resonator."""
    return {
        "xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"},
        "rr": {
            "opx_output": "#/ports/mw_outputs/con1/2/1",
            "opx_input": "#/ports/mw_inputs/con1/2/1",
        },
    }


@pytest.fixture
def flux_wiring() -> dict[str, str]:
    """LF-FEM flux wiring for a single channel."""
    return {"opx_output": "#/ports/analog_outputs/con1/3/1"}


##############################################################################
##############################################################################
#                                Helpers
##############################################################################
##############################################################################


def _build_machine() -> FixedFrequencyQuam:
    """Build a machine using the standard build_quam sub-functions."""
    from quam_builder.builder.superconducting.build_quam import (
        add_ports,
        add_transmons,
        add_pulses,
    )

    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    machine.wiring = {
        "qubits": {
            "q0": {
                "xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"},
                "rr": {
                    "opx_output": "#/ports/mw_outputs/con1/2/1",
                    "opx_input": "#/ports/mw_inputs/con1/2/1",
                },
            }
        }
    }

    add_ports(machine)
    add_transmons(machine)
    add_pulses(machine)
    return machine


def _build_machine_with_add_qubit() -> FixedFrequencyQuam:
    """Build the same machine via add_qubit."""
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    wiring = {
        "xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"},
        "rr": {
            "opx_output": "#/ports/mw_outputs/con1/2/1",
            "opx_input": "#/ports/mw_inputs/con1/2/1",
        },
    }
    add_qubit(machine, "q0", wiring)
    return machine


##############################################################################
##############################################################################
#                                add_qubit tests
##############################################################################
##############################################################################


def test_add_qubit_creates_transmon(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    transmon = add_qubit(empty_ff_machine, "q0", mw_wiring)

    assert isinstance(transmon, FixedFrequencyTransmon)
    assert transmon.id == "q0"
    assert "q0" in empty_ff_machine.qubits
    assert empty_ff_machine.qubits["q0"] is transmon


def test_add_qubit_sets_parent_chain(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    transmon = add_qubit(empty_ff_machine, "q0", mw_wiring)

    assert transmon.parent is empty_ff_machine.qubits
    assert transmon.parent.parent is empty_ff_machine


def test_add_qubit_creates_channels(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    transmon = add_qubit(empty_ff_machine, "q0", mw_wiring)

    assert transmon.xy is not None
    assert isinstance(transmon.xy, XYDriveMW)
    assert transmon.resonator is not None
    assert isinstance(transmon.resonator, ReadoutResonatorMW)


def test_add_qubit_creates_ports(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    assert isinstance(empty_ff_machine.ports.mw_outputs["con1"][1][1], MWFEMAnalogOutputPort)
    assert isinstance(empty_ff_machine.ports.mw_outputs["con1"][2][1], MWFEMAnalogOutputPort)
    assert isinstance(empty_ff_machine.ports.mw_inputs["con1"][2][1], MWFEMAnalogInputPort)


def test_add_qubit_adds_default_pulses(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    transmon = add_qubit(empty_ff_machine, "q0", mw_wiring)

    assert "saturation" in transmon.xy.operations
    assert "readout" in transmon.resonator.operations


def test_add_qubit_skips_pulses_when_disabled(
    empty_ff_machine: FixedFrequencyQuam, mw_wiring
) -> None:
    transmon = add_qubit(empty_ff_machine, "q0", mw_wiring, add_default_pulses=False)

    assert len(transmon.xy.operations) == 0


def test_add_qubit_updates_active_names(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    assert "q0" in empty_ff_machine.active_qubit_names


def test_add_qubit_inserts_wiring(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    assert "q0" in empty_ff_machine.wiring["qubits"]
    assert "xy" in empty_ff_machine.wiring["qubits"]["q0"]


def test_add_qubit_duplicate_raises(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    with pytest.raises(KeyError, match="already exists"):
        add_qubit(empty_ff_machine, "q0", mw_wiring)


def test_add_qubit_generates_config(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    config = empty_ff_machine.generate_config()
    element_names = set(config.get("elements", {}).keys())
    assert "q0.xy" in element_names or any("q0" in n for n in element_names)


##############################################################################
##############################################################################
#                                remove_qubit tests
##############################################################################
##############################################################################


def test_remove_qubit_returns_transmon(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    removed = remove_qubit(empty_ff_machine, "q0")
    assert isinstance(removed, FixedFrequencyTransmon)
    assert removed.id == "q0"


def test_remove_qubit_clears_parent(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    removed = remove_qubit(empty_ff_machine, "q0")
    assert removed.parent is None


def test_remove_qubit_removes_from_dict(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)
    remove_qubit(empty_ff_machine, "q0")

    assert "q0" not in empty_ff_machine.qubits


def test_remove_qubit_updates_active_names(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)
    remove_qubit(empty_ff_machine, "q0")

    assert "q0" not in empty_ff_machine.active_qubit_names


def test_remove_qubit_cleans_wiring(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)
    remove_qubit(empty_ff_machine, "q0")

    assert "q0" not in empty_ff_machine.wiring.get("qubits", {})


def test_remove_qubit_not_found_raises(empty_ff_machine):
    with pytest.raises(KeyError, match="not found"):
        remove_qubit(empty_ff_machine, "qfake")


def test_remove_qubit_no_longer_in_config(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)
    remove_qubit(empty_ff_machine, "q0")

    config = empty_ff_machine.generate_config()
    element_names = set(config.get("elements", {}).keys())
    assert not any("q0" in n for n in element_names)


def test_remove_qubit_rejects_when_in_pair(
    empty_ff_machine: FixedFrequencyQuam, mw_wiring
) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)
    add_qubit(empty_ff_machine, "q1", mw_wiring)
    empty_ff_machine.qubit_pairs["q0-q1"] = FixedFrequencyTransmonPair(
        id="q0-q1",
        qubit_control="#/qubits/q0",
        qubit_target="#/qubits/q1",
    )

    with pytest.raises(ValueError, match="qubit pair"):
        remove_qubit(empty_ff_machine, "q0")

    assert "q0" in empty_ff_machine.qubits


def test_remove_qubit_rejects_when_in_pair_wiring_only(
    empty_ff_machine: FixedFrequencyQuam, mw_wiring
) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)
    empty_ff_machine.wiring.setdefault("qubit_pairs", {})
    empty_ff_machine.wiring["qubit_pairs"]["q0-q1"] = {}

    with pytest.raises(ValueError, match="qubit pair"):
        remove_qubit(empty_ff_machine, "q0")

    assert "q0" in empty_ff_machine.qubits


def test_add_qubit_rejects_invalid_wiring_before_mutating(
    empty_ff_machine: FixedFrequencyQuam,
) -> None:
    wiring = {
        "xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"},
        "rr": {"not_a_valid_port_key": "#/ports/mw_outputs/con1/2/1"},
    }

    with pytest.raises(ValueError, match="Unimplemented mapping"):
        add_qubit(empty_ff_machine, "q0", wiring)

    assert "q0" not in empty_ff_machine.qubits
    assert "q0" not in empty_ff_machine.wiring.get("qubits", {})


def test_add_qubit_rejects_unknown_line_type_before_mutating(
    empty_ff_machine: FixedFrequencyQuam,
) -> None:
    wiring = {
        "xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"},
        "coupler": {"opx_output": "#/ports/analog_outputs/con1/3/1"},
    }

    with pytest.raises(ValueError, match="Unknown line type"):
        add_qubit(empty_ff_machine, "q0", wiring)

    assert "q0" not in empty_ff_machine.qubits
    assert "q0" not in empty_ff_machine.wiring.get("qubits", {})


def test_add_channel_rejects_invalid_ports_before_mutating() -> None:
    machine = FluxTunableQuam(ports=FEMPortsContainer())
    add_qubit(
        machine,
        "q0",
        {"xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"}},
        add_default_pulses=False,
    )

    with pytest.raises(ValueError, match="Unimplemented mapping"):
        add_channel(machine, "q0", "z", {"not_a_valid_port_key": "#/ports/analog_outputs/con1/3/1"})

    assert machine.qubits["q0"].z is None
    assert "z" not in machine.wiring["qubits"]["q0"]


##############################################################################
##############################################################################
#                                add_channel tests
##############################################################################
##############################################################################


def test_add_flux_channel_to_existing_qubit() -> None:
    machine = FluxTunableQuam(ports=FEMPortsContainer())
    flux_ports = {"opx_output": "#/ports/analog_outputs/con1/3/1"}
    drive_wiring = {"xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"}}

    transmon = add_qubit(machine, "q0", drive_wiring, add_default_pulses=False)
    assert transmon.z is None

    add_channel(machine, "q0", "z", flux_ports)

    assert transmon.z is not None
    assert isinstance(transmon.z, FluxLine)


def test_add_channel_preserves_existing_pulses() -> None:
    """Adding a channel must not overwrite calibrated pulses on other channels."""
    machine = FluxTunableQuam(ports=FEMPortsContainer())
    drive_wiring = {"xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"}}
    transmon = add_qubit(machine, "q0", drive_wiring, add_default_pulses=True)
    transmon.xy.operations["saturation"] = SquarePulse(amplitude=0.99, length=100)

    add_channel(
        machine,
        "q0",
        "z",
        {"opx_output": "#/ports/analog_outputs/con1/3/1"},
        add_default_pulses=True,
    )

    assert transmon.xy.operations["saturation"].amplitude == 0.99
    assert "const" in transmon.z.operations


def test_add_channel_duplicate_raises(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    with pytest.raises(ValueError, match="already exists"):
        add_channel(
            empty_ff_machine,
            "q0",
            "xy",
            {"opx_output": "#/ports/mw_outputs/con1/1/2"},
        )


def test_add_channel_qubit_not_found_raises(empty_ff_machine):
    with pytest.raises(KeyError, match="not found"):
        add_channel(
            empty_ff_machine,
            "q99",
            "xy",
            {"opx_output": "#/ports/mw_outputs/con1/1/1"},
        )


def test_add_channel_unknown_type_raises(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)

    with pytest.raises(ValueError, match="Unknown line type"):
        add_channel(empty_ff_machine, "q0", "fake_type", {})


def test_add_channel_updates_wiring() -> None:
    machine = FluxTunableQuam(ports=FEMPortsContainer())
    drive_wiring = {"xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"}}
    add_qubit(machine, "q0", drive_wiring, add_default_pulses=False)

    flux_ports = {"opx_output": "#/ports/analog_outputs/con1/3/1"}
    add_channel(machine, "q0", "z", flux_ports)

    assert "z" in machine.wiring["qubits"]["q0"]


def test_add_channel_visible_in_qubit_channels() -> None:
    machine = FluxTunableQuam(ports=FEMPortsContainer())
    drive_wiring = {"xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"}}
    add_qubit(machine, "q0", drive_wiring, add_default_pulses=False)
    add_channel(
        machine,
        "q0",
        "z",
        {"opx_output": "#/ports/analog_outputs/con1/3/1"},
        add_default_pulses=False,
    )

    transmon = machine.qubits["q0"]
    assert "z" in transmon.channels


##############################################################################
##############################################################################
#                                remove_channel tests
##############################################################################
##############################################################################


def test_remove_channel_clears_field(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)
    remove_channel(empty_ff_machine, "q0", "xy")

    assert empty_ff_machine.qubits["q0"].xy is None


def test_remove_channel_clears_parent(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    transmon = add_qubit(empty_ff_machine, "q0", mw_wiring)
    xy_before = transmon.xy

    remove_channel(empty_ff_machine, "q0", "xy")
    assert xy_before.parent is None


def test_remove_channel_empty_slot_raises(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    machine = FluxTunableQuam(ports=FEMPortsContainer())
    drive_wiring = {"xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"}}
    add_qubit(machine, "q0", drive_wiring)

    with pytest.raises(ValueError, match="does not exist"):
        remove_channel(machine, "q0", "z")


def test_remove_channel_updates_wiring(empty_ff_machine: FixedFrequencyQuam, mw_wiring) -> None:
    add_qubit(empty_ff_machine, "q0", mw_wiring)
    remove_channel(empty_ff_machine, "q0", "xy")

    assert "xy" not in empty_ff_machine.wiring["qubits"]["q0"]


def test_remove_channel_not_in_iterate_components(
    empty_ff_machine: FixedFrequencyQuam, mw_wiring
) -> None:
    transmon = add_qubit(empty_ff_machine, "q0", mw_wiring)
    xy = transmon.xy
    remove_channel(empty_ff_machine, "q0", "xy")

    components = list(empty_ff_machine.iterate_components())
    assert xy not in components


##############################################################################
##############################################################################
#                                add_port / remove_port tests
##############################################################################
##############################################################################


def test_add_mw_output_port():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    port = add_port(
        machine,
        "mw_output",
        "con1",
        fem_id=1,
        port_id=3,
        band=1,
        upconverter_frequency=5e9,
    )

    assert isinstance(port, MWFEMAnalogOutputPort)
    assert port.controller_id == "con1"
    assert port.fem_id == 1
    assert port.port_id == 3
    assert machine.ports.mw_outputs["con1"][1][3] is port


def test_add_analog_output_port():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    port = add_port(machine, "analog_output", "con1", fem_id=5, port_id=1, offset=0.0)

    assert isinstance(port, LFFEMAnalogOutputPort)
    assert machine.ports.analog_outputs["con1"][5][1] is port


def test_add_port_invalid_type_raises():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())

    with pytest.raises(ValueError, match="Unsupported"):
        add_port(machine, "teleporter", "con1", fem_id=1, port_id=1)


def test_add_port_visible_in_iterate_components():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    port = add_port(
        machine,
        "mw_output",
        "con1",
        fem_id=1,
        port_id=1,
        band=1,
        upconverter_frequency=5e9,
    )

    components = list(machine.iterate_components())
    assert port in components


def test_remove_port():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    port = add_port(
        machine,
        "mw_output",
        "con1",
        fem_id=1,
        port_id=1,
        band=1,
        upconverter_frequency=5e9,
    )

    removed = remove_port(machine, "mw_output", "con1", fem_id=1, port_id=1)
    assert removed is port
    assert removed.parent is None
    assert 1 not in machine.ports.mw_outputs["con1"][1]


def test_remove_port_not_found_raises():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())

    with pytest.raises(KeyError):
        remove_port(machine, "mw_output", "con1", fem_id=1, port_id=99)


def test_remove_port_not_in_iterate_components():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    port = add_port(
        machine,
        "mw_output",
        "con1",
        fem_id=1,
        port_id=1,
        band=1,
        upconverter_frequency=5e9,
    )
    remove_port(machine, "mw_output", "con1", fem_id=1, port_id=1)

    components = list(machine.iterate_components())
    assert port not in components


##############################################################################
##############################################################################
#                            Add vs original tests
##############################################################################
##############################################################################


def test_same_channels_created():
    machine = _build_machine()
    machine_add = _build_machine_with_add_qubit()

    assert type(machine.qubits["q0"].xy) is type(machine_add.qubits["q0"].xy)
    assert type(machine.qubits["q0"].resonator) is type(machine_add.qubits["q0"].resonator)


def test_same_pulse_operations():
    machine = _build_machine()
    machine_add = _build_machine_with_add_qubit()

    assert set(machine.qubits["q0"].xy.operations.keys()) == set(
        machine_add.qubits["q0"].xy.operations.keys()
    )
    assert set(machine.qubits["q0"].resonator.operations.keys()) == set(
        machine_add.qubits["q0"].resonator.operations.keys()
    )


def test_same_active_qubit_names():
    machine = _build_machine()
    machine_add = _build_machine_with_add_qubit()

    assert machine.active_qubit_names == machine_add.active_qubit_names


def test_same_port_types_created():
    machine = _build_machine()
    machine_add = _build_machine_with_add_qubit()

    assert type(machine.ports.mw_outputs["con1"][1][1]) is type(
        machine_add.ports.mw_outputs["con1"][1][1]
    )


def test_same_config_element_names():
    machine = _build_machine()
    machine_add = _build_machine_with_add_qubit()

    machine_config = machine.generate_config()
    machine_add_config = machine_add.generate_config()

    assert set(machine_config.get("elements", {}).keys()) == set(
        machine_add_config.get("elements", {}).keys()
    )


def test_serialization_round_trip(tmp_path):
    """Machine built with add_qubit survives save/load."""
    machine = _build_machine_with_add_qubit()

    machine.save(tmp_path / "state")
    loaded = FixedFrequencyQuam.load(tmp_path / "state")

    assert "q0" in loaded.qubits
    assert loaded.qubits["q0"].xy is not None
    assert loaded.qubits["q0"].resonator is not None
    assert "saturation" in loaded.qubits["q0"].xy.operations
    assert "readout" in loaded.qubits["q0"].resonator.operations


def test_add_then_remove_leaves_clean_machine():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    wiring = {
        "xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"},
        "rr": {
            "opx_output": "#/ports/mw_outputs/con1/2/1",
            "opx_input": "#/ports/mw_inputs/con1/2/1",
        },
    }
    add_qubit(machine, "q0", wiring)
    remove_qubit(machine, "q0")

    assert len(machine.qubits) == 0
    assert len(machine.active_qubit_names) == 0
    assert "q0" not in machine.wiring.get("qubits", {})


def test_add_multiple_qubits():
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())

    for i in range(3):
        wiring = {
            "xy": {"opx_output": f"#/ports/mw_outputs/con1/1/{i + 1}"},
            "rr": {
                "opx_output": f"#/ports/mw_outputs/con1/2/{i + 1}",
                "opx_input": f"#/ports/mw_inputs/con1/2/{i + 1}",
            },
        }
        add_qubit(machine, f"q{i}", wiring)

    assert len(machine.qubits) == 3
    assert len(machine.active_qubit_names) == 3

    config = machine.generate_config()
    elements = set(config.get("elements", {}).keys())
    for i in range(3):
        assert any(f"q{i}" in name for name in elements)
