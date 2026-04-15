"""Tests for XYDrive channel variants.

Covers XYDriveSingle, XYDriveIQ, and XYDriveMW creation, default-pulse
generation, custom-pulse addition, and .play() inside a QUA program.
All objects are real — no mocks or stubs.
"""

import pytest
from qm import qua
from quam.components import StickyChannelAddon, pulses
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    MWFEMAnalogOutputPort,
)

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    XYDriveMW,
    XYDriveSingle,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


# ---------------------------------------------------------------------------
# XYDriveSingle
# ---------------------------------------------------------------------------


class TestXYDriveSingleCreation:
    def test_basic_creation(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
        assert drive.id == "xy_single"
        assert drive.RF_frequency == int(100e6)
        assert drive.intermediate_frequency == int(100e6)

    def test_no_default_pulses_on_creation(self):
        """XYDriveSingle no longer adds default pulses in __post_init__."""
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
        # No pulses added at construction time — they come from wire_machine_macros
        assert "gaussian" not in drive.operations
        assert "pi" not in drive.operations

    def test_add_custom_pulse(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
        drive.add_pulse("rabi", pulses.GaussianPulse(length=100, amplitude=0.2, sigma=20))
        assert "rabi" in drive.operations
        assert drive.operations["rabi"].length == 100


class TestXYDriveSingleInQUA:
    def test_play_pulse_compiles(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
        drive.operations["gaussian"] = pulses.GaussianPulse(length=100, amplitude=0.2, sigma=40)
        with qua.program() as prog:
            drive.play("gaussian")
        assert prog is not None

    def test_play_with_amplitude_scale(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
        drive.operations["pi"] = pulses.SquarePulse(length=104, amplitude=0.2)
        with qua.program() as prog:
            drive.play("pi", amplitude_scale=0.5)
        assert prog is not None

    def test_play_with_duration_override(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
        drive.operations["gaussian"] = pulses.GaussianPulse(length=100, amplitude=0.2, sigma=40)
        with qua.program() as prog:
            t = qua.declare(int)
            qua.assign(t, 100)
            drive.play("gaussian", duration=t)
        assert prog is not None


# ---------------------------------------------------------------------------
# XYDriveMW
# ---------------------------------------------------------------------------


class TestXYDriveMWCreation:
    def test_basic_creation(self):
        drive = XYDriveMW(
            id="xy_mw",
            opx_output=MWFEMAnalogOutputPort(
                controller_id="con1",
                fem_id=1,
                port_id=1,
                band=2,
                upconverter_frequency=int(5e9),
                full_scale_power_dbm=10,
            ),
            intermediate_frequency=int(100e6),
        )
        assert drive.id == "xy_mw"
        assert drive.intermediate_frequency == int(100e6)
        assert drive.upconverter_frequency == int(5e9)

    def test_add_pulse_and_play(self):
        drive = XYDriveMW(
            id="xy_mw",
            opx_output=MWFEMAnalogOutputPort(
                controller_id="con1",
                fem_id=1,
                port_id=1,
                band=2,
                upconverter_frequency=int(5e9),
                full_scale_power_dbm=10,
            ),
            intermediate_frequency=int(100e6),
        )
        drive.operations["drive"] = pulses.GaussianPulse(
            length=100,
            amplitude=0.2,
            sigma=20,
        )
        with qua.program() as prog:
            drive.play("drive")
        assert prog is not None


class TestXYDriveValidation:
    def _make_mw_drive(self, upconverter_freq: int, if_freq: int) -> XYDriveMW:
        return XYDriveMW(
            id="xy_mw",
            opx_output=MWFEMAnalogOutputPort(
                controller_id="con1",
                fem_id=1,
                port_id=1,
                band=2,
                upconverter_frequency=upconverter_freq,
                full_scale_power_dbm=10,
            ),
            intermediate_frequency=if_freq,
        )

    def test_valid_if_passes(self):
        drive = self._make_mw_drive(int(5e9), int(100e6))
        drive.validate_intermediate_frequency()

    def test_mw_if_at_500mhz_passes(self):
        drive = self._make_mw_drive(int(5e9), int(500e6))
        drive.validate_intermediate_frequency()  # MW FEM limit is 500 MHz

    def test_if_exceeds_limit_raises(self):
        drive = self._make_mw_drive(int(5e9), int(600e6))
        with pytest.raises(ValueError, match="exceeds"):
            drive.validate_intermediate_frequency()

    def test_negative_if_within_limit_passes(self):
        drive = self._make_mw_drive(int(5e9), int(-200e6))
        drive.validate_intermediate_frequency()

    def test_negative_if_exceeds_limit_raises(self):
        drive = self._make_mw_drive(int(5e9), int(-600e6))
        with pytest.raises(ValueError, match="exceeds"):
            drive.validate_intermediate_frequency()


class TestXYDriveRFReference:
    def _make_machine_with_qubit(self):
        """Build minimal machine with one qubit, no XY drive yet."""
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
        return machine

    def test_mw_rf_frequency_references_larmor(self):
        """XYDriveMW.RF_frequency should resolve to qubit.larmor_frequency."""
        machine = self._make_machine_with_qubit()
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

        assert xy.RF_frequency == 5.1e9
        assert xy.intermediate_frequency == pytest.approx(0.1e9)

    def test_mw_rf_tracks_larmor_change(self):
        """Changing larmor_frequency should be reflected in xy.RF_frequency."""
        machine = self._make_machine_with_qubit()
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

        qubit.larmor_frequency = 5.2e9
        assert xy.RF_frequency == 5.2e9
        assert xy.intermediate_frequency == pytest.approx(0.2e9)
