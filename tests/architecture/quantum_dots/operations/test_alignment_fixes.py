"""Tests for builder/architecture alignment fixes.

Covers:
- SingleChannel pulse assignment (axis_angle=None for XYDriveSingle)
- ZNeg90 macro registration
- Measure macro chain (SensorDot -> QuantumDotPair -> Qubit)
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

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
    SensorDotMeasureMacro,
    MeasurePSBPairMacro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.two_qubit_macros import (
    Measure2QMacro,
)
from quam_builder.builder.quantum_dots.pulses import add_default_ldv_qubit_pulses
from quam_builder.architecture.quantum_dots.qubit import LDQubit


@pytest.fixture(autouse=True)
def _set_quam_state_path(tmp_path, monkeypatch):
    monkeypatch.setenv("QUAM_STATE_PATH", str(tmp_path / "quam_state"))


# --------------------------------------------------------------------------- #
# Fix 1: SingleChannel pulse assignment
# --------------------------------------------------------------------------- #


class TestSingleChannelPulses:
    """Verify that XYDriveSingle gets real-valued pulses (axis_angle=None)."""

    def test_single_channel_pulses_have_no_axis_angle(self):
        xy = XYDriveSingle(
            id="test_xy",
            opx_output=LFFEMAnalogOutputPort("con1", 3, port_id=1),
            RF_frequency=100_000_000,
            add_default_pulses=False,
        )
        qubit = MagicMock(spec=LDQubit)
        qubit.xy = xy
        add_default_ldv_qubit_pulses(qubit)

        for name in ("x180", "x90", "-x90", "y180", "y90", "-y90"):
            pulse = xy.operations[name]
            assert (
                pulse.axis_angle is None
            ), f"Pulse '{name}' should have axis_angle=None for SingleChannel"

    def test_iq_channel_pulses_have_axis_angle(self):
        """IQ channels should still get axis_angle values."""
        xy = MagicMock(spec=XYDriveIQ)
        xy.operations = {}
        # XYDriveIQ is not a SingleChannel
        qubit = MagicMock(spec=LDQubit)
        qubit.xy = xy
        add_default_ldv_qubit_pulses(qubit)

        x_pulse = xy.operations["x180"]
        assert x_pulse.axis_angle == 0.0
        y_pulse = xy.operations["y180"]
        assert y_pulse.axis_angle == pytest.approx(np.pi / 2)


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

    def test_pair_macro_has_correct_point_name(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        macro = pair.macros["measure"]
        assert macro.point_name == VoltagePointName.MEASURE.value

    def test_pair_has_sensor_dots(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert len(pair.sensor_dots) > 0


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
