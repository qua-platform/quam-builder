"""Tests for readout duration inference chain and apply() wiring.

Covers:
- SensorDotMeasureMacro.inferred_duration converts pulse samples to ns
- MeasurePSBPairMacro.inferred_duration = ramp + buffer + per-pair sensor duration
- MeasurePSBPairMacro.apply() aligns the resonator with the gates, ramps, then reads out
- Measure1QMacro.inferred_duration navigates full chain
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    Measure1QMacro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    MeasurePSBPairMacro,
    SensorDotMeasureMacro,
)
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.operations.names import (
    VoltagePointName,
)

_STATE_MACROS = "quam_builder.architecture.quantum_dots.operations.default_macros.state_macros"
_OWNER_PATCH = f"{_STATE_MACROS}._owner_component"
_QUA_PATCH = f"{_STATE_MACROS}.qua"


def _mock_sensor_owner(pulse_length: int = 2000) -> MagicMock:
    """Build a mock sensor dot owner with a readout resonator and pulse."""
    owner = MagicMock()
    pulse = MagicMock()
    pulse.length = pulse_length
    owner.readout_resonator.operations = {"readout": pulse}
    owner.readout_resonator.name = "rr1"
    return owner


# --------------------------------------------------------------------------- #
# SensorDotMeasureMacro.inferred_duration
# --------------------------------------------------------------------------- #


class TestSensorDotMeasureInferredDuration:
    def test_returns_pulse_length_in_seconds(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = _mock_sensor_owner(pulse_length=2000)

        with patch(_OWNER_PATCH, return_value=owner):
            assert macro.inferred_duration == pytest.approx(2000 * 1e-9)

    def test_returns_none_when_no_resonator(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = MagicMock()
        owner.readout_resonator = None

        with patch(_OWNER_PATCH, return_value=owner):
            assert macro.inferred_duration is None

    def test_returns_none_when_pulse_missing(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = MagicMock()
        owner.readout_resonator.operations = {}

        with patch(_OWNER_PATCH, return_value=owner):
            assert macro.inferred_duration is None

    def test_returns_none_when_pulse_has_no_length(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = MagicMock()
        pulse = MagicMock(spec=[])
        owner.readout_resonator.operations = {"readout": pulse}

        with patch(_OWNER_PATCH, return_value=owner):
            assert macro.inferred_duration is None

    def test_readout_pulse_length_ns_property(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = _mock_sensor_owner(pulse_length=1600)

        with patch(_OWNER_PATCH, return_value=owner):
            assert macro.readout_pulse_length_ns == 1600


# --------------------------------------------------------------------------- #
# MeasurePSBPairMacro — buffer_duration + inferred_duration
# --------------------------------------------------------------------------- #


def _mock_pair_owner(sensor_duration_s=2e-6, readout_length_ns=2000):
    """Build a mock QuantumDotPair owner whose sensor macro reports per-pair readout timing."""
    sensor_macro = MagicMock()
    sensor_macro.inferred_duration_for_pair.return_value = sensor_duration_s
    sensor_macro.readout_pulse_length_ns_for_pair.return_value = readout_length_ns

    sensor_dot = MagicMock()
    sensor_dot.macros = {VoltagePointName.MEASURE.value: sensor_macro}
    sensor_dot.readout_resonator.name = "rr1"

    owner = MagicMock()
    owner.id = "pair1"
    owner.sensor_dots = [sensor_dot]
    return owner, sensor_macro


class TestMeasurePSBPairDuration:
    def test_default_durations(self):
        macro = MeasurePSBPairMacro()
        assert macro.buffer_duration == DEFAULTS.state_macro.buffer_duration
        assert macro.ramp_duration == DEFAULTS.state_macro.ramp_duration

    def test_buffer_duration_settable(self):
        macro = MeasurePSBPairMacro(buffer_duration=500)
        assert macro.buffer_duration == 500

    def test_inferred_duration_ramp_plus_buffer_plus_sensor(self):
        macro = MeasurePSBPairMacro(buffer_duration=200, ramp_duration=50)
        owner, sensor_macro = _mock_pair_owner(sensor_duration_s=2e-6)

        with patch(_OWNER_PATCH, return_value=owner):
            dur = macro.inferred_duration

        assert dur == pytest.approx(50 * 4e-9 + 200 * 4e-9 + 2e-6)
        sensor_macro.inferred_duration_for_pair.assert_called_once_with("pair1")

    def test_inferred_duration_zero_buffer_and_ramp(self):
        """When buffer_duration and ramp_duration are None, they contribute 0."""
        macro = MeasurePSBPairMacro(buffer_duration=None, ramp_duration=None)
        owner, _ = _mock_pair_owner(sensor_duration_s=2e-6)

        with patch(_OWNER_PATCH, return_value=owner):
            dur = macro.inferred_duration

        assert dur == pytest.approx(2e-6)

    def test_inferred_duration_none_without_sensor(self):
        macro = MeasurePSBPairMacro(buffer_duration=100)
        owner = MagicMock()
        owner.sensor_dots = []

        with patch(_OWNER_PATCH, return_value=owner):
            assert macro.inferred_duration is None

    def test_inferred_duration_none_when_sensor_has_no_duration(self):
        macro = MeasurePSBPairMacro(buffer_duration=100)
        owner, _ = _mock_pair_owner(sensor_duration_s=None)

        with patch(_OWNER_PATCH, return_value=owner):
            assert macro.inferred_duration is None

    def test_apply_aligns_ramps_and_reads_out(self):
        """apply() aligns the resonator with the gates, ramps and holds through the
        readout, makes the resonator wait for ramp + buffer, then calls the sensor."""
        macro = MeasurePSBPairMacro(buffer_duration=100, ramp_duration=20)
        owner, sensor_macro = _mock_pair_owner(readout_length_ns=2000)

        ch1 = MagicMock()
        ch1.name = "gate_P1"
        ch2 = MagicMock()
        ch2.name = "gate_P2"
        owner.voltage_sequence.gate_set.channels.values.return_value = [ch1, ch2]

        with patch(_OWNER_PATCH, return_value=owner), patch(_QUA_PATCH) as qua_mod:
            macro.apply()

        qua_mod.align.assert_called_once_with("rr1", "gate_P1", "gate_P2")
        owner.ramp_to_point.assert_called_once_with(
            VoltagePointName.MEASURE.value, ramp_duration=20 * 4, duration=100 * 4 + 2000
        )
        qua_mod.wait.assert_called_once_with(100 + 20, "rr1")
        sensor_macro.apply.assert_called_once_with(
            quantum_dot_pair_id="pair1",
            voltage_sequence=owner.voltage_sequence,
            gate_channel_names=None,
        )

    def test_apply_raises_without_readout_length(self):
        macro = MeasurePSBPairMacro()
        owner, _ = _mock_pair_owner(readout_length_ns=None)

        with patch(_OWNER_PATCH, return_value=owner), patch(_QUA_PATCH):
            with pytest.raises(ValueError, match="Readout duration not found"):
                macro.apply()


# --------------------------------------------------------------------------- #
# Measure1QMacro.inferred_duration
# --------------------------------------------------------------------------- #


def _mock_qubit_with_qubit_pair():
    """Build a mock qubit whose preferred readout dot resolves to an LDQubitPair."""
    qubit = MagicMock()
    qubit.preferred_readout_quantum_dot = "dot2"
    qubit.quantum_dot.id = "dot1"

    pair = MagicMock()
    pair.qubit_control = qubit
    pair.qubit_target.quantum_dot.id = "dot2"
    qubit.machine.qubit_pairs = {"Q1_Q2": pair}
    return qubit, pair


class TestMeasure1QInferredDuration:
    def test_inferred_duration_navigates_chain(self):
        pair_macro = MagicMock()
        pair_macro.inferred_duration = 2.2e-6

        qubit, pair = _mock_qubit_with_qubit_pair()
        pair.macros = {"measure": pair_macro}

        macro = Measure1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            dur = macro.inferred_duration

        assert dur == pytest.approx(2.2e-6)

    def test_inferred_duration_none_without_preferred_dot(self):
        qubit = MagicMock()
        qubit.preferred_readout_quantum_dot = None

        macro = Measure1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            assert macro.inferred_duration is None

    def test_inferred_duration_none_when_pair_not_found(self):
        qubit, _ = _mock_qubit_with_qubit_pair()
        qubit.machine.qubit_pairs = {}

        macro = Measure1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            assert macro.inferred_duration is None

    def test_inferred_duration_none_when_pair_has_no_measure_macro(self):
        qubit, pair = _mock_qubit_with_qubit_pair()
        pair.macros = {}

        macro = Measure1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            assert macro.inferred_duration is None
