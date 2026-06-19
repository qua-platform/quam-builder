from typing import Dict

from quam.components.channels import MWChannel, StickyChannelAddon

from quam_builder.builder.qop_connectivity.channel_ports import mw_out_channel_ports
from quam_builder.builder.qop_connectivity.get_digital_outputs import (
    get_digital_outputs,
)
from quam_builder.architecture.superconducting.components.twpa import TWPA


def add_twpa_pump_component(
    twpa: TWPA,
    wiring_path: str,
    ports: Dict[str, str],
    *,
    attr: str = "pump",
    sticky: bool = True,
):
    """Adds a pump channel to a TWPA based on the provided wiring path and ports.

    Mirrors ``add_transmon_drive_component`` but builds a plain ``MWChannel`` (matching the
    known-good KRISS TWPA state): the continuous ``pump`` element is sticky, while the
    calibration ``pump_`` element is not. ``attr`` selects which TWPA field to populate
    ("pump" or "pump_"). Frequencies/amplitudes are left at defaults here and seeded later by
    the populate script.

    Args:
        twpa (TWPA): The TWPA to which the pump channel will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their references.
        attr (str): The TWPA attribute to set ("pump" or "pump_").
        sticky (bool): Whether the channel is sticky (continuous pump) or not (calibration).

    Raises:
        ValueError: If the port keys do not match the MW output mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel (the TWPA pump line). Plain MWChannel as in the KRISS state.
        channel = MWChannel(
            opx_output=f"{wiring_path}/opx_output",
            intermediate_frequency=300e6,
            upconverter=1,
            sticky=StickyChannelAddon(duration=200, enabled=True) if sticky else None,
            digital_outputs=digital_outputs,
        )
        setattr(twpa, attr, channel)
    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for TWPA ports: {ports}"
        )
