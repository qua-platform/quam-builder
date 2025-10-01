from typing import Dict, Literal

from qualang_tools.addons.calibration.calibrations import unit
from quam.components.channels import TimeTaggingAddon

from quam_builder.architecture.nv_center.components.spcm import SPCM
from quam_builder.architecture.nv_center.qubit import AnyNVCenter

u = unit(coerce_to_integer=True)


def add_nv_spcm_component(
    nv_center: AnyNVCenter, wiring_path: str, ports: Dict[str, str], name: str = "spcm"
):
    """Adds an SPCM component to an nv_center qubit based on the provided wiring path and ports.

    Args:
        nv_center (AnyNVCenter): The nv_center qubit to which the SPCM component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    time_of_flight: int = 32  # 4ns above default so that it appears in state.json

    signal_threshold: float = 800 / 4096  # The signal threshold in volts
    signal_polarity: Literal["above", "below"] = (
        "below"  # The polarity of the signal threshold
    )
    derivative_threshold: float = 300 / 4096  # The derivative threshold in volts/ns
    derivative_polarity: Literal["above", "below"] = (
        "below"  # The polarity of the derivative threshold
    )
    enabled: bool = True

    if "opx_input" and "opx_output" in ports:
        time_tagging = TimeTaggingAddon(
            signal_threshold=signal_threshold,
            signal_polarity=signal_polarity,
            derivative_threshold=derivative_threshold,
            derivative_polarity=derivative_polarity,
            enabled=enabled,
        )
        spcm = SPCM(
            opx_output=f"{wiring_path}/opx_output",
            opx_input=f"{wiring_path}/opx_input",
            opx_input_offset=0.0,
            time_of_flight=time_of_flight,
            time_tagging=time_tagging,
        )
        setattr(nv_center, name, spcm)

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
