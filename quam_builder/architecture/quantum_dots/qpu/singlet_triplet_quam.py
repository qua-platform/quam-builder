from typing import List, Dict, Union, Optional
from dataclasses import field
from pathlib import Path
from qm import QuantumMachine
from qm.qua.type_hints import QuaVariable, StreamType
from qm.qua import declare, fixed, declare_stream

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.components import (
    QuantumDot,
    SensorDot,
    BarrierGate,
    XYDriveBase,
)
from quam_builder.architecture.quantum_dots.qpu.base_quam_qd import BaseQuamQD
from quam_builder.architecture.quantum_dots.qubit import AnySpinQubit, SingletTripletQubit
from quam_builder.architecture.quantum_dots.qubit_pair import (
    AnySpinQubitPair,
    SingletTripletQubitPair,
)


__all__ = ["SingletTripletQuam"]


@quam_dataclass
class SingletTripletQuam(BaseQuamQD):
    """
    A Quam to build on top of BaseQuamQD. BaseQuamQD to be used for calibrating the underlying Quantum Dots,
    whereas use SingletTripletQuam to calibrate your Singlet Triplet qubits. It retains all the attributes and
    methods of BaseQuamQD, on top of the ones listed below:

    Attributes:
        qubits (Dict[str, AnySpinQubit]): A dictionary of the registered spin qubits.
        qubit_pairs (Dict[str, AnySpinQubitPair]): A dictionary of the registered spin qubit pairs.
        b_field (float): The operating external magnetic field.
        active_qubit_names (List[str]): A list of active qubit names.
        active_qubit_pair_names (List[str]): A list of active qubit pair names.

    Methods:
        calibrate_octave_ports: Calibrate the Octave ports for all the active qubits.
        active_qubits: Return the list of active qubits.
        active_qubit_pairs: Return the list of active qubit pairs.
        declare_qua_variables: Macro to declare the necessary QUA variables for all qubits.
        initialize_qpu: Initialize the QPU with the specified settings.
        register_qubit: Creates an internal Qubit object out of the specified QuantumDot.
        register_qubit_pair: Creates a QubitPair object internally, given a control qubit and a target qubit.
    """

    b_field: float = 0

    qubits: Dict[str, AnySpinQubit] = field(default_factory=dict)
    qubit_pairs: Dict[str, AnySpinQubitPair] = field(default_factory=dict)

    active_qubit_names: List[str] = field(default_factory=list)
    active_qubit_pair_names: List[str] = field(default_factory=list)

    @classmethod
    def load(
        cls,
        filepath_or_dict: Optional[Union[str, Path, dict]] = None,
        validate_type: bool = True,
        fix_attrs: bool = True,
    ):
        """Load machine, upgrade to LD schema, and wire runtime macro defaults."""
        instance = super().load(
            filepath_or_dict=filepath_or_dict,
            validate_type=validate_type,
            fix_attrs=fix_attrs,
        )

        if type(instance) is BaseQuamQD:  # pylint: disable=unidiomatic-typecheck
            instance.__class__ = cls

        # We only create empty fields here if it does not already have it. This is in-case the instance is a BaseQuamQD.
        if not hasattr(instance, "b_field"):
            instance.b_field = 0
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

    def get_component(self, name: str) -> Union[AnySpinQubit, QuantumDot, SensorDot, BarrierGate]:
        """
        Retrieve a component object by name from qubits, qubit_pairs, quantum_dots, quantum_dot_pairs, sensor_dots, or barrier_gates

        Args:
            name: The name of the object
        """
        collections = [
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

    def register_qubit(
        self,
        quantum_dot_pair_id: str,
        qubit_name: str,
    ) -> None:
        """
        Instantiates a Loss-DiVincenzo qubit based on the associated quantum dot.
        """
        dot_pair = quantum_dot_pair_id
        dot = self.quantum_dot_pairs[dot_pair]  # Assume a single quantum dot for a LD Qubit
        qubit = SingletTripletQubit(
            id=qubit_name,
            quantum_dot_pair=dot.get_reference(),
        )
        self.qubits[qubit_name] = qubit

    def register_qubit_pair(
        self,
        qubit_control_name: str,
        qubit_target_name: str,
        id: str = None,
    ) -> None:

        for name in [qubit_control_name, qubit_target_name]:
            if name not in self.qubits:
                raise ValueError(f"Qubit {name} not registered. Please register first")
        qubit_control, qubit_target = (
            self.qubits[qubit_control_name],
            self.qubits[qubit_target_name],
        )

        if id is None:
            id = f"{qubit_control_name}_{qubit_target_name}"

        qubit_pair = SingletTripletQubitPair(
            id=id,
            qubit_control=qubit_control.get_reference(),
            qubit_target=qubit_target.get_reference(),
        )

        self.qubit_pairs[id] = qubit_pair

    @property
    def active_qubits(self) -> List[AnySpinQubit]:
        """Return the list of active qubits"""
        return [self.qubits[q] for q in self.active_qubit_names]

    @property
    def active_qubit_pairs(self) -> List[AnySpinQubitPair]:
        """Return the list of active qubit pairs"""
        return [self.qubit_pairs[q] for q in self.active_qubit_pair_names]

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
        n_st = declare_stream()
        I = [declare(fixed) for _ in range(num_IQ_pairs)]
        Q = [declare(fixed) for _ in range(num_IQ_pairs)]
        I_st = [declare_stream() for _ in range(num_IQ_pairs)]
        Q_st = [declare_stream() for _ in range(num_IQ_pairs)]
        return I, I_st, Q, Q_st, n, n_st

    def initialize_qpu(self, **kwargs):
        """Initialize the QPU with the specified settings."""
        pass
