from quam.components import DigitalOutputChannel
from quam.components.channels import FEMDigitalOutputPort, OPXPlusDigitalOutputPort


def get_digital_outputs(
    wiring_path: str, ports: dict[str, str], digital_marker_name: str = "octave_switch"
) -> dict[str, DigitalOutputChannel]:
    """Generates a dictionary of digital output channels based on the provided wiring path and ports.

    Args:
        wiring_path (str): The path to the wiring configuration.
        ports (dict[str, str]): A dictionary mapping port names to their respective configurations.
        digital_marker_name (str): The name of the digital marker. Default is "octave_switch".

    Returns:
        dict[str, DigitalOutputChannel]: A dictionary of digital output channels.
    """
    digital_outputs = dict()
    for i, item in enumerate([port for port in ports if "digital_output" in port]):
        if digital_marker_name == "octave_switch":
            if type(DigitalOutputChannel(opx_output=f"{wiring_path}/{item}").opx_output) == FEMDigitalOutputPort:
                digital_outputs[f"{digital_marker_name}_{i}"] = DigitalOutputChannel(
                    opx_output=f"{wiring_path}/{item}",
                    delay=14,  # 14ns for QOP333 and above
                    buffer=13,  # 13ns for QOP333 and above
                )
            elif type(DigitalOutputChannel(opx_output=f"{wiring_path}/{item}").opx_output) == OPXPlusDigitalOutputPort:
                digital_outputs[f"{digital_marker_name}_{i}"] = DigitalOutputChannel(
                    opx_output=f"{wiring_path}/{item}",
                    delay=57,  # 57ns for QOP222 and above
                    buffer=18,  # 18ns for QOP222 and above
                )
        else:
            digital_outputs[f"{digital_marker_name}_{i}"] = DigitalOutputChannel(
                opx_output=f"{wiring_path}/{item}",
                delay=0,
                buffer=0,
            )

    return digital_outputs
