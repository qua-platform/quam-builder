from pathlib import Path
from typing import Union, Optional
from numpy import sqrt, ceil
from quam.components import Octave, LocalOscillator, FrequencyConverter
from quam_builder.architecture.superconducting.components.mixer import StandaloneMixer
from quam_builder.builder.quantum_dots.pulses import (
    add_default_ldv_qubit_pulses,
    add_default_ldv_qubit_pair_pulses,
)
from quam_builder.architecture.quantum_dots.components import VoltageGate

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.superconducting.qpu import AnyQuam


def build_quam(
    machine: AnyQuam, calibration_db_path: Optional[Union[Path, str]] = None
) -> AnyQuam:
    """Builds the QuAM by adding various components and saving the machine configuration.

    Args:
        machine (AnyQuam): The QuAM to be built.
        calibration_db_path (Optional[Union[Path, str]]): The path to the Octave calibration database.

    Returns:
        AnyQuam: The built QuAM.
    """
    add_octaves(machine, calibration_db_path=calibration_db_path)
    add_external_mixers(machine)
    add_ports(machine)
    add_qpu(machine)
    add_pulses(machine)

    machine.save()

    return machine


def add_ports(machine: AnyQuam):
    """Creates and stores all input/output ports according to what has been allocated to each element in the machine's wiring.

    Args:
        machine (AnyQuam): The QuAM to which the ports will be added.
    """
    for wiring_by_element in machine.wiring.values():
        for wiring_by_line_type in wiring_by_element.values():
            for ports in wiring_by_line_type.values():
                for port in ports:
                    if "ports" in ports.get_unreferenced_value(port):
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


def add_qpu(machine: AnyQuam):
    """Adds global_gates, qubits, qubit_pairs, and sensor dots to the machine based on the wiring configuration.

    This function processes the wiring configuration in multiple passes:
    1. Create physical channels (VoltageGates, XYDrives, Resonators) from wiring
    2. Create virtual gate set from quantum dot channels
    3. Register quantum dots, sensor dots, and barrier gates using BaseQuamQD methods
    4. Register qubits with their XY drives using BaseQuamQD methods
    5. Register qubit pairs using BaseQuamQD methods

    Args:
        machine (AnyQuam): The QuAM to which the QPU elements will be added.
    """
    # Storage for channels created from wiring
    plunger_channels = {}  # Maps quantum_dot_id -> VoltageGate channel
    barrier_channels = {}  # Maps barrier_id -> VoltageGate channel
    sensor_channels = {}  # Maps sensor_id -> VoltageGate channel
    sensor_resonators = {}  # Maps sensor_id -> Resonator
    xy_drives = {}  # Maps qubit_id -> XYDrive

    # Pass 1: Create all physical channels and populate the virtual gate set mapping
    virtual_channel_mapping = {}

    for element_type, wiring_by_element in machine.wiring.items():
        if element_type == "global_gates":
            global_gates = []
            machine.active_global_gate_names = []
            number_of_global_gates = len(wiring_by_element.items())
            global_gate_number = 0
            for global_gate_id, wiring_by_line_type in wiring_by_element.items():
                global_gate_class = machine.global_gate_type[global_gate_id]
                global_gate = global_gate_class(id=global_gate_id)
                machine.global_gates[global_gate_id] = global_gate
                machine.global_gates[global_gate_id].grid_location = _set_default_grid_location(
                    global_gate_number, number_of_global_gates
                )
                global_gate_number += 1
                for line_type, ports in wiring_by_line_type.items():
                    wiring_path = f"#/wiring/{element_type}/{global_gate_id}/{line_type}"
                    if line_type == WiringLineType.GLOBAL_GATE.value:
                        global_gates.append(
                            VoltageGate(id=global_gate_id, opx_output=wiring_path+f'/opx_output'),
                            )
                    else:
                        raise ValueError(f"Unknown line type: {line_type}")
                machine.active_global_gate_names.append(global_gate.name)

        elif element_type == "sensor_dots":
            for sensor_dot_id, wiring_by_line_type in wiring_by_element.items():
                sensor_gate = None
                resonator = None

                for line_type, ports in wiring_by_line_type.items():
                    wiring_path = f"#/wiring/{element_type}/{sensor_dot_id}/{line_type}"
                    if line_type == WiringLineType.SENSOR_GATE.value:
                        sensor_gate = VoltageGate(id=sensor_dot_id, opx_output=wiring_path+'/opx_output')
                        sensor_channels[sensor_dot_id] = sensor_gate
                        # Add to virtual gate set mapping
                        virtual_channel_mapping[sensor_dot_id] = sensor_gate
                    elif line_type == WiringLineType.RF_RESONATOR.value:
                        from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle
                        resonator = ReadoutResonatorSingle(
                            id=f"{sensor_dot_id}_resonator",
                            opx_output=wiring_path+'/opx_output',
                            opx_input=wiring_path+'/opx_input'
                        )
                        sensor_resonators[sensor_dot_id] = resonator

        elif element_type == "qubits":
            for qubit_id, wiring_by_line_type in wiring_by_element.items():
                plunger_gate = None
                xy_drive = None

                for line_type, ports in wiring_by_line_type.items():
                    wiring_path = f"#/wiring/{element_type}/{qubit_id}/{line_type}"
                    if line_type == WiringLineType.DRIVE.value:
                        # Determine XY drive type based on ports
                        from quam_builder.builder.qop_connectivity.channel_ports import (
                            iq_out_channel_ports,
                            mw_out_channel_ports,
                        )
                        from quam_builder.architecture.superconducting.components.xy_drive import (
                            XYDriveIQ,
                            XYDriveMW,
                        )

                        if all(key in ports for key in iq_out_channel_ports):
                            # IQ channel (Octave)
                            xy_drive = XYDriveIQ(
                                id=f"{qubit_id}_xy",
                                opx_output_I=wiring_path+'/opx_output_I',
                                opx_output_Q=wiring_path+'/opx_output_Q',
                                frequency_converter_up=wiring_path+'/frequency_converter_up'
                            )
                        elif all(key in ports for key in mw_out_channel_ports):
                            # MW-FEM channel
                            xy_drive = XYDriveMW(
                                id=f"{qubit_id}_xy",
                                opx_output=wiring_path+'/opx_output'
                            )

                        if xy_drive:
                            xy_drives[qubit_id] = xy_drive

                    elif line_type == WiringLineType.PLUNGER_GATE.value:
                        plunger_gate = VoltageGate(id=qubit_id, opx_output=wiring_path+'/opx_output')
                        plunger_channels[qubit_id] = plunger_gate
                        # Add to virtual gate set mapping
                        virtual_channel_mapping[qubit_id] = plunger_gate

        elif element_type == "qubit_pairs":
            for qubit_pair_id, wiring_by_line_type in wiring_by_element.items():
                barrier_gate = None

                for line_type, ports in wiring_by_line_type.items():
                    wiring_path = f"#/wiring/{element_type}/{qubit_pair_id}/{line_type}"
                    if line_type == WiringLineType.BARRIER_GATE.value:
                        barrier_gate = VoltageGate(id=qubit_pair_id, opx_output=wiring_path+'/opx_output')
                        barrier_channels[qubit_pair_id] = barrier_gate
                        # Add to virtual gate set mapping
                        virtual_channel_mapping[qubit_pair_id] = barrier_gate

    # Pass 2: Create virtual gate set if we have quantum dot channels
    if virtual_channel_mapping:
        machine.create_virtual_gate_set(
            virtual_channel_mapping=virtual_channel_mapping,
            gate_set_id="main_qpu",
        )

    # Pass 3: Register channel elements using BaseQuamQD registration methods
    if plunger_channels or sensor_channels or barrier_channels:
        sensor_resonator_mapping = {
            sensor_channels[sid]: sensor_resonators[sid]
            for sid in sensor_channels.keys()
            if sid in sensor_resonators
        }
        machine.register_channel_elements(
            plunger_channels=list(plunger_channels.values()),
            barrier_channels=list(barrier_channels.values()),
            sensor_resonator_mapping=sensor_resonator_mapping,
        )

        # Set active lists
        machine.active_sensor_dot_names = list(sensor_channels.keys())

    # Pass 4: Register qubits using BaseQuamQD registration method
    machine.active_qubit_names = []
    number_of_qubits = len(plunger_channels)
    for qubit_number, qubit_id in enumerate(plunger_channels.keys()):
        machine.register_qubit(
            qubit_type="loss_divincenzo",
            quantum_dot_id=qubit_id,
            qubit_name=f"Q{qubit_id.split('_')[-1] if '_' in qubit_id else qubit_id}",
            xy_channel=xy_drives.get(qubit_id, None),
        )
        qubit_name = f"Q{qubit_id.split('_')[-1] if '_' in qubit_id else qubit_id}"
        machine.qubits[qubit_name].grid_location = _set_default_grid_location(
            qubit_number, number_of_qubits
        )
        machine.active_qubit_names.append(qubit_name)

    # Pass 5: Register qubit pairs using BaseQuamQD registration methods
    if "qubit_pairs" in machine.wiring:
        machine.active_qubit_pair_names = []
        for qubit_pair_id in machine.wiring["qubit_pairs"].keys():
            # Extract qubit IDs from pair ID (format: "q1_q2")
            qc_id, qt_id = qubit_pair_id.split("_")
            qc_name = f"Q{qc_id.split('_')[-1] if '_' in qc_id else qc_id}"
            qt_name = f"Q{qt_id.split('_')[-1] if '_' in qt_id else qt_id}"

            # Find corresponding quantum dots
            qc_dot_id = qc_id
            qt_dot_id = qt_id

            # Find sensor dots - using the first sensor for now
            # TODO: This mapping should be more sophisticated based on your architecture
            sensor_dot_ids = list(sensor_channels.keys()) if sensor_channels else []

            # Register quantum dot pair first
            if qc_dot_id in plunger_channels and qt_dot_id in plunger_channels:
                machine.register_quantum_dot_pair(
                    id=f"dot{qc_id}_dot{qt_id}_pair",
                    quantum_dot_ids=[qc_dot_id, qt_dot_id],
                    sensor_dot_ids=sensor_dot_ids,
                    barrier_gate_id=qubit_pair_id if qubit_pair_id in barrier_channels else None,
                )

                # Register qubit pair
                machine.register_qubit_pair(
                    id=qubit_pair_id,
                    qubit_control_name=qc_name,
                    qubit_target_name=qt_name,
                    qubit_type="loss_divincenzo",
                )
                machine.active_qubit_pair_names.append(qubit_pair_id)


def add_pulses(machine: AnyQuam):
    """Adds default pulses to the ldv_qubit qubits and qubit pairs in the machine.

    Args:
        machine (AnyQuam): The QuAM to which the pulses will be added.
    """
    if hasattr(machine, "qubits"):
        for ldv_qubit in machine.qubits.values():
            add_default_ldv_qubit_pulses(ldv_qubit)

    if hasattr(machine, "qubit_pairs"):
        for qubit_pair in machine.qubit_pairs.values():
            add_default_ldv_qubit_pair_pulses(qubit_pair)


def add_octaves(
    machine: AnyQuam, calibration_db_path: Optional[Union[Path, str]] = None
) -> AnyQuam:
    """Adds octave components to the machine based on the wiring configuration and initializes their frequency converters.

    Args:
        machine (AnyQuam): The QuAM to which the octaves will be added.
        calibration_db_path (Optional[Union[Path, str]]): The path to the calibration database.

    Returns:
        AnyQuam: The QuAM with the added octaves.
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


def add_external_mixers(machine: AnyQuam) -> AnyQuam:
    """Adds external mixers to the machine based on the wiring configuration.

    Args:
        machine (AnyQuam): The QuAM to which the external mixers will be added.

    Returns:
        AnyQuam: The QuAM with the added external mixers.
    """
    for wiring_by_element in machine.wiring.values():
        for qubit, wiring_by_line_type in wiring_by_element.items():
            for line_type, references in wiring_by_line_type.items():
                for reference in references:
                    if "mixers" in references.get_unreferenced_value(reference):
                        mixer_name = references.get_unreferenced_value(reference).split(
                            "/"
                        )[2]
                        ldv_qubit_channel = {
                            WiringLineType.DRIVE.value: "xy",
                            WiringLineType.RESONATOR.value: "resonator",
                        }
                        frequency_converter = FrequencyConverter(
                            local_oscillator=LocalOscillator(),
                            mixer=StandaloneMixer(
                                intermediate_frequency=f"#/qubits/{qubit}/{ldv_qubit_channel[line_type]}/intermediate_frequency",
                            ),
                        )
                        machine.mixers[mixer_name] = frequency_converter

    return machine
