"""
Concrete strategy implementations for different quantum element types.

This module provides specific wiring strategies for:
- Single qubits
- Qubit pairs
- Global elements
- Readout elements
"""
from typing import Dict

from qualang_tools.wirer.connectivity.element import QubitPairReference

from quam_builder.builder.qop_connectivity.wiring_strategy import WiringStrategy, WiringContext
from quam_builder.builder.qop_connectivity.paths import QUBITS_BASE_JSON_PATH


class QubitWiringStrategy(WiringStrategy):
    """Strategy for single-qubit wiring.

    Handles wiring for individual qubits including drive, flux, resonator,
    and plunger lines.
    """

    def get_base_path(self, context: WiringContext) -> str:
        """Get base path for qubit wiring.

        Format: qubits/{qubit_id}/{line_type}

        Args:
            context: The wiring context

        Returns:
            Base path string
        """
        return f"qubits/{context.element_id}/{context.line_type.value}"

    def get_additional_references(self, context: WiringContext) -> Dict[str, str]:
        """Get additional references for qubits.

        Qubits don't need additional references beyond their port mappings.

        Args:
            context: The wiring context

        Returns:
            Empty dictionary
        """
        return {}


class QubitPairWiringStrategy(WiringStrategy):
    """Strategy for qubit-pair wiring.

    Handles wiring for qubit pairs including coupler, cross-resonance,
    ZZ-drive, and barrier lines. Includes references to control and target qubits.
    """

    def get_base_path(self, context: WiringContext) -> str:
        """Get base path for qubit pair wiring.

        Format: qubit_pairs/{pair_id}/{line_type}

        Args:
            context: The wiring context

        Returns:
            Base path string
        """
        return f"qubit_pairs/{context.element_id}/{context.line_type.value}"

    def get_additional_references(self, context: WiringContext) -> Dict[str, str]:
        """Get additional references for qubit pairs.

        Adds control_qubit and target_qubit JSON references.

        Args:
            context: The wiring context

        Returns:
            Dictionary with control_qubit and target_qubit references
        """
        if not isinstance(context.element_id, QubitPairReference):
            raise TypeError(
                f"Expected QubitPairReference, got {type(context.element_id)}"
            )

        element_id = context.element_id
        return {
            "control_qubit": f"{QUBITS_BASE_JSON_PATH}/q{element_id.control_index}",
            "target_qubit": f"{QUBITS_BASE_JSON_PATH}/q{element_id.target_index}",
        }


class GlobalElementWiringStrategy(WiringStrategy):
    """Strategy for global element wiring.

    Handles wiring for global gates that affect multiple qubits simultaneously.
    """

    def get_base_path(self, context: WiringContext) -> str:
        """Get base path for global element wiring.

        Format: globals/{element_id}/{line_type}

        Args:
            context: The wiring context

        Returns:
            Base path string
        """
        return f"globals/{context.element_id}/{context.line_type.value}"

    def get_additional_references(self, context: WiringContext) -> Dict[str, str]:
        """Get additional references for global elements.

        Global elements don't need additional references.

        Args:
            context: The wiring context

        Returns:
            Empty dictionary
        """
        return {}


class ReadoutWiringStrategy(WiringStrategy):
    """Strategy for readout wiring.

    Handles wiring for readout elements including sensor gates and
    RF resonators.
    """

    def get_base_path(self, context: WiringContext) -> str:
        """Get base path for readout wiring.

        Format: readout/{element_id}/{line_type}

        Args:
            context: The wiring context

        Returns:
            Base path string
        """
        return f"readout/{context.element_id}/{context.line_type.value}"

    def get_additional_references(self, context: WiringContext) -> Dict[str, str]:
        """Get additional references for readout elements.

        Readout elements don't need additional references.

        Args:
            context: The wiring context

        Returns:
            Empty dictionary
        """
        return {}