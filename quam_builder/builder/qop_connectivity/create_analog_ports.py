from typing import List
from qualang_tools.wirer.connectivity.element import QubitReference
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from qualang_tools.wirer.instruments.instrument_channel import AnyInstrumentChannel
from quam_builder.builder.qop_connectivity.paths import (
    OCTAVES_BASE_JSON_PATH,
    PORTS_BASE_JSON_PATH,
    MIXERS_BASE_JSON_PATH,
)


def create_external_mixer_reference(
    channel: AnyInstrumentChannel, element_id: QubitReference, line_type: WiringLineType
) -> (str, str):
    """Generates a key/JSON reference pair from which a QUAM port can be created for a single Octave channel.

    Args:
        channel (AnyInstrumentChannel): The instrument channel for which the reference is created.
        element_id (QubitReference): The ID of the qubit element.
        line_type (WiringLineType): The type of wiring line.

    Returns:
        (str, str): A tuple containing the key and the JSON reference.

    Raises:
        ValueError: If the IO type of the channel is unknown.
    """
    if channel.io_type == "output":
        key = "frequency_converter_up"
    elif channel.io_type == "input":
        key = "frequency_converter_down"
    else:
        raise ValueError(f"Unknown IO type {channel.io_type}")

    reference = MIXERS_BASE_JSON_PATH
    reference += f"/mixer{channel.con}_{element_id}.{line_type.value}"

    return key, reference


def create_octave_port(channel: AnyInstrumentChannel) -> (str, str):
    """Generates a key/JSON reference pair from which a QUAM port can be created for a single Octave channel.

    Args:
        channel (AnyInstrumentChannel): The instrument channel for which the reference is created.

    Returns:
        (str, str): A tuple containing the key and the JSON reference.

    Raises:
        ValueError: If the IO type of the channel is unknown.
    """
    if channel.io_type == "output":
        key = "frequency_converter_up"
    elif channel.io_type == "input":
        key = "frequency_converter_down"
    else:
        raise ValueError(f"Unknown IO type {channel.io_type}")

    reference = OCTAVES_BASE_JSON_PATH
    reference += f"/oct{channel.con}"
    reference += f"/RF_{channel.io_type}s"
    reference += f"/{channel.port}"

    return key, reference


def create_mw_fem_port(channel: AnyInstrumentChannel) -> (str, str):
    """Generates a key/JSON reference pair from which a QUAM port can be created for a mw-fem channel.

    Args:
        channel (AnyInstrumentChannel): The instrument channel for which the reference is created.

    Returns:
        (str, str): A tuple containing the key and the JSON reference.
    """
    reference = PORTS_BASE_JSON_PATH
    reference += f"/mw_{channel.io_type}s"
    reference += f"/con{channel.con}"
    reference += f"/{channel.slot}"
    reference += f"/{channel.port}"

    key = f"opx_{channel.io_type}"

    return key, reference


def create_lf_opx_plus_port(
    channel: AnyInstrumentChannel, channels: List[AnyInstrumentChannel]
) -> (str, str):
    """Generates a key/JSON reference pair from which a QUAM port can be created for a single non-octave channel.

    Args:
        channel (AnyInstrumentChannel): The instrument channel for which the reference is created.
        channels (List[AnyInstrumentChannel]): A list of all instrument channels.

    Returns:
        (str, str): A tuple containing the key and the JSON reference.

    Raises:
        NotImplementedError: If the number of channels with the same type is not 1 or 2.
    """
    reference = PORTS_BASE_JSON_PATH
    reference += f"/analog_{channel.io_type}s"
    if channel.instrument_id == "opx+":
        reference += f"/con{channel.con}"
        reference += f"/{channel.port}"
    else:
        reference += f"/con{channel.con}"
        reference += f"/{channel.slot}"
        reference += f"/{channel.port}"

    channels_with_same_type = get_objects_with_same_type(channel, channels)
    if len(channels_with_same_type) == 1:
        key = f"opx_{channel.io_type}"
    elif len(channels_with_same_type) == 2:
        if channel.port == min(
            [
                channel_with_same_type.port
                for channel_with_same_type in channels_with_same_type
            ]
        ):
            key = f"opx_{channel.io_type}_I"
        else:
            key = f"opx_{channel.io_type}_Q"
    else:
        raise NotImplementedError(
            f"Can't handle when channel number is not 1 or 2, got {len(channels_with_same_type)}"
        )

    return key, reference


def get_objects_with_same_type(obj, lst):
    """Returns all objects in the list that have the same type as the given object.

    Args:
        obj: The object to compare types with.
        lst: The list of objects to search through.

    Returns:
        List: A list of objects with the same type as the given object.
    """
    return [item for item in lst if isinstance(item, type(obj))]
