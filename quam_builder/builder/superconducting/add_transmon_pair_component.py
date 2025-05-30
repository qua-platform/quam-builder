from typing import Dict, Union
from quam_builder.architecture.superconducting.components.cross_resonance import (
    CrossResonanceIQ,
    CrossResonanceMW,
)
from quam_builder.architecture.superconducting.components.zz_drive import (
    ZZDriveIQ,
    ZZDriveMW,
)
from quam_builder.architecture.superconducting.qubit_pair.flux_tunable_transmon_pair import (
    TunableCoupler,
)
from quam_builder.architecture.superconducting.qubit_pair import (
    FixedFrequencyTransmonPair,
    FluxTunableTransmonPair,
)


def add_transmon_pair_tunable_coupler_component(
    transmon_pair: Union[FixedFrequencyTransmonPair, FluxTunableTransmonPair],
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a tunable coupler component to a transmon qubit pair based on the provided wiring path and ports.

    Args:
        transmon_pair (Union[FixedFrequencyTransmonPair, FluxTunableTransmonPair]): The transmon qubit pair to which the tunable coupler component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    if "opx_output" in ports:
        qubit_control_name = ports["control_qubit"].name
        qubit_target_name = ports["target_qubit"].name
        qubit_pair_name = f"{qubit_control_name}_{qubit_target_name}"
        coupler_name = f"coupler_{qubit_pair_name}"

        transmon_pair.coupler = TunableCoupler(
            id=coupler_name, opx_output=f"{wiring_path}/opx_output"
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )


def add_transmon_pair_cross_resonance_component(
    transmon_pair: Union[FixedFrequencyTransmonPair, FluxTunableTransmonPair],
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a cross resonance component to a transmon qubit pair based on the provided wiring path and ports.

    Args:
        transmon_pair (Union[FixedFrequencyTransmonPair, FluxTunableTransmonPair]): The transmon qubit pair to which the cross resonance component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    qubit_control_name = ports["control_qubit"].name
    qubit_target_name = ports["target_qubit"].name
    qubit_pair_name = f"{qubit_control_name}_{qubit_target_name}"
    cross_resonance_name = f"cr_{qubit_pair_name}"
    if "opx_output_I" in ports.keys() and "opx_output_Q" in ports.keys():
        transmon_pair.cross_resonance = CrossResonanceIQ(
            id=cross_resonance_name,
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            intermediate_frequency="#./inferred_intermediate_frequency",
            frequency_converter_up=ports.data["control_qubit"]
            + "/xy/frequency_converter_up",
            target_qubit_LO_frequency=ports.data["target_qubit"] + "/xy/LO_frequency",
            target_qubit_IF_frequency=ports.data["target_qubit"]
            + "/xy/intermediate_frequency",
        )

    elif "opx_output" in ports.keys():
        transmon_pair.cross_resonance = CrossResonanceMW(
            id=cross_resonance_name, opx_output=f"{wiring_path}/opx_output"
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )


def add_transmon_pair_zz_drive_component(
    transmon_pair: Union[FixedFrequencyTransmonPair, FluxTunableTransmonPair],
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a ZZ drive component to a transmon qubit pair based on the provided wiring path and ports.

    Args:
        transmon_pair (Union[FixedFrequencyTransmonPair, FluxTunableTransmonPair]): The transmon qubit pair to which the ZZ drive component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    qubit_control_name = ports["control_qubit"].name
    qubit_target_name = ports["target_qubit"].name
    qubit_pair_name = f"{qubit_control_name}_{qubit_target_name}"
    zz_drive_name = f"zz_{qubit_pair_name}"
    if "opx_output_I" in ports.keys() and "opx_output_Q" in ports.keys():
        transmon_pair.zz_drive = ZZDriveIQ(
            id=zz_drive_name,
            opx_output_I=f"{wiring_path}/opx_output_I",
            opx_output_Q=f"{wiring_path}/opx_output_Q",
            intermediate_frequency="#./inferred_intermediate_frequency",
            frequency_converter_up=ports.data["control_qubit"]
            + "/xy/frequency_converter_up",
            target_qubit_LO_frequency=ports.data["target_qubit"] + "/xy/LO_frequency",
            target_qubit_IF_frequency=ports.data["target_qubit"]
            + "/xy/intermediate_frequency",
            detuning=0,
        )

    elif "opx_output" in ports.keys():
        transmon_pair.zz_drive = ZZDriveMW(
            id=zz_drive_name, opx_output=f"{wiring_path}/opx_output"
        )

    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
