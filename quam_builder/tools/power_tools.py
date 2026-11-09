from typing import Optional

import numpy as np
from qualibration_libs.core.trackable_object import TrackableObject

from qualang_tools.units import unit
from quam.components import IQChannel
from quam.components.channels import MWChannel

__all__ = [
    "set_output_power_mw_channel",
    "get_output_power_mw_channel",
    "set_output_power_iq_channel",
    "get_output_power_iq_channel",
    "calculate_voltage_scaling_factor",
]


def set_output_power_mw_channel(
    channel: MWChannel,
    power_in_dbm: float,
    operation: str,
    full_scale_power_dbm: Optional[int] = None,
    max_amplitude: Optional[float] = 1,
):
    """
    Set an MW-FEM operation to `power_in_dbm` by choosing a full-scale power and
    scaling the operation amplitude.

    The full-scale power is an integer in [-11, 18] dBm. The search starts at
    `full_scale_power_dbm` when given, otherwise at the channel's current
    `opx_output.full_scale_power_dbm`, and increases in 1 dB steps while the
    voltage scaling factor `10 ** ((power_in_dbm - full_scale_power_dbm) / 20)`
    is greater than `max_amplitude`. The chosen full-scale power is written to
    `channel.opx_output.full_scale_power_dbm` and the scaling factor to
    `channel.operations[operation].amplitude`.

    Parameters:
        channel: A MW-FEM channel.
        power_in_dbm (float): Target output power in dBm.
        operation (str): Operation whose amplitude is set.
        full_scale_power_dbm (Optional[int]): Starting full-scale power in dBm.
            When omitted, the search starts at the channel's current full-scale
            power. When given, it must be at least `power_in_dbm`; the search
            can still raise it if the resulting amplitude exceeds `max_amplitude`.
        max_amplitude (Optional[float]): Maximum allowed operation amplitude.
            Defaults to 1.

    Returns:
        dict: `full_scale_power_dbm` and `amplitude` written to the channel.

    Raises:
        ValueError: If a given `full_scale_power_dbm` is below `power_in_dbm`,
            or if the required full-scale power is outside [-11, 18] dBm.
    """
    min_full_scale_power_dbm = -11
    max_full_scale_power_dbm = 18
    allowed_full_scale_power_in_dbm_values = np.arange(
        min_full_scale_power_dbm, max_full_scale_power_dbm + 1, 1
    ).astype(int)

    if full_scale_power_dbm is None:
        full_scale_power_dbm = channel.opx_output.full_scale_power_dbm
    elif power_in_dbm > full_scale_power_dbm:
        raise ValueError(
            f"Can't fix full_scale_power_dbm to {full_scale_power_dbm} dBm since it is "
            f"less than the target power {power_in_dbm} dBm."
        )

    while (
        current_amplitude := calculate_voltage_scaling_factor(
            fixed_power_dBm=full_scale_power_dbm,
            target_power_dBm=power_in_dbm,
        )
    ) > max_amplitude:
        full_scale_power_dbm = full_scale_power_dbm + 1

    if full_scale_power_dbm not in allowed_full_scale_power_in_dbm_values:
        raise ValueError(
            f"Expected full_scale_power_dbm to be in range [{min_full_scale_power_dbm}, {max_full_scale_power_dbm}] in steps of 1 dB, got {full_scale_power_dbm}."
        )

    if isinstance(channel, MWChannel):
        opx_output = channel.opx_output
        channel_name = channel.name
    elif isinstance(channel, TrackableObject):
        opx_output = channel._obj.opx_output
        channel_name = channel._obj.name
    else:
        raise ValueError(f"Expected a MWChannel or TrackableObject, got {type(channel)}")
    port_id = (opx_output.controller_id, opx_output.fem_id, opx_output.port_id)
    print(
        f"Voltage scaling factor: {current_amplitude:.5f} @ {full_scale_power_dbm} dBm (target: {power_in_dbm} dBm) on {channel_name} - {port_id}"
    )

    channel.operations[operation].amplitude = current_amplitude
    channel.opx_output.full_scale_power_dbm = full_scale_power_dbm

    return {
        "full_scale_power_dbm": full_scale_power_dbm,
        "amplitude": current_amplitude,
    }


def get_output_power_mw_channel(channel: MWChannel, operation, Z=50) -> float:
    """
    Calculate the output power in dBm for a given MW-FEM channel.

    Parameters:
        channel: A MW-FEM channel.
        operation (str): The name of the operation to retrieve the amplitude.
        Z (float): The impedance in ohms. Default is 50 ohms.

    Returns:
        float: The output power in dBm.

    The function calculates the output power based on the full-scale power in dBm and the amplitude of the specified operation.
    """
    power = channel.opx_output.full_scale_power_dbm
    amplitude = channel.operations[operation].amplitude
    x_mw = 10 ** (power / 10)
    x_v = amplitude * np.sqrt(2 * Z * x_mw / 1000)
    return 10 * np.log10(((x_v / np.sqrt(2)) ** 2 * 1000) / Z)


def set_output_power_iq_channel(
    channel: IQChannel,
    power_in_dbm: float,
    gain: Optional[int] = None,
    max_amplitude: Optional[float] = None,
    Z: int = 50,
    operation: Optional[str] = "readout",
):
    """
    Configure the output power for a specific operation by setting the gain or amplitude.
    Note that exactly one of `gain` or `amplitude` must be specified and the function calculates
    the other parameter specifically to meet the desired output power.

    Parameters:
        channel (IQChannel): The IQ channel.
        power_in_dbm (float): Desired output power in dBm.
        gain (Optional[int]): Optional Octave gain in dB to set, must be within [-20, 20].
        max_amplitude (Optional[float]): Optional pulse amplitude in volts, must be within [-0.5, 0.5).
        Z (int): Impedance in ohms, default is 50.
        operation (Optional[str]): Name of the operation to configure, default is "readout".

    Raises:
        RuntimeError: If neither nor both `gain` and `amplitude` are specified.
        ValueError: If `gain` or `amplitude` is outside their valid ranges.

    """

    u = unit(coerce_to_integer=True)
    amplitude = None

    if (max_amplitude is None) == (gain is None):
        raise RuntimeError("Either or gain or amplitude must be specified.")
    elif max_amplitude is not None:
        gain = round((power_in_dbm - u.volts2dBm(max_amplitude, Z=Z)) * 2) / 2
        gain = max(min(gain, 20), -20)
        amplitude = u.dBm2volts(power_in_dbm - gain)
    elif gain is not None:
        amplitude = u.dBm2volts(power_in_dbm - channel.frequency_converter_up.gain)

    if not -20 <= gain <= 20:
        raise ValueError(f"Expected Octave gain within [-20:0.5:20] dB, got {gain} dB.")

    if not -0.5 <= max_amplitude < 0.5:
        raise ValueError("The OPX+ pulse amplitude must be within [-0.5, 0.5) V.")

    print(f"Setting the Octave gain to {gain} dB")
    print(f"Setting the {operation} amplitude to {amplitude} V")

    channel.frequency_converter_up.gain = gain
    channel.operations[operation].amplitude = amplitude

    return {"gain": gain, "amplitude": max_amplitude}


def get_output_power_iq_channel(channel: IQChannel, operation, Z=50) -> float:
    """
    Calculate the output power in dBm for a given IQ channel.

    Parameters:
        channel (IQChannel): The IQ channel.
        operation (str): The name of the operation to retrieve the amplitude.
        Z (float): The impedance in ohms. Default is 50 ohms.

    Returns:
        float: The output power in dBm.

    The function calculates the output power based on the amplitude of the specified operation and the gain of the frequency up-converter.
    It converts the amplitude to dBm using the specified impedance.
    """
    u = unit(coerce_to_integer=True)
    amplitude = channel.operations[operation].amplitude
    return channel.frequency_converter_up.gain + u.volts2dBm(amplitude, Z=Z)


def calculate_voltage_scaling_factor(fixed_power_dBm: float, target_power_dBm: float):
    """
    Calculate the voltage scaling factor required to scale fixed power to target power.

    Parameters:
        fixed_power_dBm (float): The fixed power in dBm.
        target_power_dBm (float): The target power in dBm.

    Returns:
        float: The voltage scaling factor.
    """
    power_difference = target_power_dBm - fixed_power_dBm
    voltage_scaling_factor = 10 ** (power_difference / 20)

    return voltage_scaling_factor
