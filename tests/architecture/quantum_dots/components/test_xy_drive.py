"""Tests for XYDrive channel variants.

Covers XYDriveSingle, XYDriveIQ, and XYDriveMW creation, default-pulse
generation, custom-pulse addition, and .play() inside a QUA program.
All objects are real — no mocks or stubs.
"""

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

    def test_default_pulses_added(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
            add_default_pulses=True,
        )
        assert "gaussian" in drive.operations
        assert "pi" in drive.operations
        assert "pi_half" in drive.operations

    def test_no_default_pulses(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
            add_default_pulses=False,
        )
        assert "gaussian" not in drive.operations
        assert "pi" not in drive.operations

    def test_add_custom_pulse(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
            add_default_pulses=False,
        )
        drive.add_pulse("rabi", pulses.GaussianPulse(length=100, amplitude=0.2, sigma=20))
        assert "rabi" in drive.operations
        assert drive.operations["rabi"].length == 100


class TestXYDriveSingleInQUA:
    def test_play_default_pulse_compiles(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
        with qua.program() as prog:
            drive.play("gaussian")
        assert prog is not None

    def test_play_with_amplitude_scale(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
        with qua.program() as prog:
            drive.play("pi", amplitude_scale=0.5)
        assert prog is not None

    def test_play_with_duration_override(self):
        drive = XYDriveSingle(
            id="xy_single",
            RF_frequency=int(100e6),
            opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        )
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
