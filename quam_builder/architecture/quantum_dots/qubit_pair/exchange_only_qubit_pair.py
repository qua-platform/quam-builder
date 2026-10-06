from typing import List, Optional
from dataclasses import field

from quam.components import QubitPair, Qubit
from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.components.mixins import VoltageMacroMixin
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["ExchangeOnlyQubitPair"]

@quam_dataclass
class ExchangeOnlyQubitPair(VoltageMacroMixin, QubitPair): 
    
    barrier_gate: Optional[VoltageMacroMixin] = None

    @property
    def machine(self) -> "BaseQuamQD":
        return self.qubits[0].machine

    @property
    def voltage_sequence(self):
        return self.qubits[0].voltage_sequence
