from typing import Dict

from qualang_tools.addons.calibration.calibrations import unit

from quam_builder.architecture.nv_center.components.laser import (
    LaserLFAnalog,
    LaserLFDigital,
)
from quam_builder.architecture.nv_center.qubit import AnyNVCenter
from quam_builder.builder.qop_connectivity.get_digital_outputs import (
    get_digital_outputs,
)

u = unit(coerce_to_integer=True)


def add_nv_laser_component(
    nv_center: AnyNVCenter, wiring_path: str, ports: Dict[str, str]
):
    """Adds a laser component to a nv_center qubit based on the provided wiring path and ports.

    Args:
        nv_center (AnyNVCenter): The nv_center qubit to which the laser component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    digital_outputs = get_digital_outputs(wiring_path, ports, "laser_switch")

    laser_length = 1 * u.us

    if "opx_output" in ports:
        nv_center.laser = LaserLFAnalog(
            opx_output=f"{wiring_path}/opx_output",
            laser_length=laser_length,
            digital_outputs=digital_outputs
        )
    elif "digital_output" in ports:
        nv_center.laser = LaserLFDigital(
            digital_outputs=digital_outputs, laser_length=laser_length
        )
    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
