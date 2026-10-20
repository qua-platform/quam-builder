"""Tests for LDQubit (Loss DiVincenzo spin qubit).

All objects are real — no mocks or stubs.
"""

import pytest
from qm import qua
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort, MWFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import (
    QuantumDot,
    VoltageGate,
    XYDriveMW,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


class TestLDQubitProperties:
    def test_physical_channel(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.physical_channel is qubit.quantum_dot.physical_channel

    def test_machine_reference(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.machine is qd_machine

    def test_voltage_sequence(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.voltage_sequence is qubit.quantum_dot.voltage_sequence

    def test_quantum_dot_is_real(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert isinstance(qubit.quantum_dot, QuantumDot)

    def test_xy_none_by_default(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.xy is None


class TestThermalizationTime:
    def test_default_when_T1_is_none(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.T1 is None
        therm = qubit.thermalization_time
        assert therm == 50_000

    def test_calculated_from_T1(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        qubit.T1 = 1e-6  # 1 µs
        expected = round(5 * 1e-6 * 1e9 / 4) * 4
        assert qubit.thermalization_time == expected


class TestVoltageOperations:
    def test_add_point(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        full_name = qubit.add_point("idle", {"virtual_dot_1": 0.1}, duration=100)
        macros = qubit.quantum_dot.voltage_sequence.gate_set.get_macros()
        assert full_name in macros

    def test_step_to_point_in_qua(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        qubit.add_point("idle", {"virtual_dot_1": 0.1}, duration=100)

        with qua.program() as prog:
            qubit.step_to_point("idle")

        assert prog is not None

    def test_ramp_to_point_in_qua(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        qubit.add_point("target", {"virtual_dot_1": 0.3}, duration=100)

        with qua.program() as prog:
            qubit.ramp_to_point("target", ramp_duration=20)

        assert prog is not None


class TestReset:
    def test_thermal_reset_in_qua(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        with qua.program() as prog:
            qubit.reset("thermal")

        assert prog is not None


def _make_qubit_with_xy():
    """Helper: build a minimal machine with one qubit wired to an XYDriveMW."""
    machine = LossDiVincenzoQuam()

    gate = VoltageGate(
        id="plunger_1",
        opx_output=LFFEMAnalogOutputPort("con1", 2, port_id=1),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    machine.create_virtual_gate_set(
        virtual_channel_mapping={"vdot1": gate},
        gate_set_id="main",
    )
    machine.register_channel_elements(
        plunger_channels=[gate],
        barrier_channels=[],
        sensor_resonator_mappings={},
    )
    machine.register_qubit(quantum_dot_id="vdot1", qubit_name="Q1")

    qubit = machine.qubits["Q1"]
    qubit.larmor_frequency = 5.1e9

    xy = XYDriveMW(
        id="xy_mw",
        opx_output=MWFEMAnalogOutputPort(
            controller_id="con1",
            fem_id=1,
            port_id=1,
            band=2,
            upconverter_frequency=int(5e9),
            full_scale_power_dbm=10,
        ),
    )
    qubit.xy = xy
    return machine, qubit


class TestLDQubitDriveFrequency:
    def test_drive_IF_property(self):
        _, qubit = _make_qubit_with_xy()
        assert qubit.drive_IF == pytest.approx(0.1e9)

    def test_drive_LO_property(self):
        _, qubit = _make_qubit_with_xy()
        assert qubit.drive_LO == int(5e9)

    def test_larmor_frequency_propagates_to_IF(self):
        _, qubit = _make_qubit_with_xy()
        qubit.larmor_frequency = 5.3e9
        assert qubit.drive_IF == pytest.approx(0.3e9)

    def test_if_validation_rejects_over_400mhz(self):
        _, qubit = _make_qubit_with_xy()
        with pytest.raises(ValueError, match="exceeds"):
            qubit.larmor_frequency = 6e9  # IF = 1 GHz, over 400 MHz

    def test_if_validation_allows_within_limit(self):
        _, qubit = _make_qubit_with_xy()
        qubit.larmor_frequency = 5.3e9  # IF = 300 MHz, within limit

    def test_set_xy_frequency_removed(self):
        _, qubit = _make_qubit_with_xy()
        assert not hasattr(qubit, "set_xy_frequency")
