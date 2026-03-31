import numpy as np
from typing import Union, List, Optional

from quam.core import quam_dataclass, QuamComponent
from quam.components import Channel

__all__ = ["DacSpec", "QdacSpec"]


@quam_dataclass
class DacSpec(QuamComponent):
    """
    Quam Component for an agnostic DAC, to be parented by VoltageGate.
    Attributes:
        - output_port: An integer to indicate which channel you are outputting via. The driver structuer
                        should look like driver.channel_method(output_port).
        - opx_trigger_out: A digital channel associated to the VoltageGate, used for sending a digital trigger pulse to the DAC.
    """

    output_port: int = None
    opx_trigger_out: Channel = None
    dac_name: str = "main"

    def __post_init__(self):
        super().__post_init__()
        if self.output_port is None and isinstance(self, DacSpec):
            raise ValueError("output_port is required for DacSpec")

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
        return dac_obj


@quam_dataclass
class QdacSpec(DacSpec):
    """
    Quam Component for a QDAC Channel, to be parented by VoltageGate.
    Attributes:
        - qdac_trigger_in: The QDAC external trigger port associated with the VoltageGate DC component.
        - qdac_output_port: The QDAC port associated with the VoltageGate DC component.
    """

    qdac_trigger_in: int = None
    qdac_output_port: int = None

    def __post_init__(self):
        if self.qdac_output_port is None and self.output_port is None:
            raise ValueError("Either output_port or qdac_output_port must be provided")
        if self.qdac_output_port is None:  # Means only the output_port is defined
            self.qdac_output_port = self.output_port
        else:  # Means that the user has inputted a qdac_output_port. We can sync them again
            self.output_port = self.qdac_output_port
        super().__post_init__()

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
        dc_list = self.qdac.channel(self.qdac_output_port).dc_list(
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

        triangle_wave = self.qdac.channel(self.qdac_output_port).triangle_wave(
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
