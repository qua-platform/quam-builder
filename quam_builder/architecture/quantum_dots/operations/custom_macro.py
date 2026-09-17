from typing import Any, get_type_hints, Optional
import dataclasses

from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    _owner_component as find_owner,
)

__all__ = ["CustomMacro"]

class _MacroParameters:
    """
    Builds a ``Parameters`` model for each ``CustomMacro`` subclass.

    The generated model is created from the macro's own dataclass fields,
    excluding framework fields inherited from ``CustomMacro`` / ``QuamMacro``.
    Each generated field is optional and defaults to ``None``, so the model can
    be used for node-level overrides without creating a second handwritten
    parameter class.
    """

    def __init__(self):
        self._cache = {}

    def __get__(self, instance, owner):
        if owner not in self._cache:
            from pydantic import create_model

            base_fields = {f.name for f in dataclasses.fields(CustomMacro)}
            try:
                hints = get_type_hints(owner)
            except Exception:
                hints = {}
            fields = {
                f.name: (Optional[hints.get(f.name, f.type)], None)
                for f in dataclasses.fields(owner)
                if f.name not in base_fields
            }
            self._cache[owner] = create_model(
                f"{owner.__name__}Parameters", __module__=owner.__module__, **fields
            )
        return self._cache[owner]


@quam_dataclass
class CustomMacro(QuamMacro):
    """
    A Custom Macro class that users can subclass to create their own custom macro.

    To create a custom macro, subclass this class, declare any configurable
    fields directly on the dataclass, and implement the QUA logic in
    :meth:`apply`.

    The configurable fields you put on the macro class serve two purposes:

    1. They are stored on the macro object itself and therefore participate in
       serialization, ``update(...)``, and ``resolve_params(...)``.
    2. They are automatically exposed through the ``Parameters`` descriptor as
       an optional Pydantic model that Qualibrate nodes can mix into their
       parameter classes.

    The below example creates a custom initialize macro, which simply steps to a point for a
    particular duration. The macro's configurable parameters are declared as class attributes; 
    you can either use self.resolve_params() to resolve the attribute value from the kwargs, or 
    you can add them manually as arguments of the apply() function. 

    Pattern 1: use ``resolve_params(...)`` as a convenience helper.
    >>> @quam_dataclass
    ... class CustomInitializeMacro(CustomMacro):
    ...     # Add default values to the macro dataclass itself
    ...     point_duration: int = 100
    ...     point_voltages: float = 0.1
    ...
    ...     def apply(self, *args, **kwargs):
    ...         params = self.resolve_params(**kwargs)
    ...         point_duration = params["point_duration"]
    ...         point_voltages = params["point_voltages"]
    ...         qd_pair = self.owner
    ...         qd_pair.step_to_voltages(
    ...             voltages = {qd_pair.name : point_voltages},
    ...             duration = point_duration
    ...         )
    ...
    ...     @property
    ...     def inferred_duration(self):
    ...         return self.point_duration

    Pattern 2: spell out the fallback logic directly in ``apply(...)``.
    >>> @quam_dataclass
    ... class CustomInitializeMacro(CustomMacro):
    ...     # Add default values to the macro dataclass itself
    ...     point_duration: int = 100
    ...     point_voltages: float = 0.1
    ...
    ...     def apply(
    ...         self,
    ...         *args,
    ...         point_duration: Optional[int] = None,
    ...         point_voltages: Optional[float] = None,
    ...         **kwargs,
    ...     ):
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

    It is also good practice to implement :attr:`inferred_duration` when you
    can estimate how long the macro takes to run.
    """
    Parameters = _MacroParameters()

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
        base_field_names = {f.name for f in dataclasses.fields(CustomMacro)}
        return {f.name for f in dataclasses.fields(cls)} - base_field_names

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

    def resolve_params(self, **overrides) -> dict:
        """Merge this macro's dataclass field values with any explicit
        per-call overrides. A None or missing override falls back to self.<field>."""
        resolved = {}
        for f in dataclasses.fields(self):
            override = overrides.get(f.name)
            resolved[f.name] = getattr(self, f.name) if override is None else override
        return resolved
