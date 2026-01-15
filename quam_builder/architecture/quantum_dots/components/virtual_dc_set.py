"""Virtual DC gate set for quantum dot systems."""

# pylint: disable=access-member-before-definition,invalid-field-call,no-member,not-an-iterable
# pylint: disable=unsubscriptable-object
# pylint: disable=too-many-branches,too-many-statements,unsupported-assignment-operation

from dataclasses import field
import warnings
from typing import Dict, List

import numpy as np

from quam.core import quam_dataclass, macro
from quam.components import QuantumComponent
from quam_builder.architecture.quantum_dots.components.voltage_gate import VoltageGate
from quam_builder.architecture.quantum_dots.virtual_gates import VirtualizationLayer

from quam_builder.architecture.quantum_dots.components.gate_set import VoltageTuningPoint

__all__ = ["VirtualDCSet"]


@quam_dataclass
class VirtualDCSet(QuantumComponent):
    """
    A set of DC virtual gates that can be used to create a virtual gate layer independent of the OPX.
    A VirtualDCSet manages a collection of VoltageGate channels, and allows collective control of their
    DC offsets.

    The VirtualDCSet allows one to:
    - Add any number of virtualization layers onto any subset of physical or virtual gates,
      using user-defined matrices (square by default, or rectangular when enabled)
    - Define named voltage tuning points (macros), which can consist of any combination of
      physical and virtual gates, that can be reused across sequences
    - Resolve voltages for all gates, even if the input voltages contain both physical
      and virtual gates; with default fallbacks

    Attributes:
        layers: A list of `VirtualizationLayer` objects, applied sequentially.
        allow_rectangular_matrices: Enables pseudo-inverse based resolution so layers
            may use non-square matrices.
        channels: Physical channels are `VoltageGate` instances that the virtual
            gates ultimately resolve to.

    Example:
        >>> from quam.components.channels import SingleChannel
        >>> # Create channels for a quantum dot
        >>> plunger_ch = VoltageGate("plunger", ...)
        >>> barrier_ch = VoltageGate("barrier", ...)
        >>>
        >>> # Create virtual DC set
        >>> dot_gates = VirtualDCSet(
        ...     id="Dots DC",
        ...     channels={"plunger": plunger_ch, "barrier": barrier_ch}
        ... )
        >>>
        >>> # Create any number of virtualization layers
        >>> dot_gates.add_layer(
        ...     source_gates = ["virtual1", "virtual2"],
        ...     target_gates=["plunger", "barrier"],
        ...     matrix = [[1, 0.3],[0.4, 1]]
        ... )
        >>>
        >>> # Add voltage tuning points
        >>> dot_gates.add_point("load", {"virtual1": 0.5, "barrier": -0.2}, 1000)
        >>> dot_gates.add_point("measure", {"plunger": 0.3, "virtual2": 0.1}, 500)
        >>>
    """

    id: str = None
    channels: Dict[str, VoltageGate]
    layers: List[VirtualizationLayer] = field(default_factory=list)
    allow_rectangular_matrices: bool = False

    _current_physical_voltages: Dict[str, float] = field(default_factory=dict)
    _current_levels: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize current voltage tracking and validate channel offsets."""
        # Check for offset_parameter in all the channels
        for channel in self.channels.values():
            if channel.offset_parameter is None:
                raise ValueError(
                    f"Channel {channel.id} does not have an associated offset_parameter. Set this first"
                )

        # Instantiate all the physical voltages in full voltages dict
        for name, channel in self.channels.items():
            self._current_physical_voltages[name] = channel.offset_parameter()
        all_voltages = self.all_current_voltages
        for name in self.valid_channel_names:
            self._current_levels[name] = all_voltages[name]

    @property
    def name(self):
        """Return the VirtualDCSet identifier."""
        return self.id

    @property
    def current_physical_voltages(self) -> Dict[str, float]:
        """Query, update and return the current dict of all physical voltages"""
        for name, channel in self.channels.items():
            self._current_physical_voltages[name] = channel.offset_parameter()
        return self._current_physical_voltages

    @property
    def all_current_voltages(self) -> Dict[str, float]:
        """Return a dict of virtual voltages derived from the physical voltages."""
        full_voltages_dict = self.current_physical_voltages.copy()

        # Build the dict layer by layer. First layer should always be mapped to the physical anyway
        # With each iteration, the new dict should be updated, so all the virtual values will be
        # updated depending on the current physical ones.
        for layer in self.layers:
            target_names = layer.target_gates
            source_names = layer.source_gates
            target_voltages_array = np.array([full_voltages_dict[name] for name in target_names])
            matrix_array = np.asarray(layer.matrix, dtype=float)
            source_voltages_array = matrix_array @ target_voltages_array
            for idx, name in enumerate(source_names):
                full_voltages_dict[name] = source_voltages_array[idx]
        self._current_levels = full_voltages_dict.copy()
        return full_voltages_dict

    @property
    def valid_channel_names(self) -> list[str]:
        """Return the list of physical and virtual gate names."""
        # Collect all virtual gate names from all layers
        virtual_channels = set(ch for layer in self.layers for ch in layer.source_gates)
        # Combine physical and virtual gate names
        return list(self.channels) + list(virtual_channels)

    def add_point(self, name: str, voltages: Dict[str, float], duration: int) -> None:
        """Register a named voltage point macro for this virtual gate set."""
        invalid_channel_names = set(voltages) - set(self.valid_channel_names)

        if invalid_channel_names:
            raise ValueError(
                f"Channel(s) '{invalid_channel_names}' specified in voltages for point "
                f"'{name}' are not part of this VirtualDCSet."
            )

        # Ensure macros dict exists if not handled by Pydantic model of QuantumComponent
        if not hasattr(self, "macros") or self.macros is None:
            self.macros: Dict[str, macro.QuamMacro] = {}

        self.macros[name] = VoltageTuningPoint(voltages=voltages, duration=duration)

    def _validate_new_layer(
        self,
        layer_id: str,
        source_gates: List[str],
        target_gates: List[str],
        matrix: List[List[float]],
    ) -> None:
        """
        Validates the new layer to be added to the VirtualDCSet.

        Checks:
        - Each target gate must correspond to a lower layer source gate
          or physical channel
        - Each target gate must not be a target gate in any previous layer
        - Each source gate must not be a source gate in any previous layer
        - Each source gate must not be a target gate in any previous layer
        - Matrix dimensions match the number of source/target gates
        - Matrix is square and invertible unless ``allow_rectangular_matrices`` is True

        Args:
            source_gates: A list of names for the virtual gates in this layer.
            target_gates: A list of names for the physical (or underlying virtual)
                          gates that this layer maps to.
            matrix: The virtualization matrix defining the transformation.

        Raises:
            ValueError: If any of the checks fail.
        """
        existing_layer_names = set()
        existing_source_gates = set()
        existing_target_gates = set()
        for lyr in self.layers:
            existing_source_gates.update(lyr.source_gates)
            existing_target_gates.update(lyr.target_gates)
            if lyr.id is not None:
                existing_layer_names.add(lyr.id)

        # Check 1: Each target gate must correspond to a lower layer source gate or
        # physical channel.
        # This check is implicitly handled if we consider that target_gates of the
        # first layer must be present in self.channels (physical gates).
        # For subsequent layers, target_gates must be source_gates of previous layers.
        if self.layers:  # Not the first layer
            # Get all source gates from previous layers
            all_previous_source_gates = set()
            for lyr in self.layers:  # Iterate through existing layers before adding the new one
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

        # Check 5: The layer name must be unique
        for lyr in self.layers:
            if layer_id == lyr.id:
                raise ValueError(f"Layer name '{layer_id}' is already used in a previous layer.")

        matrix_array = np.array(matrix, dtype=float)
        is_square = matrix_array.shape[0] == matrix_array.shape[1]
        if not is_square and not self.allow_rectangular_matrices:
            raise ValueError(
                f"Matrix must be square when allow_rectangular_matrices is False. "
                f"Got shape {matrix_array.shape}"
            )

        expected_shape = (len(source_gates), len(target_gates))
        if matrix_array.shape != expected_shape:
            raise ValueError(
                "Matrix dimensions do not match source/target gate counts. "
                f"Expected {expected_shape}, got {matrix_array.shape}"
            )

        if is_square:
            # Check 6: Matrix must be invertible (non-zero determinant)
            try:
                det = np.linalg.det(matrix_array)
                if abs(det) < 1e-10:  # Use small tolerance for floating point
                    raise ValueError(f"Matrix is not invertible (determinant ≈ 0): {det}")
            except np.linalg.LinAlgError as e:
                raise ValueError(f"Matrix inversion failed: {e}")

    def add_layer(
        self,
        source_gates: List[str],
        target_gates: List[str],
        matrix: List[List[float]],
        layer_id: str = None,
    ) -> VirtualizationLayer:
        """
        Adds a new virtualization layer to the VirtualDCSet.

        Args:
            source_gates: A list of names for the virtual gates in this layer.
            target_gates: A list of names for the physical (or underlying virtual)
                          gates that this layer maps to.
            matrix: The virtualization matrix defining the transformation.

        Returns:
            The created VirtualizationLayer object.
        """
        self._validate_new_layer(layer_id, source_gates, target_gates, matrix)

        matrix_array = np.array(matrix, dtype=float)
        use_pseudoinverse = matrix_array.shape[0] != matrix_array.shape[1]

        virtualization_layer = VirtualizationLayer(
            id=layer_id,
            source_gates=source_gates,
            target_gates=target_gates,
            matrix=matrix,
            use_pseudoinverse=use_pseudoinverse,
        )
        self.layers.append(virtualization_layer)

        # Populate the new layer
        all_voltages = self.all_current_voltages
        self._current_levels.update(all_voltages)
        return virtualization_layer

    def add_to_layer(
        self,
        source_gates: List[str],
        target_gates: List[str],
        matrix: List[List[float]],
        layer_id: str | None = None,
    ) -> VirtualizationLayer:
        """Extend an existing layer with additional gates and mappings."""
        if not self.allow_rectangular_matrices:
            raise ValueError(
                "add_to_layer requires allow_rectangular_matrices=True to enable "
                "non-square virtual gate layers."
            )

        if layer_id is None and self.layers:
            layer_id = self.layers[-1].id

        if not self.layers:
            return self.add_layer(
                layer_id=layer_id,
                source_gates=source_gates,
                target_gates=target_gates,
                matrix=matrix,
            )

        # Check: target gates should not exist in any other layers
        for lyr in self.layers:
            # Skip current layer
            if lyr.id == layer_id:
                continue
            conflicts = set(target_gates) & set(lyr.target_gates)
            if conflicts:
                raise ValueError(
                    f"Target gates {conflicts} already exists as a target gate in layer {lyr.id}"
                )

        # Check: matrix shape validation
        matrix_array = np.array(matrix, dtype=float)
        expected_shape = (len(source_gates), len(target_gates))
        if matrix_array.shape != expected_shape:
            raise ValueError(
                "Matrix dimensions do not match source/target gate counts. "
                f"Expected {expected_shape}, got {matrix_array.shape}"
            )

        target_overlap_layer = next((lyr for lyr in self.layers if lyr.id == layer_id), None)

        if target_overlap_layer is None:
            return self.add_layer(
                layer_id=layer_id,
                source_gates=source_gates,
                target_gates=target_gates,
                matrix=matrix,
            )

        layer = target_overlap_layer
        existing_targets = list(layer.target_gates)
        existing_sources = list(layer.source_gates)

        new_targets = []
        for target in target_gates:
            if target not in existing_targets:
                existing_targets.append(target)
                new_targets.append(target)

        full_matrix = np.asarray(layer.matrix, dtype=float)

        if new_targets:
            zeros_to_add = np.zeros((full_matrix.shape[0], len(new_targets)))
            full_matrix = np.hstack([full_matrix, zeros_to_add])

        source_rows: list[tuple[str, np.ndarray, list[tuple[str, float]]]] = []
        for idx, source in enumerate(source_gates):
            source_row = np.zeros((len(existing_targets),), dtype=float)
            target_value_pairs = []
            for col_idx, target in enumerate(target_gates):
                target_position = existing_targets.index(target)
                value = matrix_array[idx][col_idx]
                source_row[target_position] = value
                target_value_pairs.append((target, value))
            source_rows.append((source, source_row, target_value_pairs))

        rows_to_append = []
        sources_to_append = []
        for source, row_vector, target_pairs in source_rows:
            if source in existing_sources:
                row_idx = existing_sources.index(source)
                for target, value in target_pairs:
                    target_position = existing_targets.index(target)
                    old_value = full_matrix[row_idx, target_position]
                    if not np.isclose(old_value, value):
                        warnings.warn(
                            f"Overwriting virtualization matrix element for source '{source}' "
                            f"and target '{target}' in layer "
                            f"'{layer.id if hasattr(layer, 'id') else 'unnamed'}'.",
                            UserWarning,
                        )
                    full_matrix[row_idx, target_position] = value
            else:
                rows_to_append.append(row_vector)
                sources_to_append.append(source)

        if rows_to_append:
            full_matrix = np.vstack([full_matrix] + rows_to_append)
            existing_sources.extend(sources_to_append)

        layer.source_gates = existing_sources
        layer.target_gates = existing_targets
        layer.matrix = full_matrix.tolist()
        layer.use_pseudoinverse = True
        # Populate the new layer
        all_voltages = self.all_current_voltages
        self._current_levels.update(all_voltages)
        return layer

    def resolve_voltages(
        self, voltages: Dict[str, float], allow_extra_entries: bool = False
    ) -> Dict[str, float]:
        """
        Resolves all virtual gate voltages to physical gate voltages by applying
        all virtualization layers in reverse order.

        Args:
            voltages: A dictionary mapping gate names (virtual or physical) to
                      voltages.
            allow_extra_entries: If True, gates in `voltages` that are not
                part of this VirtualDCSet (neither physical nor virtual)
                will be ignored. If False, a ValueError will be raised.

        Returns:
            A dictionary mapping physical gate names to their fully resolved
            voltages.
        """

        # If not allowing extra entries, check that all keys in voltages are either
        # physical channels or virtual channels defined in any layer.
        if not allow_extra_entries:
            # Find any keys in voltages that are not recognized
            extra_channels = set(voltages) - set(self.valid_channel_names)
            if extra_channels:
                raise ValueError(
                    f"Channels {extra_channels} in voltages that are not part of the "
                    f"VirtualDCSet.channels: {self.channels}"
                )

        # Start with a copy of the input voltages to avoid mutating the original
        resolved_voltages = voltages.copy()

        # Apply each virtualization layer in reverse order (from highest to lowest)
        # Each layer resolves its virtual gates to the next lower layer
        for layer in reversed(list(self.layers)):
            resolved_voltages = layer.resolve_voltages(resolved_voltages, allow_extra_entries=True)

        base_resolved_voltages = {}
        for ch_name in self.channels:
            base_resolved_voltages[ch_name] = resolved_voltages.get(ch_name, 0.0)

        return base_resolved_voltages

    def set_voltages(self, voltages: Dict[str, float]) -> None:
        """
        Input a dict of {name: voltage} and resolve to physical voltages to apply.
        """
        self._current_levels = self.all_current_voltages.copy()
        deltas = {}
        for name, new_value in voltages.items():
            old_value = self._current_levels.get(name, 0.0)
            deltas[name] = new_value - old_value
        physical_deltas = self.resolve_voltages(deltas)
        for name, delta in physical_deltas.items():
            current_physical = self.channels[name].offset_parameter()
            self.channels[name].offset_parameter(current_physical + delta)
        self._current_levels = self.all_current_voltages.copy()

    def get_voltage(self, name: str, requery: bool = False) -> float:
        """
        Return the value of a particular voltage (physical or virtual) from the VirtualDCSet.
        If requery = True, then this will:
            1. Measure the physical outputs of the offset_parameter
            2. Calculate the virtual structure of the entire VirtualDCSet
            3. Return the relevant float value of the desired virtual gate name
        If requery = False, then the value will be extracted from the current levels dict.
        """
        if name not in self.valid_channel_names:
            raise ValueError(f"Channel {name} not in list of valid channel names")
        if requery:
            return self.all_current_voltages[name]
        return self._current_levels.get(name, 0.0)

    def go_to_point(self, name: str) -> None:
        """Apply a registered voltage point by name."""
        if name not in self.macros:
            raise ValueError(
                f"Point name {name} not in registered macros: {list(self.macros.keys())}"
            )
        point = self.macros[name]
        self.set_voltages(point.voltages)
