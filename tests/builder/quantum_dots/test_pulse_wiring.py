"""Tests for pulse wiring via PulseWirer / wire_machine_macros and TOML-style pulse setup."""

from quam.components import pulses as quam_pulses, StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveSingle
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.macro_engine.wiring import PulseWirer
from quam_builder.architecture.quantum_dots.qubit import LDQubit


def _make_voltage_gate(lf_fem: int, port: int, gate_id: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=port),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )


def _make_wired_machine() -> LossDiVincenzoQuam:
    """Build a minimal wired machine for pulse testing."""
    machine = LossDiVincenzoQuam()
    lf = 6

    p1 = _make_voltage_gate(lf, 1, "plunger_1")
    s1 = _make_voltage_gate(lf, 8, "sensor_DC")

    resonator = ReadoutResonatorSingle(
        id="readout_resonator",
        frequency_bare=0,
        intermediate_frequency=500e6,
        operations={},
        opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        opx_input=LFFEMAnalogInputPort("con1", 5, port_id=2),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    xy_drive = XYDriveSingle(
        id="Q1_xy",
        RF_frequency=int(100e6),
        opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=3),
    )

    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": p1,
            "virtual_sensor_1": s1,
        },
        gate_set_id="main_qpu",
    )

    machine.register_channel_elements(
        plunger_channels=[p1],
        barrier_channels=[],
        sensor_resonator_mappings={s1: resonator},
    )

    machine.register_qubit(
        quantum_dot_id="virtual_dot_1",
        qubit_name="Q1",
        xy=xy_drive,
    )

    return machine


class TestDefaultPulseWiring:
    """Test that PulseWirer adds pulses to the right places."""

    def test_xy_drive_gets_default_pulse(self):
        machine = _make_wired_machine()
        PulseWirer().wire(machine)

        xy = machine.qubits["Q1"].xy
        assert "gaussian_x90" in xy.operations

    def test_all_families_wired(self):
        machine = _make_wired_machine()
        PulseWirer().wire(machine)

        xy = machine.qubits["Q1"].xy
        for family in ("gaussian", "square", "kaiser", "hermite", "drag"):
            assert f"{family}_x90" in xy.operations
            assert f"{family}_x180" in xy.operations

    def test_all_families_axis_variants_wired(self):
        """All axis variants (x_neg90, y90, y180, y_neg90) should be wired for every family."""
        machine = _make_wired_machine()
        PulseWirer().wire(machine)

        xy = machine.qubits["Q1"].xy
        for family in ("gaussian", "square", "kaiser", "hermite", "drag"):
            for gate in ("x_neg90", "y90", "y180", "y_neg90"):
                assert f"{family}_{gate}" in xy.operations, (
                    f"Expected '{family}_{gate}' in xy.operations"
                )

    def test_hermite_pulse_wired_with_correct_type(self):
        """Hermite family should wire ScalableHermitePulse instances."""
        from quam_builder.architecture.quantum_dots.components.pulses import ScalableHermitePulse

        machine = _make_wired_machine()
        PulseWirer().wire(machine)

        xy = machine.qubits["Q1"].xy
        assert isinstance(xy.operations["hermite_x90"], ScalableHermitePulse)
        assert isinstance(xy.operations["hermite_x180"], ScalableHermitePulse)

    def test_drag_pulse_wired_with_correct_type(self):
        """DRAG family should wire ScalableDragPulse instances."""
        from quam_builder.architecture.quantum_dots.components.pulses import ScalableDragPulse

        machine = _make_wired_machine()
        PulseWirer().wire(machine)

        xy = machine.qubits["Q1"].xy
        assert isinstance(xy.operations["drag_x90"], ScalableDragPulse)
        assert isinstance(xy.operations["drag_x180"], ScalableDragPulse)

    def test_single_channel_no_axis_angle(self):
        machine = _make_wired_machine()
        PulseWirer().wire(machine)

        xy = machine.qubits["Q1"].xy
        assert xy.operations["gaussian_x90"].axis_angle is None

    def test_readout_resonator_gets_default_pulse(self):
        machine = _make_wired_machine()
        PulseWirer().wire(machine)

        rr = machine.sensor_dots["virtual_sensor_1"].readout_resonator
        assert "readout" in rr.operations
        assert isinstance(rr.operations["readout"], quam_pulses.SquareReadoutPulse)

    def test_existing_pulses_not_overwritten(self):
        machine = _make_wired_machine()
        custom_pulse = quam_pulses.GaussianPulse(length=500, amplitude=0.3, sigma=83)
        machine.qubits["Q1"].xy.operations["gaussian_x90"] = custom_pulse

        PulseWirer().wire(machine)

        assert machine.qubits["Q1"].xy.operations["gaussian_x90"] is custom_pulse

    def test_existing_readout_not_overwritten(self):
        machine = _make_wired_machine()
        custom_readout = quam_pulses.SquareReadoutPulse(length=5000, amplitude=0.5)
        machine.sensor_dots["virtual_sensor_1"].readout_resonator.operations[
            "readout"
        ] = custom_readout

        PulseWirer().wire(machine)

        rr = machine.sensor_dots["virtual_sensor_1"].readout_resonator
        assert rr.operations["readout"] is custom_readout


class TestWireMacrosPulseIntegration:
    """Test that wire_machine_macros wires both macros and pulses."""

    def test_full_wiring_adds_pulses(self):
        machine = _make_wired_machine()
        wire_machine_macros(machine)

        xy = machine.qubits["Q1"].xy
        assert "gaussian_x90" in xy.operations

        rr = machine.sensor_dots["virtual_sensor_1"].readout_resonator
        assert "readout" in rr.operations

    def test_pulse_override_all_ldqubits_before_wire(self):
        """Override pulse on all LDQubits by pre-seeding xy.operations (PulseWirer is additive)."""
        machine = _make_wired_machine()
        for qubit in machine.qubits.values():
            if not isinstance(qubit, LDQubit) or qubit.xy is None:
                continue
            qubit.xy.operations["gaussian_x90"] = quam_pulses.GaussianPulse(
                length=500, amplitude=0.3, sigma=83
            )

        wire_machine_macros(machine)

        gaussian = machine.qubits["Q1"].xy.operations["gaussian_x90"]
        assert gaussian.length == 500
        assert gaussian.amplitude == 0.3

    def test_pulse_removed_after_wire(self):
        """Removing the default XY pulse after wiring (no type-level pulse-disable hook)."""
        machine = _make_wired_machine()
        wire_machine_macros(machine)

        for qubit in machine.qubits.values():
            if not isinstance(qubit, LDQubit) or qubit.xy is None:
                continue
            qubit.xy.operations.pop("gaussian_x90", None)

        xy = machine.qubits["Q1"].xy
        assert "gaussian_x90" not in xy.operations

    def test_instance_pulse_override_before_wire(self):
        """Override pulse on one qubit by pre-seeding operations before wire_machine_macros."""
        machine = _make_wired_machine()
        machine.qubits["Q1"].xy.operations["gaussian_x90"] = quam_pulses.GaussianPulse(
            length=800, amplitude=0.15, sigma=133
        )

        wire_machine_macros(machine)

        gaussian = machine.qubits["Q1"].xy.operations["gaussian_x90"]
        assert gaussian.length == 800
        assert gaussian.amplitude == 0.15


class TestPulseFamilySwitchingIntegration:
    """Test set_pulse_family() propagation to macros after wiring."""

    def test_set_pulse_family_propagates_to_macros(self):
        machine = _make_wired_machine()
        wire_machine_macros(machine)

        machine.set_pulse_family("kaiser")

        q1 = machine.qubits["Q1"]
        xy_macro = q1.macros["xy_drive"]
        assert xy_macro.pulse_family == "kaiser"
        assert xy_macro.pulse_name == "kaiser_x90"

    def test_set_pulse_family_invalid_raises(self):
        import pytest

        machine = _make_wired_machine()
        wire_machine_macros(machine)

        with pytest.raises(ValueError, match="Unknown pulse family"):
            machine.set_pulse_family("nonexistent")

    def test_set_pulse_family_switches_all_macro_types(self):
        machine = _make_wired_machine()
        wire_machine_macros(machine)

        machine.set_pulse_family("square")

        q1 = machine.qubits["Q1"]
        assert q1.macros["x180"].pulse_name == "square_x180"
        assert q1.macros["x90"].pulse_name == "square_x90"
        assert q1.macros["y90"].pulse_name == "square_y90"

    def test_default_pulse_family_is_gaussian(self):
        machine = _make_wired_machine()
        assert machine.pulse_family == "gaussian"

        wire_machine_macros(machine)

        q1 = machine.qubits["Q1"]
        assert q1.macros["xy_drive"].pulse_name == "gaussian_x90"

    def test_set_pulse_family_hermite_propagates(self):
        """set_pulse_family('hermite') should switch all XY macros to the hermite family."""
        machine = _make_wired_machine()
        wire_machine_macros(machine)

        machine.set_pulse_family("hermite")

        q1 = machine.qubits["Q1"]
        assert q1.macros["xy_drive"].pulse_family == "hermite"
        assert q1.macros["xy_drive"].pulse_name == "hermite_x90"
        assert q1.macros["x180"].pulse_name == "hermite_x180"
        assert q1.macros["y90"].pulse_name == "hermite_y90"
        assert q1.macros["x_neg90"].pulse_name == "hermite_x_neg90"

    def test_set_pulse_family_drag_propagates(self):
        """set_pulse_family('drag') should switch all XY macros to the drag family."""
        machine = _make_wired_machine()
        wire_machine_macros(machine)

        machine.set_pulse_family("drag")

        q1 = machine.qubits["Q1"]
        assert q1.macros["xy_drive"].pulse_family == "drag"
        assert q1.macros["xy_drive"].pulse_name == "drag_x90"
        assert q1.macros["x180"].pulse_name == "drag_x180"
        assert q1.macros["y90"].pulse_name == "drag_y90"
        assert q1.macros["x_neg90"].pulse_name == "drag_x_neg90"
