from pathlib import Path
from typing import Optional, Union

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components import FrequencyConverter, LocalOscillator, Octave
from quam_builder.architecture.superconducting.components.mixer import StandaloneMixer
from quam_builder.builder.quantum_dots.build_qpu import (
    QpuAssembly,
    _QpuBuilder,
    _set_default_grid_location,
)
from quam_builder.builder.quantum_dots.pulses import (
    add_default_ldv_qubit_pair_pulses,
    add_default_ldv_qubit_pulses,
    add_default_resonator_pulses
)
from quam_builder.architecture.superconducting.qpu import AnyQuam

__all__ = [
    "build_quam",
    "add_octaves",
    "add_external_mixers",
    "add_ports",
    "add_qpu",
    "add_pulses",
    "_resolve_calibration_db_path",
    "_set_default_grid_location",
]


def build_quam(
    machine: AnyQuam,
    calibration_db_path: Optional[Union[Path, str]] = None,
    save: bool = True,
) -> AnyQuam:
    """High-level builder that wires instruments, registers QPU elements, and applies defaults.

    The workflow mirrors ``wiring_lffem_mwfem.py``: build wiring, load the machine, then
    call this function to attach hardware abstractions. Saving can be skipped when the
    caller wants to inspect the machine before persisting.

    Args:
        machine: The QuAM to be built.
        calibration_db_path: Path to the Octave calibration database. Defaults to the
            machine's state directory when omitted.
        save: Whether to persist the machine state at the end of the build.

    Returns:
        AnyQuam: The built QuAM.
    """
    builder = _OrchestratedQuamBuilder(machine, calibration_db_path)
    builder.add_octaves()
    builder.add_external_mixers()
    builder.add_ports()
    builder.add_qpu()
    builder.add_pulses()

    if save:
        machine.save()

    return machine


class _OrchestratedQuamBuilder:
    """Coordinates the build flow so each stage has a focused responsibility."""

    def __init__(self, machine: AnyQuam, calibration_db_path: Optional[Union[Path, str]]):
        self.machine = machine
        self.calibration_db_path = calibration_db_path

    def add_octaves(self):
        add_octaves(self.machine, calibration_db_path=self.calibration_db_path)

    def add_external_mixers(self):
        add_external_mixers(self.machine)

    def add_ports(self):
        add_ports(self.machine)

    def add_qpu(self):
        add_qpu(self.machine)

    def add_pulses(self):
        add_pulses(self.machine)


def add_ports(machine: AnyQuam):
    """Creates and stores all input/output ports according to what has been allocated to each element in the machine's wiring."""

    for wiring_by_element in machine.wiring.values():
        for wiring_by_line_type in wiring_by_element.values():
            for ports in wiring_by_line_type.values():
                for port in ports:
                    if "ports" in ports.get_unreferenced_value(port):
                        machine.ports.reference_to_port(
                            ports.get_unreferenced_value(port), create=True
                        )


def add_qpu(machine: AnyQuam):
    """Adds global_gates, qubits, qubit_pairs, and sensor dots using the QPU builder."""

    _QpuBuilder(machine).build()


def add_pulses(machine: AnyQuam):
    """Adds default pulses to the ldv_qubit qubits and qubit pairs in the machine."""

    if hasattr(machine, "qubits"):
        for ldv_qubit in machine.qubits.values():
            add_default_ldv_qubit_pulses(ldv_qubit)

    if hasattr(machine, "qubit_pairs"):
        for qubit_pair in machine.qubit_pairs.values():
            add_default_ldv_qubit_pair_pulses(qubit_pair)

    if hasattr(machine, "sensor_dots"):
        for sensor_dot in machine.sensor_dots.values():
            add_default_resonator_pulses(sensor_dot.readout_resonator)

def _resolve_calibration_db_path(
    machine: AnyQuam, calibration_db_path: Optional[Union[Path, str]]
) -> Path:
    """Normalizes calibration path inputs so builders can rely on a Path object."""

    if calibration_db_path is None:
        serializer = machine.get_serialiser()
        calibration_db_path = serializer._get_state_path().parent

    if isinstance(calibration_db_path, str):
        calibration_db_path = Path(calibration_db_path)

    return calibration_db_path


def add_octaves(
    machine: AnyQuam, calibration_db_path: Optional[Union[Path, str]] = None
) -> AnyQuam:
    """Adds octave components to the machine based on the wiring configuration and initializes their frequency converters."""

    calibration_db_path = _resolve_calibration_db_path(machine, calibration_db_path)

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
    """Adds external mixers to the machine based on the wiring configuration."""

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
