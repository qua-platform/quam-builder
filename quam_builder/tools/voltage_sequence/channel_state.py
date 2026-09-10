"""Physical-channel voltage and area tracking for VoltageSequence."""

from typing import Optional

import numpy as np
from qm.qua import Cast, assign, declare, fixed, if_
from qm.qua.type_hints import QuaVariable, Scalar

from quam_builder.tools.qua_tools import is_qua_type
from quam_builder.tools.voltage_sequence.exceptions import StateError

__all__ = [
    "ChannelState",
    "VOLTAGE_FRAC_BITS",
    "VOLTAGE_SCALE",
    "CLOCK_CYCLE_NS",
    "voltage_counts",
    "split_mul",
]

VOLTAGE_FRAC_BITS = 16
VOLTAGE_SCALE = 1 << VOLTAGE_FRAC_BITS  # 2 ** 16
CLOCK_CYCLE_NS = 4
# v_counts at 2.5 V is 163840; 15-bit low limb keeps v_lo * d_lo inside 32-bit.
_V_LO_BITS = 15
_V_LO_MASK = (1 << _V_LO_BITS) - 1
_D_LO_MASK = 0xFFFF


def voltage_counts(level: float) -> int:
    """16-bit OPX voltage counts (same grid as sticky / float16)."""
    return int(np.round(float(np.float16(level)) * VOLTAGE_SCALE))


def split_mul(v_counts: int, duration_ns: int) -> int:
    """``v_counts * duration_ns`` using 15×16-bit limbs (fits signed 32-bit muls).

    Valid for |v_counts| <= 2.5 * 2**16 and duration_ns that fits in a QUA int.
    """
    v0 = v_counts & _V_LO_MASK
    v1 = v_counts >> _V_LO_BITS
    if v_counts < 0:
        # Two's-complement-style split is only used for non-negative counts;
        # signed area is applied by the caller via signed v_counts in Python.
        return v_counts * duration_ns
    d0 = duration_ns & _D_LO_MASK
    d1 = duration_ns >> 16
    p00 = v0 * d0
    p01 = v0 * d1
    p10 = v1 * d0
    p11 = v1 * d1
    return p00 + (p01 << 16) + (p10 << _V_LO_BITS) + (p11 << (16 + _V_LO_BITS))


class ChannelState:
    """Tracks sticky level and DC area for one physical OPX element.

    Area is stored as ``coarse`` (integer V·ns) plus ``fine`` (units of
    ``2**-16`` V·ns) so that ``area = coarse + fine / VOLTAGE_SCALE``.
    ``integrated_voltage`` is the same area in units of ``2**-16`` V·ns
    (``coarse * VOLTAGE_SCALE + fine``), matching 16-bit voltage × ns.
    """

    def __init__(
        self,
        element_name: str,
        track_integrated_voltage: bool = True,
        enforce_qua_calcs: bool = False,
    ):
        if not isinstance(element_name, str) or not element_name:
            raise ValueError("element_name must be a non-empty string.")

        self._element_name = element_name
        self._track_integrated_voltage = track_integrated_voltage
        self._enforce_qua_calcs = enforce_qua_calcs
        self._current_level_internal: Scalar[float] = 0.0
        self._python_level: float = 0.0
        self._coarse = 0
        self._fine = 0
        self._qua_coarse: Optional[QuaVariable] = None
        self._qua_fine: Optional[QuaVariable] = None
        self._current_py_val_before_promotion = None

    def initialize_qua_vars(self):
        self._coarse = 0
        self._fine = 0
        self._qua_coarse = None
        self._qua_fine = None
        self._current_py_val_before_promotion = None
        self._python_level = (
            float(self._current_level_internal)
            if not is_qua_type(self._current_level_internal)
            else 0.0
        )
        if self._enforce_qua_calcs:
            val = (
                self._current_level_internal
                if not is_qua_type(self._current_level_internal)
                else 0.0
            )
            self._current_level_internal = declare(fixed, value=val)
        if self._track_integrated_voltage and self._enforce_qua_calcs:
            self._qua_coarse = declare(int, value=0)
            self._qua_fine = declare(int, value=0)

    @property
    def element_name(self) -> str:
        return self._element_name

    @property
    def current_level(self) -> Scalar[float]:
        return self._current_level_internal

    @current_level.setter
    def current_level(self, level: Scalar[float]):
        if is_qua_type(level):
            if not is_qua_type(self._current_level_internal):
                self._current_level_internal = declare(fixed)
            assign(self._current_level_internal, level)
        elif is_qua_type(self._current_level_internal):
            assign(self._current_level_internal, level)
            self._python_level = float(level)
        else:
            self._current_level_internal = level
            self._python_level = float(level)

    @property
    def coarse(self) -> Scalar[int]:
        if self._qua_coarse is not None:
            return self._qua_coarse
        return self._coarse

    @property
    def fine(self) -> Scalar[int]:
        if self._qua_fine is not None:
            return self._qua_fine
        return self._fine

    @property
    def integrated_voltage(self) -> Scalar[int]:
        if self._qua_coarse is not None:
            # QUA accumulator is the full scaled area (2**-16 V·ns), same as Python
            # ``coarse * VOLTAGE_SCALE + fine``.
            return self._qua_coarse
        return self._coarse * VOLTAGE_SCALE + self._fine

    @property
    def _integrated_voltage_qua_var(self):
        return self._qua_coarse

    def reset_integrated_voltage(self):
        if self._qua_coarse is not None:
            prefix = self._current_py_val_before_promotion
            if prefix is not None:
                assign(self._qua_coarse, prefix)
            else:
                assign(self._qua_coarse, 0)
            if self._qua_fine is not None:
                assign(self._qua_fine, 0)
        else:
            self._coarse = 0
            self._fine = 0

    def _ensure_qua_area(self) -> None:
        if self._qua_coarse is not None:
            return
        if not isinstance(self._coarse, int) or not isinstance(self._fine, int):
            raise StateError(
                f"Inconsistent state for integrated voltage of '{self._element_name}'. "
                f"Expected int before QUA variable promotion, got {type(self._coarse)}."
            )
        current = self._coarse * VOLTAGE_SCALE + self._fine
        self._current_py_val_before_promotion = current
        self._qua_coarse = declare(int, value=current)
        self._qua_fine = declare(int, value=0)

    def _ensure_qua_integrated_voltage_var(self) -> QuaVariable:
        """Compatibility hook; area is two ints (coarse, fine)."""
        self._ensure_qua_area()
        return self._qua_coarse

    def _add_scaled_python(self, v_counts: int, duration_ns: int) -> None:
        if duration_ns == 0 or v_counts == 0:
            return
        product = split_mul(abs(v_counts), int(duration_ns))
        if v_counts < 0:
            product = -product
        total = self._coarse * VOLTAGE_SCALE + self._fine + product
        self._coarse = total // VOLTAGE_SCALE
        self._fine = total % VOLTAGE_SCALE
        if self._fine < 0:
            self._coarse -= 1
            self._fine += VOLTAGE_SCALE

    def _add_scaled_qua(self, level, duration_ns) -> None:
        """Add ``level * duration`` in scaled units with one QUA assign.

        Matches the previous tracker: ``Cast.mul_int_by_fixed(duration << 16, level)``.
        Split-limb muls are only used on the Python path (see ``split_mul``).
        """
        self._ensure_qua_area()
        acc = self._qua_coarse
        if is_qua_type(level):
            if is_qua_type(duration_ns):
                shifted = duration_ns << VOLTAGE_FRAC_BITS
            else:
                shifted = int(duration_ns) << VOLTAGE_FRAC_BITS
            assign(acc, acc + Cast.mul_int_by_fixed(shifted, level))
        else:
            scaled = voltage_counts(float(level))
            assign(acc, acc + duration_ns * scaled)

    def update_integrated_voltage(
        self,
        level: Scalar[float],
        duration: Scalar[int],
        ramp_duration: Optional[Scalar[int]] = None,
    ):
        if not self._track_integrated_voltage:
            return

        current_level_val = self._current_level_internal
        needs_qua = any(
            is_qua_type(v)
            for v in [level, duration, ramp_duration, current_level_val, self._qua_coarse]
            if v is not None
        )

        def _hold(lvl, dur):
            if dur is None:
                return
            if not is_qua_type(dur) and int(dur) == 0:
                return
            if needs_qua:
                self._add_scaled_qua(lvl, dur)
            else:
                self._add_scaled_python(voltage_counts(float(lvl)), int(dur))

        if ramp_duration is not None:
            avg = (level + current_level_val) * 0.5
            _hold(avg, ramp_duration)
        _hold(level, duration)

    def python_area_v_ns(self) -> float:
        """Area in V·ns from Python coarse/fine (not valid once QUA-promoted)."""
        if self._qua_coarse is not None:
            raise StateError("python_area_v_ns is only available for Python-tracked area.")
        return self._coarse + self._fine / VOLTAGE_SCALE
