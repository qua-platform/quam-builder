from typing import List

from quam_builder.architecture.quantum_dots.components import QuantumDotPair
from quam.core import quam_dataclass

__all__ = ["ExchangeAxis"]

@quam_dataclass
class ExchangeAxis(QuantumDotPair): 

    @property
    def exchange_axis_name(self): 
        return f"{self.id}_exchange"

    def define_axes(
        self, 
        matrix: List[List[float]], 
    ) -> None: 
        """
        A function to add both the detuning axis to layer 2, as well as the exchange axis.
        
        This virtualization matrix must also include the detuning axis. 
        """

        pass

