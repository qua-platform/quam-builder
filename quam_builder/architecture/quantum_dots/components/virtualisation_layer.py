from typing import List, Dict, Any
import numpy as np

from quam.core import QuamComponent, quam_dataclass
from quam_builder.tools.qua_tools import VoltageLevelType


__all__ = ["VirtualisationLayer"]


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
            - NOTE: Matrix elements must be python literals, not QUA variables
    """

    source_gates: List[str]
    target_gates: List[str]
    matrix: List[List[float]]

    def calculate_inverse_matrix(self) -> np.ndarray:
        """Calculates the inverse of the virtualisation matrix."""
        try:
            inv_matrix = np.linalg.inv(self.matrix)
            if not inv_matrix.shape == (len(self.source_gates), len(self.target_gates)):
                raise ValueError(
                    "Inverse matrix has incorrect dimensions. "
                    f"Expected {len(self.source_gates)}x{len(self.target_gates)}, "
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
                f"VirtualisationLayer.source_gates: {self.source_gates}"
            )

        resolved_voltages = voltages.copy()

        inverse_matrix = self.calculate_inverse_matrix()

        source_voltages = [
            resolved_voltages.pop(source_gate, 0.0) for source_gate in self.source_gates
        ]

        for target_gate, inv_matrix_row in zip(self.target_gates, inverse_matrix):
            resolved_voltages.setdefault(target_gate, 0.0)
            resolved_voltages[target_gate] += inv_matrix_row @ source_voltages

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
