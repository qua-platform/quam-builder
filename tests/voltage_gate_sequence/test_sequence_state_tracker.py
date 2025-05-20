import pytest
import numpy as np
from unittest.mock import MagicMock, call

from quam_builder.architecture.quantum_dots.voltage_gate_sequence.sequence_state_tracker import (
    SequenceStateTracker,
    INTEGRATED_VOLTAGE_SCALING_FACTOR,
    is_qua_type,
    StateError,
    VoltageLevelType,
    DurationType,
)

# --- Mock QUA objects and functions ---
# Define a dummy StateError if the original path is complex for testing
# class StateError(Exception):  # Already imported from main module
#     pass


# Mock for qm.qua.QuaVariable to be used by is_qua_type
class MockQuaVariable:
    """Mocks a QUA variable for testing purposes."""

    def __init__(self, name: str = "mock_qua_var"):
        self.name = name

    def __repr__(self) -> str:
        return f"<MockQuaVariable {self.name}>"

    def __add__(self, other: any) -> "MockQuaVariable":
        return self

    def __sub__(self, other: any) -> "MockQuaVariable":
        return self

    def __mul__(self, other: any) -> "MockQuaVariable":
        return self

    def __rmul__(self, other: any) -> "MockQuaVariable":
        return self

    def __rshift__(self, other: any) -> "MockQuaVariable":
        return self


# Mock for qm.qua.QuaExpression
class MockQuaExpression:
    """Mocks a QUA expression for testing purposes."""

    def __init__(self, name: str = "mock_qua_expr"):
        self.name = name

    def __repr__(self) -> str:
        return f"<MockQuaExpression {self.name}>"

    def __add__(self, other: any) -> "MockQuaExpression":
        return self

    def __sub__(self, other: any) -> "MockQuaExpression":
        return self

    def __mul__(self, other: any) -> "MockQuaExpression":
        return self

    def __rmul__(self, other: any) -> "MockQuaExpression":
        return self

    def __rshift__(self, other: any) -> "MockQuaExpression":
        return self


@pytest.fixture
def mock_qua_declare(mocker: MagicMock) -> MagicMock:
    """Fixture to mock qm.qua.declare."""
    return mocker.patch(
        "quam_builder.architecture.quantum_dots.virtual_gates.sequence_state_tracker.declare",
        side_effect=lambda _type, value=None, name=None: MagicMock(
            spec=MockQuaVariable, name=name or "declared_var"
        ),
    )


@pytest.fixture
def mock_qua_assign(mocker: MagicMock) -> MagicMock:
    """Fixture to mock qm.qua.assign."""
    return mocker.patch(
        "quam_builder.architecture.quantum_dots.virtual_gates.sequence_state_tracker.assign"
    )


@pytest.fixture
def mock_qua_cast_mul_int_by_fixed(mocker: MagicMock) -> MagicMock:
    """Fixture to mock qm.qua.Cast.mul_int_by_fixed."""
    mock_cast_obj = mocker.patch(
        "quam_builder.architecture.quantum_dots.virtual_gates.sequence_state_tracker.Cast"
    )
    # This mock should return a value that can be assigned or added
    mock_cast_obj.mul_int_by_fixed.return_value = MagicMock(
        spec=MockQuaExpression, name="mul_int_by_fixed_result"
    )
    return mock_cast_obj.mul_int_by_fixed


@pytest.fixture
def tracker() -> SequenceStateTracker:
    """Returns a SequenceStateTracker instance for element 'P1'."""
    return SequenceStateTracker("P1")


# --- Test Cases ---


def test_initialization_and_properties(tracker: SequenceStateTracker):
    """Tests basic initialization and property accessors.

    Covers:
    - Correct initial values for element_name, current_level, integrated_voltage.
    - ValueError for invalid element_name.
    - Setting and getting current_level with Python floats and mock QUA variables.
    """
    assert tracker.element_name == "P1"
    assert tracker.current_level == 0.0
    assert tracker.integrated_voltage == 0
    assert tracker._integrated_voltage_qua_var is None

    with pytest.raises(ValueError, match="element_name must be a non-empty string."):
        SequenceStateTracker("")  # type: ignore
    with pytest.raises(ValueError, match="element_name must be a non-empty string."):
        SequenceStateTracker(None)  # type: ignore

    tracker.current_level = 0.5
    assert tracker.current_level == 0.5

    mock_qua_level = MockQuaVariable(name="qua_level")
    tracker.current_level = mock_qua_level  # type: ignore
    assert tracker.current_level is mock_qua_level

    # Test integrated_voltage is read-only directly
    with pytest.raises(AttributeError):
        tracker.integrated_voltage = 100  # type: ignore


def test_ensure_qua_integrated_voltage_var_promotion_and_idempotency(
    tracker: SequenceStateTracker, mock_qua_declare: MagicMock
):
    """Tests QUA variable promotion and its idempotency.

    Covers:
    - Promotion from Python int to QUA variable on first call.
    - `declare` being called correctly.
    - No re-declaration on subsequent calls.
    - StateError for inconsistent state before promotion (optional here or separate).
    """
    tracker._integrated_voltage_internal = 123  # Initial Python int value

    # First call - promotion
    returned_var1 = tracker._ensure_qua_integrated_voltage_var()
    mock_qua_declare.assert_called_once_with(int, value=123, name="P1_integrated_v")
    assert tracker._integrated_voltage_qua_var is not None
    assert tracker._integrated_voltage_qua_var is returned_var1
    assert tracker.integrated_voltage is tracker._integrated_voltage_qua_var

    # Second call - should be idempotent
    returned_var2 = tracker._ensure_qua_integrated_voltage_var()
    mock_qua_declare.assert_called_once()  # Still only called once
    assert returned_var2 is returned_var1  # Should return the same existing var

    # Test StateError for inconsistent type before promotion
    tracker_new = SequenceStateTracker("P2_inconsistent")
    tracker_new._integrated_voltage_internal = "not_an_int"  # type: ignore
    with pytest.raises(StateError, match="Expected int before QUA variable promotion"):
        tracker_new._ensure_qua_integrated_voltage_var()


def test_reset_integrated_voltage(
    tracker: SequenceStateTracker,
    mock_qua_assign: MagicMock,
    mock_qua_declare: MagicMock,
):
    """Tests resetting integrated_voltage in both Python and QUA states.

    Covers:
    - Resetting when integrated_voltage is a Python int.
    - Resetting when integrated_voltage is a QUA variable (checks assign call).
    """
    # Test reset from Python state
    tracker._integrated_voltage_internal = 1000
    tracker.reset_integrated_voltage()
    assert tracker.integrated_voltage == 0
    assert tracker._integrated_voltage_qua_var is None

    # Promote to QUA variable
    tracker._ensure_qua_integrated_voltage_var()
    mock_var = tracker._integrated_voltage_qua_var
    assert mock_var is not None
    # mock_qua_declare has been called. Reset its call count for the next check.
    mock_qua_declare.reset_mock()

    # Test reset from QUA state
    tracker.reset_integrated_voltage()
    mock_qua_assign.assert_called_once_with(mock_var, 0)
    # The integrated_voltage property should still point to the QUA variable
    assert tracker.integrated_voltage is mock_var


def test_update_integrated_voltage_python_only_cases(tracker: SequenceStateTracker):
    """Tests update_integrated_voltage with Python-native inputs.

    Covers:
    - No ramp, multiple updates.
    - With ramp.
    - Zero duration.
    """
    # --- No ramp ---
    tracker.current_level = 0.0
    level1: VoltageLevelType = 0.1
    duration1: DurationType = 200  # ns
    tracker.update_integrated_voltage(level1, duration1)
    expected_int_v1 = int(
        np.round(level1 * duration1 * INTEGRATED_VOLTAGE_SCALING_FACTOR)
    )
    assert tracker.integrated_voltage == expected_int_v1

    tracker.current_level = level1
    level2: VoltageLevelType = -0.05
    duration2: DurationType = 100
    tracker.update_integrated_voltage(level2, duration2)
    expected_int_v2 = int(
        np.round(level2 * duration2 * INTEGRATED_VOLTAGE_SCALING_FACTOR)
    )
    assert tracker.integrated_voltage == expected_int_v1 + expected_int_v2

    # --- With ramp ---
    tracker_ramp = SequenceStateTracker("P1_ramp")
    tracker_ramp.current_level = 0.1
    level_r: VoltageLevelType = 0.3
    duration_r: DurationType = 100  # ns (flat top duration)
    ramp_duration_r: DurationType = 20  # ns
    tracker_ramp.update_integrated_voltage(level_r, duration_r, ramp_duration_r)

    flat_contrib = level_r * duration_r * INTEGRATED_VOLTAGE_SCALING_FACTOR
    avg_ramp_level = (level_r + 0.1) / 2.0  # type: ignore
    ramp_contrib = avg_ramp_level * ramp_duration_r * INTEGRATED_VOLTAGE_SCALING_FACTOR  # type: ignore
    expected_int_v_ramp = int(np.round(flat_contrib + ramp_contrib))
    assert tracker_ramp.integrated_voltage == expected_int_v_ramp

    # --- Zero duration ---
    tracker_zero = SequenceStateTracker("P1_zero")
    tracker_zero.current_level = 0.1
    initial_int_v_zero = tracker_zero.integrated_voltage
    tracker_zero.update_integrated_voltage(0.5, 0, 0)
    assert tracker_zero.integrated_voltage == initial_int_v_zero  # No change


def test_update_integrated_voltage_qua_interaction_promotion_and_ramp(
    tracker: SequenceStateTracker,
    mock_qua_declare: MagicMock,
    mock_qua_assign: MagicMock,
    mock_qua_cast_mul_int_by_fixed: MagicMock,
):
    """Tests update_integrated_voltage with QUA interactions.

    Covers:
    - Promotion to QUA variable when a QUA type is introduced.
    - Correct calls to mocked QUA functions (declare, assign, Cast.mul_int_by_fixed).
    - A scenario involving ramps with QUA variables.
    """
    # --- Initial Python state, then QUA level triggers promotion (no ramp) ---
    tracker.current_level = 0.05
    py_duration: DurationType = 100
    qua_level = MockQuaVariable("qua_target_level_1")

    tracker.update_integrated_voltage(qua_level, py_duration)  # type: ignore

    # Check promotion occurred
    mock_qua_declare.assert_called_once_with(
        int,
        value=0,
        name="P1_integrated_v",  # Assuming initial integrated_v was 0
    )
    promoted_var = tracker._integrated_voltage_qua_var
    assert promoted_var is not None

    # Check Cast.mul_int_by_fixed for the flat part
    # py_duration << 10 is py_duration * 1024
    mock_qua_cast_mul_int_by_fixed.assert_called_once_with(py_duration << 10, qua_level)

    # Check assign call
    # assign(promoted_var, promoted_var + cast_result)
    # The mock for cast_result is mock_qua_cast_mul_int_by_fixed.return_value
    assert mock_qua_assign.call_count == 1
    assign_call_args = mock_qua_assign.call_args_list[0]
    assert assign_call_args[0][0] is promoted_var  # Target of assign
    # The second arg is an expression like `promoted_var + result_of_cast`
    # which depends on how MockQuaVariable.__add__ is mocked.

    # Reset mocks for the next part of the test
    mock_qua_declare.reset_mock()
    mock_qua_assign.reset_mock()
    mock_qua_cast_mul_int_by_fixed.reset_mock()

    # --- Already in QUA state, update with QUA level, duration, and ramp_duration ---
    # tracker.current_level is already qua_level (a MockQuaVariable)
    tracker.current_level = qua_level  # Explicitly ensure it's QUA for this part

    qua_level_2 = MockQuaVariable("qua_target_level_2")
    qua_duration = MockQuaVariable("qua_duration_2")
    qua_ramp_duration = MockQuaVariable("qua_ramp_duration_2")

    tracker.update_integrated_voltage(
        qua_level_2,
        qua_duration,
        qua_ramp_duration,  # type: ignore
    )

    # No new declaration should happen
    mock_qua_declare.assert_not_called()

    # Two calls to Cast.mul_int_by_fixed: one for flat, one for ramp
    assert mock_qua_cast_mul_int_by_fixed.call_count == 2

    # Flat part contribution call
    # (duration << 10, target_level)
    first_cast_call = mock_qua_cast_mul_int_by_fixed.call_args_list[0]
    assert (
        first_cast_call[0][0] is qua_duration
    )  # Simplified: real would be qua_duration << 10
    assert first_cast_call[0][1] is qua_level_2

    # Ramp part contribution call
    # (ramp_duration << 10, avg_ramp_level_expr)
    # avg_ramp_level_expr is (target_level + current_level) * 0.5
    second_cast_call = mock_qua_cast_mul_int_by_fixed.call_args_list[1]
    assert second_cast_call[0][0] is qua_ramp_duration  # Simplified
    # The second argument to cast is (qua_level_2 + qua_level) * 0.5,
    # which is a MockQuaExpression due to mocked arithmetic.

    # Two assign calls (one for flat, one for ramp)
    assert mock_qua_assign.call_count == 2
    assert mock_qua_assign.call_args_list[0][0][0] is promoted_var
    assert mock_qua_assign.call_args_list[1][0][0] is promoted_var


def test_is_qua_type_helper():
    """Tests the is_qua_type helper function."""
    from qm.qua import program, declare, assign

    with program() as p:
        q = declare(int)
        assert is_qua_type(q) is True
        assert is_qua_type(10) is False
        assert is_qua_type(0.5) is False
        assert is_qua_type("string") is False
        assert is_qua_type(None) is False
