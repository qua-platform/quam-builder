from dataclasses import field
from typing import List, Dict

from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.voltage_sequence.gate_set import GateSet
from quam_builder.architecture.quantum_dots.utils import VoltageLevelType
from quam_builder.architecture.quantum_dots.virtual_gates.virtualisation_layer import (
    VirtualisationLayer,
)


__all__ = ["VirtualGateSet"]


@quam_dataclass
class VirtualGateSet(GateSet):
    """
    A set of virtual gates that can be used to create a virtual gate layer.

    Attributes:
        layers: A list of `VirtualisationLayer` objects, applied sequentially.
    """

    layers: List[VirtualisationLayer] = field(default_factory=list)

    def _validate_new_layer(
        self,
        source_gates: List[str],
        target_gates: List[str],
    ):
        """
        Validates the new layer to be added to the VirtualGateSet.

        Checks:
        - Each target gate must correspond to a lower layer source gate
          or physical channel
        - Each target gate must not be a target gate in any previous layer
        - Each source gate must not be a source gate in any previous layer
        - Each source gate must not be a target gate in any previous layer

        Args:
            source_gates: A list of names for the virtual gates in this layer.
            target_gates: A list of names for the physical (or underlying virtual)
                          gates that this layer maps to.

        Raises:
            ValueError: If any of the checks fail.
        """
        existing_source_gates = set()
        existing_target_gates = set()
        for lyr in self.layers:
            existing_source_gates.update(lyr.source_gates)
            existing_target_gates.update(lyr.target_gates)

        # Check 1: Each target gate must correspond to a lower layer source gate or
        # physical channel.
        # This check is implicitly handled if we consider that target_gates of the
        # first layer must be present in self.channels (physical gates).
        # For subsequent layers, target_gates must be source_gates of previous layers.
        if self.layers:  # Not the first layer
            # Get all source gates from previous layers
            all_previous_source_gates = set()
            for lyr in (
                self.layers
            ):  # Iterate through existing layers before adding the new one
                all_previous_source_gates.update(lyr.source_gates)

            # Combine with physical channels for the very first layer's target check
            valid_target_options = all_previous_source_gates.union(set(self.channels))
        else:  # First layer
            valid_target_options = set(self.channels)

        for tg in target_gates:
            if tg not in valid_target_options:
                raise ValueError(
                    f"Target gate '{tg}' in new layer does not correspond to any "
                    f"source gate of a previous layer or a physical channel. "
                    f"Valid options are: {valid_target_options}"
                )

        # Check 2: Each target gate must not be a target gate in any previous layer
        for tg in target_gates:
            if tg in existing_target_gates:
                raise ValueError(
                    f"Target gate '{tg}' in new layer is already a target gate in a "
                    f"previous layer. Existing target gates: {existing_target_gates}"
                )

        # Check 3: Each source gate must not be a source gate in any previous layer
        for sg in source_gates:
            if sg in existing_source_gates:
                raise ValueError(
                    f"Source gate '{sg}' in new layer is already a source gate in a "
                    f"previous layer. Existing source gates: {existing_source_gates}"
                )

        # Check 4: Each source gate must not be a target gate in any previous layer
        for sg in source_gates:
            if sg in existing_target_gates:
                raise ValueError(
                    f"Source gate '{sg}' in new layer is already a target gate in a "
                    f"previous layer. Existing target gates: {existing_target_gates}"
                )

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
        self._validate_new_layer(source_gates, target_gates)

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

        # If not allowing extra entries, check that all keys in voltages are either
        # physical channels or virtual channels defined in any layer.
        if not allow_extra_entries:
            # Collect all virtual gate names from all layers
            virtual_channels = set(
                ch for layer in self.layers for ch in layer.source_gates
            )
            # Combine physical and virtual gate names
            all_channels = set(list(self.channels) + list(virtual_channels))
            # Find any keys in voltages that are not recognized
            extra_channels = set(voltages) - all_channels
            if extra_channels:
                raise ValueError(
                    f"Channels {extra_channels} in voltages that are not part of the "
                    f"VirtualGateSet.channels: {self.channels}"
                )

        # Start with a copy of the input voltages to avoid mutating the original
        resolved_voltages = voltages.copy()

        # Apply each virtualisation layer in reverse order (from highest to lowest)
        # Each layer resolves its virtual gates to the next lower layer
        for layer in reversed(self.layers):
            resolved_voltages = layer.resolve_voltages(
                resolved_voltages, allow_extra_entries=True
            )

        # Finally, resolve any remaining voltages using the base class method
        # For example, add any voltages to channels that are undefined
        resolved_voltages = super().resolve_voltages(
            resolved_voltages, allow_extra_entries=True
        )
        return resolved_voltages
