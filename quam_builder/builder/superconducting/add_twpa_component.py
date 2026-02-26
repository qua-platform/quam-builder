from typing import Dict, Union
from quam.components.channels import StickyChannelAddon
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_out_channel_ports,
    mw_out_channel_ports,
)
from quam_builder.architecture.superconducting.components.twpa import TWPA, XYDriveMW, XYDriveIQ
from quam_builder.builder.qop_connectivity.get_digital_outputs import (
    get_digital_outputs,
)
from quam_builder.architecture.superconducting.qubit import (
    FixedFrequencyTransmon,
    FluxTunableTransmon,
)
from qualang_tools.addons.calibration.calibrations import unit


u = unit(coerce_to_integer=True)


def add_twpa_pump_component(
    twpa: TWPA,
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds an amplification pump component to a TWPA based on the provided wiring path and ports.

    Args:
        twpa (TWPA): The TWPA component to which the amplification pump component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in iq_out_channel_ports):
        # LF-FEM & Octave or OPX+ & Octave
        twpa.pump = XYDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            sticky=StickyChannelAddon(duration=100, digital=False),
            RF_frequency=None,
            digital_outputs=digital_outputs,
        )
        twpa.pump_ = XYDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            RF_frequency=None,
            digital_outputs=digital_outputs,
        )

        RF_output = twpa.pump.frequency_converter_up
        RF_output.channel = twpa.pump.get_reference()
        RF_output.output_mode = "always_on"  # "triggered"

    elif all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel
        twpa.pump = XYDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            sticky=StickyChannelAddon(duration=100, digital=False),
            digital_outputs=digital_outputs,
            RF_frequency=None,
        )
        twpa.pump_ = XYDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            sticky=StickyChannelAddon(duration=100, digital=False),
            digital_outputs=digital_outputs,
            RF_frequency=None,
        )

    else:
        raise ValueError(f"Unimplemented mapping of port keys to channel for ports: {ports}")


def add_twpa_isolation_component(
    twpa: TWPA,
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds an isolation pump component to a TWPA based on the provided wiring path and ports.

    Args:
        twpa (TWPA): The TWPA component to which the isolation pump component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports)

    if all(key in ports for key in iq_out_channel_ports):
        # LF-FEM & Octave or OPX+ & Octave
        twpa.isolation = XYDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            sticky=StickyChannelAddon(duration=100, digital=False),
            RF_frequency=None,
            digital_outputs=digital_outputs,
        )
        twpa.isolation_ = XYDriveIQ(
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            frequency_converter_up=f"{wiring_path}/frequency_converter_up",
            RF_frequency=None,
            digital_outputs=digital_outputs,
        )

        RF_output = twpa.pump.frequency_converter_up
        RF_output.channel = twpa.pump.get_reference()
        RF_output.output_mode = "always_on"  # "triggered"

    elif all(key in ports for key in mw_out_channel_ports):
        # MW-FEM single channel
        twpa.isolation = XYDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            sticky=StickyChannelAddon(duration=100, digital=False),
            digital_outputs=digital_outputs,
            RF_frequency=None,
        )
        twpa.isolation_ = XYDriveMW(
            opx_output=f"{wiring_path}/opx_output",
            sticky=StickyChannelAddon(duration=100, digital=False),
            digital_outputs=digital_outputs,
            RF_frequency=None,
        )

    else:
        raise ValueError(f"Unimplemented mapping of port keys to channel for ports: {ports}")
