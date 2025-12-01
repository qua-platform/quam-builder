from quam.core import quam_dataclass
from quam.components.channels import IQChannel
from quam import QuamComponent
from typing import Union, ClassVar
from qm.qua import align, wait
import numpy as np
from qm.qua import update_frequency

__all__ = ["TWPA"]


@quam_dataclass
class TWPA(QuamComponent):
    """
    Example QuAM component for a TWPA.

    Args:
        id (str, int): The id of the TWPA, used to generate the name.
            Can be a string, or an integer in which case it will add`Channel._default_label`.
        pump (IQChannel): The pump component(sticky element) used for continuous output. 
        pump_ (IQChannel): The pump component(non sticky element)used for TWPA calibration
        spectroscopy (IQChannel): Probe tone used for calibrating the saturation power of the TWPA
    """

    id: Union[int, str]

    pump: IQChannel = None
    pump_: IQChannel = None
    spectroscopy: IQChannel = None

    max_avg_gain: float = None
    max_avg_snr_improvement: float = None
    pump_frequency : float = None
    pump_amplitude : float = None
    mltpx_pump_frequency : float = None
    mltpx_pump_amplitude : float = None
    p_saturation: float = None
    avg_std_gain: float=None
    avg_std_snr_improvement: float= None

    dispersive_feature: float = None
    qubits: list = None
    
    with_initialization: bool = True
    
    # Class-level set to track initialized object IDs externally
    # This won't be serialized since it's not an instance attribute
    _initialized_ids: ClassVar[set] = set()
    
    def get_output_power(self, operation, Z=50) -> float:
        power = self.xy.opx_output.full_scale_power_dbm
        amplitude = self.xy.operations[operation].amplitude
        x_mw = 10 ** (power / 10)                       #Pmw
        x_v = amplitude * np.sqrt(2 * Z * x_mw / 1000) # Vp
        return 10 * np.log10(((x_v / np.sqrt(2)) ** 2 * 1000) / Z) # Pdbm

    
    @property
    def name(self):
        """The name of the transmon"""
        return self.id if isinstance(self.id, str) else f"q{self.id}"

   
    def align(self, other = None):
        channels = [self.xy.name, self.resonator.name, self.z.name]

        if other is not None:
            channels += [other.xy.name, other.resonator.name, other.z.name]

        align(*channels)

    def wait(self, duration):
        wait(duration, self.xy.name, self.z.name, self.resonator.name)

    def initialize(self):
        if not self.with_initialization:
            return
        
        # Check initialization state using object ID (memory address)
        # This won't be serialized since it's stored in a class-level set
        obj_id = id(self)
        if obj_id in self._initialized_ids:
            return
        
        f_p = self.pump_frequency
        p_p = self.pump_amplitude
        update_frequency(
            self.pump.name,
            f_p+ self.pump.intermediate_frequency,
        )
        self.pump.play("pump", amplitude_scale=p_p)
        # Store object ID externally (won't be serialized)
        self._initialized_ids.add(obj_id)
       

