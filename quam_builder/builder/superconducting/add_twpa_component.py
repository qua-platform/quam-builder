from typing import Dict
from quam.components.channels import IQChannel, MWChannel
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_out_channel_ports,
    mw_out_channel_ports,
)
from quam_builder.builder.qop_connectivity.get_digital_outputs import (
    get_digital_outputs,
)
from quam_builder.architecture.superconducting.components.twpa import TWPA


def add_twpa_pump_component(
    twpa: TWPA,
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a pump component to a TWPA based on the provided wiring path and ports.

    The TWPA pump is configured as a sticky element for continuous output, used for
    parametric amplification of readout signals. The pump channel is typically an RF
    output on an MW-FEM.

    Args:
        twpa (TWPA): The TWPA to which the pump component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in iq_out_channel_ports):
        # LF-FEM & Octave or OPX+ & Octave
        twpa.pump = IQChannel(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            intermediate_frequency=0,
            digital_outputs=digital_outputs,
        )

        RF_output = twpa.pump.frequency_converter_up
        RF_output.channel = twpa.pump.get_reference()
        RF_output.output_mode = "always_on"

    elif all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel - pump is a sticky element for continuous output
        twpa.pump = MWChannel(
            opx_output=f"{wiring_path}/opx_output",
            intermediate_frequency=0,
            digital_outputs=digital_outputs,
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
