from typing import Dict, Union, Optional, List
from pathlib import Path
from dataclasses import field
from abc import ABC, abstractmethod

from qm.qua.type_hints import QuaVariable, StreamType
from qm.qua import declare, declare_output_stream, fixed
from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qubit import AnySpinQubit
from quam_builder.architecture.quantum_dots.qubit_pair import AnySpinQubitPair
from quam_builder.architecture.quantum_dots.components import (
    QuantumDot, 
    BarrierGate, 
    QuantumDotPair, 
    SensorDot, 
    VoltageGate,
)

@quam_dataclass 
class BaseSpinQubitQuam(BaseQuamQD, ABC): 
    """
    Base class for a spin qubit-based Quam. 

    Attributes: 
        qubits (Dict[str, AnySpinQubit]) : A dictionary containing any spin qubit type. 
        qubit_pairs (Dict[str, AnySpinQubitPair]) : A dictionary containing any spin qubit pair type. 
        active_qubit_names (List[str]): A list of active qubit names.
        active_qubit_pair_names (List[str]): A list of active qubit pair names.
    """

    qubits: Dict[str, AnySpinQubit] = field(default_factory = None)
    qubit_pairs: Dict[str, AnySpinQubitPair] = field(default_factory = None)

    active_qubit_names: List[str] = field(default_factory=list)
    active_qubit_pair_names: List[str] = field(default_factory=list)

    @classmethod
    def load(
        cls,
        filepath_or_dict: Optional[Union[str, Path, dict]] = None,
        validate_type: bool = True,
        fix_attrs: bool = True,
    ):
        """Load machine, upgrade to ExchangeOnly schema, and wire runtime macro defaults."""
        instance = super().load(
            filepath_or_dict=filepath_or_dict,
            validate_type=validate_type,
            fix_attrs=fix_attrs,
        )

        if type(instance) is BaseQuamQD:  # pylint: disable=unidiomatic-typecheck
            instance.__class__ = cls

        # We only create empty fields here if it does not already have it. This is in-case the instance is a BaseQuamQD.
        if not hasattr(instance, "qubits"):
            instance.qubits = {}
        if not hasattr(instance, "qubit_pairs"):
            instance.qubit_pairs = {}
        if not hasattr(instance, "active_qubit_names"):
            instance.active_qubit_names = []
        if not hasattr(instance, "active_qubit_pair_names"):
            instance.active_qubit_pair_names = []

        from quam_builder.architecture.quantum_dots.macro_engine import (
            wire_machine_macros,
        )

        wire_machine_macros(instance, fill_only=True)

        return instance

    @property
    def active_qubits(self) -> List[AnySpinQubit]:
        """Return the list of active qubits"""
        return [self.qubits[q] for q in self.active_qubit_names]

    @property
    def active_qubit_pairs(self) -> List[AnySpinQubitPair]:
        """Return the list of active qubit pairs"""
        return [self.qubit_pairs[q] for q in self.active_qubit_pair_names]

    @abstractmethod
    def register_qubit(self, qubit_name: str, **kwargs): 
        """
        An abstract method to register a Qubit in this QuamRoot object. 
        The input arguments must be expanded to include any necessary arguments, based on the Qubit type. 
        """
        pass

    @abstractmethod
    def register_qubit_pair(self, qubit_pair_name: str, **kwargs): 
        """
        An abstract method to register a QubitPair in this QuamRoot object. 
        The input arguments must be expanded to include any necessary arguments, based on the QubitPair type. 
        """
        pass

    def get_component(self, name: str) -> Union[VoltageGate, AnySpinQubit, QuantumDot, SensorDot, BarrierGate, QuantumDotPair]:
        """
        Retrieve a component object by name from qubits, qubit_pairs, quantum_dots, quantum_dot_pairs, sensor_dots, or barrier_gates

        Args:
            name: The name of the object
        """
        collections = [
            self.physical_channels, 
            self.qubits,
            self.quantum_dots,
            self.sensor_dots,
            self.barrier_gates,
            self.quantum_dot_pairs,
            self.qubit_pairs,
        ]
        for collection in collections:
            if name in collection:
                return collection[name]

        raise ValueError(f"Element {name} not found in Quam")

    def declare_qua_variables(
        self,
        num_IQ_pairs: Optional[int] = None,
    ) -> tuple[
        list[QuaVariable],
        list[StreamType],
        list[QuaVariable],
        list[StreamType],
        QuaVariable,
        StreamType,
    ]:
        """Macro to declare the necessary QUA variables for all qubits.

        Args:
            num_IQ_pairs (Optional[int]): Number of IQ pairs (I and Q variables) to declare.
                If None, it defaults to the number of qubits in `self.qubits`.

        Returns:
            tuple: A tuple containing lists of QUA variables and streams.
        """
        if num_IQ_pairs is None:
            num_IQ_pairs = len(self.qubits)

        n = declare(int)
        n_st = declare_output_stream()
        I = [declare(fixed) for _ in range(num_IQ_pairs)]
        Q = [declare(fixed) for _ in range(num_IQ_pairs)]
        I_st = [declare_output_stream() for _ in range(num_IQ_pairs)]
        Q_st = [declare_output_stream() for _ in range(num_IQ_pairs)]
        return I, I_st, Q, Q_st, n, n_st