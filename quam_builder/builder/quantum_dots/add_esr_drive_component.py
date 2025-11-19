from typing import Dict, Union
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

from quam_builder.architecture.quantum_dots.qubit import (
LDQubit
)

from qualang_tools.addons.calibration.calibrations import unit


u = unit(coerce_to_integer=True)


def add_esr_drive_component(
    qubit: Union[LDQubit],
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a drive component to a quantum dot qubit based on the provided wiring path and ports.

    Args:
        qubit (Union[LDQubit,]): The ldv qubit to which the drive component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in iq_out_channel_ports):
        # LF-FEM & Octave or OPX+ & Octave
        qubit.xy = XYDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            RF_frequency=None,
            digital_outputs=digital_outputs,
        )

        RF_output = qubit.xy.frequency_converter_up
        RF_output.channel = qubit.xy.get_reference()
        RF_output.output_mode = "always_on"  # "triggered"

    elif all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel
        qubit.xy = XYDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            digital_outputs=digital_outputs,
            RF_frequency=None,
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
