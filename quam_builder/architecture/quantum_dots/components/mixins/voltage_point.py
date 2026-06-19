"""Voltage point management mixin for quantum dot components.

This module provides point creation and navigation functionality, building
on top of VoltageControlMixin.
"""

from typing import TYPE_CHECKING, Dict, Optional

from quam.core import quam_dataclass

from .voltage_control import VoltageControlMixin

if TYPE_CHECKING:
    from quam_builder.tools.voltage_sequence import VoltageSequence

__all__ = ["VoltagePointMixin"]


@quam_dataclass
class VoltagePointMixin(VoltageControlMixin):
    """Mixin providing voltage point management operations.

    This mixin extends VoltageControlMixin with point-based operations:
    - Creating and registering named voltage points
    - Navigating to points via step or ramp transitions
    - Point reference management for macro creation

    Following quam's Pulse -> Macro -> Operation pattern:
    - Voltage point ~ Pulse definition
    - PointMacro ~ PulseMacro
    - Sequence/Operation ~ Gate
    """

    def add_point(
        self,
        point_name: str,
        voltages: Dict[str, float],
        duration: int = 16,
        replace_existing_point: bool = True,
    ) -> str:
        """Define a voltage point in the gate set for later use by macros.

        This method registers a named voltage configuration in the VirtualGateSet
        with a prefixed name: "{component.id}_{point_name}". Once registered,
        the point can be referenced by StepPointMacro and RampPointMacro instances.

        Args:
            point_name: Local name for the point (without prefix). Used in macro references.
            voltages: Voltage values for each gate. Key format depends on component type:
                     - QuantumDot: Use gate IDs (e.g., 'virtual_dot_0')
                     - LDQubit/LDQubitPair: Can use qubit names (e.g., 'Q0'), automatically
                       mapped to quantum dot IDs if _should_map_qubit_names() returns True
            duration: Default hold duration for this point (nanoseconds, default: 16).
                     Can be overridden when creating macros or during execution.
            replace_existing_point: If True (default), overwrites existing point with same name.
                                   If False, raises ValueError if point exists.

        Returns:
            str: The full gate_set name ("{component.id}_{point_name}")

        Raises:
            ValueError: If point already exists and replace_existing_point is False

        Example:
            .. code-block:: python

                # Define voltage points
                quantum_dot.add_point('idle', voltages={'virtual_dot_0': 0.1})
                # Returns: 'quantum_dot_0_idle'

                quantum_dot.add_point('loading', voltages={'virtual_dot_0': 0.3})
                # Returns: 'quantum_dot_0_loading'
        """
        gate_set = self.voltage_sequence.gate_set
        existing_points = gate_set.get_macros()

        # Construct full gate_set name with component prefix
        full_name = self._create_point_name(point_name)

        # Check if point already exists
        if full_name in existing_points and not replace_existing_point:
            raise ValueError(
                f"Point '{point_name}' already exists as '{full_name}'. "
                "Set replace_existing_point=True to overwrite."
            )

        # Validate voltage keys
        for channel_name in voltages.keys():
            self._validate_component_id_in_gate_set(channel_name)

        # Register in gate set
        gate_set.add_point(name=full_name, voltages=voltages, duration=duration)

        return full_name

    def _create_point_name(self, point_name: str) -> str:
        """Construct the full gate_set name from a local point name.

        Args:
            point_name: Local point name (without component prefix)

        Returns:
            str: Full gate_set name in format "{component.id}_{point_name}"
        """
        return f"{self.id}_{point_name}"

    def _get_or_create_point_ref(
        self,
        macro_name: str,
        voltages: Optional[Dict[str, float]],
        duration: int,
        replace_existing_point: bool,
    ) -> str:
        """Get reference to an existing point or create a new one.

        Args:
            macro_name: Name for the point (will be prefixed with component id)
            voltages: Optional voltage values. If None, looks up existing point.
            duration: Duration for the point (used when creating new point)
            replace_existing_point: If True, overwrites existing point

        Returns:
            str: Reference string to the point

        Raises:
            KeyError: If voltages is None and the point doesn't exist
        """
        full_name = self._create_point_name(macro_name)

        if voltages is not None:
            self.add_point(
                point_name=macro_name,
                voltages=voltages,
                duration=duration,
                replace_existing_point=replace_existing_point,
            )
        else:
            existing_points = self.voltage_sequence.gate_set.get_macros()
            if full_name not in existing_points:
                raise KeyError(
                    f"Point '{macro_name}' (full name: '{full_name}') does not exist. "
                    f"Available points: {list(existing_points.keys())}. "
                    f"To create a new point, provide the 'voltages' parameter."
                )

        return self.voltage_sequence.gate_set.macros[full_name].get_reference()

    def step_to_point(self, point_name: str, duration: Optional[int] = None) -> None:
        """Step instantly to a pre-defined voltage point (convenience method).

        This is a convenience wrapper around voltage_sequence.step_to_point()
        that handles automatic name prefixing. For reusable operations, consider
        creating a StepPointMacro instead and storing it in self.macros.

        Args:
            point_name: Local point name (without prefix, must be added via add_point())
            duration: Hold duration in nanoseconds (default: uses point's default)

        Raises:
            KeyError: If the point has not been registered via add_point()

        Example:
            .. code-block:: python

                # Direct usage (convenience)
                quantum_dot.add_point('idle', voltages={'virtual_dot_0': 0.1})
                quantum_dot.step_to_point('idle', duration=100)

                # Equivalent using macro (reusable, serializable)
                quantum_dot.macros['idle'] = StepPointMacro('idle', 100)
                quantum_dot.macros['idle']()
        """
        full_name = self._create_point_name(point_name)
        self.voltage_sequence.step_to_point(name=full_name, duration=duration)

    def ramp_to_point(
        self, point_name: str, ramp_duration: int, duration: Optional[int] = None
    ) -> None:
        """Ramp gradually to a pre-defined voltage point (convenience method).

        This is a convenience wrapper around voltage_sequence.ramp_to_point()
        that handles automatic name prefixing. For reusable operations, consider
        creating a RampPointMacro instead and storing it in self.macros.

        Args:
            point_name: Local point name (without prefix, must be added via add_point())
            ramp_duration: Time for voltage transition in nanoseconds
            duration: Hold duration at target in nanoseconds (default: uses point's default)

        Raises:
            KeyError: If the point has not been registered via add_point()

        Example:
            .. code-block:: python

                # Direct usage (convenience)
                quantum_dot.add_point('loading', voltages={'virtual_dot_0': 0.3})
                quantum_dot.ramp_to_point('loading', ramp_duration=500, duration=200)

                # Equivalent using macro (reusable, serializable)
                quantum_dot.macros['load'] = RampPointMacro('loading', 200, 500)
                quantum_dot.macros['load']()
        """
        full_name = self._create_point_name(point_name)
        self.voltage_sequence.ramp_to_point(
            name=full_name, duration=duration, ramp_duration=ramp_duration
        )
