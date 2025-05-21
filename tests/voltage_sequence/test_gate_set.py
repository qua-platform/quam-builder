import pytest

from quam.components import SingleChannel
from quam_builder.architecture.quantum_dots.voltage_sequence.gate_set import (
    VoltageTuningPoint,
)


def test_gateset_initialization(machine):
    gate_set = machine.gate_set
    assert gate_set.name == "test_gate_set"
    assert set(gate_set.channels.keys()) == {"ch1", "ch2"}
    assert isinstance(gate_set.channels["ch1"], SingleChannel)
    assert isinstance(gate_set.channels["ch2"], SingleChannel)


def test_gateset_add_point_valid(machine):
    gate_set = machine.gate_set
    voltages = {"ch1": 0.1, "ch2": -0.2}
    duration = 100
    gate_set.add_point("point1", voltages, duration)
    assert "point1" in gate_set.macros
    macro = gate_set.macros["point1"]
    assert isinstance(macro, VoltageTuningPoint)
    assert macro.voltages == voltages
    assert macro.duration == duration


def test_gateset_add_point_invalid_channel(machine):
    gate_set = machine.gate_set
    voltages = {"ch1": 0.1, "ch3": 0.2}  # ch3 does not exist
    duration = 50
    with pytest.raises(ValueError) as excinfo:
        gate_set.add_point("bad_point", voltages, duration)
    assert "not part of this GateSet" in str(excinfo.value)


def test_gateset_macros_multiple_points(machine):
    gate_set = machine.gate_set
    gate_set.add_point("p1", {"ch1": 0.0, "ch2": 0.1}, 10)
    gate_set.add_point("p2", {"ch1": 0.2, "ch2": -0.1}, 20)
    assert set(gate_set.macros.keys()) == {"p1", "p2"}
    assert gate_set.macros["p1"].duration == 10
    assert gate_set.macros["p2"].voltages["ch2"] == -0.1
