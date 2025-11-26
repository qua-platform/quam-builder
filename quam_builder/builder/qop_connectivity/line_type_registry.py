"""
Registry for mapping line types to element categories and strategies.

This module provides centralized configuration for how different line types
(drive, flux, coupler, etc.) map to element categories and wiring strategies.
"""
from enum import Enum
from typing import Dict, Type, Union

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType

from quam_builder.builder.qop_connectivity.wiring_strategy import WiringStrategy
from quam_builder.builder.qop_connectivity.concrete_strategies import (
    QubitWiringStrategy,
    QubitPairWiringStrategy,
    GlobalElementWiringStrategy,
    ReadoutWiringStrategy,
)


class ElementCategory(Enum):
    """Categories of quantum elements.

    Each category corresponds to a different wiring strategy and path structure.
    """
    QUBIT = "qubit"
    QUBIT_PAIR = "qubit_pair"
    GLOBAL_ELEMENT = "global_element"
    READOUT = "readout"


class LineTypeRegistry:
    """Registry mapping line types to element categories and strategies.

    This class provides a centralized place to configure how different line types
    are categorized and processed. It enables easy extension by allowing custom
    line types and strategies to be registered.

    Example:
        # >>> registry = LineTypeRegistry()
        # >>> category = registry.get_category(WiringLineType.DRIVE)
        # >>> strategy_class = registry.get_strategy_class(category)
    """

    def __init__(self):
        """Initialize the registry with default mappings."""
        self._mappings: Dict[Union[WiringLineType, WiringLineType, str], ElementCategory] = {}
        self._strategy_map: Dict[ElementCategory, Type[WiringStrategy]] = {}
        self._setup_default_mappings()

    def _setup_default_mappings(self):
        """Setup default line type to category mappings.

        This method configures the standard mappings for common quantum
        computing line types. Uses WiringLineType which includes
        both base types from qualang_tools and custom types for quantum dots.
        """
        # Qubit line types - single qubit control and readout
        qubit_lines = [
            WiringLineType.RESONATOR,
            WiringLineType.DRIVE,
            WiringLineType.FLUX,
            WiringLineType.PLUNGER_GATE,
        ]
        for line_type in qubit_lines:
            self.register(line_type, ElementCategory.QUBIT)

        # Qubit pair line types - two-qubit gates and interactions
        pair_lines = [
            WiringLineType.COUPLER,
            WiringLineType.CROSS_RESONANCE,
            WiringLineType.ZZ_DRIVE,
            WiringLineType.BARRIER_GATE,
        ]
        for line_type in pair_lines:
            self.register(line_type, ElementCategory.QUBIT_PAIR)

        # Global line types - operations affecting multiple qubits
        element_lines = [
            WiringLineType.GLOBAL_GATE,
        ]
        for line_type in element_lines:
            self.register(line_type, ElementCategory.GLOBAL_ELEMENT)

        # Readout line types - measurement operations
        readout_lines = [
            WiringLineType.SENSOR_GATE,
            WiringLineType.RF_RESONATOR,
        ]
        for line_type in readout_lines:
            self.register(line_type, ElementCategory.READOUT)

        # Register default strategies
        self._strategy_map = {
            ElementCategory.QUBIT: QubitWiringStrategy,
            ElementCategory.QUBIT_PAIR: QubitPairWiringStrategy,
            ElementCategory.GLOBAL_ELEMENT: GlobalElementWiringStrategy,
            ElementCategory.READOUT: ReadoutWiringStrategy,
        }

    def register(
        self,
        line_type: Union[WiringLineType, WiringLineType],
        category: ElementCategory
    ) -> None:
        """Register a line type to category mapping.

        Args:
            line_type: The wiring line type to register (base)
            category: The element category it belongs to
        """
        # Store by string value for compatibility between WiringLineType and WiringLineType
        self._mappings[line_type.value if hasattr(line_type, 'value') else line_type] = category

    def get_category(self, line_type: Union[WiringLineType, WiringLineType]) -> ElementCategory:
        """Get the element category for a line type.

        Args:
            line_type: The wiring line type to look up (base)

        Returns:
            The element category for this line type

        Raises:
            ValueError: If the line type is not registered
        """
        # Look up by string value for compatibility
        key = line_type.value if hasattr(line_type, 'value') else line_type
        if key not in self._mappings:
            raise ValueError(
                f"Unknown line type: {line_type}. "
                f"Please register it using registry.register()"
            )
        return self._mappings[key]

    def get_strategy_class(
        self,
        category: ElementCategory
    ) -> Type[WiringStrategy]:
        """Get the strategy class for an element category.

        Args:
            category: The element category

        Returns:
            The strategy class to use for this category

        Raises:
            KeyError: If no strategy is registered for this category
        """
        if category not in self._strategy_map:
            raise KeyError(
                f"No strategy registered for category: {category}. "
                f"Use register_custom_strategy() to add one."
            )
        return self._strategy_map[category]

    def register_custom_strategy(
        self,
        category: ElementCategory,
        strategy_class: Type[WiringStrategy]
    ) -> None:
        """Register a custom strategy for a category.

        This allows extending the system with custom wiring strategies.

        Args:
            category: The element category
            strategy_class: The strategy class to use for this category

        Example:
            # >>> class CustomStrategy(WiringStrategy):
            # ...     # Custom implementation
            # ...     pass
            # >>> registry.register_custom_strategy(
            # ...     ElementCategory.QUBIT,
            # ...     CustomStrategy
            # ... )
        """
        self._strategy_map[category] = strategy_class

    def get_all_line_types(self) -> Dict[ElementCategory, list[str]]:
        """Get all line types organized by category.

        Returns:
            Dictionary mapping categories to lists of line type string values

        Example:
            # >>> registry.get_all_line_types()
            {
                ElementCategory.QUBIT: ['drive', 'flux', ...],
                ElementCategory.QUBIT_PAIR: ['coupler', ...],
                ...
            }
        """
        result: Dict[ElementCategory, list[str]] = {
            category: [] for category in ElementCategory
        }

        for line_type, category in self._mappings.items():
            result[category].append(line_type)

        return result