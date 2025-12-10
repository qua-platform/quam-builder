# Sticky Voltage Tracking Test Suite

## Overview

This test suite demonstrates a bug in the current implementation where sticky voltage compensation tracking fails when non-voltage macros (like `x180()`) execute while voltages are held at a non-zero level.

## Test File
- `test_sticky_voltage_tracking.py`

## Test Results

### Current Status (Before Fix)
- ✅ `test_voltage_tracking_without_non_voltage_operation` - PASSED
  Baseline test confirms voltage tracking works for voltage-only operations

- ⚠️  `test_sticky_voltage_tracking_with_non_voltage_operation` - XFAIL (Expected Failure)
  **This is the main bug demonstration**: Shows that integrated voltage doesn't account for non-voltage macro durations

- ✅ `test_complex_sequence_with_multiple_non_voltage_operations` - PASSED
  Confirms buggy behavior in complex sequences

- ✅ `test_sticky_voltage_tracking_only_affects_non_zero_voltages` - PASSED
  Edge case verification for zero voltages

## The Bug

### Problem
When a voltage is set to a non-zero value and made "sticky", subsequent non-voltage operations (like RF pulses for qubit rotations) don't update the integrated voltage tracker, even though the voltage remains at the sticky level during these operations.

### Example
```python
qubit.initialize()  # Sets voltage to initialization point for 100ns
qubit.x180()       # RF-only operation taking 100ns
                   # Voltage is still sticky at initialization point
                   # BUT: tracker only counts the first 100ns, not the second!
```

### Expected Behavior (After Fix)
The integrated voltage should be: `initialization_voltage * (100ns + 100ns)`

### Current Buggy Behavior
The integrated voltage is only: `initialization_voltage * 100ns`

## Running the Tests

```bash
cd /path/to/quam-builder
pytest tests/quantum_dots/test_sticky_voltage_tracking.py -v
```

## After Implementing the Fix

1. Remove the `@pytest.mark.xfail` decorator from `test_sticky_voltage_tracking_with_non_voltage_operation`
2. Uncomment the correct-behavior assertions in `test_complex_sequence_with_multiple_non_voltage_operations`
3. All tests should pass

## Technical Details

- **Scaling Factor**: 1024 (used for fixed-point precision in integrated voltage calculations)
- **Physical vs Virtual Gates**: Tests use physical channel name `plunger_1` for tracker access
- **Duration Constraints**: All durations must be multiples of 4ns (QUA requirement)

## Mock Components

The test suite uses a `MockX180Macro` that:
- Has a known `inferred_duration` of 100ns
- Simulates an RF-only operation (no voltage channel usage)
- Demonstrates the tracking issue when voltage is sticky
