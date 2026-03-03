"""Unit tests for quantum dot pulse generation with all XY drive types."""

# pylint: disable=too-few-public-methods

from unittest.mock import MagicMock

import pytest
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorSingle,
    XYDriveSingle,
    XYDriveIQ,
    XYDriveMW,
)
from quam_builder.builder.quantum_dots.pulses import (
    add_default_ldv_qubit_pulses,
    add_default_ldv_qubit_pair_pulses,
    add_default_resonator_pulses,
)

_EXPECTED_XY_PULSES = ["x180", "x90", "y180", "y90", "-x90", "-y90"]


def _make_mock_qubit_with_xy(xy_drive):
    """Return a mock qubit whose .xy is the given drive instance."""
    qubit = MagicMock()
    qubit.xy = xy_drive
    qubit.xy.operations = {}
    return qubit


class TestAddDefaultLDVQubitPulsesXYDriveSingle:
    """Tests for add_default_ldv_qubit_pulses using XYDriveSingle."""

    def test_add_xy_pulses(self):
        qubit = _make_mock_qubit_with_xy(
            XYDriveSingle(
                opx_output="/tmp/opx",
                id="xy_single",
                RF_frequency=100_000_000,
                add_default_pulses=False,
            )
        )
        qubit.xy.operations = {}

        add_default_ldv_qubit_pulses(qubit)

        for name in _EXPECTED_XY_PULSES:
            assert name in qubit.xy.operations, f"Pulse {name} not found"

    def test_xy_pulse_properties(self):
        qubit = _make_mock_qubit_with_xy(
            XYDriveSingle(
                opx_output="/tmp/opx",
                id="xy_single",
                RF_frequency=100_000_000,
                add_default_pulses=False,
            )
        )
        qubit.xy.operations = {}

        add_default_ldv_qubit_pulses(qubit)

        x180 = qubit.xy.operations["x180"]
        assert x180.length == 1000
        assert x180.amplitude == 0.2
        assert x180.axis_angle == pytest.approx(0.0)

        y90 = qubit.xy.operations["y90"]
        assert y90.amplitude == 0.1
        assert y90.axis_angle == pytest.approx(1.5707963, rel=1e-5)

    def test_six_operations_added(self):
        qubit = _make_mock_qubit_with_xy(
            XYDriveSingle(
                opx_output="/tmp/opx",
                id="xy_single",
                RF_frequency=100_000_000,
                add_default_pulses=False,
            )
        )
        qubit.xy.operations = {}

        add_default_ldv_qubit_pulses(qubit)

        assert len(qubit.xy.operations) == 6


class TestAddDefaultLDVQubitPulsesXYDriveIQ:
    """Tests for add_default_ldv_qubit_pulses using XYDriveIQ."""

    def _make_iq_qubit(self):
        xy = XYDriveIQ(
            id="q1_xy",
            intermediate_frequency=500_000_000,
            opx_output_I="#/wiring/q1/drive/opx_output_I",
            opx_output_Q="#/wiring/q1/drive/opx_output_Q",
            frequency_converter_up="#/wiring/q1/drive/frequency_converter_up",
        )
        qubit = MagicMock()
        qubit.xy = xy
        qubit.xy.operations = {}
        return qubit

    def test_add_xy_pulses(self):
        qubit = self._make_iq_qubit()

        add_default_ldv_qubit_pulses(qubit)

        for name in _EXPECTED_XY_PULSES:
            assert name in qubit.xy.operations, f"Pulse {name} not found for XYDriveIQ"

    def test_xy_pulse_properties(self):
        qubit = self._make_iq_qubit()

        add_default_ldv_qubit_pulses(qubit)

        x180 = qubit.xy.operations["x180"]
        assert x180.length == 1000
        assert x180.amplitude == 0.2
        assert x180.axis_angle == pytest.approx(0.0)

    def test_six_operations_added(self):
        qubit = self._make_iq_qubit()

        add_default_ldv_qubit_pulses(qubit)

        assert len(qubit.xy.operations) == 6


class TestAddDefaultLDVQubitPulsesXYDriveMW:
    """Tests for add_default_ldv_qubit_pulses using XYDriveMW."""

    def _make_mw_qubit(self):
        xy = XYDriveMW(
            id="q1_xy",
            intermediate_frequency=500_000_000,
            opx_output="#/wiring/q1/drive/opx_output",
        )
        qubit = MagicMock()
        qubit.xy = xy
        qubit.xy.operations = {}
        return qubit

    def test_add_xy_pulses(self):
        qubit = self._make_mw_qubit()

        add_default_ldv_qubit_pulses(qubit)

        for name in _EXPECTED_XY_PULSES:
            assert name in qubit.xy.operations, f"Pulse {name} not found for XYDriveMW"

    def test_xy_pulse_properties(self):
        qubit = self._make_mw_qubit()

        add_default_ldv_qubit_pulses(qubit)

        x180 = qubit.xy.operations["x180"]
        assert x180.length == 1000
        assert x180.amplitude == 0.2
        assert x180.axis_angle == pytest.approx(0.0)

    def test_six_operations_added(self):
        qubit = self._make_mw_qubit()

        add_default_ldv_qubit_pulses(qubit)

        assert len(qubit.xy.operations) == 6


class TestAddDefaultLDVQubitPulsesEdgeCases:
    """Edge-case tests independent of drive type."""

    def test_add_readout_pulses_to_resonator(self):
        qubit = MagicMock()
        qubit.resonator = ReadoutResonatorSingle(
            id="readout_resonator",
            frequency_bare=0.0,
            opx_output=LFFEMAnalogOutputPort("con1", 1, port_id=1),
            opx_input=LFFEMAnalogInputPort("con1", 1, port_id=2),
            sticky=StickyChannelAddon(duration=16, digital=False),
            operations={},
        )

        add_default_resonator_pulses(qubit.resonator)

        assert "readout" in qubit.resonator.operations
        assert qubit.resonator.operations["readout"] is not None

    def test_no_pulses_added_when_xy_is_none(self):
        qubit = MagicMock()
        qubit.xy = None
        qubit.resonator = None

        add_default_ldv_qubit_pulses(qubit)  # Must not raise

    def test_both_xy_and_resonator_pulses(self):
        qubit = MagicMock()
        qubit.xy = XYDriveSingle(
            opx_output="/tmp/opx",
            id="xy_single",
            RF_frequency=100_000_000,
            add_default_pulses=False,
        )
        qubit.xy.operations = {}
        qubit.resonator = ReadoutResonatorSingle(
            id="readout_resonator",
            frequency_bare=0.0,
            opx_output=LFFEMAnalogOutputPort("con1", 1, port_id=1),
            opx_input=LFFEMAnalogInputPort("con1", 1, port_id=2),
            sticky=StickyChannelAddon(duration=16, digital=False),
            operations={},
        )

        add_default_ldv_qubit_pulses(qubit)
        add_default_resonator_pulses(qubit.resonator)

        assert len(qubit.xy.operations) == 6
        assert "readout" in qubit.resonator.operations


class TestAddDefaultLDVQubitPairPulses:
    """Tests for add_default_ldv_qubit_pair_pulses function."""

    def test_qubit_pair_pulse_function_runs_without_error(self):
        qubit_pair = MagicMock()
        qubit_pair.z = MagicMock()

        add_default_ldv_qubit_pair_pulses(qubit_pair)
