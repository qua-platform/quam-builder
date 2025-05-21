from typing import List, Dict, Any
import numpy as np

from quam.core import QuamComponent, quam_dataclass
from quam_builder.architecture.quantum_dots.utils import VoltageLevelType


@quam_dataclass
class VirtualisationLayer(QuamComponent):
    """
    Represents a layer of virtual gates, defining the transformation from
    virtual gate voltages to physical gate voltages.

    Attributes:
        source_gates: Names of the virtual gates defined in this layer.
        target_gates: Names of the physical or underlying virtual gates this
                      layer maps to.
        matrix: The virtualisation matrix [source_gates x target_gates]
            defining the transformation.
    """

    source_gates: List[str]
    """Names of the virtual gates defined in this layer."""
    target_gates: List[str]
    """Names of the physical or underlying virtual gates this layer maps to."""
    matrix: List[List[float]]
    """The virtualisation matrix [source_gates x target_gates]
    defining the transformation."""

    def calculate_inverse_matrix(self) -> np.ndarray:
        """Calculates the inverse of the virtualisation matrix."""
        return np.linalg.inv(self.matrix)

    def resolve_voltages(
        self, voltages: Dict[str, VoltageLevelType], allow_extra_entries: bool = False
    ) -> Dict[str, VoltageLevelType]:
        """
        Resolves virtual gate voltages to physical gate voltages for this layer.

        Args:
            voltages: A dictionary mapping gate names to voltage levels.
                These can be virtual or physical gate names.
            allow_extra_entries: If True, gates in `voltages` that are not
                part of `source_gates` will be ignored. If False, an
                AssertionError will be raised.

        Returns:
            A dictionary mapping physical gate names to their resolved voltage levels.
        """
        if not allow_extra_entries:
            assert all(ch_name in self.source_gates for ch_name in voltages), (
                "All channels in voltages must be part of the "
                f"VirtualisationLayer.source_gates: {self.source_gates}"
            )

        resolved_voltages = voltages.copy()
        inverse_matrix = self.calculate_inverse_matrix()

        for source_gate, inv_matrix_row in zip(self.source_gates, inverse_matrix):
            if source_gate not in resolved_voltages:
                continue

            source_voltage = resolved_voltages.pop(source_gate)

            for target_gate, inv_matrix_value in zip(self.target_gates, inv_matrix_row):
                resolved_voltages[target_gate] += inv_matrix_value * source_voltage

        return resolved_voltages

    def to_dict(
        self, follow_references: bool = False, include_defaults: bool = False
    ) -> Dict[str, Any]:
        """
        Converts the VirtualisationLayer to a dictionary.

        Ensures that the matrix is converted to a list if it's a numpy array.

        Args:
            follow_references: If True, follow references to other QuamComponents.
            include_defaults: If True, include default values in the dictionary.

        Returns:
            A dictionary representation of the VirtualisationLayer.
        """
        d = super().to_dict(
            follow_references=follow_references, include_defaults=include_defaults
        )
        if isinstance(d["matrix"], np.ndarray):
            d["matrix"] = d["matrix"].tolist()
        return d
