"""Tests for pulse wiring via wire_machine_macros and TOML pulse overrides."""

import pytest
from unittest.mock import MagicMock

from quam.components import pulses as quam_pulses, StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveSingle
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.macro_engine.wiring import (
    _ensure_default_pulses,
)


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
    """Test that _ensure_default_pulses adds pulses to the right places."""

    def test_xy_drive_gets_default_pulses(self):
        machine = _make_wired_machine()
        _ensure_default_pulses(machine)

        xy = machine.qubits["Q1"].xy
        assert "x180" in xy.operations
        assert "x90" in xy.operations
        assert "y180" in xy.operations
        assert "y90" in xy.operations
        assert "-x90" in xy.operations
        assert "-y90" in xy.operations

    def test_single_channel_no_axis_angle(self):
        machine = _make_wired_machine()
        _ensure_default_pulses(machine)

        xy = machine.qubits["Q1"].xy
        for name in ("x180", "x90", "-x90", "y180", "y90", "-y90"):
            assert xy.operations[name].axis_angle is None

    def test_readout_resonator_gets_default_pulse(self):
        machine = _make_wired_machine()
        _ensure_default_pulses(machine)

        rr = machine.sensor_dots["virtual_sensor_1"].readout_resonator
        assert "readout" in rr.operations
        assert isinstance(rr.operations["readout"], quam_pulses.SquareReadoutPulse)

    def test_existing_pulses_not_overwritten(self):
        machine = _make_wired_machine()
        custom_pulse = quam_pulses.GaussianPulse(length=500, amplitude=0.3, sigma=83)
        machine.qubits["Q1"].xy.operations["x180"] = custom_pulse

        _ensure_default_pulses(machine)

        # Custom pulse should be preserved
        assert machine.qubits["Q1"].xy.operations["x180"] is custom_pulse

    def test_existing_readout_not_overwritten(self):
        machine = _make_wired_machine()
        custom_readout = quam_pulses.SquareReadoutPulse(length=5000, amplitude=0.5)
        machine.sensor_dots["virtual_sensor_1"].readout_resonator.operations[
            "readout"
        ] = custom_readout

        _ensure_default_pulses(machine)

        rr = machine.sensor_dots["virtual_sensor_1"].readout_resonator
        assert rr.operations["readout"] is custom_readout


class TestWireMacrosPulseIntegration:
    """Test that wire_machine_macros wires both macros and pulses."""

    def test_full_wiring_adds_pulses(self, reset_catalog):
        machine = _make_wired_machine()
        wire_machine_macros(machine)

        xy = machine.qubits["Q1"].xy
        assert "x180" in xy.operations

        rr = machine.sensor_dots["virtual_sensor_1"].readout_resonator
        assert "readout" in rr.operations

    def test_pulse_overrides_via_mapping(self, reset_catalog):
        machine = _make_wired_machine()
        overrides = {
            "component_types": {
                "LDQubit": {
                    "pulses": {
                        "x180": {
                            "type": "GaussianPulse",
                            "length": 500,
                            "amplitude": 0.3,
                            "sigma": 83,
                        }
                    }
                }
            }
        }
        wire_machine_macros(machine, macro_overrides=overrides)

        x180 = machine.qubits["Q1"].xy.operations["x180"]
        assert x180.length == 500
        assert x180.amplitude == 0.3

    def test_pulse_disable_via_mapping(self, reset_catalog):
        machine = _make_wired_machine()
        overrides = {"component_types": {"LDQubit": {"pulses": {"-y90": {"enabled": False}}}}}
        wire_machine_macros(machine, macro_overrides=overrides)

        xy = machine.qubits["Q1"].xy
        assert "x180" in xy.operations  # others still present
        assert "-y90" not in xy.operations  # disabled

    def test_instance_pulse_override(self, reset_catalog):
        machine = _make_wired_machine()
        overrides = {
            "instances": {
                "qubits.Q1": {
                    "pulses": {
                        "x180": {
                            "type": "GaussianPulse",
                            "length": 800,
                            "amplitude": 0.15,
                            "sigma": 133,
                        }
                    }
                }
            }
        }
        wire_machine_macros(machine, macro_overrides=overrides)

        x180 = machine.qubits["Q1"].xy.operations["x180"]
        assert x180.length == 800
        assert x180.amplitude == 0.15
