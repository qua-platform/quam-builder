from dataclasses import field

from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.voltage_sequence.gate_set import GateSet
from quam_builder.architecture.quantum_dots.utils import VoltageLevelType


@quam_dataclass
class VirtualGateSet(GateSet):
    """
    A set of virtual gates that can be used to create a virtual gate layer.

    Attributes:
        layers: A list of `VirtualisationLayer` objects, applied sequentially.
    """

    layers: List[VirtualisationLayer] = field(default_factory=list)
    """A list of `VirtualisationLayer` objects, applied sequentially."""

    def add_layer(
        self,
        source_gates: List[str],
        target_gates: List[str],
        matrix: List[List[float]],
    ) -> VirtualisationLayer:
        """
        Adds a new virtualisation layer to the VirtualGateSet.

        Args:
            source_gates: A list of names for the virtual gates in this layer.
            target_gates: A list of names for the physical (or underlying virtual)
                          gates that this layer maps to.
            matrix: The virtualisation matrix defining the transformation.

        Returns:
            The created VirtualisationLayer object.
        """
        # TODO Ensure that source_gates and target_gates are not yet used

        virtualisation_layer = VirtualisationLayer(
            source_gates=source_gates, target_gates=target_gates, matrix=matrix
        )
        self.layers.append(virtualisation_layer)
        return virtualisation_layer

    def resolve_voltages(
        self, voltages: Dict[str, VoltageLevelType], allow_extra_entries: bool = False
    ) -> Dict[str, VoltageLevelType]:
        """
        Resolves all virtual gate voltages to physical gate voltages by applying
        all virtualisation layers in reverse order.

        Args:
            voltages: A dictionary mapping gate names (virtual or physical) to
                      voltage levels.
            allow_extra_entries: If True, gates in `voltages` that are not
                part of this VirtualGateSet (neither physical nor virtual)
                will be ignored. If False, a ValueError will be raised.

        Returns:
            A dictionary mapping physical gate names to their fully resolved
            voltage levels.
        """
        # Ensure that all channels in voltages are registered in the VirtualGateSet
        if not allow_extra_entries:
            virtual_channels = set(
                ch for layer in self.layers for ch in layer.source_gates
            )
            all_channels = set(list(self.channels) + list(virtual_channels))
            extra_channels = set(voltages) - all_channels
            if extra_channels:
                raise ValueError(
                    f"Channels {extra_channels} in voltages that are not part of the "
                    f"VirtualGateSet.channels: {self.channels}"
                )

        resolved_voltages = voltages.copy()

        for layer in reversed(self.layers):
            resolved_voltages = layer.resolve_voltages(
                resolved_voltages, allow_extra_entries=True
            )

        resolved_voltages = super().resolve_voltages(
            resolved_voltages, allow_extra_entries=True
        )
        return resolved_voltages
