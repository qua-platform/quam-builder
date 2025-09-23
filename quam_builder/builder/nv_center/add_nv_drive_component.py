from typing import Dict, Union

from qualang_tools.addons.calibration.calibrations import unit

from quam_builder.architecture.nv_center.components.xy_drive import (
    XYDriveIQ,
    XYDriveMW,
)
from quam_builder.architecture.nv_center.qubit import NVCenter
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_out_channel_ports,
    mw_out_channel_ports,
)
from quam_builder.builder.qop_connectivity.get_digital_outputs import (
    get_digital_outputs,
)

u = unit(coerce_to_integer=True)


def add_nv_drive_component(
    nv_center: NVCenter,
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a drive component to an nv_center qubit based on the provided wiring path and ports.

    Args:
        nv_center (NVCenter): The nv_center qubit to which the drive component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in iq_out_channel_ports):
        # LF-FEM & Octave or OPX+ & Octave
        nv_center.xy = XYDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            RF_frequency=None,
            digital_outputs=digital_outputs,
        )

        RF_output = nv_center.xy.frequency_converter_up
        RF_output.channel = nv_center.xy.get_reference()
        RF_output.output_mode = "always_on"  # "triggered"

    elif all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel
        nv_center.xy = XYDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            digital_outputs=digital_outputs,
            RF_frequency=None,
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
