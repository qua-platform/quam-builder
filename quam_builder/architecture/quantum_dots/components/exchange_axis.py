from typing import List

from .quantum_dot_pair import QuantumDotPair
from quam.core import quam_dataclass

__all__ = ["ExchangeAxis"]

@quam_dataclass
class ExchangeAxis(QuantumDotPair): 
    """
    A Quam Component building on the QuantumDotPair. The QuantumDotPair can be up-graded to an ExchangeAxis
    in the case of use with an ExchangeOnlyQubit. 

    Attrs: 
        exchange_axis_name: A read-only property that defines the name of the exchange axis in the VirtualizationLayer. 
    
    Methods: 
        add_exchange_axis: Expand the second VirtualizationLayer to include the exchange axis, mapped as identity to the 
            barrier gate. This allows further virtualization of the ExchangeAxis to the plungers, independently of the 
            virtual barrier gate. 
    """

    @property
    def exchange_axis_name(self): 
        return f"{self.id}_exchange"

    def add_exchange_axis(
        self, 
        matrix: List[List[float]] = [[1, -1, 0],[0, 0, 1]], 
    ) -> None: 
        """
        A function to add the exchange axis to VirtualizationLayer 2.
        This virtualization matrix must also include the detuning axis.
        """
        if self.barrier_gate is None:
            raise ValueError(f"{self.id} has no barrier gate")

        source_gates = [self.id, self.exchange_axis_name]
        target_gates = [qd.id for qd in self.quantum_dots]
        target_gates.append(self.barrier_gate.id)

        if len(matrix) != len(source_gates):
            raise ValueError(
                f"Matrix must have {len(source_gates)} rows. Received {len(matrix)}"
            )
        if any(len(row) != len(target_gates) for row in matrix):
            raise ValueError(
                f"Matrix must have {len(target_gates)} columns. "
                f"Received {[len(row) for row in matrix]}"
            )

        self.gate_set.add_to_layer(
            layer_id="quantum_dot_pair_detuning_matrix",
            target_gates=target_gates,
            source_gates=source_gates,
            matrix=matrix,
        )

