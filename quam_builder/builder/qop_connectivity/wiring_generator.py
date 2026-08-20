"""
Main orchestrator for wiring generation.

This module provides the WiringGenerator class that coordinates the entire
wiring generation process using the strategy pattern.
"""

from typing import Dict, Optional

from qualang_tools.wirer import Connectivity

from quam_builder.builder.qop_connectivity.wiring_strategy import WiringStrategy, WiringContext
from quam_builder.builder.qop_connectivity.line_type_registry import (
    LineTypeRegistry,
    ElementCategory,
)
from quam_builder.builder.qop_connectivity.channel_port_factory import ChannelPortFactory
from quam_builder.builder.qop_connectivity.utils import set_nested_value_with_path


class WiringGenerator:
    """Main class for generating wiring configurations.

    This orchestrator coordinates the wiring generation process by:
    1. Receiving a connectivity configuration
    2. Looking up the appropriate strategy for each line type
    3. Generating wiring configurations for each element
    4. Assembling the complete wiring dictionary

    Example:
        # >>> generator = WiringGenerator()
        # >>> wiring = generator.generate(connectivity)
        # >>> # Returns complete wiring dictionary
    """

    def __init__(
        self,
        registry: Optional[LineTypeRegistry] = None,
        port_factory: Optional[ChannelPortFactory] = None,
    ):
        """Initialize the wiring generator.

        Args:
            registry: Optional custom line type registry. If not provided,
                     uses default registry with standard mappings.
            port_factory: Optional custom port factory. If not provided,
                         uses default factory with standard instrument support.
        """
        self.registry = registry or LineTypeRegistry()
        self.port_factory = port_factory or ChannelPortFactory()
        self._strategy_cache: Dict[ElementCategory, WiringStrategy] = {}

    def generate(self, connectivity: Connectivity) -> Dict:
        """Generate wiring configuration from connectivity.

        This is the main entry point for wiring generation. It processes all
        elements in the connectivity configuration and generates a complete
        wiring dictionary.

        Args:
            connectivity: The connectivity configuration containing all quantum
                         elements and their associated channels

        Returns:
            Dictionary containing QUAM-compatible wiring references organized
            by element type, element ID, and line type

        Example:
            # >>> connectivity = Connectivity(...)
            # >>> wiring = generator.generate(connectivity)
            # >>> # Result structure:
            # >>> # {
            # >>> #     "qubits": {
            # >>> #         "q0": {
            # >>> #             "drive": {"opx_output": "#/ports/port1", ...},
            # >>> #             "flux": {...},
            # >>> #         },
            # >>> #         ...
            # >>> #     },
            # >>> #     "qubit_pairs": {...},
            # >>> #     ...
            # >>> # }
        """
        wiring = {}

        for element_id, element in connectivity.elements.items():
            for line_type, channels in element.channels.items():
                # Get the appropriate strategy for this line type
                category = self.registry.get_category(line_type)
                strategy = self._get_strategy(category)

                # Create context for this element/line combination
                context = WiringContext(
                    element_id=element_id,
                    line_type=line_type,
                    channels=channels,
                )

                # Generate wiring for this element/line_type
                element_wiring = strategy.generate_wiring(context)

                # Build the path and merge into main wiring dict
                base_path = strategy.get_base_path(context)
                for key, value in element_wiring.items():
                    full_path = f"{base_path}/{key}"
                    set_nested_value_with_path(wiring, full_path, value)

        return wiring

    def _get_strategy(self, category: ElementCategory) -> WiringStrategy:
        """Get or create a strategy instance for a category.

        Strategies are cached to avoid repeated instantiation. Each category
        gets a single strategy instance that is reused.

        Args:
            category: The element category

        Returns:
            A strategy instance for the category
        """
        if category not in self._strategy_cache:
            strategy_class = self.registry.get_strategy_class(category)
            self._strategy_cache[category] = strategy_class(self.port_factory)
        return self._strategy_cache[category]

    def clear_cache(self) -> None:
        """Clear the strategy cache.

        This can be useful if you need to force recreation of strategies,
        for example after modifying the registry or port factory.
        """
        self._strategy_cache.clear()

    def get_cached_strategies(self) -> Dict[ElementCategory, WiringStrategy]:
        """Get all currently cached strategies.

        Returns:
            Dictionary mapping categories to cached strategy instances

        Example:
            # >>> strategies = generator.get_cached_strategies()
            # >>> for category, strategy in strategies.items():
            # ...     print(f"{category}: {type(strategy).__name__}")
        """
        return self._strategy_cache.copy()
