from typing import Dict, Optional

from qualang_tools.addons.calibration.calibrations import unit

from quam_builder.architecture.nv_center.components.laser import (
    LaserLFAnalog,
    LaserLFDigital,
    LaserControl,
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

    nv_center.laser = LaserControl()

    # If we have a digital trigger path for the laser
    if "digital_output" in ports:
        nv_center.laser.trigger = LaserLFDigital(
            id=None,
            digital_outputs=digital_outputs,
        )

    # If we have an analog control path for laser power
    if "opx_output" in ports:
        nv_center.laser.power = LaserLFAnalog(
            id=None,
            opx_output=f"{wiring_path}/opx_output",
        )

    if nv_center.laser.trigger is None and nv_center.laser.power is None:
        raise ValueError(
            "Laser wiring must provide at least one of: 'opx_output' (analog) "
            "or 'digital_output' (digital)."
        )
