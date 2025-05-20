from typing import Optional
from qm.qua.type_hints import QuaVariable, QuaScalarExpression, Scalar
from .exceptions import TimingError


from typing import Any

DurationType = Scalar[int]
CLOCK_CYCLE_NS = 4
MIN_PULSE_DURATION_NS = 16


def is_qua_type(var: Any) -> bool:
    """Checks if a variable is a QUA expression or variable."""
    return isinstance(var, (QuaScalarExpression, QuaVariable))


def validate_duration(duration: Optional[DurationType], param_name: str):
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
        except TypeError:
            # This case should ideally not happen with DurationType hint,
            # but good for robustness.
            raise TimingError(f"{param_name} must be numeric or QUA type.")

        if duration_int < 0:
            raise TimingError(f"{param_name} ({duration_int}ns) must be non-negative.")
        if duration_int % CLOCK_CYCLE_NS != 0:
            raise TimingError(
                f"{param_name} ({duration_int}ns) must be a multiple of "
                f"{CLOCK_CYCLE_NS}ns."
            )
        if 0 < duration_int < MIN_PULSE_DURATION_NS:
            raise TimingError(
                f"\nDuration ({duration_int}ns) for {param_name} is less than the "
                f"minimum recommended ({MIN_PULSE_DURATION_NS}ns). This might "
                f"lead to timing issues or gaps. Use with care."
            )
