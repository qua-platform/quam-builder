from qualang_tools.wirer.connectivity.channel_spec import ChannelSpec
from qualang_tools.wirer.connectivity.types import QubitsType, QubitPairsType
from qualang_tools.wirer.connectivity.wiring_spec import WiringFrequency, WiringIOType, WiringLineType
from qualang_tools.wirer.connectivity.connectivity_base import ConnectivityBase


class ConnectivityQuantumDotQubits(ConnectivityBase):
    """
    Represents the high-level wiring configuration for a transmon-based QPU setup.

    This class defines and stores placeholders for quantum elements (e.g., qubits and resonators)
    and specifies the wiring requirements for each of their control and readout lines. It enables
    the configuration of line types (e.g., drive, flux, resonator), their I/O roles, and associated
    frequency domains (RF or DC), as well as constraints for channel allocation.

    The API is designed to model a variety of qubit configurations, such as fixed-frequency and
    flux-tunable transmons, along with pairwise coupling mechanisms like cross-resonance and ZZ drive.
    """
    def add_ldv_qubits(self, qubits: QubitsType):
        self.add_qubit_gate_voltage_lines(qubits)
        self.add_resonator_line(qubits)
        self.add_qubit_drive_lines(qubits)

    def add_resonator_line(self, qubits: QubitsType, triggered: bool = False, constraints: ChannelSpec = None):
        """
        Adds a specification (placeholder) for a resonator line for the specified qubits.

        This method configures a resonator line specification (placeholder) that can handle both input and output,
        typically for reading out the state of qubits. It also allows optional triggering and constraints on
        which channel configurations can be allocated for this line.

        No channels are allocated at this stage.

        Args:
            qubits (QubitsType): The qubits to associate with the resonator line.
            triggered (bool, optional): Whether the line is triggered. Defaults to False.
            constraints (ChannelSpec, optional): Constraints on the channel, if any. Defaults to None.

        Returns:
            A wiring specification (placeholder) for the resonator line.
        """
        elements = self._make_qubit_elements(qubits)
        return self.add_wiring_spec(
            WiringFrequency.RF,
            WiringIOType.INPUT_AND_OUTPUT,
            WiringLineType.RESONATOR,
            triggered,
            constraints,
            elements,
            shared_line=True,
        )

    def add_qubit_drive_lines(self, qubits: QubitsType, triggered: bool = False, constraints: ChannelSpec = None):
        """
        Adds specifications (placeholders) for drive lines for the specified qubits.

        This method configures the qubit drive line specifications (placeholders), which are typically used to apply
        control signals to qubits. It allows optional triggering and constraints on which channel configurations
        can be allocated for this line.

        No channels are allocated at this stage.


        Args:
            qubits (QubitsType): The qubits to configure the drive lines for.
            triggered (bool, optional): Whether the line is triggered. Defaults to False.
            constraints (ChannelSpec, optional): Constraints on the channel, if any. Defaults to None.

        Returns:
            A wiring specification (placeholder) for the qubit drive lines.
        """
        elements = self._make_qubit_elements(qubits)
        return self.add_wiring_spec(
            WiringFrequency.RF, WiringIOType.OUTPUT, WiringLineType.DRIVE, triggered, constraints, elements
        )

    def add_qubit_gate_voltage_lines(self, qubits: QubitsType, triggered: bool = False, constraints: ChannelSpec = None):
        """
        Adds specifications (placeholders) for gate voltage bias lines for the specified qubits.

        This method configures gate voltage bias line specifications (placeholders), typically used for DC control, to tune
        the qubits' frequency. One can also specify constraints on which channel configurations can be allocated
        for this line.

        No channels are allocated at this stage.

        Args:
            qubits (QubitsType): The qubits to configure the flux bias lines for.
            triggered (bool, optional): Whether the line is triggered. Defaults to False.
            constraints (ChannelSpec, optional): Constraints on the channel, if any. Defaults to None.

        Returns:
            A wiring specification (placeholder) for the qubit flux bias lines.
        """
        elements = self._make_qubit_elements(qubits)
        return self.add_wiring_spec(
            WiringFrequency.DC, WiringIOType.OUTPUT, WiringLineType.FLUX, triggered, constraints, elements
        )