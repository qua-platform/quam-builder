from pathlib import Path
from typing import Optional, Union

from numpy import ceil, sqrt
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components import FrequencyConverter, LocalOscillator, Octave

from quam_builder.architecture.superconducting.components.mixer import StandaloneMixer
from quam_builder.architecture.nv_center.qpu import AnyQuamNV
from quam_builder.builder.nv_center.add_nv_laser_component import add_nv_laser_component
from quam_builder.builder.nv_center.add_nv_spcm_component import add_nv_spcm_component
from quam_builder.builder.nv_center.add_nv_drive_component import add_nv_drive_component
from quam_builder.builder.nv_center.pulses import (
    add_default_nv_center_pulses,
    add_default_nv_center_pair_pulses,
)


def build_quam(
    machine: AnyQuamNV, calibration_db_path: Optional[Union[Path, str]] = None
) -> AnyQuamNV:
    """Builds the QuAM by adding various components and saving the machine configuration.

    Args:
        machine (AnyQuamNV): The QuAM to be built.
        calibration_db_path (Optional[Union[Path, str]]): The path to the Octave calibration database.

    Returns:
        AnyQuamNV: The built QuAM.
    """
    add_octaves(machine, calibration_db_path=calibration_db_path)
    add_external_mixers(machine)
    add_ports(machine)
    add_nv_center(machine)
    add_pulses(machine)

    machine.save()

    return machine


def add_ports(machine: AnyQuamNV):
    """Creates and stores all input/output ports according to what has been allocated to each element in the machine's wiring.

    Args:
        machine (AnyQuamNV): The QuAM to which the ports will be added.
    """
    for wiring_by_element in machine.wiring.values():
        for wiring_by_line_type in wiring_by_element.values():
            for ports in wiring_by_line_type.values():
                for port in ports:
                    if "ports" in ports.get_raw_value(port):
                        machine.ports.reference_to_port(
                            ports.get_unreferenced_value(port), create=True
                        )


def _set_default_grid_location(qubit_number: int, total_number_of_qubits: int) -> str:
    """Sets the default grid location for a qubit based on its number and the total number of qubits.

    Args:
        qubit_number (int): The number of the qubit.
        total_number_of_qubits (int): The total number of qubits.

    Returns:
        str: The grid location in the format "x,y".
    """
    number_of_rows = int(ceil(sqrt(total_number_of_qubits)))
    y = qubit_number % number_of_rows
    x = qubit_number // number_of_rows
    return f"{x},{y}"


def add_nv_center(machine: AnyQuamNV):
    """Adds NV center qubits and qubit pairs to the machine based on the wiring configuration.

    Args:
        machine (AnyQuamNV): The QuAM to which the NV center will be added.
    """
    for element_type, wiring_by_element in machine.wiring.items():
        if element_type == "qubits":
            machine.active_qubit_names = []
            number_of_qubits = len(wiring_by_element.items())
            qubit_number = 0
            for qubit_id, wiring_by_line_type in wiring_by_element.items():
                qubit_class = machine.qubit_type
                nv_center = qubit_class(id=qubit_id)
                machine.qubits[qubit_id] = nv_center
                machine.qubits[qubit_id].grid_location = _set_default_grid_location(
                    qubit_number, number_of_qubits
                )
                qubit_number += 1
                spcm_number = 1
                for line_type, ports in wiring_by_line_type.items():
                    wiring_path = f"#/wiring/{element_type}/{qubit_id}/{line_type}"
                    if line_type == WiringLineType.LASER.value:
                        add_nv_laser_component(nv_center, wiring_path, ports)
                    elif line_type == WiringLineType.SPCM.value:
                        spcm_name = f"spcm{spcm_number}"
                        add_nv_spcm_component(nv_center, wiring_path, ports, spcm_name)
                        spcm_number += 1
                    elif line_type == WiringLineType.DRIVE.value:
                        add_nv_drive_component(nv_center, wiring_path, ports)
                    else:
                        raise ValueError(f"Unknown line type: {line_type}")
                machine.active_qubit_names.append(nv_center.name)

        elif element_type == "qubit_pairs":
            raise NotImplementedError("NV qubit pairs not implemented yet.")
            # machine.active_qubit_pair_names = []
            # for qubit_pair_id, wiring_by_line_type in wiring_by_element.items():
            #     qc, qt = qubit_pair_id.split("-")
            #     qt = f"q{qt}"
            #     nv_center_pair = machine.qubit_pair_type(
            #         id=qubit_pair_id,
            #         qubit_control=f"#/qubits/{qc}",
            #         qubit_target=f"#/qubits/{qt}",
            #     )
            #     for line_type, ports in wiring_by_line_type.items():
            #         wiring_path = f"#/wiring/{element_type}/{qubit_pair_id}/{line_type}"
            #         if line_type == WiringLineType.COUPLER.value:
            #             add_transmon_pair_tunable_coupler_component(
            #                 nv_center_pair, wiring_path, ports
            #             )
            #         elif line_type == WiringLineType.CROSS_RESONANCE.value:
            #             add_transmon_pair_cross_resonance_component(
            #                 nv_center_pair, wiring_path, ports
            #             )
            #         elif line_type == WiringLineType.ZZ_DRIVE.value:
            #             add_transmon_pair_zz_drive_component(
            #                 nv_center_pair, wiring_path, ports
            #             )
            #         else:
            #             raise ValueError(f"Unknown line type: {line_type}")
            #         machine.qubit_pairs[nv_center_pair.name] = nv_center_pair
            #         machine.active_qubit_pair_names.append(nv_center_pair.name)


def add_pulses(machine: AnyQuamNV):
    """Adds default pulses to the nv_center qubits and qubit pairs in the machine.

    Args:
        machine (AnyQuamNV): The QuAM to which the pulses will be added.
    """
    if hasattr(machine, "qubits"):
        for nv_center in machine.qubits.values():
            add_default_nv_center_pulses(nv_center)

    if hasattr(machine, "qubit_pairs"):
        for qubit_pair in machine.qubit_pairs.values():
            add_default_nv_center_pair_pulses(qubit_pair)


def add_octaves(
    machine: AnyQuamNV, calibration_db_path: Optional[Union[Path, str]] = None
) -> AnyQuamNV:
    """Adds octave components to the machine based on the wiring configuration and initializes their frequency converters.

    Args:
        machine (AnyQuamNV): The QuAM to which the octaves will be added.
        calibration_db_path (Optional[Union[Path, str]]): The path to the calibration database.

    Returns:
        AnyQuamNV: The QuAM with the added octaves.
    """
    if calibration_db_path is None:
        serializer = machine.get_serialiser()
        calibration_db_path = serializer._get_state_path().parent

    if isinstance(calibration_db_path, str):
        calibration_db_path = Path(calibration_db_path)

    for wiring_by_element in machine.wiring.values():
        for qubit, wiring_by_line_type in wiring_by_element.items():
            for line_type, references in wiring_by_line_type.items():
                for reference in references:
                    if "octaves" in references.get_unreferenced_value(reference):
                        octave_name = references.get_unreferenced_value(
                            reference
                        ).split("/")[2]
                        octave = Octave(
                            name=octave_name,
                            calibration_db_path=str(calibration_db_path),
                        )
                        machine.octaves[octave_name] = octave
                        octave.initialize_frequency_converters()

    return machine


def add_external_mixers(machine: AnyQuamNV) -> AnyQuamNV:
    """Adds external mixers to the machine based on the wiring configuration.

    Args:
        machine (AnyQuamNV): The QuAM to which the external mixers will be added.

    Returns:
        AnyQuamNV: The QuAM with the added external mixers.
    """
    for wiring_by_element in machine.wiring.values():
        for qubit, wiring_by_line_type in wiring_by_element.items():
            for line_type, references in wiring_by_line_type.items():
                for reference in references:
                    if "mixers" in references.get_unreferenced_value(reference):
                        mixer_name = references.get_unreferenced_value(reference).split(
                            "/"
                        )[2]
                        nv_center_channel = {
                            WiringLineType.DRIVE.value: "xy",
                            WiringLineType.RESONATOR.value: "resonator",
                        }
                        frequency_converter = FrequencyConverter(
                            local_oscillator=LocalOscillator(),
                            mixer=StandaloneMixer(
                                intermediate_frequency=f"#/qubits/{qubit}/{nv_center_channel[line_type]}/intermediate_frequency",
                            ),
                        )
                        machine.mixers[mixer_name] = frequency_converter

    return machine
