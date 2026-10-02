from typing import List, Dict, Union, Any, TYPE_CHECKING
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
        self.jn_pair = self.jz_pair.get_reference()
        self.jz_pair = self.jn_pair.get_reference()

    @property
    def machine(self) -> "BaseQuamQD":
        return self.quantum_dot_pairs[0].machine

    @property
    def xy(self) -> None: 
        """For compatibility with existing code, this is set to None. build_base_quam must be updated."""
        return None

    @property
    def voltage_sequence(self):
        return self.quantum_dot_pairs[0].voltage_sequence

    @property
    def quantum_dots(self) -> List: 
        """Extract a list of the 3 QuantumDot objects that are associated with the ExchangeOnlyQubit."""
        return list({pair.quantum_dots for pair in [self.jn_pair, self.jz_pair]})

    @property
    def thermalization_time(self):
        """The transmon thermalization time in ns."""
        if self.T1 is not None:
            return int(self.thermalization_time_factor * self.T1 * 1e9 / 4) * 4
        else:
            return int(self.thermalization_time_factor * DEFAULTS.qubit.fallback_t1 * 1e9 / 4) * 4