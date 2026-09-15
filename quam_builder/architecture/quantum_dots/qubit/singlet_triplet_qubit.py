# Quantum component inheritance depth is framework-driven for QuAM dataclasses.
# pylint: disable=too-many-ancestors

from typing import Any, Dict, Tuple, Union, Literal, TYPE_CHECKING, Optional
from dataclasses import field
import numpy as np

from quam.components.quantum_components import Qubit
from quam.components import Channel
from quam.core import quam_dataclass
from quam.utils import string_reference

from quam_builder.architecture.quantum_dots.components.mixins import VoltageMacroMixin
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from qm.octave.octave_mixer_calibration import MixerCalibrationResults
from qm import logger
from qm import QuantumMachine
from qm.qua import wait, frame_rotation_2pi

from quam_builder.architecture.quantum_dots.components import QuantumDotPair

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["SingletTripletQubit"]


@quam_dataclass
class SingletTripletQubit(VoltageMacroMixin, Qubit):  # pylint: disable=too-many-ancestors
    # pylint: disable=no-member
    """
    An example QUAM component for a Singlet Triplet Qubit

    Attributes:
        id: returns the id of the associated QuantumDot
        quantum_dot_pair (QuantumDotPair): The QuantumDotPair associated with the Singlet Triplet Qubit.
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
        thermalization_time: Returns the Loss DiVincenzo Qubit thermalization time in ns.
        reset: Reset the qubit state with a specified reset type. Default is thermal (wait thermalization time).
        add_point: Adds a named voltage point to the associated VirtualGateSet. Can accept qubit names
        step_to_point: Steps to a pre-defined point in the internal points dict.
        ramp_to_point: Ramps to a pre-defined point in the internal points dict.
    """

    id: Union[str, int] = None
    grid_location: str = None

    quantum_dot_pair: QuantumDotPair

    delta_bz: float = None

    # Qubit Specific Features
    T1: float = None
    T2ramsey: float = None
    T2echo: float = None
    thermalization_time_factor: int = DEFAULTS.qubit.thermalization_time_factor

    gate_fidelity: Dict[str, Any] = field(default_factory=dict)
    points: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @property
    def physical_channel(self) -> Channel:
        """Returns the barrier physical channel."""
        return self.quantum_dot_pair.physical_channel

    @property
    def machine(self) -> "BaseQuamQD":
        return self.quantum_dot_pair.machine

    @property
    def thermalization_time(self):
        """The transmon thermalization time in ns."""
        if self.T1 is not None:
            return int(self.thermalization_time_factor * self.T1 * 1e9 / 4) * 4
        else:
            return int(self.thermalization_time_factor * DEFAULTS.qubit.fallback_t1 * 1e9 / 4) * 4

    @property
    def voltage_sequence(self):
        return self.quantum_dot_pair.voltage_sequence

    def _get_component_id_for_voltages(self) -> str:
        """Target the quantum_dot for voltage operations."""
        return self.quantum_dot_pair.id

    def reset(
        self,
        reset_type: Literal["thermal"] = "thermal",
    ):

        if reset_type == "thermal":
            self.reset_qubit_thermal()

    def reset_qubit_thermal(self):
        """
        Perform a thermal reset of the qubit.

        This function waits for a duration specified by the thermalization time
        to allow the qubit to return to its ground state through natural thermal
        relaxation.
        """
        self.wait(self.thermalization_time // 4)

    def wait(self, duration: int):
        """Wait for a given duration on all channels of the qubit.

        Args:
            duration (int): The duration to wait for in unit of clock cycles (4ns).
        """
        channel_names = [channel.name for channel in self.channels.values()]
        wait(duration, *channel_names)

    def idle(self, duration: int) -> None:
        wait(duration, self.physical_channel.name)
