"""Unit tests for SequenceStateTracker and KeepLevels.

These tests exercise Python-side integrated-voltage math and QUA promotion.
They do not require qua-qsim.
"""

import numpy as np
import pytest
from qm import qua

from quam_builder.tools.qua_tools import is_qua_type
from quam_builder.tools.voltage_sequence.exceptions import StateError
from quam_builder.tools.voltage_sequence.sequence_state_tracker import (
    INTEGRATED_VOLTAGE_SCALING_FACTOR,
    KeepLevels,
    SequenceStateTracker,
)


def _expected_integral(level: float, duration: int) -> int:
    return int(np.round(level * duration * INTEGRATED_VOLTAGE_SCALING_FACTOR))


def test_init_rejects_empty_or_non_string_element_name():
    """SequenceStateTracker requires a non-empty string element_name."""
    with pytest.raises(ValueError, match="element_name must be a non-empty string"):
        SequenceStateTracker("")
    with pytest.raises(ValueError, match="element_name must be a non-empty string"):
        SequenceStateTracker(None)  # type: ignore[arg-type]


def test_init_starts_at_zero_voltage_and_zero_integrated_voltage():
    """A new tracker reports 0 V current_level and 0 integrated_voltage."""
    tracker = SequenceStateTracker("P1")
    assert tracker.element_name == "P1"
    assert tracker.current_level == 0.0
    assert tracker.integrated_voltage == 0
    assert tracker._integrated_voltage_qua_var is None


def test_current_level_round_trip_with_python_float():
    """Setting current_level to a Python float stores that value for later reads."""
    tracker = SequenceStateTracker("P1")
    tracker.current_level = 0.5
    assert tracker.current_level == 0.5


def test_integrated_voltage_has_no_public_setter():
    """integrated_voltage is read-only; updates go through update_integrated_voltage."""
    tracker = SequenceStateTracker("P1")
    with pytest.raises(AttributeError):
        tracker.integrated_voltage = 100  # type: ignore[misc]


def test_update_integrated_voltage_accumulates_python_step_contribution():
    """A constant-level update adds round(level * duration * 1024) to the integral."""
    tracker = SequenceStateTracker("P1")
    tracker.update_integrated_voltage(0.1, 200)
    expected = _expected_integral(0.1, 200)
    assert tracker.integrated_voltage == expected

    tracker.current_level = 0.1
    tracker.update_integrated_voltage(-0.05, 100)
    assert tracker.integrated_voltage == expected + _expected_integral(-0.05, 100)


def test_update_integrated_voltage_includes_average_level_over_python_ramp():
    """A ramp contribution uses the average of current_level and the target level."""
    tracker = SequenceStateTracker("P1")
    tracker.current_level = 0.1
    tracker.update_integrated_voltage(level=0.3, duration=100, ramp_duration=20)

    flat = 0.3 * 100 * INTEGRATED_VOLTAGE_SCALING_FACTOR
    ramp = ((0.3 + 0.1) / 2.0) * 20 * INTEGRATED_VOLTAGE_SCALING_FACTOR
    assert tracker.integrated_voltage == int(np.round(flat + ramp))


def test_update_integrated_voltage_zero_duration_does_not_change_integral():
    """duration=0 and ramp_duration=0 add nothing to a Python-tracked integral."""
    tracker = SequenceStateTracker("P1")
    tracker.current_level = 0.1
    tracker.update_integrated_voltage(0.5, 0, 0)
    assert tracker.integrated_voltage == 0


def test_reset_integrated_voltage_clears_python_accumulator():
    """reset_integrated_voltage sets a Python-tracked integral back to 0."""
    tracker = SequenceStateTracker("P1")
    tracker.update_integrated_voltage(0.1, 1000)
    assert tracker.integrated_voltage != 0
    tracker.reset_integrated_voltage()
    assert tracker.integrated_voltage == 0
    assert tracker._integrated_voltage_qua_var is None


def test_ensure_qua_integrated_voltage_var_raises_if_internal_state_is_not_int():
    """Promotion to a QUA variable requires the Python accumulator to be an int."""
    tracker = SequenceStateTracker("P1")
    tracker._integrated_voltage_internal = "not_an_int"  # type: ignore[assignment]
    with pytest.raises(StateError, match="Expected int before QUA variable promotion"):
        tracker._ensure_qua_integrated_voltage_var()


def test_update_integrated_voltage_promotes_to_qua_when_level_is_qua():
    """A QUA voltage argument promotes integrated_voltage from a Python int to a QUA var."""
    with qua.program() as _prog:
        tracker = SequenceStateTracker("P1")
        tracker.update_integrated_voltage(0.1, 100)
        assert isinstance(tracker.integrated_voltage, int)

        qua_level = qua.declare(qua.fixed, value=0.2)
        tracker.update_integrated_voltage(qua_level, 80)
        assert is_qua_type(tracker.integrated_voltage)
        assert tracker._integrated_voltage_qua_var is tracker.integrated_voltage


def test_reset_integrated_voltage_after_qua_promotion_assigns_python_prefix():
    """After promotion, reset assigns the QUA var back to the Python value captured
    at promotion time (the offsets accumulated before any QUA contribution)."""
    with qua.program() as _prog:
        tracker = SequenceStateTracker("P1")
        tracker.update_integrated_voltage(0.1, 100)
        python_prefix = tracker.integrated_voltage

        qua_level = qua.declare(qua.fixed, value=0.2)
        tracker.update_integrated_voltage(qua_level, 80)
        tracker.reset_integrated_voltage()

        assert tracker._current_py_val_before_promotion == python_prefix
        assert tracker.integrated_voltage is tracker._integrated_voltage_qua_var


def test_current_level_setter_promotes_and_then_accepts_python_values():
    """Assigning a QUA level declares a QUA current_level; later Python assigns
    write into that same QUA variable."""
    with qua.program() as _prog:
        tracker = SequenceStateTracker("P1")
        tracker.current_level = 0.5
        assert tracker.current_level == 0.5

        qua_level = qua.declare(qua.fixed, value=0.2)
        tracker.current_level = qua_level
        assert is_qua_type(tracker.current_level)

        tracker.current_level = 0.1
        assert is_qua_type(tracker.current_level)


def test_enforce_qua_calcs_declares_current_level_as_qua_at_init():
    """enforce_qua_calcs=True declares current_level as a QUA fixed at construction."""
    with qua.program() as _prog:
        tracker = SequenceStateTracker("P1", enforce_qua_calcs=True)
        assert is_qua_type(tracker.current_level)


def test_keep_levels_fills_omitted_gates_with_last_set_value(machine):
    """KeepLevels.update_voltage_dict_with_current returns every valid gate.
    Gates omitted from the new dict keep the value from the previous update;
    never-set gates stay at 0 V."""
    keep = KeepLevels(machine.gate_set)

    first = keep.update_voltage_dict_with_current({"ch1": 0.2})
    assert first["ch1"] == 0.2
    assert first["ch2"] == 0.0

    second = keep.update_voltage_dict_with_current({"ch2": 0.1})
    assert second["ch1"] == 0.2
    assert second["ch2"] == 0.1

    third = keep.update_voltage_dict_with_current({"ch1": 0.3})
    assert third["ch1"] == 0.3
    assert third["ch2"] == 0.1
