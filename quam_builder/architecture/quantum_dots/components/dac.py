from quam.core import quam_dataclass, QuamComponent
from quam.components import Channel

__all__ = ["DacSpec", "QdacSpec"]


@quam_dataclass
class DacSpec(QuamComponent):
    """
    Quam Component for an agnostic DAC, to be parented by VoltageGate.
    """

    output_port: int = None

    def __post_init__(self):
        super().__post_init__()
        if self.output_port is None and isinstance(self, DacSpec):
            raise ValueError("output_port is required for DacSpec")


@quam_dataclass
class QdacSpec(DacSpec):
    """
    Quam Component for a QDAC Channel, to be parented by VoltageGate.
    Attributes:
        - opx_trigger_out: A digital channel associated to the VoltageGate, used for sending a digital trigger pulse to the Qdac.
        - qdac_trigger_in: The QDAC external trigger port associated with the VoltageGate DC component.
        - qdac_output_port: The QDAC port associated with the VoltageGate DC component.
    """

    opx_trigger_out: Channel = None
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
