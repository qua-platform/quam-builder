from typing import Any

from qm.qua import assign, declare
from qm.qua.type_hints import QuaScalarExpression, QuaVariable, Scalar

# --- Type Aliases ---
VoltageLevelType = Scalar[float]
DurationType = Scalar[int]

CLOCK_CYCLE_NS = 4
MIN_PULSE_DURATION_NS = 16


def is_qua_type(var: Any) -> bool:
    """Checks if a variable is a QUA expression or variable."""
    return isinstance(var, QuaScalarExpression | QuaVariable)


def validate_duration(duration: DurationType | None, param_name: str):
    """
    Checks if a duration value is valid (non-negative, multiple of 4ns).

    Warns if duration is > 0 and < MIN_PULSE_DURATION_NS.

    Args:
        duration: The duration value to validate.
        param_name: The name of the parameter being validated (for error messages).
    """
    if duration is None:
        return  # Allow None where optional

    if not is_qua_type(duration):
        try:
            duration_int = int(duration)
        except TypeError as e:
            # This case should ideally not happen with DurationType hint,
            # but good for robustness.
            raise TypeError(f"{param_name} must be numeric or QUA type.") from e

        if duration_int < 0:
            raise TypeError(f"{param_name} ({duration_int}ns) must be non-negative.")
        if duration_int % CLOCK_CYCLE_NS != 0:
            raise TypeError(
                f"{param_name} ({duration_int}ns) must be a multiple of " f"{CLOCK_CYCLE_NS}ns."
            )
        if 0 < duration_int < MIN_PULSE_DURATION_NS:
            raise TypeError(
                f"\nDuration ({duration_int}ns) for {param_name} is less than the "
                f"minimum recommended ({MIN_PULSE_DURATION_NS}ns). This might "
                f"lead to timing issues or gaps. Use with care."
            )


def integer_abs(qua_int: QuaVariable):
    """Absolute value of an integer qua variable."""
    temp = declare(int)
    assign(temp, qua_int >> 31)
    assign(qua_int, qua_int ^ temp)
    assign(qua_int, qua_int + (temp & 1))
    return qua_int
