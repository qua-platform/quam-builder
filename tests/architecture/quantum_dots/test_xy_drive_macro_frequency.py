"""Tests for XYDriveMacro frequency update/apply behaviour."""

import pytest
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort, MWFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDriveMW
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


@pytest.fixture
def wired_qubit():
    """Qubit with XY drive and macros wired."""
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

    machine.reset_voltage_sequence("main")
    qubit.add_point(VoltagePointName.INITIALIZE, {"vdot1": 0.1}, duration=200)
    qubit.add_point(VoltagePointName.MEASURE, {"vdot1": 0.15}, duration=200)
    qubit.add_point(VoltagePointName.EMPTY, {"vdot1": 0.0}, duration=200)

    wire_machine_macros(machine)
    return qubit


class TestXYDriveMacroFrequencyUpdate:
    def test_update_frequency_sets_larmor(self, wired_qubit):
        qubit = wired_qubit
        xy_macro = qubit.macros[SingleQubitMacroName.XY_DRIVE]

        xy_macro.update(frequency=5.2e9)
        assert qubit.larmor_frequency == 5.2e9

    def test_update_frequency_offset_adjusts_larmor(self, wired_qubit):
        qubit = wired_qubit
        xy_macro = qubit.macros[SingleQubitMacroName.XY_DRIVE]

        original = qubit.larmor_frequency
        xy_macro.update(frequency_offset=10e6)
        assert qubit.larmor_frequency == pytest.approx(original + 10e6)

    def test_update_frequency_and_offset_raises(self, wired_qubit):
        qubit = wired_qubit
        xy_macro = qubit.macros[SingleQubitMacroName.XY_DRIVE]

        with pytest.raises(ValueError, match="either frequency or frequency_offset"):
            xy_macro.update(frequency=5.2e9, frequency_offset=10e6)

    def test_update_no_recenter_lo_parameter(self, wired_qubit):
        """recenter_LO parameter should no longer exist."""
        qubit = wired_qubit
        xy_macro = qubit.macros[SingleQubitMacroName.XY_DRIVE]

        with pytest.raises(TypeError):
            xy_macro.update(frequency=5.2e9, recenter_LO=True)
