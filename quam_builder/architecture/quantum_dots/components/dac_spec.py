import numpy as np
from typing import Union, List, Optional, Dict
from dataclasses import field

from quam.core import quam_dataclass, QuamComponent
from quam.components import Channel

__all__ = ["DacSpec", "QdacSpec"]

# A dummy object to flag whether the user has actually passed a value or not
_NOT_GIVEN = object()

LIMITS = ("max_voltage", "min_voltage", "max_step_size")


@quam_dataclass
class DacSpec(QuamComponent):
    """
    Quam Component for an agnostic DAC, to be parented by VoltageGate.
    Attributes:
        - output_port: An integer to indicate which channel you are outputting via. The driver structure
                        should look like driver.channel_method(output_port).
        - opx_trigger_out: A digital channel associated to the VoltageGate, used for sending a digital trigger pulse to the DAC.
        - dac_name: The key of the driver in machine.dacs that this channel belongs to. Default "main".
        - limits: Safety limits enforced by VirtualDCSet.set_voltages on this physical channel. Keys:
            - "max_voltage": Highest voltage the channel may be set to.
            - "min_voltage": Lowest voltage the channel may be set to.
            - "max_step_size": Largest change allowed in a single set_voltages call, in either
                direction.
            All three default to None, which disables that check, so a new DacSpec has no limits.
            A partial dict passed at construction is merged over the defaults. After construction,
            limits cannot be reassigned; change them with update_limits.
    """

    output_port: int = None
    opx_trigger_out: Channel = None
    dac_name: str = "main"

    limits: Dict[str, Optional[float]] = field(default_factory = dict)

    def __post_init__(self):
        super().__post_init__()
        if self.output_port is None and isinstance(self, DacSpec):
            raise ValueError("output_port is required for DacSpec")

        limits = {
            lim: None for lim in LIMITS
        }
        if not self.limits: 
            # Means that the user has not inputted a limit
            self.limits = limits
        else:
            # Means that there is a partial or whole limits dict. We COMBINE with the default. 
            unrecognised = sorted(set(self.limits) - set(LIMITS))
            if unrecognised:
                raise ValueError(
                    f"Unrecognised limit(s) {unrecognised}. Available limits: {list(LIMITS)}"
                )
            limits.update(self.limits)
            self.limits = limits.copy()

        # Stored in __dict__ directly so it is not a QUAM attribute and is never serialised.
        self.__dict__["_limits_locked"] = True

    def __setattr__(self, name, value):
        if name == "limits" and self.__dict__.get("_limits_locked", False):
            raise AttributeError(
                "DacSpec.limits cannot be reassigned, as this would drop the other limit keys. "
                "Use update_limits(...) instead."
            )
        super().__setattr__(name, value)

    def update_limits(
            self,
            max_voltage: float | None = _NOT_GIVEN,
            min_voltage: float | None = _NOT_GIVEN,
            max_step_size: float | None = _NOT_GIVEN,
        ) -> None:
        """
        Update one or more limits, leaving the others unchanged.

        Pass None to disable a check, e.g. update_limits(max_step_size=None).
        The arguments must match LIMITS.
        """
        updates = {
            "max_voltage": max_voltage,
            "min_voltage": min_voltage,
            "max_step_size": max_step_size,
        }
        self.limits.update({key: value for key, value in updates.items() if value is not _NOT_GIVEN})

    @property
    def machine(self) -> "BaseQuamQD":
        # Climb up the parent ladder in order to find the machine in the machine
        obj = self
        while obj.parent is not None:
            obj = obj.parent
        machine = obj
        return machine

    @property
    def dac(self):
        dac_obj = self.machine.dacs.get(self.dac_name, None)
        if dac_obj is None:
            raise ValueError(
                f"DAC name {self.dac_name} not found in machine. Have you run machine.connect_to_external_source() ?"
            )
        return dac_obj["driver"]


@quam_dataclass
class QdacSpec(DacSpec):
    """
    Quam Component for a QDAC Channel, to be parented by VoltageGate.
    Attributes:
        - qdac_trigger_in: The QDAC external trigger port associated with the VoltageGate DC component.
        - qdac_output_port: Legacy attribute, now an alias for ``output_port``
    """

    qdac_trigger_in: int = None

    @property
    def qdac_output_port(self) -> int:
        """Legacy alias for ``output_port``."""
        return self.output_port

    @property
    def qdac(self):
        return self.dac

    def free_all_triggers(self) -> None:
        self.qdac.free_all_triggers()

    def load_dc_list(
        self,
        voltages: Union[List, np.ndarray],
        dwell_s: float = 200e-6,
        stepped: bool = True,
    ) -> None:
        self.qdac.channel(self.output_port).dc_mode("list")
        dc_list = self.qdac.channel(self.output_port).dc_list(
            voltages=voltages,
            dwell_s=dwell_s,
            stepped=stepped,
        )
        if stepped:  # This means it is triggered
            dc_list.start_on_external(trigger=self.qdac_trigger_in)

    def play_triangle_wave(
        self,
        frequency_Hz: Optional[float] = None,
        period_s: Optional[float] = None,
        repetitions: int = -1,
        duty_cycle_percent: float = 50.0,
        inverted: bool = False,
        span_V: float = 0.2,
        offset_V: float = 0.0,
        delay_s: float = 0,
        slew_V_s: Optional[float] = None,
        triggered: bool = True,
    ):
        """An example of how to fully utilise the QDAC API in the QdacSpec. This example plays a triangle wave."""

        triangle_wave = self.qdac.channel(self.output_port).triangle_wave(
            frequency_Hz=frequency_Hz,
            repetitions=repetitions,
            period_s=period_s,
            duty_cycle_percent=duty_cycle_percent,
            inverted=inverted,
            span_V=span_V,
            offset_V=offset_V,
            delay_s=delay_s,
            slew_V_s=slew_V_s,
        )
        if triggered:
            triangle_wave.start_on_external(trigger=self.qdac_trigger_in)
