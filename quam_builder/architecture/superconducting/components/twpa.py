from quam.core import quam_dataclass
from quam.components.channels import IQChannel
from quam import QuamComponent
from typing import Union, ClassVar
from qm.qua import align, wait, update_frequency
import numpy as np

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

        max_avg_gain (float): The maximum average gain around the readout resonators related to the TWPA
        max_avg_snr_improvement (float): The maximum average SNR improvement around the readout resonators related to the TWPA
        pump_frequency (float): calibrated pump frequency at which twpa gives the maximum average snr improvement 
        pump_amplitude (float): calibrated pump amplitude at which twpa gives the maximum average snr improvement 
        mltpx_pump_frequency (float): calibrated pump frequency at which twpa gives proper snr improvement for multiplexed readout
        mltpx_pump_amplitude (float): calibrated pump amplitude at which twpa gives proper snr improvement for multiplexed readout
        p_saturation (float): calibrated saturation power of the twpa 
        avg_std_gain (float): standard deviation of the average gain around the readout resonators related to the TWPA
        avg_std_snr_improvement (float): standard deviation of the average snr improvement around the readout resonators related to the TWPA
        
        dispersive_feature (float): dispersive feature of the twpa defined from it's designed parameters
        qubits (list): list of qubits of which the signals are amplified by the twpa
       
        initialization (bool): whether to use the twpa in the QUA program or not
        _initialized_ids (ClassVar[set]): A class-level set to track initialized twpa object IDs externally.
            This won't be serialized since it's not an instance attribute.

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
    
    initialization: bool = True
    _initialized_ids: ClassVar[set] = set()
    

    @property
    def name(self):
        """The name of the twpa"""
        return self.id if isinstance(self.id, str) else f"twpa{self.id}"



    def initialize(self):
        # dont use twpa for the QUA program if initialization is set to False
        if not self.initialization:
            return        
        # Check initialization state using object ID (memory address)
        # Initialize TWPA pump only when it hasn't been initialized yet        
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
        # guarantee initializing twpa pump only once per QUA program execution
        self._initialized_ids.add(obj_id)
       

