from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.qpu.base_qubit_quam import BaseSpinQubitQuam
from quam_builder.architecture.quantum_dots.qubit import ExchangeOnlyQubit
from quam_builder.architecture.quantum_dots.qubit_pair import ExchangeOnlyQubitPair

__all__ = ["ExchangeOnlyQuam"]

@quam_dataclass
class ExchangeOnlyQuam(BaseSpinQubitQuam): 
    """
    An Exchange-Only add-on for the BaseQuamQD object. 

    Attributes: 
        N/A
    Methods:  
        register_qubit: Register an ExchangeOnlyQubit instance in self.qubits.
        register_qubit_pair: Register an ExchangeOnlyQubitPair instance in self.qubit_pairs.
    """

    def register_qubit(
        self,
        qubit_name: str,
        jn_pair: str,
        jz_pair: str,
    ) -> None:
        """
        Instantiates a Loss-DiVincenzo qubit based on the associated quantum dot.
        """
        jn_pair = self.quantum_dot_pairs[jn_pair].get_reference()
        jz_pair = self.quantum_dot_pairs[jz_pair].get_reference()

        qubit = ExchangeOnlyQubit(
            id=qubit_name,
            jn_pair = jn_pair,
            jz_pair = jz_pair
        )

        self.qubits[qubit_name] = qubit

    def register_qubit_pair(
        self,
        qubit_control_name: str,
        qubit_target_name: str,
        barrier_gate_name: str,
        id: str = None,
    ) -> None:
        for name in [qubit_control_name, qubit_target_name]:
            if name not in self.qubits:
                raise ValueError(f"Qubit {name} not registered. Please register first")
        qubit_control, qubit_target = (
            self.qubits[qubit_control_name],
            self.qubits[qubit_target_name],
        )

        if barrier_gate_name not in self.barrier_gates: 
            raise ValueError(f"Barrier gate {barrier_gate_name} is not in this Quam.")

        if id is None:
            id = f"{qubit_control_name}_{qubit_target_name}"

        qubit_pair = ExchangeOnlyQubitPair(
            id=id,
            qubit_control=qubit_control.get_reference(),
            qubit_target=qubit_target.get_reference(),
            barrier_gate = self.barrier_gates[barrier_gate_name].get_reference(), 
        )

        self.qubit_pairs[id] = qubit_pair
