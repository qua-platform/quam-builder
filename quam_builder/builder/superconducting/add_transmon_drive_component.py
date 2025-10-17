from typing import Dict, Union
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_out_channel_ports,
    mw_out_channel_ports,
)
from quam_builder.architecture.superconducting.components.xy_drive import (
    XYDriveIQ,
    XYDriveMW,
)
from quam_builder.architecture.superconducting.components.xy_detuned_drive import (
    XYDetunedDriveIQ,
    XYDetunedDriveMW,
)
from quam_builder.builder.qop_connectivity.get_digital_outputs import (
    get_digital_outputs,
)
from quam_builder.architecture.superconducting.qubit import (
    FixedFrequencyTransmon,
    FluxTunableTransmon,
)
from quam_builder.architecture.superconducting.qubit import AnyTransmon
from qualang_tools.addons.calibration.calibrations import unit


u = unit(coerce_to_integer=True)


def add_transmon_drive_component(
    transmon: Union[FixedFrequencyTransmon, FluxTunableTransmon],
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a drive component to a transmon qubit based on the provided wiring path and ports.

    Args:
        transmon (Union[FixedFrequencyTransmon, FluxTunableTransmon]): The transmon qubit to which the drive component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in iq_out_channel_ports):
        # LF-FEM & Octave or OPX+ & Octave
        transmon.xy = XYDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            RF_frequency=None,
            digital_outputs=digital_outputs,
        )

        RF_output = transmon.xy.frequency_converter_up
        RF_output.channel = transmon.xy.get_reference()
        RF_output.output_mode = "always_on"  # "triggered"

    elif all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel
        transmon.xy = XYDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            digital_outputs=digital_outputs,
            RF_frequency=None,
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )


def add_transmon_detuned_drive_component(
    transmon: AnyTransmon,
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a drive component to a transmon qubit based on the provided wiring path and ports.

    Args:
        transmon (Union[FixedFrequencyTransmon, FluxTunableTransmon]): The transmon qubit to which the drive component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in iq_out_channel_ports):
        # LF-FEM & Octave or OPX+ & Octave
        transmon.xy_detuned = XYDetunedDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            xy_RF_frequency="#../xy/inferred_RF_frequency",
            xy_intermediate_frequency="#../xy/inferred_intermediate_frequency",
            digital_outputs=digital_outputs,
        )

        RF_output = transmon.xy.frequency_converter_up
        RF_output.channel = transmon.xy.get_reference()
        RF_output.output_mode = "always_on"  # "triggered"

    elif all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel
        transmon.xy_detuned = XYDetunedDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            digital_outputs=digital_outputs,
            xy_RF_frequency="#../xy/inferred_RF_frequency",
            xy_intermediate_frequency="#../xy/inferred_intermediate_frequency",
            detuning=None,
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
