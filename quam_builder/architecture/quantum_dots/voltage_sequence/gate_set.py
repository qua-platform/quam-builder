from quam.components import QuantumComponent
from quam.components.channels import SingleChannel
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro


from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.voltage_sequence.voltage_sequence import (
        VoltageSequence,
    )

from quam_builder.architecture.quantum_dots.utils import VoltageLevelType

__all__ = ["GateSet", "VoltageTuningPoint"]


@quam_dataclass
class VoltageTuningPoint(QuamMacro):
    """
    Defines a specific set of DC voltage levels for a group of channels,
    along with a default duration to hold these voltages.
    """

    voltages: Dict[str, float]  # Maps channel name to its target voltage
    duration: int  # Default duration in ns

    def apply(self, *args, **kwargs):
        # TODO: Implement apply method
        pass


@quam_dataclass
class GateSet(QuantumComponent):
    """
    Represents a set of gate channels used for voltage sequencing.
    Allows defining named voltage tuning points (macros) for this set.
    """

    channels: Dict[str, SingleChannel]

    @property
    def name(self) -> str:
        return self.id

    def resolve_voltages(
        self, voltages: Dict[str, VoltageLevelType], allow_extra_entries: bool = False
    ) -> Dict[str, VoltageLevelType]:
        """
        Adds any channels in the GateSet that are not in the target_levels_dict
        to the target_levels_dict with a default voltage of 0.0.
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

    def add_point(self, name: str, voltages: Dict[str, float], duration: int):
        """
        Adds a named voltage tuning point (macro) to this GateSet.

        Args:
            name: The name for this tuning point.
            voltages: A dictionary mapping channel names (keys in self.channels)
                to their target DC voltage (float) for this point.
            duration: The default duration (ns) to hold these voltages.
        """
        for ch_name in voltages.keys():
            if ch_name not in self.channels:
                raise ValueError(
                    f"Channel '{ch_name}' specified in voltages for point '{name}' "
                    f"is not part of this GateSet."
                )
        # Ensure macros dict exists if not handled by Pydantic model of QuantumComponent
        if not hasattr(self, "macros") or self.macros is None:
            self.macros: Dict[str, QuamMacro] = {}

        self.macros[name] = VoltageTuningPoint(voltages=voltages, duration=duration)

    def new_sequence(self) -> "VoltageSequence":
        """
        Creates a new VoltageSequence instance associated with this GateSet.
        """
        from quam_builder.architecture.quantum_dots.voltage_sequence import (
            VoltageSequence,
        )

        return VoltageSequence(self)
