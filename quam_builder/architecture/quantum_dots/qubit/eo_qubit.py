from typing import List, Dict, Union, Any, TYPE_CHECKING
import numpy as np
from dataclasses import field

from quam.components import Qubit
from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.components.mixins import VoltageMacroMixin
from quam_builder.architecture.quantum_dots.components import ExchangeAxis
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["ExchangeOnlyQubit"]

@quam_dataclass
class ExchangeOnlyQubit(VoltageMacroMixin, Qubit): 
    """
    A QuamComponent representing the Exchange-Only qubit. 
    
    Attributes:
        id: returns the id of the ExchangeOnlyQubit
        quantum_dots (QuantumDot): A list of the 3 QuantumDot objects in this ExchangeOnlyQubit. 
        T1 (float): The qubit T1 in seconds. Default is None.
        T2ramsey (float): The qubit T2* in seconds.
        T2echo (float): The qubit T2 in seconds.
        thermalization_time_factor (int): Thermalization time in units of T1. Default is 5.
        gate_fidelity (Dict[str, Any]): Collection of single qubit gate fidelity metrics.
        points (Dict[str, Dict[str, float]]): A dictionary of instantiated macro points.

    Methods:
        go_to_voltages: To be used in a sequence.simultaneous block for simultaneous stepping/ramping to a particular voltage.
        step_to_voltages: Enters a dictionary to the VoltageSequence to step to the particular voltage.
        ramp_to_voltages: Enters a dictionary to the VoltageSequence to ramp to the particular voltage.
        calibrate_octave: Calibrates the Octave channels (xy and resonator) linked to this qubit.
        thermalization_time: Returns the Loss DiVincenzo Qubit thermalization time in ns.
        add_point: Adds a named voltage point to the associated VirtualGateSet. Can accept qubit names
        step_to_point: Steps to a pre-defined point in the internal points dict.
        ramp_to_point: Ramps to a pre-defined point in the internal points dict.
    """
    
    jn_pair: ExchangeAxis
    jz_pair: ExchangeAxis

    id: Union[str, int] = None
    grid_location: str = None

    # Qubit Specific Features
    T1: float = None
    T2ramsey: float = None
    T2echo: float = None
    thermalization_time_factor: int = DEFAULTS.qubit.thermalization_time_factor

    gate_fidelity: Dict[str, Any] = field(default_factory=dict)
    points: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def swap_axis_assignment(self) -> None: 
        """A convenience method to swap the axis assignments of the ExchangeOnlyQubit's ExchangeAxis."""
        jn_ref = self.jn_pair.get_reference()
        jz_ref = self.jz_pair.get_reference()

        self.jn_pair = jz_ref
        self.jz_pair = jn_ref
    
    @property
    def x_axis_name(self): 
        return f"{self.name}_x_axis"

    @property
    def z_axis_name(self): 
        return f"{self.name}_z_axis"

    def define_qubit_control_axes(
        self, 
        matrix: List[List[float]] | None = None
    ) -> None: 

        gate_set = self.voltage_sequence.gate_set

        # Validate that the exchange axes actually exists in layer 1
        layer_1_sources = gate_set.layers[1].source_gates
        if self.jn_pair.exchange_axis_name not in layer_1_sources or self.jz_pair.exchange_axis_name not in layer_1_sources: 
            raise ValueError(f"Exchange axes {self.jn_pair.exchange_axis_name} and {self.jz_pair.exchange_axis_name} undefined. Please construct them first.")

        source_gates = [self.x_axis_name, self.z_axis_name]
        target_gates = [self.jn_pair.exchange_axis_name, self.jz_pair.exchange_axis_name]

        if matrix is None: 
            matrix = [[np.sqrt(3)/2, 0], [- 0.5, 1]]

        if len(matrix) != 2: 
            raise ValueError(f"X and Z qubit control axes matrix does not satisfy len(matrix) == 2. len(matrix) == {len(matrix)}")
        
        if len(matrix[0]) != 2 or len(matrix[1]) != 2: 
            raise ValueError(f"X and Z qubit control axes matrix is not 2x2.")
        
        gate_set.add_to_layer(
            layer_id = "qubit_control_layer", 
            source_gates = source_gates, 
            target_gates = target_gates, 
            matrix = matrix
        )

    @property
    def machine(self) -> "BaseQuamQD":
        return self.jn_pair.machine

    @property
    def xy(self) -> None: 
        """For compatibility with existing code, this is set to None. build_base_quam must be updated."""
        return None

    @property
    def voltage_sequence(self):
        return self.jn_pair.voltage_sequence

    @property
    def quantum_dots(self) -> List:
        return list(
            set(self.jn_pair.quantum_dots)
            | set(self.jz_pair.quantum_dots)
        )

    @property
    def thermalization_time(self):
        """The transmon thermalization time in ns."""
        if self.T1 is not None:
            return int(self.thermalization_time_factor * self.T1 * 1e9 / 4) * 4
        else:
            return int(self.thermalization_time_factor * DEFAULTS.qubit.fallback_t1 * 1e9 / 4) * 4
