from quam.components import QuantumComponent, pulses
from quam.components.channels import SingleChannel
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro


from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from quam_builder.tools.voltage_sequence import (
        VoltageSequence,
    )

from qm.qua import declare, assign, fixed

from quam_builder.tools.qua_tools import (
    VoltageLevelType,
    CLOCK_CYCLE_NS,
    MIN_PULSE_DURATION_NS,
    is_qua_type
)

DEFAULT_PULSE_NAME = "half_max_square"
BITSHIFT_FACTOR = 2

__all__ = ["GateSet", "VoltageTuningPoint"]


@quam_dataclass
class VoltageTuningPoint(QuamMacro):
    """
    Defines a specific set of DC voltages for a group of channels,
    along with a default duration to hold these voltages.

    This class is typically not instantiated directly by users, but is created
    automatically by the GateSet.add_point() method. Once created, instances
    are stored in the GateSet's macros dictionary and can be referenced by
    name in voltage sequences.

    Attributes:
        voltages: Dictionary mapping channel names to their target voltages.
        duration: Default duration in nanoseconds to hold these voltages.
            - Duration must be in integer multiple of 4ns
            - Minimum duration is 16ns
    """

    voltages: Dict[str, float]
    duration: int

    def apply(self, *args, **kwargs):
        raise NotImplementedError("Not yet implemented")


@quam_dataclass
class GateSet(QuantumComponent):
    """
    Represents a set of gate channels used for voltage sequencing in quantum dot
    experiments.

    A GateSet manages a collection of channels (instances of `SingleChannel`,
    including subclasses like `VoltageGate`) and provides
    functionality to:
    - Define named voltage tuning points (macros) that can be reused across
      sequences
    - Resolve voltages for all channels with default fallbacks
    - Create voltage sequences with proper channel configuration

    The GateSet acts as a logical grouping of related channels (e.g., gates
    controlling a specific quantum dot) and enables high-level voltage control
    operations. This class also serves as the base for VirtualGateSet, which
    enables linear combinations of physical gates.

    Attributes:
        channels: Dictionary mapping channel names to `SingleChannel` instances.
            This may include `VoltageGate` objects, which are specialized
            `SingleChannel`s that model voltage gates with optional attenuation
            and DC offset handling.

    Example:
        >>> from quam.components.channels import SingleChannel
        >>> # Create channels for a quantum dot
        >>> plunger_ch = SingleChannel("plunger", ...)
        >>> barrier_ch = SingleChannel("barrier", ...)
        >>>
        >>> # Create gate set
        >>> dot_gates = GateSet(
        ...     id="dot1",
        ...     channels={"plunger": plunger_ch, "barrier": barrier_ch}
        ... )
        >>>
        >>> # Add voltage tuning points
        >>> dot_gates.add_point("load", {"plunger": 0.5, "barrier": -0.2}, 1000)
        >>> dot_gates.add_point("measure", {"plunger": 0.3, "barrier": 0.1}, 500)
        >>>
        >>> # Create and use voltage sequence
        >>> with qua.program() as prog:
        ...     seq = dot_gates.new_sequence()
        ...     seq.step_to_point("load")  # Uses the predefined voltage point
    """

    channels: Dict[str, SingleChannel]
    adjust_for_attenuation: bool = False

    def __post_init__(self): 
        for ch in self.channels.values():
            if hasattr(ch.opx_output, "output_mode"):
                if ch.opx_output.output_mode == "amplified":
                    ch.operations[DEFAULT_PULSE_NAME] = pulses.SquarePulse(
                        amplitude=1.25, length=MIN_PULSE_DURATION_NS
                    )
                else:
                    ch.operations[DEFAULT_PULSE_NAME] = pulses.SquarePulse(
                        amplitude=0.25, length=MIN_PULSE_DURATION_NS
                    )
            else:
                ch.operations[DEFAULT_PULSE_NAME] = pulses.SquarePulse(
                    amplitude=0.25, length=MIN_PULSE_DURATION_NS
                )

    @property
    def name(self) -> str:
        return self.id

    def resolve_voltages(
        self, voltages: Dict[str, VoltageLevelType], allow_extra_entries: bool = False
    ) -> Dict[str, VoltageLevelType]:
        """
        Resolves voltages for all channels in the GateSet.

        Adds any channels in the GateSet that are not in the provided voltages dict
        with a default voltage of 0.0. Optionally validates that all provided voltage
        entries correspond to valid channels in this GateSet.

        This method is particularly useful when you want to specify voltages for only
        a subset of channels while ensuring all other channels have defined values,
        which is essential for voltage sequence operations that need complete channel
        state information.

        Args:
            voltages: Dictionary mapping channel names to their voltages.
            allow_extra_entries: If False, raises ValueError if voltages contains
                channel names not present in this GateSet's channels. If True,
                extra entries are ignored.

        Returns:
            Dict[str, VoltageLevelType]: Dictionary containing voltages for all
            channels in this GateSet. Missing channels are assigned 0.0 voltage.

        Raises:
            ValueError: If allow_extra_entries is False and voltages contains
                channel names not present in this GateSet.

        Example:
            >>> # Assume gate_set has channels: {"P1": ch1, "P2": ch2, "B1": ch3}
            >>> partial_voltages = {"P1": 0.3, "B1": -0.1}
            >>> complete_voltages = gate_set.resolve_voltages(partial_voltages)
            >>> print(complete_voltages)
            {"P1": 0.3, "P2": 0.0, "B1": -0.1}

            >>> # With invalid channel name (raises error by default)
            >>> try:
            ...     gate_set.resolve_voltages({"P1": 0.3, "invalid": 0.1})
            ... except ValueError as e:
            ...     print(f"Error: {e}")
            Error: Channel 'invalid' passed to GateSet.resolve_voltages for GateSet 'gate_set_name' is not part of the GateSet.channels.
        """
        resolved_voltages = {}

        if not allow_extra_entries:
            for ch_name in voltages:
                if ch_name not in self.channels:
                    raise ValueError(
                        f"Channel '{ch_name}' passed to GateSet.resolve_voltages for "
                        f"GateSet '{self.name}' is not part of the GateSet.channels."
                    )

        # Add any channels in the GateSet that are not in the voltages dict
        for ch_name in self.channels:
            resolved_voltages[ch_name] = voltages.get(ch_name, 0.0)

        return resolved_voltages

    @property
    def valid_channel_names(self) -> list[str]:
        return list(self.channels.keys())

    def add_point(self, name: str, voltages: Dict[str, float], duration: int):
        """
        Adds a named voltage tuning point (macro) to this GateSet.

        Args:
            name: The name for this tuning point.
            voltages: A dictionary mapping channel names (keys in self.channels)
                to their target DC voltage (float) for this point.
                - Values are to be entered in units of V
            duration: The default duration (ns) to hold these voltages.
                - The duration must be an integer multiple of 4ns
                - Minimum duration is 16ns

        Example:
            >>> gate_set = GateSet(channels={"gate1": ch1, "gate2": ch2})
            >>> # Create a macro that can be used in voltage sequences
            >>> gate_set.add_point("load", {"gate1": 0.5, "gate2": -0.2}, duration=1000)
        """
        invalid_channel_names = set(voltages) - set(self.valid_channel_names)
        if invalid_channel_names:
            raise ValueError(
                f"Channel(s) '{invalid_channel_names}' specified in voltages for point "
                f"'{name}' are not part of this GateSet."
            )

        # Ensure macros dict exists if not handled by Pydantic model of QuantumComponent
        if not hasattr(self, "macros") or self.macros is None:
            self.macros: Dict[str, QuamMacro] = {}

        self.macros[name] = VoltageTuningPoint(voltages=voltages, duration=duration)

    def new_sequence(self, track_integrated_voltage: bool = False) -> "VoltageSequence":
        """
        Creates a new VoltageSequence instance associated with this GateSet.

        Automatically configures DEFAULT_PULSE_NAME operations for all channels based on
        their output mode (amplified vs direct) before creating the sequence.

        Args:
            track_integrated_voltage: Whether to track integrated voltage.
                If False, the sequence will not track integrated voltage, and
                apply_compensation_pulse will not be available.

        Returns:
            VoltageSequence: A new voltage sequence instance configured with this GateSet
                and the specified integrated voltage tracking setting.
        """
        # Avoid circular import
        from quam_builder.tools.voltage_sequence import (
            VoltageSequence,
        )

        for ch in self.channels.values():
            if hasattr(ch.opx_output, "output_mode"):
                if ch.opx_output.output_mode == "amplified":
                    ch.operations[DEFAULT_PULSE_NAME] = pulses.SquarePulse(
                        amplitude=1.25, length=MIN_PULSE_DURATION_NS
                    )
                else:
                    ch.operations[DEFAULT_PULSE_NAME] = pulses.SquarePulse(
                        amplitude=0.25, length=MIN_PULSE_DURATION_NS
                    )
            else:
                ch.operations[DEFAULT_PULSE_NAME] = pulses.SquarePulse(
                    amplitude=0.25, length=MIN_PULSE_DURATION_NS
                )
        return VoltageSequence(self, track_integrated_voltage)
