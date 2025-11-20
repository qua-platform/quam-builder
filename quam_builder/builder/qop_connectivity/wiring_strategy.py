"""
Base strategy classes for wiring generation.

This module provides the abstract base class and context for different
wiring strategies used in quantum element configuration.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, TYPE_CHECKING

from qualang_tools.wirer.connectivity.element import ElementReference
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from qualang_tools.wirer.instruments.instrument_channel import AnyInstrumentChannel

if TYPE_CHECKING:
    from quam_builder.builder.qop_connectivity.channel_port_factory import ChannelPortFactory


@dataclass
class WiringContext:
    """Context information for wiring generation.

    Attributes:
        element_id: The quantum element identifier (qubit, qubit pair, etc.)
        line_type: The type of wiring line (drive, flux, coupler, etc.)
        channels: List of instrument channels for this element/line combination
    """
    element_id: ElementReference
    line_type: WiringLineType
    channels: List[AnyInstrumentChannel]


class WiringStrategy(ABC):
    """Base strategy for generating wiring configurations.

    This abstract base class defines the interface for all wiring strategies.
    Each concrete strategy handles a specific type of quantum element
    (qubit, qubit pair, global element, readout).
    """

    def __init__(self, port_factory: 'ChannelPortFactory'):
        """Initialize the strategy with a port factory.

        Args:
            port_factory: Factory for creating port references from channels
        """
        self.port_factory = port_factory

    @abstractmethod
    def get_base_path(self, context: WiringContext) -> str:
        """Returns the base path for this element type.

        Args:
            context: The wiring context containing element and line type info

        Returns:
            Base path string (e.g., "qubits/q0/drive")
        """
        pass

    @abstractmethod
    def get_additional_references(self, context: WiringContext) -> Dict[str, str]:
        """Returns any additional references needed.

        Some element types need additional references beyond port mappings.
        For example, qubit pairs need control_qubit and target_qubit references.

        Args:
            context: The wiring context

        Returns:
            Dictionary of additional key-value references
        """
        pass

    def generate_wiring(self, context: WiringContext) -> Dict[str, str]:
        """Main method to generate wiring dictionary.

        This method coordinates the wiring generation process:
        1. Gets additional references (if any)
        2. Processes each channel to create port references
        3. Returns the complete wiring dictionary

        Args:
            context: The wiring context

        Returns:
            Dictionary mapping keys to QUAM-compatible JSON references
        """
        wiring = self.get_additional_references(context)

        for channel in context.channels:
            if self._should_process_channel(channel):
                key, reference = self.port_factory.create_port_reference(
                    channel, context
                )
                wiring[key] = reference

        return wiring

    def _should_process_channel(self, channel: AnyInstrumentChannel) -> bool:
        """Determines if a channel should be processed.

        By default, filters out digital input channels as they are typically
        not included in the wiring configuration.

        Args:
            channel: The channel to check

        Returns:
            True if the channel should be processed, False otherwise
        """
        return not (channel.signal_type == "digital" and channel.io_type == "input")
