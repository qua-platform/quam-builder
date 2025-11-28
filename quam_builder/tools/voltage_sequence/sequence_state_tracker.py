from typing import Optional
import numpy as np

from qm.qua.type_hints import QuaVariable, Scalar
from qm.qua import declare, assign, Cast, fixed

from quam_builder.tools.voltage_sequence.exceptions import StateError
from quam_builder.tools.qua_tools import is_qua_type
from quam_builder.architecture.quantum_dots.components.gate_set import GateSet
from quam_builder.architecture.quantum_dots.components.virtual_gate_set import (
    VirtualGateSet,
)
from typing import Dict

__all__ = [
    "SequenceStateTracker",
]

# --- Constants ---
INTEGRATED_VOLTAGE_BITSHIFT = 10
INTEGRATED_VOLTAGE_SCALING_FACTOR = (
    2**INTEGRATED_VOLTAGE_BITSHIFT
)  # For fixed-point precision (V*ns*1024)

# --- Type Aliases ---
VoltageLevelType = Scalar[float]
DurationType = Scalar[int]


# --- State Tracking ---
class SequenceStateTracker:
    """
    Tracks and manages the dynamic state of a single gate element within a sequence.

    This class is responsible for maintaining the last applied voltage level
    (`current_level`) and the accumulated time-integrated voltage
    (`integrated_voltage`) for the specified element. The integrated voltage
    is crucial for calculating DC compensation pulses.

    The class handles both standard Python numerical types (float, int) for
    voltages and durations, as well as QUA variables/expressions
    (`QuaVariable`, `QuaExpression`). When QUA types are involved in calculations
    that update the integrated voltage, the internal tracking for the element's
    integrated voltage is automatically promoted to a QUA variable if it isn't
    one already. This ensures that all calculations involving QUA types are
    performed within the QUA execution environment.

    Attributes:
        element_name (str): The name of the element tracked by this instance.
        current_level (VoltageLevelType): The current voltage level of the element.
            Can be read and set.
        integrated_voltage (Union[int, QuaVariable]): The accumulated integrated
            voltage. Read-only from an external perspective (updated via methods).

    Key functionalities include:
    - Initializing the state for a single element (starting at 0V and
      0 integrated voltage).
    - Updating the accumulated integrated voltage based on a pulse's level,
      duration, and optional ramp duration.
    - Resetting the integrated voltage (typically done after
      ramping to zero or applying full compensation).

    The integrated voltage is calculated as `sum(level * duration)` for steps,
    and includes the contribution from ramps, scaled by
    `INTEGRATED_VOLTAGE_SCALING_FACTOR` for fixed-point precision when QUA
    variables are used.
    """

    def __init__(self, element_name: str, track_integrated_voltage: bool = True):
        """
        Initializes the SequenceStateTracker for a given element name.

        The element's state (current voltage and integrated voltage) is
        initialized to zero.

        Args:
            element_name: The unique string name for the gate element to be tracked.
                Used for debugging purposes.

        Raises:
            ValueError: If `element_name` is empty or not a string.
        """
        if not isinstance(element_name, str) or not element_name:
            raise ValueError("element_name must be a non-empty string.")

        self._element_name: str = element_name
        # Initialize state variables directly for the single element
        self._current_level_internal: Scalar[float] = 0.0
        # Whether to track integrated voltage
        self._track_integrated_voltage: bool = track_integrated_voltage
        # Stores accumulated voltage*duration*scale_factor
        self._integrated_voltage_internal: Scalar[int] = 0
        # Keep track of the declared QUA variable for integrated voltage, if any
        self._integrated_voltage_qua_var: Optional[QuaVariable] = None
        self._current_py_val_before_promotion = None

    def declare_current_level_var(self):
        """Must be called within QUA program context before any operations."""
        self._current_level_internal = declare(fixed, value=0.0)

    @property
    def element_name(self) -> str:
        """Gets the name of the element tracked by this instance."""
        return self._element_name

    @property
    def current_level(self) -> Scalar[float]:
        """
        Gets the current voltage level for the tracked element.

        Returns:
            The current voltage level of the element. This can be a
            Python float or a QUA variable/expression if the level was set
            using a QUA type.
        """
        return self._current_level_internal

    @current_level.setter
    def current_level(self, level: Scalar[float]):
        """
        Updates the current voltage level for the tracked element.

        This method should be called after a voltage step or ramp has been
        applied to the element.

        Args:
            level: The new voltage level (float or QUA type) of the element.
        """

        if is_qua_type(level):
            if not is_qua_type(self._current_level_internal):
                self._current_level_internal = declare(fixed)
            assign(self._current_level_internal, level)
        elif is_qua_type(self._current_level_internal):
            assign(self._current_level_internal, level)
        else:
            self._current_level_internal = level

    @property
    def integrated_voltage(self) -> Scalar[int]:
        """
        Gets the accumulated integrated voltage for the tracked element.

        The integrated voltage is a measure of `sum(voltage * duration)` over
        the sequence, scaled for precision if QUA variables are involved.
        It is used for calculating DC compensation pulses.

        Returns:
            The accumulated integrated voltage for the element. This
            can be a Python int or a QUA variable if QUA types have been
            involved in its calculation.
        """
        return self._integrated_voltage_internal

    def reset_integrated_voltage(self):
        """
        Resets the accumulated integrated voltage for the tracked element to zero or the required python value.

        This is typically done after an "apply_compensation_pulse" operation,
        if a compensation pulse is applied inside a qua loop containing both python offsets and qua offsets,
        the value is reset to account for all python offsets
        """
        # Reset QUA variable if it exists, otherwise reset Python int
        if self._integrated_voltage_qua_var is not None:
            if self._current_py_val_before_promotion is not None:
                assign(
                    self._integrated_voltage_qua_var,
                    self._current_py_val_before_promotion,
                )
            else:
                assign(self._integrated_voltage_qua_var, 0)
            # The _integrated_voltage_internal attribute should still point to the QUA var
            self._integrated_voltage_internal = self._integrated_voltage_qua_var
        else:
            self._integrated_voltage_internal = 0

    def _ensure_qua_integrated_voltage_var(self) -> QuaVariable:
        """
        Ensures a QUA variable exists for integrated voltage tracking.

        If the current tracking for the element's integrated voltage is a Python
        integer, this method declares a new QUA integer variable, initializes it
        with the current Python integer value, and updates the internal tracking
        to use this new QUA variable. If a QUA variable already exists,
        it is simply returned.

        This mechanism allows for seamless promotion of Python-tracked state to
        QUA-managed state when QUA operations require it.

        Returns:
            The QUA variable (`qm.qua.QuaVariable`) used for tracking the
            integrated voltage of the element.

        Raises:
            StateError: If the internal state for the element's integrated
                voltage is inconsistent (e.g., not an int before promotion).
        """
        if self._integrated_voltage_qua_var is None:
            current_py_val = self._integrated_voltage_internal
            if not isinstance(current_py_val, int):
                raise StateError(
                    f"Inconsistent state for integrated voltage of '{self._element_name}'. "
                    f"Expected int before QUA variable promotion, got {type(current_py_val)}."
                )

            # Use element name in variable declaration for clarity in generated QUA
            self._current_py_val_before_promotion = current_py_val
            int_v_var = declare(int, value=current_py_val)
            self._integrated_voltage_qua_var = int_v_var
            self._integrated_voltage_internal = (
                int_v_var  # Update tracking to use the QUA var
            )
            return int_v_var
        else:
            # QUA Variable already exists for this element's integrated voltage
            return self._integrated_voltage_qua_var

    def update_integrated_voltage(
        self,
        level: Scalar[float],
        duration: Scalar[int],
        ramp_duration: Optional[Scalar[int]] = None,
    ):
        """
        Updates the accumulated integrated voltage for the tracked element.

        This calculation accounts for the voltage level and duration of a flat
        pulse segment, and optionally includes the contribution from a linear
        ramp to that level. The integrated voltage is scaled by
        `INTEGRATED_VOLTAGE_SCALING_FACTOR` for fixed-point arithmetic precision
        when QUA variables are involved.

        If any of the inputs (`level`, `duration`, `ramp_duration`) or the
        current state (`current_level`, `integrated_voltage`)
        are QUA types, all calculations are performed using QUA operations, and
        the element's integrated voltage tracking is promoted to a QUA variable
        if it isn't one already.

        Args:
            level: The target voltage level (V) of the pulse segment.
            duration: The duration (ns) spent at the target voltage level.
            ramp_duration: Optional. The duration (ns) of the linear ramp from
                the element's current voltage to the target `level`. If None,
                no ramp contribution is added.
        """
        current_level_val = self._current_level_internal
        element_int_v = self._integrated_voltage_internal  # Can be int or QUA var

        # --- Determine if QUA calculation is needed for any part of the update ---
        needs_qua_calc = any(
            is_qua_type(v)
            for v in [element_int_v, level, duration, ramp_duration, current_level_val]
            if v is not None
        )

        # --- Calculate contribution from the constant level (flat top) part ---
        if needs_qua_calc:
            int_v_var = self._ensure_qua_integrated_voltage_var()
            level_contribution = Cast.mul_int_by_fixed(
                duration
                << INTEGRATED_VOLTAGE_BITSHIFT,  # duration * INTEGRATED_VOLTAGE_SCALING_FACTOR
                level,
            )
            assign(int_v_var, int_v_var + level_contribution)
        else:  # All inputs and current state are Python types
            level_contribution = int(
                np.round((level * duration) * INTEGRATED_VOLTAGE_SCALING_FACTOR)
            )
            # _integrated_voltage_internal is guaranteed to be an int here
            # because needs_qua_calc is false.
            self._integrated_voltage_internal += level_contribution

        # --- Calculate contribution from the ramp part (if applicable) ---
        if ramp_duration is not None:
            avg_ramp_level = (level + current_level_val) * 0.5

            if needs_qua_calc:
                # int_v_var is already guaranteed to be a QUA variable if needs_qua_calc is true
                int_v_var = self._integrated_voltage_qua_var
                if int_v_var is None:  # Should not happen due to _ensure call logic
                    raise StateError(
                        f"QUA variable for integrated voltage of '{self._element_name}' "
                        "not initialized during QUA ramp calculation."
                    )

                ramp_contribution = Cast.mul_int_by_fixed(
                    ramp_duration
                    << INTEGRATED_VOLTAGE_BITSHIFT,  # ramp_duration * INTEGRATED_VOLTAGE_SCALING_FACTOR
                    avg_ramp_level,
                )
                assign(int_v_var, int_v_var + ramp_contribution)
            else:  # All inputs for ramp part are Python types
                ramp_contribution = int(
                    np.round(
                        avg_ramp_level
                        * ramp_duration
                        * INTEGRATED_VOLTAGE_SCALING_FACTOR
                    )
                )
                # _integrated_voltage_internal is guaranteed to be an int here
                self._integrated_voltage_internal += ramp_contribution


class KeepLevels:
    """
    Keep track of physical/virtual gate levels throughout a VoltageSequence
    Removes the need to supply voltage points for gates that are already at their desired non-zero level.
    example:
    seq.step_to_voltages(voltages={"ch1": 0.2}, duration=100)
    seq.step_to_voltages(voltages={"ch2": 0.1}, duration=100) #ch1 will be held at 0.2 here
    seq.step_to_voltages(voltages={"ch1": 0.3}, duration=100)
    """

    def __init__(self, gate_set: GateSet | VirtualGateSet):
        self._keep_levels_dict = {}
        for channel in gate_set.valid_channel_names:
            self._keep_levels_dict[channel] = SequenceStateTracker(
                channel, track_integrated_voltage=False
            )

    def update_voltage_dict_with_current(
        self, voltages_dict: Dict[str, VoltageLevelType]
    ):
        """
        adds points that are not supplied to the voltages_dict
        """
        self.update_tracking(voltages_dict=voltages_dict)

        return {
            name: tracker.current_level
            for name, tracker in self._keep_levels_dict.items()
        }

    def update_tracking(self, voltages_dict: Dict[str, VoltageLevelType]):
        """
        updates the internal state for newly supplied points
        """
        for name, level in voltages_dict.items():
            self._keep_levels_dict[name].current_level = level
