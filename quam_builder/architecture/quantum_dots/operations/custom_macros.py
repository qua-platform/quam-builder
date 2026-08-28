from typing import Any
from dataclasses import fields

from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    _owner_component as find_owner,
)

__all__ = ["CustomMacro"]

@quam_dataclass
class CustomMacro(QuamMacro):
    """
    A Custom Macro class that users can subclass to create their own custom macro.

    In order to create your own macro, subclass this and add any QUA code to the apply() function.

    The below example creates a custom initialize macro, which simply steps to a point for a 
    particular duration. It is recommended that you add any arguments necessary in the apply() 
    function as dataclass attributes, so that the apply functions can fall back to a default value 
    stored at the class level. 

    Additionally, it is good practise to update the inferred_duration based on the apply() function that 
    you have written. 

    E.g.
    >>> @quam_dataclass
    ... class CustomInitializeMacro(CustomMacro):
    ...     # Add default values to the arguments passed in the apply function
    ...     point_duration: int = 100
    ...     point_voltages: float = 0.1
    ...
    ...     def apply(self, *args, point_duration: Optional[int] = None, point_voltages: Optional[float] = None, **kwargs):
    ...         point_duration = self.point_duration if point_duration is None else point_duration
    ...         point_voltages = self.point_voltages if point_voltages is None else point_voltages
    ...         qd_pair = self.owner
    ...         qd_pair.step_to_voltages(
    ...             voltages = {qd_pair.name : point_voltages},
    ...             duration = point_duration
    ...         )
    ...
    ...     @property
    ...     def inferred_duration(self):
    ...         return self.point_duration
    """

    def __call__(self, *args, **kwargs):
        """
        Allows the macro's apply function to run via the call method.

        E.g. For an InitializeMacro, calling qubit.initialize() runs the InitializeMacro's
        apply() function.
        """
        return self.apply(*args, **kwargs)

    @property
    def owner(self):
        """
        Extracts the owner of this particular macro. In general, the owner should be considered to be the 
        QuantumDotPair object, as most macros are done at a pairwise level.
        """
        owner = find_owner(self)
        return owner

    def point_voltages(self, point: str | dict) -> dict[str, float]:
        """
        Given an owner and a point name, find a dict of voltages associated with this point.
        """
        owner = self.owner
        if isinstance(point, dict):
            return point
        full_name = owner._create_point_name(point)
        tuning_point = owner.voltage_sequence.gate_set.macros.get(full_name)
        return dict(tuning_point.voltages)

    @classmethod
    def _own_field_names(cls) -> set[str]:
        """Field names declared on the subclass itself, excluding framework fields
        inherited from CustomMacro/QuamMacro/QuamComponent (id, parent, etc.)."""
        base_field_names = {f.name for f in fields(CustomMacro)}
        return {f.name for f in fields(cls)} - base_field_names

    def update(self, **kwargs) -> None:
        """Persistently update calibrated parameters.

        Any keyword argument matching a dataclass field you added on your
        subclass is set directly, if not None. Passing an unknown keyword
        raises TypeError, matching normal Python keyword-argument behavior.
        """
        updatable = self._own_field_names()
        for key, value in kwargs.items():
            if key not in updatable:
                raise TypeError(
                    f"{type(self).__name__}.update() got an unexpected keyword argument {key!r}"
                )
            if value is not None:
                setattr(self, key, value)
