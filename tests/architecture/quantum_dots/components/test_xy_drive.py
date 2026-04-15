"""Tests for XYDrive channel variants.

Covers XYDriveSingle, XYDriveIQ, and XYDriveMW creation, default-pulse
generation, custom-pulse addition, and .play() inside a QUA program.
All objects are real — no mocks or stubs.
"""

import pytest
from qm import qua
from quam.components import pulses
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    MWFEMAnalogOutputPort,
)

from quam_builder.architecture.quantum_dots.components import (
    XYDriveSingle,
    XYDriveMW,
)


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

    def test_if_exceeds_400mhz_raises(self):
        drive = self._make_mw_drive(int(5e9), int(500e6))
        with pytest.raises(ValueError, match="exceeds"):
            drive.validate_intermediate_frequency()

    def test_negative_if_within_limit_passes(self):
        drive = self._make_mw_drive(int(5e9), int(-200e6))
        drive.validate_intermediate_frequency()

    def test_negative_if_exceeds_limit_raises(self):
        drive = self._make_mw_drive(int(5e9), int(-500e6))
        with pytest.raises(ValueError, match="exceeds"):
            drive.validate_intermediate_frequency()
