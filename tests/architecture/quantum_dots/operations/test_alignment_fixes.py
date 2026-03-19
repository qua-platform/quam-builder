"""Tests for builder/architecture alignment fixes.

Covers:
- SingleChannel pulse assignment (axis_angle=None for XYDriveSingle)
- ZNeg90 macro registration
- Measure macro chain (SensorDot -> QuantumDotPair -> Qubit)
"""

from inspect import signature
from unittest.mock import MagicMock, call, patch

import pytest
import numpy as np

from quam.components import pulses as quam_pulses, StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.components.xy_drive import (
    XYDriveSingle,
    XYDriveMW,
    XYDriveIQ,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    ZNeg90Macro,
    SINGLE_QUBIT_MACROS,
    Measure1QMacro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    ExchangeStateMacro,
    InitializeStateMacro,
    SensorDotMeasureMacro,
    MeasurePSBPairMacro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.two_qubit_macros import (
    Measure2QMacro,
)
from quam_builder.architecture.quantum_dots.operations.component_pulse_catalog import (
    _make_xy_pulse_factories,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit


@pytest.fixture(autouse=True)
def _set_quam_state_path(tmp_path, monkeypatch):
    monkeypatch.setenv("QUAM_STATE_PATH", str(tmp_path / "quam_state"))


# --------------------------------------------------------------------------- #
# Fix 1: SingleChannel pulse assignment
# --------------------------------------------------------------------------- #


class TestSingleChannelPulses:
    """Verify that XYDriveSingle gets real-valued pulses (axis_angle=None)."""

    def test_single_channel_pulse_has_no_axis_angle(self):
        xy = XYDriveSingle(
            id="test_xy",
            opx_output=LFFEMAnalogOutputPort("con1", 3, port_id=1),
            RF_frequency=100_000_000,
        )
        default_pulses = _make_xy_pulse_factories(xy)
        for name, pulse in default_pulses.items():
            xy.operations[name] = pulse

        pulse = xy.operations["gaussian"]
        assert (
            pulse.axis_angle is None
        ), "Pulse 'gaussian' should have axis_angle=None for SingleChannel"

    def test_iq_channel_pulse_has_axis_angle(self):
        """IQ channels should still get axis_angle=0.0."""
        xy = MagicMock(spec=XYDriveIQ)
        xy.operations = {}
        default_pulses = _make_xy_pulse_factories(xy)
        for name, pulse in default_pulses.items():
            xy.operations[name] = pulse

        pulse = xy.operations["gaussian"]
        assert pulse.axis_angle == 0.0


# --------------------------------------------------------------------------- #
# Fix 3: ZNeg90 macro
# --------------------------------------------------------------------------- #


class TestZNeg90Macro:
    """Verify ZNeg90Macro is registered and invokes z rotation."""

    def test_z_neg90_in_macro_catalog(self):
        assert SingleQubitMacroName.Z_NEG_90.value in SINGLE_QUBIT_MACROS
        assert SINGLE_QUBIT_MACROS[SingleQubitMacroName.Z_NEG_90.value] is ZNeg90Macro

    def test_z_neg90_default_angle(self):
        macro = ZNeg90Macro()
        assert macro.default_angle == pytest.approx(-np.pi / 2)

    def test_z_neg90_wired_to_qubit(self, reset_catalog):
        """After wiring, qubit should have z_neg90 macro."""
        machine = _make_wired_machine()
        wire_machine_macros(machine)

        q = machine.qubits["Q1"]
        assert "z_neg90" in q.macros


# --------------------------------------------------------------------------- #
# Fix 2: Measure macro chain
# --------------------------------------------------------------------------- #


class TestMeasureMacroRegistration:
    """Verify macro types are correctly registered in the catalog."""

    def test_measure1q_macro_type(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        q = machine.qubits["Q1"]
        assert isinstance(q.macros["measure"], Measure1QMacro)

    def test_measure_psb_pair_macro_type(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert isinstance(pair.macros["measure"], MeasurePSBPairMacro)

    def test_sensor_dot_measure_macro_type(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        sd = machine.sensor_dots["virtual_sensor_1"]
        assert isinstance(sd.macros["measure"], SensorDotMeasureMacro)

    def test_measure2q_delegates(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        qp = machine.qubit_pairs["Q1_Q2"]
        assert isinstance(qp.macros["measure"], Measure2QMacro)


class TestMeasure1QNavigation:
    """Test that Measure1QMacro navigates to the correct QuantumDotPair."""

    def test_raises_without_preferred_readout(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        q = machine.qubits["Q1"]
        # No preferred_readout_quantum_dot set
        q.preferred_readout_quantum_dot = None
        with pytest.raises(ValueError, match="preferred_readout_quantum_dot"):
            q.macros["measure"].apply()

    def test_raises_with_invalid_pair(self, reset_catalog):
        """Setting preferred_readout_quantum_dot to a non-existent dot should fail at the setter."""
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        q = machine.qubits["Q1"]
        with pytest.raises(ValueError, match="not a registered Quantum Dot"):
            q.preferred_readout_quantum_dot = "nonexistent_dot"


class TestMeasurePSBPairNavigation:
    """Test MeasurePSBPairMacro structure and error paths."""

    def test_pair_macro_has_correct_point(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        macro = pair.macros["measure"]
        assert macro.point == VoltagePointName.MEASURE.value

    def test_pair_has_sensor_dots(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert len(pair.sensor_dots) > 0


class TestStateMacroPointDispatch:
    """Verify state macros dispatch on the new `point` keyword type."""

    def test_state_macro_signature_uses_point_keyword(self):
        initialize_sig = signature(InitializeStateMacro)
        exchange_sig = signature(ExchangeStateMacro)
        measure_pair_sig = signature(MeasurePSBPairMacro)

        assert "point" in initialize_sig.parameters
        assert "point_name" not in initialize_sig.parameters
        assert "point" in exchange_sig.parameters
        assert "return_point" in exchange_sig.parameters
        assert "point_name" not in exchange_sig.parameters
        assert "return_point_name" not in exchange_sig.parameters
        assert "point" in measure_pair_sig.parameters
        assert "point_name" not in measure_pair_sig.parameters

    def test_initialize_state_macro_ramps_to_named_point(self):
        macro = InitializeStateMacro(point="custom_init", ramp_duration=48, hold_duration=64)
        owner = MagicMock()

        with patch(
            "quam_builder.architecture.quantum_dots.operations.default_macros.state_macros._owner_component",
            return_value=owner,
        ):
            macro.apply()

        owner.ramp_to_point.assert_called_once_with("custom_init", ramp_duration=48, duration=64)
        owner.ramp_to_voltages.assert_not_called()

    def test_initialize_state_macro_ramps_to_voltage_dict(self):
        voltages = {"virtual_dot_1": 0.1, "virtual_barrier_1": -0.05}
        macro = InitializeStateMacro(point=voltages, ramp_duration=48, hold_duration=64)
        owner = MagicMock()

        with patch(
            "quam_builder.architecture.quantum_dots.operations.default_macros.state_macros._owner_component",
            return_value=owner,
        ):
            macro.apply()

        owner.ramp_to_voltages.assert_called_once_with(voltages, duration=64, ramp_duration=48)
        owner.ramp_to_point.assert_not_called()

    def test_exchange_state_macro_accepts_voltage_dict_targets(self):
        exchange_voltages = {"virtual_dot_1": 0.2}
        return_voltages = {"virtual_dot_1": 0.0}
        macro = ExchangeStateMacro(
            point=exchange_voltages,
            return_point=return_voltages,
            ramp_duration=32,
            wait_duration=80,
        )
        owner = MagicMock()

        with patch(
            "quam_builder.architecture.quantum_dots.operations.default_macros.state_macros._owner_component",
            return_value=owner,
        ):
            macro.apply()

        owner.ramp_to_voltages.assert_has_calls(
            [
                call(exchange_voltages, duration=None, ramp_duration=32),
                call(return_voltages, duration=None, ramp_duration=32),
            ]
        )
        owner.ramp_to_point.assert_not_called()
        owner.voltage_sequence.step_to_voltages.assert_called_once_with({}, duration=80)

    def test_measure_psb_pair_macro_steps_to_voltage_dict(self):
        voltages = {"virtual_dot_1": -0.1}
        macro = MeasurePSBPairMacro(point=voltages, hold_duration=96)
        sensor_dot = MagicMock()
        owner = MagicMock()
        owner.id = "dot1_dot2_pair"
        owner.sensor_dots = [sensor_dot]

        with patch(
            "quam_builder.architecture.quantum_dots.operations.default_macros.state_macros._owner_component",
            return_value=owner,
        ):
            macro.apply()

        owner.step_to_voltages.assert_called_once_with(voltages, duration=96)
        owner.step_to_point.assert_not_called()
        sensor_dot.call_macro.assert_called_once_with(
            VoltagePointName.MEASURE.value,
            quantum_dot_pair_id="dot1_dot2_pair",
        )


class TestMeasure2QDelegation:
    """Test Measure2QMacro delegates to quantum_dot_pair."""

    def test_qubit_pair_has_quantum_dot_pair(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        qp = machine.qubit_pairs["Q1_Q2"]
        assert qp.quantum_dot_pair is not None

    def test_measure2q_raises_without_quantum_dot_pair(self, reset_catalog):
        """Directly test Measure2QMacro.apply with no quantum_dot_pair."""
        macro = Measure2QMacro()
        owner = MagicMock()
        owner.id = "test_pair"
        owner.quantum_dot_pair = None
        with patch(
            "quam_builder.architecture.quantum_dots.operations.default_macros.two_qubit_macros._owner_component",
            return_value=owner,
        ):
            with pytest.raises(ValueError, match="no quantum_dot_pair"):
                macro.apply()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_voltage_gate(lf_fem: int, port: int, gate_id: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=port),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )


def _make_wired_machine() -> LossDiVincenzoQuam:
    """Build a machine similar to the conftest qd_machine but standalone."""
    machine = LossDiVincenzoQuam()
    lf = 6

    p1 = _make_voltage_gate(lf, 1, "plunger_1")
    p2 = _make_voltage_gate(lf, 2, "plunger_2")
    b1 = _make_voltage_gate(lf, 5, "barrier_1")
    s1 = _make_voltage_gate(lf, 8, "sensor_DC")

    resonator = ReadoutResonatorSingle(
        id="readout_resonator",
        frequency_bare=0,
        intermediate_frequency=500e6,
        operations={
            "readout": quam_pulses.SquareReadoutPulse(length=200, id="readout", amplitude=0.01)
        },
        opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        opx_input=LFFEMAnalogInputPort("con1", 5, port_id=2),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": p1,
            "virtual_dot_2": p2,
            "virtual_barrier_1": b1,
            "virtual_sensor_1": s1,
        },
        gate_set_id="main_qpu",
    )

    machine.register_channel_elements(
        plunger_channels=[p1, p2],
        barrier_channels=[b1],
        sensor_resonator_mappings={s1: resonator},
    )

    machine.register_qubit(quantum_dot_id="virtual_dot_1", qubit_name="Q1")
    machine.register_qubit(quantum_dot_id="virtual_dot_2", qubit_name="Q2")

    machine.register_quantum_dot_pair(
        id="dot1_dot2_pair",
        quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
        sensor_dot_ids=["virtual_sensor_1"],
        barrier_gate_id="virtual_barrier_1",
    )

    machine.quantum_dot_pairs["dot1_dot2_pair"].define_detuning_axis(
        matrix=[[1, -1]],
        detuning_axis_name="dot1_dot2_epsilon",
        set_dc_virtual_axis=False,
    )

    machine.register_qubit_pair(qubit_control_name="Q1", qubit_target_name="Q2", id="Q1_Q2")
    machine.reset_voltage_sequence("main_qpu")

    return machine
