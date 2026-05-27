"""Virtual gate set definitions for quantum dot architectures."""

# pylint: disable=bad-reversed-sequence,invalid-field-call,no-member,not-an-iterable
# pylint: disable=unsubscriptable-object

from dataclasses import field
from typing import Any, Dict, List
import warnings
import numpy as np

from quam.core import QuamComponent, quam_dataclass
from .gate_set import GateSet
from quam_builder.tools.qua_tools import VoltageLevelType


__all__ = ["VirtualGateSet", "VirtualizationLayer"]


@quam_dataclass
class VirtualizationLayer(QuamComponent):
    """
    Represents a layer of virtual gates, defining the transformation from
    virtual gate voltages to physical gate voltages.

    Attributes:
        source_gates: Names of the virtual gates defined in this layer.
        target_gates: Names of the physical or underlying virtual gates this
                      layer maps to.
        matrix: The virtualization matrix [source_gates x target_gates]
            defining the transformation.
            - NOTE: Matrix elements must be python literals, not QUA variables
    """

    id: str = None
    source_gates: List[str]
    target_gates: List[str]
    matrix: List[List[float]]
    use_pseudoinverse: bool = False

    def _as_matrix_array(self) -> np.ndarray:
        return np.asarray(self.matrix, dtype=float)

    def _plot_labeled_matrix(
        self,
        matrix_array: np.ndarray,
        row_labels: List[str],
        column_labels: List[str],
        row_axis_label: str,
        column_axis_label: str,
        colorbar_label: str,
        default_title: str,
        ax: Any,
        annotate: bool,
        colorbar: bool,
        cmap: str,
        value_format: str,
        title: str | None,
    ) -> tuple[Any, Any]:
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise ImportError(
                "VirtualizationLayer matrix plotting requires matplotlib to be installed."
            ) from exc

        if ax is None:
            fig_width = max(4.0, 0.8 * len(column_labels) + 2.5)
            fig_height = max(3.0, 0.55 * len(row_labels) + 1.8)
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        else:
            fig = ax.figure

        max_abs_value = float(np.max(np.abs(matrix_array))) if matrix_array.size else 0.0
        color_limit = max_abs_value if max_abs_value > 0 else 1.0
        image = ax.imshow(
            matrix_array,
            aspect="auto",
            cmap=cmap,
            vmin=-color_limit,
            vmax=color_limit,
        )

        ax.set_xticks(np.arange(len(column_labels)))
        ax.set_xticklabels(column_labels, rotation=45, ha="right")
        ax.set_yticks(np.arange(len(row_labels)))
        ax.set_yticklabels(row_labels)
        ax.set_xlabel(column_axis_label)
        ax.xaxis.set_label_position("top")
        ax.xaxis.tick_top()
        ax.set_ylabel(row_axis_label)
        ax.set_title(title if title is not None else default_title)

        ax.set_xticks(np.arange(len(column_labels) + 1) - 0.5, minor=True)
        ax.set_yticks(np.arange(len(row_labels) + 1) - 0.5, minor=True)
        ax.grid(which="minor", color="white", linestyle="-", linewidth=1.5)
        ax.tick_params(which="minor", bottom=False, left=False)

        if annotate:
            for row_idx, row in enumerate(matrix_array):
                for col_idx, value in enumerate(row):
                    text_color = "white" if abs(value) > 0.5 * color_limit else "black"
                    ax.text(
                        col_idx,
                        row_idx,
                        format(value, value_format),
                        ha="center",
                        va="center",
                        color=text_color,
                    )

        if colorbar:
            cbar = fig.colorbar(image, ax=ax)
            cbar.set_label(colorbar_label)

        fig.tight_layout()
        return fig, ax

    def plot_matrix(
        self,
        ax: Any = None,
        annotate: bool = True,
        colorbar: bool = True,
        cmap: str = "coolwarm",
        value_format: str = ".3g",
        title: str | None = None,
    ) -> tuple[Any, Any]:
        """
        Plot the virtualization matrix as a labeled source-to-target heatmap.

        Rows correspond to ``source_gates`` and columns correspond to
        ``target_gates``. The matrix is shown with a zero-centered color scale so
        users can quickly identify positive, negative, and weak couplings.

        Args:
            ax: Optional matplotlib axes to draw on.
            annotate: If True, write the matrix value inside each cell.
            colorbar: If True, add a colorbar showing the coefficient scale.
            cmap: Matplotlib colormap used for the heatmap.
            value_format: Format specifier used for cell annotations.
            title: Optional plot title. Defaults to the layer id when available.

        Returns:
            A tuple of ``(figure, axes)``.
        """
        matrix_array = self._as_matrix_array()
        expected_shape = (len(self.source_gates), len(self.target_gates))
        if matrix_array.shape != expected_shape:
            raise ValueError(
                "Matrix dimensions do not match source/target gate counts. "
                f"Expected {expected_shape}, got {matrix_array.shape}"
            )

        default_title = (
            f"Virtualization matrix: {self.id}" if self.id is not None else "Virtualization matrix"
        )
        return self._plot_labeled_matrix(
            matrix_array=matrix_array,
            row_labels=self.source_gates,
            column_labels=self.target_gates,
            row_axis_label="Source gates",
            column_axis_label="Target gates",
            colorbar_label="Virtualization coefficient",
            default_title=default_title,
            ax=ax,
            annotate=annotate,
            colorbar=colorbar,
            cmap=cmap,
            value_format=value_format,
            title=title,
        )

    def plot_inverse_matrix(
        self,
        ax: Any = None,
        annotate: bool = True,
        colorbar: bool = True,
        cmap: str = "coolwarm",
        value_format: str = ".3g",
        title: str | None = None,
    ) -> tuple[Any, Any]:
        """
        Plot the inverse virtualization matrix as a labeled target-to-source heatmap.

        Rows correspond to ``target_gates`` and columns correspond to
        ``source_gates`` because the inverse matrix maps source gate voltages back
        onto target gate voltages.

        Args:
            ax: Optional matplotlib axes to draw on.
            annotate: If True, write the matrix value inside each cell.
            colorbar: If True, add a colorbar showing the coefficient scale.
            cmap: Matplotlib colormap used for the heatmap.
            value_format: Format specifier used for cell annotations.
            title: Optional plot title. Defaults to the layer id when available.

        Returns:
            A tuple of ``(figure, axes)``.
        """
        inverse_matrix = self.calculate_inverse_matrix()
        default_title = (
            f"Inverse virtualization matrix: {self.id}"
            if self.id is not None
            else "Inverse virtualization matrix"
        )
        return self._plot_labeled_matrix(
            matrix_array=inverse_matrix,
            row_labels=self.target_gates,
            column_labels=self.source_gates,
            row_axis_label="Target gates",
            column_axis_label="Source gates",
            colorbar_label="Inverse virtualization coefficient",
            default_title=default_title,
            ax=ax,
            annotate=annotate,
            colorbar=colorbar,
            cmap=cmap,
            value_format=value_format,
            title=title,
        )

    def calculate_inverse_matrix(self) -> np.ndarray:
        """Calculates the inverse (or pseudo-inverse) of the virtualization matrix."""
        matrix_array = self._as_matrix_array()
        expected_shape = (len(self.target_gates), len(self.source_gates))
        try:
            matrix_is_square = matrix_array.shape[0] == matrix_array.shape[1]
            if matrix_is_square and not self.use_pseudoinverse:
                inv_matrix = np.linalg.inv(matrix_array)
            else:
                inv_matrix = np.linalg.pinv(matrix_array)
            if inv_matrix.shape != expected_shape:
                raise ValueError(
                    "Inverse matrix has incorrect dimensions. "
                    f"Expected {expected_shape[0]}x{expected_shape[1]}, "
                    f"got {inv_matrix.shape}."
                )
            return inv_matrix
        except Exception as e:
            raise ValueError(f"Error calculating inverse matrix: {e}")

    def resolve_voltages(
        self, voltages: Dict[str, VoltageLevelType], allow_extra_entries: bool = False
    ) -> Dict[str, VoltageLevelType]:
        """
        Resolves virtual gate voltages to physical gate voltages for this layer.

        Args:
            voltages: A dictionary mapping gate names to voltages.
                These can be virtual or physical gate names.
            allow_extra_entries: If True, gates in `voltages` that are not
                part of `source_gates` will be ignored. If False, an
                AssertionError will be raised.

        Returns:
            A dictionary mapping physical gate names to their resolved voltages.
        """
        if not allow_extra_entries:
            assert all(ch_name in self.source_gates for ch_name in voltages), (
                "All channels in voltages must be part of the "
                f"VirtualizationLayer.source_gates: {self.source_gates}"
            )

        resolved_voltages = voltages.copy()

        inverse_matrix = self.calculate_inverse_matrix()

        source_voltages = [
            resolved_voltages.pop(source_gate, 0.0) for source_gate in self.source_gates
        ]

        for target_gate, inv_matrix_row in zip(self.target_gates, inverse_matrix):
            resolved_voltages.setdefault(target_gate, 0.0)
            resolved_voltages[target_gate] = (
                resolved_voltages[target_gate] + inv_matrix_row @ source_voltages
            )

        return resolved_voltages

    def to_dict(
        self, follow_references: bool = False, include_defaults: bool = False
    ) -> Dict[str, Any]:
        """
        Converts the VirtualizationLayer to a dictionary.

        Ensures that the matrix is converted to a list if it's a numpy array.

        Args:
            follow_references: If True, follow references to other QuamComponents.
            include_defaults: If True, include default values in the dictionary.

        Returns:
            A dictionary representation of the VirtualizationLayer.
        """
        d = super().to_dict(follow_references=follow_references, include_defaults=include_defaults)
        if isinstance(d["matrix"], np.ndarray):
            d["matrix"] = d["matrix"].tolist()
        return d


@quam_dataclass
class VirtualGateSet(GateSet):
    """
    A set of virtual gates that can be used to create a virtual gate layer.

    Inheriting from GateSet, VirtualGateSet allows control of a set of virtual
    gates that can be used to create a virtual gate layer.

    A VirtualGateSet manages a collection of channels (instances of `SingleChannel`,
    including subclasses like `VoltageGate`) and provides all the functionalities
    of a GateSet, plus functionality to:
    - Add any number of virtualization layers onto any subset of physical or virtual gates,
      using user-defined matrices (square by default, or rectangular when enabled)
    - Define named voltage tuning points (macros), which can consist of any combination of
      physical and virtual gates, that can be reused across sequences
    - Resolve voltages for all gates, even if the input voltages contain both physical
      and virtual gates; with default fallbacks

    The VirtualGateSet retains all the capabilities of the GateSet (i.e. acting as
    a logical grouping of related channels), while also allowing linear combinations
    of physical and virtual gates for universal control.

    Attributes:
        layers: A list of `VirtualizationLayer` objects, applied sequentially.
        allow_rectangular_matrices: Enables pseudo-inverse based resolution so layers
            may use non-square matrices.
        channels: Inherited from `GateSet`. Physical channels are `SingleChannel`
            instances (and may be `VoltageGate` objects) that the virtual gates
            ultimately resolve to.

    Example:
        >>> from quam.components.channels import SingleChannel
        >>> # Create channels for a quantum dot
        >>> plunger_ch = SingleChannel("plunger", ...)
        >>> barrier_ch = SingleChannel("barrier", ...)
        >>>
        >>> # Create virtual gate set
        >>> dot_gates = VirtualGateSet(
        ...     id="dot1",
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
        >>> # Create and use voltage sequence
        >>> with qua.program() as prog:
        ...     seq = dot_gates.new_sequence()
        ...     seq.step_to_point("load")  # Uses the predefined voltage point
    """

    layers: List[VirtualizationLayer] = field(default_factory=list)
    allow_rectangular_matrices: bool = False

    @property
    def valid_channel_names(self) -> list[str]:
        """
        Returns a list of valid channel names for the VirtualGateSet.
        """
        # Collect all virtual gate names from all layers
        virtual_channels = set(ch for layer in self.layers for ch in layer.source_gates)
        # Combine physical and virtual gate names
        return list(self.channels) + list(virtual_channels)

    def _validate_new_layer(
        self,
        layer_id: str,
        source_gates: List[str],
        target_gates: List[str],
        matrix: List[List[float]],
    ):  # pylint: disable=too-many-branches
        """
        Validates the new layer to be added to the VirtualGateSet.

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
            # Allow unnamed layers (None) to stack without collision; only enforce when an id is provided
            if layer_id is not None and layer_id == lyr.id:
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
        Adds a new virtualization layer to the VirtualGateSet.

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
        return virtualization_layer

    def add_to_layer(
        self,
        source_gates: List[str],
        target_gates: List[str],
        matrix: List[List[float]],
        layer_id: str | None = None,
    ) -> VirtualizationLayer:
        """Add gates to an existing layer, or create a new layer if needed."""
        # pylint: disable=too-many-branches,too-many-statements
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

        return layer

    def resolve_voltages(
        self, voltages: Dict[str, VoltageLevelType], allow_extra_entries: bool = False
    ) -> Dict[str, VoltageLevelType]:
        """
        Resolves all virtual gate voltages to physical gate voltages by applying
        all virtualization layers in reverse order.

        Args:
            voltages: A dictionary mapping gate names (virtual or physical) to
                      voltages.
            allow_extra_entries: If True, gates in `voltages` that are not
                part of this VirtualGateSet (neither physical nor virtual)
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
                    f"VirtualGateSet.channels: {self.channels}"
                )

        # Start with a copy of the input voltages to avoid mutating the original
        resolved_voltages = voltages.copy()

        # Apply each virtualization layer in reverse order (from highest to lowest)
        # Each layer resolves its virtual gates to the next lower layer
        for layer in reversed(self.layers):
            resolved_voltages = layer.resolve_voltages(resolved_voltages, allow_extra_entries=True)

        # Finally, resolve any remaining voltages using the base class method
        # For example, add any voltages to channels that are undefined
        resolved_voltages = super().resolve_voltages(resolved_voltages, allow_extra_entries=True)
        return resolved_voltages
