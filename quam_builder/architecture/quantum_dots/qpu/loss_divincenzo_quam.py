from typing import Union, Optional
from pathlib import Path
from qm import QuantumMachine

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.components import XYDriveBase
from quam_builder.architecture.quantum_dots.qpu.base_qubit_quam import BaseSpinQubitQuam
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair

__all__ = ["LossDiVincenzoQuam"]


@quam_dataclass
class LossDiVincenzoQuam(BaseSpinQubitQuam):
    """
    A Quam to build on top of BaseQuamQD. BaseQuamQD to be used for calibrating the underlying Quantum Dots,
    whereas use LossDiVincenzoQuam to calibrate your Loss DiVincenzo qubits. It retains all the attributes and
    methods of BaseQuamQD, on top of the ones listed below:

    Attributes:
        b_field (float): The operating external magnetic field.

    Methods:
        calibrate_octave_ports: Calibrate the Octave ports for all the active qubits.
        initialize_qpu: Initialize the QPU with the specified settings.
        register_qubit: Creates an internal Qubit object out of the specified QuantumDot. Specify the qubit type in the input, default "loss_divincenzo"
        register_qubit_pair: Creates a QubitPair object internally, given a control qubit and a target qubit.
    """

    b_field: float = 0

    @classmethod
    def load(
        cls,
        filepath_or_dict: Optional[Union[str, Path, dict]] = None,
        validate_type: bool = True,
        fix_attrs: bool = True,
    ): 
        """Load the base class as a LossDiVincenzoQuam, adding b_field = 0"""
        instance = super().load(
            filepath_or_dict,
            validate_type,
            fix_attrs,
        )
        if not hasattr(instance, "b_field"):
            instance.b_field = 0
        return instance

    def register_qubit(
        self,
        quantum_dot_id: str,
        qubit_name: str,
        xy: XYDriveBase = None,
        readout_quantum_dot: str = None,
    ) -> None:
        """
        Instantiates a Loss-DiVincenzo qubit based on the associated quantum dot.
        """

        d = quantum_dot_id
        dot = self.quantum_dots[d]  # Assume a single quantum dot for a LD Qubit
        qubit = LDQubit(
            id=qubit_name,
            quantum_dot=dot.get_reference(),
            xy=xy,
            preferred_readout_quantum_dot=readout_quantum_dot,
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

        quantum_dot_pair = self.find_quantum_dot_pair(
            qubit_control.quantum_dot.id, qubit_target.quantum_dot.id
        )
        if quantum_dot_pair is None:
            raise ValueError(
                "QuantumDotPair for associated qubits not registered. Please register first"
            )

        qubit_pair = LDQubitPair(
            id=id,
            qubit_control=qubit_control.get_reference(),
            qubit_target=qubit_target.get_reference(),
            quantum_dot_pair=self.quantum_dot_pairs[quantum_dot_pair].get_reference(),
        )

        self.qubit_pairs[id] = qubit_pair

    def calibrate_octave_ports(self, QM: QuantumMachine) -> None:
        """Calibrate the Octave ports for all the active qubits.

        Args:
            QM (QuantumMachine): The running quantum machine.
        """
        from qm.octave.octave_mixer_calibration import NoCalibrationElements

        for qubit in self.qubits.values():
            try:
                qubit.calibrate_octave(QM)
            except NoCalibrationElements:
                print(f"No calibration elements found for {qubit.id}. Skipping calibration.")
