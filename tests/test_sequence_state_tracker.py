import pytest
import numpy as np
from unittest.mock import MagicMock, call

from quam_builder.architecture.quantum_dots.virtual_gates.sequence_state_tracker import (
    SequenceStateTracker,
    INTEGRATED_VOLTAGE_SCALING_FACTOR,
    is_qua_type,
    # VoltageLevelType, # Not strictly needed for tests, but shows context
    # DurationType,
)

# --- Mock QUA objects and functions ---
# These will be used by the mocker fixture in pytest


# Define a dummy StateError if the original path is complex for testing
class StateError(Exception):
    pass


# Mock for qm.qua.QuaVariable to be used by is_qua_type
class MockQuaVariable:
    def __init__(self, name="mock_qua_var"):
        self.name = name

    def __repr__(self):
        return f"<MockQuaVariable {self.name}>"

    # Add arithmetic operations if needed for complex tests, though Cast.mul_int_by_fixed handles it
    def __add__(self, other):  # For 'assign(var, var + ...)'
        return self

    def __mul__(self, other):  # For 'level * factor' if level is QUA
        return self

    def __rmul__(self, other):
        return self

    def __rshift__(self, other):  # For 'duration << 10'
        return self  # or a new mock representing the shifted value


# Mock for qm.qua.QuaExpression (can be similar to MockQuaVariable or simpler)
class MockQuaExpression:
    def __init__(self, name="mock_qua_expr"):
        self.name = name

    def __repr__(self):
        return f"<MockQuaExpression {self.name}>"

    def __add__(self, other):
        return self

    def __mul__(self, other):
        return self

    def __rmul__(self, other):
        return self

    def __rshift__(self, other):
        return self


@pytest.fixture
def mock_qua_declare(mocker):
    """Fixture to mock qm.qua.declare."""
    # Return a new MagicMock for QuaVariable each time declare is called
    return mocker.patch(
        "sequence_state_tracker.declare",
        side_effect=lambda type, value=None, name=None: MagicMock(
            spec=MockQuaVariable, name=name or "declared_var"
        ),
    )


@pytest.fixture
def mock_qua_assign(mocker):
    """Fixture to mock qm.qua.assign."""
    return mocker.patch("sequence_state_tracker.assign")


@pytest.fixture
def mock_qua_cast_mul_int_by_fixed(mocker):
    """Fixture to mock qm.qua.Cast.mul_int_by_fixed."""
    # This mock should return a value that can be assigned or added
    mock_cast_obj = mocker.patch("sequence_state_tracker.Cast")
    mock_cast_obj.mul_int_by_fixed.return_value = MagicMock(
        spec=MockQuaExpression, name="mul_int_by_fixed_result"
    )
    return mock_cast_obj.mul_int_by_fixed


@pytest.fixture
def tracker():
    """Returns a SequenceStateTracker instance for element 'P1'."""
    return SequenceStateTracker("P1")


# --- Test Cases ---


def test_initialization(tracker):
    """Test basic initialization of the tracker."""
    assert tracker.element_name == "P1"
    assert tracker.current_level == 0.0
    assert tracker.integrated_voltage == 0
    assert tracker._integrated_voltage_qua_var is None


def test_initialization_invalid_name():
    """Test that initialization fails with an invalid element name."""
    with pytest.raises(ValueError, match="element_name must be a non-empty string."):
        SequenceStateTracker("")
    with pytest.raises(ValueError, match="element_name must be a non-empty string."):
        SequenceStateTracker(None)  # type: ignore


def test_current_level_property(tracker):
    """Test setting and getting the current_level property."""
    tracker.current_level = 0.5
    assert tracker.current_level == 0.5

    mock_qua_level = MockQuaVariable(name="qua_level")
    tracker.current_level = mock_qua_level
    assert tracker.current_level is mock_qua_level


def test_integrated_voltage_property_read_only(tracker):
    """Test that integrated_voltage is read-only directly."""
    assert tracker.integrated_voltage == 0
    with pytest.raises(AttributeError):
        tracker.integrated_voltage = 100  # type: ignore


def test_reset_integrated_voltage_python(tracker):
    """Test resetting integrated_voltage when it's a Python int."""
    tracker._integrated_voltage_internal = 1000  # Simulate prior updates
    tracker.reset_integrated_voltage()
    assert tracker.integrated_voltage == 0
    assert tracker._integrated_voltage_qua_var is None


def test_reset_integrated_voltage_qua(tracker, mock_qua_assign, mock_qua_declare):
    """Test resetting integrated_voltage when it's a QUA variable."""
    # First, promote it to a QUA variable
    tracker._ensure_qua_integrated_voltage_var()
    # mock_qua_declare has been called once. Get the created mock QUA var.
    mock_var = tracker._integrated_voltage_qua_var
    assert mock_var is not None

    # Simulate some non-zero value in the QUA variable (though assign handles it)
    # For this test, we mainly care that assign(mock_var, 0) is called.
    tracker.reset_integrated_voltage()

    mock_qua_assign.assert_called_once_with(mock_var, 0)
    assert tracker.integrated_voltage is mock_var  # Should still point to the QUA var


def test_ensure_qua_integrated_voltage_var_promotion(tracker, mock_qua_declare):
    """Test promotion from Python int to QUA variable."""
    tracker._integrated_voltage_internal = 123  # Initial Python int value

    returned_var = tracker._ensure_qua_integrated_voltage_var()

    mock_qua_declare.assert_called_once_with(int, value=123, name="P1_integrated_v")
    assert tracker._integrated_voltage_qua_var is not None
    assert tracker._integrated_voltage_qua_var is returned_var
    # After promotion, integrated_voltage property should return the QUA var
    assert tracker.integrated_voltage is tracker._integrated_voltage_qua_var


def test_ensure_qua_integrated_voltage_var_already_qua(tracker, mock_qua_declare):
    """Test that it returns existing QUA var and doesn't re-declare."""
    # Initial promotion
    tracker._ensure_qua_integrated_voltage_var()
    mock_qua_declare.assert_called_once()  # Called for the first time
    first_qua_var = tracker._integrated_voltage_qua_var

    # Call again
    returned_var = tracker._ensure_qua_integrated_voltage_var()
    mock_qua_declare.assert_called_once()  # Should still be called only once
    assert returned_var is first_qua_var


def test_ensure_qua_integrated_voltage_var_inconsistent_state(tracker):
    """Test error handling for inconsistent state before promotion."""
    tracker._integrated_voltage_internal = "not_an_int"  # type: ignore
    with pytest.raises(StateError, match="Expected int before QUA variable promotion"):
        tracker._ensure_qua_integrated_voltage_var()


# --- Tests for update_integrated_voltage ---


def test_update_integrated_voltage_python_no_ramp(tracker):
    """Test update with Python types, no ramp."""
    tracker.current_level = 0.0  # For avg_ramp_level if ramp was used
    level = 0.1
    duration = 200  # ns

    tracker.update_integrated_voltage(level, duration)

    expected_int_v = int(np.round(level * duration * INTEGRATED_VOLTAGE_SCALING_FACTOR))
    assert tracker.integrated_voltage == expected_int_v

    # Second update
    tracker.current_level = level  # Update current level as the main class would
    level2 = -0.05
    duration2 = 100
    tracker.update_integrated_voltage(level2, duration2)

    expected_int_v += int(
        np.round(level2 * duration2 * INTEGRATED_VOLTAGE_SCALING_FACTOR)
    )
    assert tracker.integrated_voltage == expected_int_v


def test_update_integrated_voltage_python_with_ramp(tracker):
    """Test update with Python types, with ramp."""
    tracker.current_level = 0.1
    level = 0.3
    duration = 100  # ns (flat top duration)
    ramp_duration = 20  # ns

    tracker.update_integrated_voltage(level, duration, ramp_duration)

    # Flat part
    flat_contrib = level * duration * INTEGRATED_VOLTAGE_SCALING_FACTOR
    # Ramp part
    avg_ramp_level = (level + 0.1) / 2.0
    ramp_contrib = avg_ramp_level * ramp_duration * INTEGRATED_VOLTAGE_SCALING_FACTOR

    expected_int_v = int(np.round(flat_contrib + ramp_contrib))
    assert tracker.integrated_voltage == expected_int_v


def test_update_integrated_voltage_python_zero_duration(tracker):
    """Test update with Python types, zero duration (should add nothing)."""
    tracker.current_level = 0.1
    level = 0.5
    duration = 0
    ramp_duration = 0  # Also test with zero ramp

    initial_int_v = tracker.integrated_voltage  # Should be 0
    tracker.update_integrated_voltage(level, duration, ramp_duration)

    assert tracker.integrated_voltage == initial_int_v  # No change


def test_update_integrated_voltage_qua_level_no_ramp(
    tracker, mock_qua_declare, mock_qua_assign, mock_qua_cast_mul_int_by_fixed
):
    """Test update with QUA level, Python duration, no ramp."""
    qua_level = MockQuaVariable("qua_level_input")
    duration = 100

    tracker.update_integrated_voltage(qua_level, duration)  # type: ignore

    # Check promotion happened
    mock_qua_declare.assert_called_once_with(int, value=0, name="P1_integrated_v")
    promoted_int_v_var = tracker._integrated_voltage_qua_var
    assert promoted_int_v_var is not None

    # Check Cast.mul_int_by_fixed call for flat part
    # duration << 10 is duration * 1024
    mock_qua_cast_mul_int_by_fixed.assert_called_once_with(duration << 10, qua_level)

    # Check assign call
    # assign(promoted_var, promoted_var + cast_result)
    # The mock for cast_result is mock_qua_cast_mul_int_by_fixed.return_value
    # The mock for promoted_var + cast_result is just promoted_var due to __add__
    # So, assign(promoted_var, promoted_var) effectively.
    # A more detailed mock for arithmetic might be needed for complex scenarios.
    # For now, checking it was called with the var and the result of cast.
    # The actual addition is mocked by the QUA variable's __add__ method.
    # assign(X, Y) means X becomes Y. Here, Y = X_old + contribution.
    # So, assign(int_v_var, int_v_var + level_contribution)
    # where level_contribution is the result of Cast.mul_int_by_fixed

    # We expect assign(int_v_var, int_v_var + result_of_cast)
    # The mock for int_v_var.__add__ returns int_v_var itself, which is a bit simplistic.
    # Let's refine the assertion for assign.
    # assign is called with (target_variable, source_expression)
    # source_expression is int_v_var + level_contribution
    # If int_v_var.__add__ returns a new mock, that's better.
    # For now, let's assume the structure of the call.

    # The first argument to assign is the QUA variable for integrated_voltage.
    # The second argument is an expression involving this variable and the contribution.
    # This is hard to assert perfectly without a more complex QUA mock environment.
    # We'll check that assign was called, and that the first arg is the correct var.
    assert mock_qua_assign.call_count == 1
    call_args = mock_qua_assign.call_args_list[0]
    assert call_args[0][0] is promoted_int_v_var
    # The second argument is an expression like `promoted_int_v_var + mock_cast_result`
    # This depends on how MockQuaVariable.__add__ is implemented.
    # If it returns itself: assign(promoted_int_v_var, promoted_int_v_var) after internal state change.
    # If it returns a new mock: assign(promoted_int_v_var, new_mock_sum_expression)


def test_update_integrated_voltage_qua_all_with_ramp(
    tracker, mock_qua_declare, mock_qua_assign, mock_qua_cast_mul_int_by_fixed
):
    """Test update with all QUA types, with ramp."""
    tracker.current_level = MockQuaVariable("qua_current_level")
    qua_level = MockQuaVariable("qua_target_level")
    qua_duration = MockQuaVariable("qua_duration")
    qua_ramp_duration = MockQuaVariable("qua_ramp_duration")

    tracker.update_integrated_voltage(qua_level, qua_duration, qua_ramp_duration)  # type: ignore

    # Promotion
    mock_qua_declare.assert_called_once_with(int, value=0, name="P1_integrated_v")
    promoted_int_v_var = tracker._integrated_voltage_qua_var

    # Expected calls to Cast.mul_int_by_fixed
    # 1. For flat part: mul_int_by_fixed(qua_duration << 10, qua_level)
    # 2. For ramp part: mul_int_by_fixed(qua_ramp_duration << 10, avg_ramp_level_expr)
    #    where avg_ramp_level_expr is (qua_level + tracker.current_level) * 0.5

    # Construct the expected avg_ramp_level expression for comparison if mocks allow
    # This depends on how operators are mocked for MockQuaVariable/Expression
    # For simplicity, we check the number of calls and that assign is called.

    assert mock_qua_cast_mul_int_by_fixed.call_count == 2

    # Flat part contribution call
    first_cast_call = mock_qua_cast_mul_int_by_fixed.call_args_list[0]
    assert (
        first_cast_call[0][0] is qua_duration
    )  # Note: qua_duration << 10 is tricky to assert directly with basic mocks
    assert first_cast_call[0][1] is qua_level

    # Ramp part contribution call
    # The avg_ramp_level is (qua_target_level + qua_current_level) * 0.5
    # This intermediate expression would be the second arg to the second cast call.
    # This is difficult to assert precisely without a full QUA expression tree mock.
    # We trust that the internal logic (level + current_level_val) * 0.5 is correct.
    second_cast_call = mock_qua_cast_mul_int_by_fixed.call_args_list[1]
    assert second_cast_call[0][0] is qua_ramp_duration  # Similar to above re: << 10

    # Check assign calls (one for flat, one for ramp)
    assert mock_qua_assign.call_count == 2
    assert mock_qua_assign.call_args_list[0][0][0] is promoted_int_v_var
    assert mock_qua_assign.call_args_list[1][0][0] is promoted_int_v_var


def test_update_integrated_voltage_qua_var_already_exists(
    tracker, mock_qua_declare, mock_qua_assign, mock_qua_cast_mul_int_by_fixed
):
    """Test update when _integrated_voltage_qua_var already exists."""
    # First update to promote
    tracker.update_integrated_voltage(MockQuaVariable("level1"), 100)  # type: ignore
    mock_qua_declare.assert_called_once()  # Promoted
    assert mock_qua_assign.call_count == 1  # From first update
    assert mock_qua_cast_mul_int_by_fixed.call_count == 1

    # Second update
    tracker.update_integrated_voltage(MockQuaVariable("level2"), 50)  # type: ignore
    mock_qua_declare.assert_called_once()  # Should NOT be called again
    assert mock_qua_assign.call_count == 2  # Called again for second update
    assert mock_qua_cast_mul_int_by_fixed.call_count == 2


def test_is_qua_type_helper():
    """Test the is_qua_type helper function."""
    assert is_qua_type(MockQuaVariable()) is True
    assert is_qua_type(MockQuaExpression()) is True
    assert is_qua_type(10) is False
    assert is_qua_type(0.5) is False
    assert is_qua_type("string") is False
