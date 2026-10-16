from typing import get_type_hints, Optional
import dataclasses
from abc import ABC, abstractmethod

from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    _owner_component as find_owner,
)

from .default_macros.single_qubit_macros import XYDriveMacro

__all__ = ["CustomStateMacro", "CustomQubitMacro"]

class _MacroParameters:
    """
    A descriptor that builds a ``Parameters`` model for each custom macro subclass.

    Accessing ``Parameters`` on a subclass of :class:`BaseCustomMacro` returns a
    Pydantic model built from the fields declared on that subclass. The model:

    1. Excludes the framework fields inherited from ``BaseCustomMacro`` /
       ``QuamMacro`` (``id``, ``fidelity``, ``duration``, ...).
    2. Makes every field optional with a default of ``None``, so the model can be
       used for node-level overrides without writing a second parameter class.

    One model is built per subclass and cached.

    >>> @quam_dataclass
    ... class CustomInitializeMacro(CustomStateMacro):
    ...     point_duration: int = 100
    ...     voltage: float = 0.1
    ...
    >>> CustomInitializeMacro.Parameters().model_dump()
    {'point_duration': None, 'voltage': None}
    """

    def __init__(self):
        self._cache = {}

    def __get__(self, instance, owner):
        if owner not in self._cache:
            from pydantic import create_model

            own_fields = owner._own_field_names()
            try:
                hints = get_type_hints(owner)
            except Exception:
                hints = {}
            fields = {
                f.name: (Optional[hints.get(f.name, f.type)], None)
                for f in dataclasses.fields(owner)
                if f.name in own_fields
            }
            self._cache[owner] = create_model(
                f"{owner.__name__}Parameters", __module__=owner.__module__, **fields
            )
        return self._cache[owner]

@quam_dataclass
class BaseCustomMacro(QuamMacro, ABC): 
    """
    The base class for all custom macros.

    In most cases, subclass :class:`CustomStateMacro` (owner is the
    QuantumDotPair) or :class:`CustomQubitMacro` (owner is the qubit) rather
    than this class. Subclass ``BaseCustomMacro`` directly only when the macro
    runs on a different component, in which case you must implement
    :attr:`owner`.

    A subclass declares its configurable fields directly on the dataclass and
    implements the QUA logic in :meth:`apply`. This base class then provides:

    1. ``Parameters``, an optional Pydantic model built from the declared fields
       that Qualibrate nodes can mix into their parameter classes.
    2. ``__call__``, so that calling the macro runs :meth:`apply`.
    3. ``update(...)``, which persistently sets declared fields and rejects
       unknown keywords.
    4. ``resolve_params(...)``, which merges the stored field values with
       per-call overrides.

    It is also good practice to implement :attr:`inferred_duration`, in seconds,
    when you can estimate how long the macro takes to run.
    """

    Parameters = _MacroParameters()

    @property
    @abstractmethod
    def owner(self): 
        """
        Identifies the QuamComponent from which the macro should be run. 

        For state macros, this should be the QuantumDotPair, since many state-level operations are done 
        pairwise. 

        For qubit macros, this should be the Qubit object. 
        """
        pass
    
    def __call__(self, *args, **kwargs):
        """
        Allows the macro's apply function to run via the call method.

        E.g. For an InitializeMacro, calling qubit.initialize() runs the InitializeMacro's
        apply() function.
        """
        return self.apply(*args, **kwargs)

    @classmethod
    def _own_field_names(cls) -> set[str]:
        """Field names declared on the subclass itself, excluding framework fields
        inherited from BaseCustomMacro/QuamMacro/QuamComponent (id, parent, etc.)."""
        base_field_names = {f.name for f in dataclasses.fields(BaseCustomMacro)}
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
        """Merge the fields declared on the subclass with any explicit per-call overrides.
        A None or missing override falls back to self.<field>. Framework fields such as
        ``id`` and ``duration`` are not included."""
        own_fields = self._own_field_names()
        resolved = {}
        for f in dataclasses.fields(self):
            if f.name not in own_fields:
                continue
            override = overrides.get(f.name)
            resolved[f.name] = getattr(self, f.name) if override is None else override
        return resolved


@quam_dataclass
class CustomStateMacro(BaseCustomMacro):
    """
    A Custom State Macro class that users can subclass to create their own state-level macro.

    The owner of a state macro is the QuantumDotPair it is attached to, since most
    state-level operations (initialize, measure, empty, ...) are done pairwise.
    :meth:`point_voltages` looks up the voltages of a named point on that pair.

    To create a custom state macro, subclass this class, declare any configurable
    fields directly on the dataclass, and implement the QUA logic in
    :meth:`apply`.

    The configurable fields you put on the macro class serve two purposes:

    1. They are stored on the macro object itself and therefore participate in
       serialization, ``update(...)``, and ``resolve_params(...)``.
    2. They are automatically exposed through the ``Parameters`` descriptor as
       an optional Pydantic model that Qualibrate nodes can mix into their
       parameter classes.

    Do not name a field after a method or property of this class (for example
    ``point_voltages`` or ``owner``), since the field would replace it.

    The below example creates a custom initialize macro, which simply steps to a voltage for a
    particular duration. The macro's configurable parameters are declared as class attributes;
    you can either use self.resolve_params() to resolve the attribute value from the kwargs, or
    you can add them manually as arguments of the apply() function.

    Pattern 1: use ``resolve_params(...)`` as a convenience helper.
    >>> @quam_dataclass
    ... class CustomInitializeMacro(CustomStateMacro):
    ...     # Add default values to the macro dataclass itself
    ...     point_duration: int = 100
    ...     voltage: float = 0.1
    ...
    ...     def apply(self, *args, **kwargs):
    ...         params = self.resolve_params(**kwargs)
    ...         point_duration = params["point_duration"]
    ...         voltage = params["voltage"]
    ...         qd_pair = self.owner
    ...         qd_pair.step_to_voltages(
    ...             voltages = {qd_pair.name : voltage},
    ...             duration = point_duration
    ...         )
    ...
    ...     @property
    ...     def inferred_duration(self):
    ...         return self.point_duration * 1e-9

    Pattern 2: spell out the fallback logic directly in ``apply(...)``.
    >>> @quam_dataclass
    ... class CustomInitializeMacro(CustomStateMacro):
    ...     # Add default values to the macro dataclass itself
    ...     point_duration: int = 100
    ...     voltage: float = 0.1
    ...
    ...     def apply(
    ...         self,
    ...         *args,
    ...         point_duration: Optional[int] = None,
    ...         voltage: Optional[float] = None,
    ...         **kwargs,
    ...     ):
    ...         point_duration = self.point_duration if point_duration is None else point_duration
    ...         voltage = self.voltage if voltage is None else voltage
    ...         qd_pair = self.owner
    ...         qd_pair.step_to_voltages(
    ...             voltages = {qd_pair.name : voltage},
    ...             duration = point_duration
    ...         )
    ...
    ...     @property
    ...     def inferred_duration(self):
    ...         return self.point_duration * 1e-9

    It is also good practice to implement :attr:`inferred_duration`, in seconds, when you
    can estimate how long the macro takes to run.
    """

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

@quam_dataclass
class CustomQubitMacro(XYDriveMacro, BaseCustomMacro):
    """
    A Custom Qubit Macro class that users can subclass to create their own qubit-level macro.

    The owner is the qubit the macro is attached to. Declare configurable fields on the
    subclass and implement the QUA logic in :meth:`apply`, as for :class:`CustomStateMacro`.

    The default :meth:`apply` plays one XY pulse,
    ``qubit.xy.operations[f"{pulse_family}_{gate_suffix}"]``. For example,
    ``gate_suffix = "x90"`` selects ``gaussian_x90``, or ``drag_x90`` after
    ``machine.set_pulse_family("drag")``.

    - ``gate_suffix`` is ``None`` (the default): the default :meth:`apply` raises
    ``ValueError``, so write your own :meth:`apply`. Use this for macros without an XY
    pulse, e.g. exchange-only or singlet-triplet gates.
    - ``gate_suffix`` is set and :meth:`apply` is not overridden: the default :meth:`apply`
    plays the pulse.
    - ``gate_suffix`` is set and :meth:`apply` is overridden: the pulse is only played where
    your :meth:`apply` calls ``super().apply(...)``.

    To replace a built-in XY gate such as ``x180`` or ``x90``, set ``gate_suffix`` and make
    sure calls to :meth:`apply` play the pulse. Calibration nodes call
    ``apply(amplitude_scale=..., duration=...)``, with ``duration`` in clock cycles, and
    ``update(amplitude_scale=..., duration=...)``, which multiplies the stored pulse amplitude
    and sets its length in ns. ``update`` also accepts ``frequency`` and ``frequency_offset``,
    which set ``qubit.larmor_frequency``, and your own fields. The operation must exist for
    every pulse family you switch to; :meth:`check_pulse` raises ``KeyError`` before playing
    or updating if it does not.

    >>> @quam_dataclass
    ... class EchoedX180Macro(CustomQubitMacro):
    ...     gate_suffix: str = "x180"
    ...     pre_wait: int = 4
    ...
    ...     def apply(self, amplitude_scale=None, duration=None, **kwargs):
    ...         params = self.resolve_params(**kwargs)
    ...         self.owner.idle(params["pre_wait"])
    ...         super().apply(amplitude_scale=amplitude_scale, duration=duration)
    """

    gate_suffix: Optional[str] = None
    """Suffix of the played XY operation, ``{pulse_family}_{gate_suffix}``. ``None`` for no XY pulse."""

    _XY_UPDATE_KEYS = frozenset({"amplitude_scale", "duration", "frequency", "frequency_offset"})

    @classmethod
    def _own_field_names(cls) -> set[str]:
        framework = {f.name for f in dataclasses.fields(XYDriveMacro)} | {"gate_suffix"}
        return super()._own_field_names() - framework

    @property
    def owner(self):
        from quam.components.quantum_components.qubit import Qubit
        parent = self.parent
        if isinstance(parent, Qubit):
            return parent
        if isinstance(getattr(parent, "parent", None), Qubit):
            return parent.parent
        raise ValueError("This CustomQubitMacro is not associated with a Qubit object.")

    @property
    def pulse_name(self) -> Optional[str]:
        if self.gate_suffix is None:
            return None
        return f"{self.pulse_family}_{self.gate_suffix.lstrip('_')}"

    def check_pulse(self) -> None:
        """Raise if ``gate_suffix`` is unset or the operation for the active pulse family is missing."""
        if self.gate_suffix is None:
            raise ValueError(
                f"{type(self).__name__} has no gate_suffix, so it has no XY pulse to play or "
                f"update. Set gate_suffix, or override apply()."
            )
        operations = self.owner.xy.operations
        if self.pulse_name not in operations:
            family_ops = sorted(op for op in operations if op.startswith(f"{self.pulse_family}_"))
            raise KeyError(
                f"{type(self).__name__} on qubit '{self.qubit.id}' plays '{self.pulse_name}' "
                f"(pulse_family={self.pulse_family!r}, gate_suffix={self.gate_suffix!r}), "
                f"which is not in qubit.xy.operations. Operations for this family: {family_ops}"
            )

    @property
    def pulse(self):
        self.check_pulse()
        return super().pulse

    @property
    def inferred_duration(self) -> float | None:
        if self.gate_suffix is None:
            return None
        self.check_pulse()
        return super().inferred_duration

    def apply(self, amplitude_scale: float | None = None, duration=None, angle: float | None = None):
        self.check_pulse()
        return super().apply(amplitude_scale=amplitude_scale, duration=duration, angle=angle)

    def update(self, **kwargs) -> None:
        """
        We have update functions in both XYDriveMacro and BaseCustomMacro. We need to be able to 
        cleanly apply them both here. First, filter out the XY params to update, update, and then 
        update the rest.
        """
        xy_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in self._XY_UPDATE_KEYS}
        if xy_kwargs:
            self.check_pulse()
            XYDriveMacro.update(self, **xy_kwargs)
        BaseCustomMacro.update(self, **kwargs)
