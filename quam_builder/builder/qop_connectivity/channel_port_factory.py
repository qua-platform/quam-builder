"""
Factory for creating channel port references.

This module provides a centralized factory for converting instrument channels
into QUAM-compatible port references. It handles all instrument types and
can be extended with custom port creators.
"""
from typing import Callable, Tuple, TYPE_CHECKING

from qualang_tools.wirer.instruments.instrument_channel import AnyInstrumentChannel

from quam_builder.builder.qop_connectivity.create_analog_ports import (
    create_octave_port,
    create_mw_fem_port,
    create_lf_opx_plus_port,
    create_external_mixer_reference,
)
from quam_builder.builder.qop_connectivity.create_digital_ports import (
    create_digital_output_port,
)

if TYPE_CHECKING:
    from quam_builder.builder.qop_connectivity.wiring_strategy import WiringContext


# Type alias for port creator functions
PortCreator = Callable[..., Tuple[str, str]]


class ChannelPortFactory:
    """Factory for creating channel port references.

    This factory centralizes the logic for converting instrument channels into
    QUAM-compatible JSON port references. It supports all standard instrument
    types and can be extended with custom creators.

    Example:
        >>> factory = ChannelPortFactory()
        >>> key, ref = factory.create_port_reference(channel, context)
        >>> # key = "opx_output", ref = "#/ports/port1"
    """

    def __init__(self):
        """Initialize the factory with default port creators."""
        self._digital_creator = create_digital_output_port

        # Analog instrument creators
        self._analog_creators = {
            "octave": create_octave_port,
            "mw-fem": create_mw_fem_port,
            "lf-fem": create_lf_opx_plus_port,
            "opx+": create_lf_opx_plus_port,
        }

        # Special instrument creators (need additional context)
        self._special_creators = {
            "external-mixer": create_external_mixer_reference,
        }

        # Instruments that need the full channel list
        self._needs_channel_list = {"lf-fem", "opx+"}

    def create_port_reference(
        self,
        channel: AnyInstrumentChannel,
        context: 'WiringContext',
    ) -> Tuple[str, str]:
        """Create a port reference for the given channel.

        This method dispatches to the appropriate creator function based on
        the channel's instrument type and signal type.

        Args:
            channel: The instrument channel to create a reference for
            context: The wiring context containing element and line type info

        Returns:
            Tuple of (key, reference) where:
                - key is the port identifier (e.g., "opx_output")
                - reference is the JSON path (e.g., "#/ports/port1")

        Raises:
            ValueError: If the instrument type is unknown

        Example:
            >>> channel = Mock(instrument_id="octave", signal_type="analog")
            >>> context = WiringContext(...)
            >>> key, ref = factory.create_port_reference(channel, context)
        """
        # Handle special instruments first (need element_id and line_type)
        if channel.instrument_id in self._special_creators:
            creator = self._special_creators[channel.instrument_id]
            return creator(channel, context.element_id, context.line_type)

        # Handle digital vs analog
        if channel.signal_type == "digital":
            return self._digital_creator(channel)

        # Handle analog instruments
        return self._create_analog_port_reference(channel, context)

    def _create_analog_port_reference(
        self,
        channel: AnyInstrumentChannel,
        context: 'WiringContext',
    ) -> Tuple[str, str]:
        """Create port reference for analog channels.

        Args:
            channel: The analog channel
            context: The wiring context

        Returns:
            Tuple of (key, reference)

        Raises:
            ValueError: If the instrument type is unknown
        """
        if channel.instrument_id not in self._analog_creators:
            raise ValueError(
                f"Unknown instrument type: {channel.instrument_id}. "
                f"Known types: {list(self._analog_creators.keys())}"
            )

        creator = self._analog_creators[channel.instrument_id]

        # Some creators need the full channel list
        if channel.instrument_id in self._needs_channel_list:
            return creator(channel, context.channels)

        return creator(channel)

    def register_instrument(
        self,
        instrument_id: str,
        creator: PortCreator,
        needs_channel_list: bool = False,
    ) -> None:
        """Register a custom port creator for an instrument.

        This allows extending the factory with support for new instrument types
        without modifying the factory code.

        Args:
            instrument_id: The instrument identifier (e.g., "custom-awg")
            creator: The port creator function
            needs_channel_list: Whether this creator needs the full channel list

        Example:
            >>> def create_custom_port(channel, channels=None):
            ...     return ("custom_port", f"#/ports/{channel.port}")
            >>> factory.register_instrument(
            ...     "custom-awg",
            ...     create_custom_port,
            ...     needs_channel_list=True
            ... )
        """
        self._analog_creators[instrument_id] = creator
        if needs_channel_list:
            self._needs_channel_list.add(instrument_id)

    def register_special_instrument(
        self,
        instrument_id: str,
        creator: PortCreator,
    ) -> None:
        """Register a special port creator that needs element and line type.

        Special creators receive (channel, element_id, line_type) instead of
        just the channel.

        Args:
            instrument_id: The instrument identifier
            creator: The port creator function with signature:
                     (channel, element_id, line_type) -> (key, reference)

        Example:
            >>> def create_special_port(channel, element_id, line_type):
            ...     return ("special_port", f"#/special/{element_id}")
            >>> factory.register_special_instrument(
            ...     "special-instrument",
            ...     create_special_port
            ... )
        """
        self._special_creators[instrument_id] = creator

    def get_supported_instruments(self) -> dict[str, list[str]]:
        """Get all supported instrument types.

        Returns:
            Dictionary categorizing supported instruments:
                - analog: Standard analog instruments
                - special: Instruments needing special handling
                - needs_channel_list: Instruments that need full channel list

        Example:
            >>> factory.get_supported_instruments()
            {
                'analog': ['octave', 'mw-fem', 'lf-fem', 'opx+'],
                'special': ['external-mixer'],
                'needs_channel_list': ['lf-fem', 'opx+']
            }
        """
        return {
            'analog': list(self._analog_creators.keys()),
            'special': list(self._special_creators.keys()),
            'needs_channel_list': list(self._needs_channel_list),
        }
