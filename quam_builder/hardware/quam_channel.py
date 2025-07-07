from qcodes.parameters import DelegateParameter
from quam.core.quam_classes import QuamBase
from typing import ClassVar, Dict, List, Optional, Sequence, Dict
from quam.components.channels import (
    SingleChannel,
    InOutSingleChannel
)

import numpy as np
import time
from abc import ABC
from dataclasses import field
from typing import ClassVar, Dict, List, Optional, Sequence, Literal, Tuple, Union, Any
import warnings
from packaging.version import Version

import qm

from quam.components.hardware import BaseFrequencyConverter, Mixer, LocalOscillator
from quam.components.ports.digital_outputs import (
    DigitalOutputPort,
    OPXPlusDigitalOutputPort,
)
from quam.components.ports.analog_inputs import (
    LFAnalogInputPort,
    LFFEMAnalogInputPort,
    MWFEMAnalogInputPort,
    OPXPlusAnalogInputPort,
)
from quam.components.ports.analog_outputs import (
    LFAnalogOutputPort,
    LFFEMAnalogOutputPort,
    MWFEMAnalogOutputPort,
    OPXPlusAnalogOutputPort,
)


LF_output_port_types = Union[
    LFFEMAnalogOutputPort,
    OPXPlusAnalogOutputPort,
    Tuple[str, int],
    Tuple[str, int, int],
]

LF_input_port_types = Union[
    LFFEMAnalogInputPort,
    OPXPlusAnalogInputPort,
    Tuple[str, int],
    Tuple[str, int, int],
]


from quam.components.pulses import Pulse, BaseReadoutPulse
from quam.components.ports.digital_outputs import (
    FEMDigitalOutputPort,
)
from quam.core import QuamComponent, quam_dataclass
from quam.core.quam_classes import QuamDict
from quam.utils import string_reference as str_ref
from quam.utils.qua_types import (
    _PulseAmp,
    ChirpType,
    StreamType,
    ScalarInt,
    ScalarFloat,
    ScalarBool,
    QuaScalarInt,
    QuaVariableInt,
    QuaVariableFloat,
)

from qm.qua import (
    align,
    amp,
    play,
    wait,
    measure,
    declare,
    set_dc_offset,
    fixed,
    demod,
    dual_demod,
    update_frequency,
    frame_rotation,
    frame_rotation_2pi,
    time_tagging,
    reset_if_phase
)

__all__ = [
    "QdacChannel",
    "QdacOpxChannel"
]

@quam_dataclass
class QdacChannel(QuamBase):
    """
    A Quam Channel for Qdacs only, to be used in conjunction with the QCoDeS Qdac driver
    Specifically made to set DC bias 
    It should not pollute the QUA JSON, so that the config file generation is not affected for use with the OPX
    """
    # parent: Optional[QuamBase] = field(
    #     default = None, 
    #     metadata = {'description': 'attach this channel to the guven parent component'}
    # )

    id: str
    qdac: object
    channel: int
    unit: str = 'V'
    # param: DelegateParameter
    max_slew_rate: float = 1


    def __post_init__(self):
        source_param = self.qdac.channel(self.channel)
        self.dc_param = DelegateParameter(
            source = source_param.dc_constant_V,
            name = f'{self.id}_dc', 
            label = f'Qdac ch{self.channel} DC'
        )
        self.dc_param.units = self.unit


        # self._raw_sqw = source_param.square_wave
        # self.sqw_param = DelegateParameter(
        #     source = source_param.square_wave,
        #     name = f'{self.id}_sq_wave', 
        #     label = f'Qdac ch{self.channel} Square Wave'
        # )
        # self._raw_triangle = source_param.triangle_wave
        # self.triangle_param = DelegateParameter(
        #     source = source_param.triangle_wave,
        #     name = f'{self.id}_triangle_wave', 
        #     label = f'Qdac ch{self.channel} Triangle Wave'
        # )
    

    def set_dc_V(self, dc_V: float):
        """Set a voltage on the wrapped param (channel.dc_constant_V)"""
        current_voltage = self.get_dc_V()
        dV = dc_V - current_voltage
        if dV == 0:
            return
        if self.max_slew_rate <= 0:
            raise ValueError('Invalid Slew Rate')
        
        dt = 10e-3
        total_time = abs(dV/self.max_slew_rate)

        n = max(int(total_time/dt), 1)
        voltages = np.linspace(current_voltage, dc_V, n+1)[1:]
        for v in voltages: 
            self.dc_param.set(v)
            time.sleep(dt)
        
        #Set slew rate via qcodes QDac slew rate 

    
    def get_dc_V(self) -> float:
        """Get the DC voltage on the wrapped param (channel.dc_constant_V)"""
        return self.dc_param.get_latest()
    
    def to_dict(self, follow_references = False, include_defaults = False):
        d = super().to_dict(follow_references, include_defaults)
        d.pop('qdac', None)
        return d
    
    # def set_dc_zero(self):
    #     self.dc_param.set(0)

    # def square_wave_params(self, span_V: float, frequency_Hz: float, repetitions: int, offset_V: float = 0,):

    #     self.sqw_param.set(frequency_Hz = frequency_Hz, span_V = span_V, offset_V = 0, repetitions = repetitions)

    # def square_wave_start(self):
    #     self._raw_sqw.start()

    # def triangle_wave_params(self, span_V: float, frequency_Hz: float, repetitions: int, offset_V: float = 0,):

    #     self.triangle_param.set(frequency_Hz = frequency_Hz, span_V = span_V, offset_V = 0, repetitions = repetitions)
    
    # def triangle_wave_start(self):
    #     self._raw_triangle.start()


class CoupledSingleChannel(SingleChannel):
    """
    Quick subclass to add a couplings input, that is not going to be saved in your QUAM state
    """
    def __init__(self, *args, couplings: dict[str, float], **kwargs):
        super().__init__(*args, **kwargs)
        self.couplings = couplings or {}

    def to_dict(self, follow_references = False, include_defaults = False):
        d = super().to_dict(follow_references, include_defaults)
        d.pop('couplings', None)
        return d
    
class CoupledInOutSingleChannel(InOutSingleChannel):
    """
    Quick subclass to add a couplings input to the normal InOutSingleChannel. Couplings not saved in the QUAM state
    """
    def __init__(self, *args, couplings: dict[str, float], **kwargs):
        super().__init__(*args, **kwargs)
        self.couplings = couplings or {}

    def to_dict(self, follow_references = False, include_defaults = False):
        d = super().to_dict(follow_references, include_defaults)
        d.pop('couplings', None)
        return d



@quam_dataclass
class QdacOpxChannel(SingleChannel):
    qdac: object
    qdac_channel: int
    qdac_unit: str = 'V'
    dc_channel: QdacChannel = field(init = False)
    qdac_max_slew_rate: float = 1.0
    couplings: dict[str, float] = field(default_factory = dict, repr = False)
    #gate_id: str

    def __post_init__(self):
        super().__post_init__()
        self.dc_channel = QdacChannel(
            id = f"{self.id}_dc", 
            qdac = self.qdac,
            channel = self.qdac_channel,
            unit = self.qdac_unit, 
            max_slew_rate=self.qdac_max_slew_rate,
        )

    def set_dc_V(self, dc_V: float):
        """Set a voltage on the wrapped param (channel.dc_constant_V)"""
        self.dc_channel.set_dc_V(dc_V)
    
    def get_dc_V(self) -> float:
        """Get the DC voltage on the wrapped param (channel.dc_constant_V)"""
        return self.dc_channel.get_dc_V()
    
    def to_dict(self, follow_references = False, include_defaults = False):
        d = super().to_dict(follow_references, include_defaults)
        d.pop('couplings', None)
        d.pop('qdac', None)
        d['dc_channel'] = self.dc_channel.get_dc_V()
        return d

    
@quam_dataclass
class QdacOpxReadout(InOutSingleChannel):
    qdac: object
    qdac_channel: int
    qdac_unit: str = 'V'
    dc_channel: QdacChannel = field(init = False)
    qdac_max_slew_rate: float = 1.0
    couplings: dict[str, float] = field(default_factory = dict, repr = False)

    def __post_init__(self):
        super().__post_init__()
        self.dc_channel = QdacChannel(
            id = f"{self.id}_dc", 
            qdac = self.qdac,
            channel = self.qdac_channel,
            unit = self.qdac_unit, 
            max_slew_rate=self.qdac_max_slew_rate,
        )

    def set_dc_V(self, dc_V: float):
        """Set a voltage on the wrapped param (channel.dc_constant_V)"""
        self.dc_channel.set_dc_V(dc_V)
    
    def get_dc_V(self) -> float:
        """Get the DC voltage on the wrapped param (channel.dc_constant_V)"""
        return self.dc_channel.get_dc_V()
    
    def to_dict(self, follow_references = False, include_defaults = False):
        d = super().to_dict(follow_references, include_defaults)
        d.pop('couplings', None)
        d.pop('qdac', None)
        #Don't store the qdac information, just what dc voltage was supplied for this 
        d['dc_channel'] = self.dc_channel.get_dc_V()
        return d

