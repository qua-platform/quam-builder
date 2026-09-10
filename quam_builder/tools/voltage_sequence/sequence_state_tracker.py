"""Sequence state tracking: ChannelState adapter plus KeepLevels."""

from typing import Dict

from quam_builder.architecture.quantum_dots.components.gate_set import GateSet
from quam_builder.architecture.quantum_dots.components.virtual_gate_set import (
    VirtualGateSet,
)
from quam_builder.tools.qua_tools import VoltageLevelType
from quam_builder.tools.voltage_sequence.channel_state import (
    VOLTAGE_FRAC_BITS,
    VOLTAGE_SCALE,
    ChannelState,
)

__all__ = [
    "SequenceStateTracker",
    "KeepLevels",
    "INTEGRATED_VOLTAGE_BITSHIFT",
    "INTEGRATED_VOLTAGE_SCALING_FACTOR",
]

INTEGRATED_VOLTAGE_BITSHIFT = VOLTAGE_FRAC_BITS
INTEGRATED_VOLTAGE_SCALING_FACTOR = VOLTAGE_SCALE

# Drop-in name used by VoltageSequence and existing tests.
SequenceStateTracker = ChannelState


class KeepLevels:
    """
    Keep track of physical/virtual gate levels throughout a VoltageSequence
    Removes the need to supply voltage points for gates that are already at their desired non-zero level.
    example:
    seq.step_to_voltages(voltages={"ch1": 0.2}, duration=100)
    seq.step_to_voltages(voltages={"ch2": 0.1}, duration=100) #ch1 will be held at 0.2 here
    seq.step_to_voltages(voltages={"ch1": 0.3}, duration=100)
    """

    def __init__(self, gate_set: GateSet | VirtualGateSet):
        self._keep_levels_dict = {}
        for channel in gate_set.valid_channel_names:
            self._keep_levels_dict[channel] = SequenceStateTracker(
                channel, track_integrated_voltage=False
            )

    def update_voltage_dict_with_current(self, voltages_dict: Dict[str, VoltageLevelType]):
        """
        adds points that are not supplied to the voltages_dict
        """
        self.update_tracking(voltages_dict=voltages_dict)

        return {name: tracker.current_level for name, tracker in self._keep_levels_dict.items()}

    def update_tracking(self, voltages_dict: Dict[str, VoltageLevelType]):
        """
        updates the internal state for newly supplied points
        """
        for name, level in voltages_dict.items():
            self._keep_levels_dict[name].current_level = level
