from typing import Dict
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_out_channel_ports,
    mw_out_channel_ports,
)
from quam_builder.architecture.superconducting.components.xy_drive import (
    XYDriveIQ,
    XYDriveMW,
)
from quam_builder.builder.qop_connectivity.get_digital_outputs import (
    get_digital_outputs,
)
from quam_builder.architecture.superconducting.qubit import BosonicMode


def add_cavity_drive_component(
    cavity: BosonicMode,
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a drive component to a bosonic cavity based on the provided wiring path and ports.

    Bosonic cavities (harmonic oscillators) are controlled via an XY drive, similar to
    transmon qubits. This function configures the appropriate drive type (IQ or MW)
    based on the available hardware ports.

    Args:
        cavity (BosonicMode): The bosonic cavity to which the drive component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in iq_out_channel_ports):
        # LF-FEM & Octave or OPX+ & Octave
        cavity.xy = XYDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            RF_frequency=None,
            digital_outputs=digital_outputs,
        )

        RF_output = cavity.xy.frequency_converter_up
        RF_output.channel = cavity.xy.get_reference()
        RF_output.output_mode = "always_on"

    elif all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel
        cavity.xy = XYDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            digital_outputs=digital_outputs,
            RF_frequency=None,
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
