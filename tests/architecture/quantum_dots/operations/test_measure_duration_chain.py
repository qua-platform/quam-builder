"""Tests for readout duration inference chain and apply() wiring.

Covers:
- SensorDotMeasureMacro.inferred_duration converts pulse samples to ns
- SensorDotMeasureMacro.apply() calls qua.align + track_sticky_duration
- MeasurePSBPairMacro.inferred_duration = buffer + sensor duration
- MeasurePSBPairMacro.buffer_duration rename (from hold_duration)
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
from quam_builder.architecture.quantum_dots.operations.names import (
    VoltagePointName,
)

_OWNER_PATCH = (
    "quam_builder.architecture.quantum_dots.operations.default_macros"
    ".state_macros._owner_component"
)


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
            assert macro.inferred_duration == pytest.approx(2000 * 4e-9)

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
            assert macro.readout_pulse_length_ns == 6400


# --------------------------------------------------------------------------- #
# SensorDotMeasureMacro.apply() — alignment and voltage tracking
# --------------------------------------------------------------------------- #


def _qua_mock_context():
    """Context manager that mocks ``qm.qua`` imports used by ``apply()``."""
    mock_mod = MagicMock()
    mock_mod.declare.return_value = 0.0
    mock_mod.fixed = "fixed_sentinel"
    return patch.dict("sys.modules", {"qm": MagicMock(), "qm.qua": mock_mod}), mock_mod


class TestSensorDotMeasureApply:
    def test_aligns_gates_with_resonator(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = _mock_sensor_owner(pulse_length=2000)
        vs = MagicMock()
        gate_names = ["gate_P1", "gate_P2"]

        ctx, qua_mod = _qua_mock_context()
        with patch(_OWNER_PATCH, return_value=owner), ctx:
            macro.apply(
                voltage_sequence=vs,
                gate_channel_names=gate_names,
            )

        qua_mod.align.assert_called_once_with("gate_P1", "gate_P2", "rr1")

    def test_tracks_sticky_duration(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = _mock_sensor_owner(pulse_length=2000)
        vs = MagicMock()

        ctx, _ = _qua_mock_context()
        with patch(_OWNER_PATCH, return_value=owner), ctx:
            macro.apply(
                voltage_sequence=vs,
                gate_channel_names=["gate_P1"],
            )

        vs.track_sticky_duration.assert_called_once_with(8000)

    def test_no_align_without_gate_names(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = _mock_sensor_owner(pulse_length=2000)
        vs = MagicMock()

        ctx, qua_mod = _qua_mock_context()
        with patch(_OWNER_PATCH, return_value=owner), ctx:
            macro.apply(voltage_sequence=vs)

        qua_mod.align.assert_not_called()

    def test_no_track_without_voltage_sequence(self):
        macro = SensorDotMeasureMacro(pulse_name="readout")
        owner = _mock_sensor_owner(pulse_length=2000)

        ctx, _ = _qua_mock_context()
        with patch(_OWNER_PATCH, return_value=owner), ctx:
            result = macro.apply(gate_channel_names=["gate_P1"])

        assert result is not None


# --------------------------------------------------------------------------- #
# MeasurePSBPairMacro — buffer_duration + inferred_duration
# --------------------------------------------------------------------------- #


class TestMeasurePSBPairDuration:
    def test_buffer_duration_field_exists(self):
        macro = MeasurePSBPairMacro()
        assert hasattr(macro, "buffer_duration")
        assert macro.buffer_duration is None

    def test_buffer_duration_settable(self):
        macro = MeasurePSBPairMacro(buffer_duration=500)
        assert macro.buffer_duration == 500

    def test_inferred_duration_buffer_plus_sensor(self):
        macro = MeasurePSBPairMacro(buffer_duration=200)
        sensor_macro = MagicMock()
        sensor_macro.inferred_duration = 2e-6

        sensor_dot = MagicMock()
        sensor_dot.macros = {VoltagePointName.MEASURE.value: sensor_macro}

        owner = MagicMock()
        owner.sensor_dots = [sensor_dot]

        with patch(_OWNER_PATCH, return_value=owner):
            dur = macro.inferred_duration

        assert dur == pytest.approx(200e-9 + 2e-6)

    def test_inferred_duration_zero_buffer(self):
        """When buffer_duration is None, buffer contribution is 0."""
        macro = MeasurePSBPairMacro(buffer_duration=None)
        sensor_macro = MagicMock()
        sensor_macro.inferred_duration = 2e-6

        sensor_dot = MagicMock()
        sensor_dot.macros = {VoltagePointName.MEASURE.value: sensor_macro}

        owner = MagicMock()
        owner.sensor_dots = [sensor_dot]

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
        sensor_macro = MagicMock()
        sensor_macro.inferred_duration = None

        sensor_dot = MagicMock()
        sensor_dot.macros = {VoltagePointName.MEASURE.value: sensor_macro}

        owner = MagicMock()
        owner.sensor_dots = [sensor_dot]

        with patch(_OWNER_PATCH, return_value=owner):
            assert macro.inferred_duration is None

    def test_apply_passes_voltage_context_to_sensor(self):
        """Verify apply() forwards voltage_sequence and gate_channel_names."""
        macro = MeasurePSBPairMacro(buffer_duration=100)
        sensor_dot = MagicMock()

        ch1 = MagicMock()
        ch1.name = "gate_P1"
        ch2 = MagicMock()
        ch2.name = "gate_P2"

        owner = MagicMock()
        owner.id = "pair1"
        owner.sensor_dots = [sensor_dot]
        owner.voltage_sequence.gate_set.channels.values.return_value = [ch1, ch2]

        with patch(_OWNER_PATCH, return_value=owner):
            macro.apply()

        sensor_dot.macros[VoltagePointName.MEASURE.value].apply.assert_called_once_with(
            quantum_dot_pair_id="pair1",
            voltage_sequence=owner.voltage_sequence,
            gate_channel_names=["gate_P1", "gate_P2"],
        )


# --------------------------------------------------------------------------- #
# Measure1QMacro.inferred_duration
# --------------------------------------------------------------------------- #


class TestMeasure1QInferredDuration:
    def test_inferred_duration_navigates_chain(self):
        pair_macro = MagicMock()
        pair_macro.inferred_duration = 2.2e-6

        pair = MagicMock()
        pair.macros = {"measure": pair_macro}

        qubit = MagicMock()
        qubit.preferred_readout_quantum_dot = "dot2"
        qubit.quantum_dot.id = "dot1"
        qubit.machine.find_quantum_dot_pair.return_value = "dot1_dot2_pair"
        qubit.machine.quantum_dot_pairs = {"dot1_dot2_pair": pair}

        macro = Measure1QMacro()

        with patch.object(type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)):
            dur = macro.inferred_duration

        assert dur == pytest.approx(2.2e-6)

    def test_inferred_duration_none_without_preferred_dot(self):
        qubit = MagicMock()
        qubit.preferred_readout_quantum_dot = None

        macro = Measure1QMacro()

        with patch.object(type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)):
            assert macro.inferred_duration is None

    def test_inferred_duration_none_when_pair_not_found(self):
        qubit = MagicMock()
        qubit.preferred_readout_quantum_dot = "dot2"
        qubit.quantum_dot.id = "dot1"
        qubit.machine.find_quantum_dot_pair.return_value = None

        macro = Measure1QMacro()

        with patch.object(type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)):
            assert macro.inferred_duration is None

    def test_inferred_duration_none_when_pair_has_no_measure_macro(self):
        pair = MagicMock()
        pair.macros = {}

        qubit = MagicMock()
        qubit.preferred_readout_quantum_dot = "dot2"
        qubit.quantum_dot.id = "dot1"
        qubit.machine.find_quantum_dot_pair.return_value = "dot1_dot2_pair"
        qubit.machine.quantum_dot_pairs = {"dot1_dot2_pair": pair}

        macro = Measure1QMacro()

        with patch.object(type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)):
            assert macro.inferred_duration is None
