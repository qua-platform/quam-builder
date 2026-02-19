"""Tests for ReadoutResonator components.

All objects are real — no mocks or stubs.
"""

from quam.components import StickyChannelAddon, pulses
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.components.readout_resonator import (
    ReadoutResonatorBase,
)


class TestReadoutResonatorSingleCreation:
    def test_basic_creation(self):
        rr = ReadoutResonatorSingle(
            id="rr_test",
            frequency_bare=5e9,
            intermediate_frequency=100e6,
            operations={
                "readout": pulses.SquareReadoutPulse(length=200, id="readout", amplitude=0.01)
            },
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
            opx_input=LFFEMAnalogInputPort("con1", 5, port_id=2),
        )
        assert rr.id == "rr_test"
        assert rr.frequency_bare == 5e9
        assert "readout" in rr.operations

    def test_with_sticky_addon(self):
        rr = ReadoutResonatorSingle(
            id="rr_sticky",
            frequency_bare=0,
            intermediate_frequency=200e6,
            operations={"readout": pulses.SquareReadoutPulse(length=100, id="ro", amplitude=0.05)},
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
            opx_input=LFFEMAnalogInputPort("con1", 5, port_id=2),
            sticky=StickyChannelAddon(duration=16, digital=False),
        )
        assert rr.sticky is not None


class TestVoltageScalingFactor:
    def test_same_power_gives_factor_of_one(self):
        factor = ReadoutResonatorBase.calculate_voltage_scaling_factor(0, 0)
        assert abs(factor - 1.0) < 1e-9

    def test_increase_power(self):
        factor = ReadoutResonatorBase.calculate_voltage_scaling_factor(0, 6)
        expected = 10 ** (6 / 20)
        assert abs(factor - expected) < 1e-6

    def test_decrease_power(self):
        factor = ReadoutResonatorBase.calculate_voltage_scaling_factor(0, -6)
        expected = 10 ** (-6 / 20)
        assert abs(factor - expected) < 1e-6

    def test_large_difference(self):
        factor = ReadoutResonatorBase.calculate_voltage_scaling_factor(-40, 10)
        expected = 10 ** (50 / 20)
        assert abs(factor - expected) < 1e-3


class TestResonatorInMachine:
    def test_sensor_dot_has_resonator(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        assert sd.readout_resonator is not None
        assert isinstance(sd.readout_resonator, ReadoutResonatorSingle)

    def test_resonator_operations(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        assert "readout" in sd.readout_resonator.operations
