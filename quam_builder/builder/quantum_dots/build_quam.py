"""High-level QuAM configuration builder for quantum dot systems.

This module provides the main entry point for building complete QuAM configurations
from wiring specifications. It orchestrates:
- Octave frequency converter initialization
- External mixer configuration
- Port registration
- QPU element creation (gates, qubits, qubit pairs)
- Default pulse assignment
"""

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
    qubit_pair_sensor_map: Optional[dict] = None,
    save: bool = True,
) -> AnyQuam:
    """Build complete QuAM configuration from wiring specifications.

    This is the main entry point for configuring quantum dot systems. It processes
    wiring specifications and configures all necessary components including Octaves,
    mixers, ports, quantum gates, qubits, qubit pairs, and default pulses.

    The build process executes these steps:
    1. Initialize Octave frequency converters from wiring
    2. Configure external mixers
    3. Register all I/O ports
    4. Build QPU elements (global gates, qubits, qubit pairs, sensors)
    5. Add default pulse configurations

    Args:
        machine: QuAM instance with wiring specifications already defined.
        calibration_db_path: Path to Octave calibration database. If None, uses
            the machine's state directory.
        qubit_pair_sensor_map: Optional mapping to specify which sensor dots are
            used for each qubit pair. Format: {"q1_q2": ["s1", "s2"]}. If None,
            all sensors are associated with all qubit pairs.
        save: If True, saves the machine state after building. Set to False to
            inspect the configuration before persisting.

    Returns:
        The fully configured QuAM instance.

    Example:
        >>> from quam_builder.builder.quantum_dots import build_quam
        >>> # Load a machine with wiring already defined
        >>> machine = AnyQuam.load("state.json")
        >>> # Build the complete configuration
        >>> configured_machine = build_quam(machine)
        >>> # Access configured qubits
        >>> print(machine.qubits.keys())  # ['q1', 'q2', ...]

    Example with sensor mapping:
        >>> # Specify which sensors to use for each qubit pair
        >>> sensor_map = {
        ...     "q1_q2": ["s1", "s2"],  # Pair q1-q2 uses sensors s1 and s2
        ...     "q2_q3": ["s2", "s3"],  # Pair q2-q3 uses sensors s2 and s3
        ... }
        >>> machine = build_quam(machine, qubit_pair_sensor_map=sensor_map)

    Note:
        The machine must have its wiring specifications defined before calling
        this function. Use the wiring builder tools to create wiring configurations.
    """
    builder = _OrchestratedQuamBuilder(
        machine,
        calibration_db_path=calibration_db_path,
        qubit_pair_sensor_map=qubit_pair_sensor_map,
    )
    builder.add_octaves()
    builder.add_external_mixers()
    builder.add_ports()
    builder.add_qpu()
    builder.add_pulses()

    if save:
        machine.save()

    return machine


class _OrchestratedQuamBuilder:
    """Internal coordinator for sequential build stages.

    Ensures each build stage (octaves, mixers, ports, QPU, pulses) executes
    in the correct order with proper dependencies.

    Attributes:
        machine: QuAM instance being configured.
        calibration_db_path: Path to Octave calibration database.
        qubit_pair_sensor_map: Optional sensor-to-pair mapping.
    """

    def __init__(
        self,
        machine: AnyQuam,
        calibration_db_path: Optional[Union[Path, str]],
        qubit_pair_sensor_map: Optional[dict],
    ) -> None:
        self.machine = machine
        self.calibration_db_path = calibration_db_path
        self.qubit_pair_sensor_map = qubit_pair_sensor_map

    def add_octaves(self) -> None:
        """Add and initialize Octave components."""
        add_octaves(self.machine, calibration_db_path=self.calibration_db_path)

    def add_external_mixers(self) -> None:
        """Add external frequency mixers."""
        add_external_mixers(self.machine)

    def add_ports(self) -> None:
        """Register all I/O ports."""
        add_ports(self.machine)

    def add_qpu(self) -> None:
        """Build and register QPU elements."""
        add_qpu(self.machine, qubit_pair_sensor_map=self.qubit_pair_sensor_map)

    def add_pulses(self) -> None:
        """Add default pulse configurations."""
        add_pulses(self.machine)


def add_ports(machine: AnyQuam) -> None:
    """Register all I/O ports referenced in wiring specifications.

    Scans the wiring configuration and creates port objects for all
    referenced inputs and outputs.

    Args:
        machine: QuAM instance with wiring defined.
    """
    for wiring_by_element in machine.wiring.values():
        for wiring_by_line_type in wiring_by_element.values():
            for ports in wiring_by_line_type.values():
                for port in ports:
                    if "ports" in ports.get_unreferenced_value(port):
                        machine.ports.reference_to_port(
                            ports.get_unreferenced_value(port), create=True
                        )


def add_qpu(machine: AnyQuam, qubit_pair_sensor_map: Optional[dict] = None) -> None:
    """Build and register QPU elements from wiring specifications.

    Creates and registers:
    - Global gates
    - Quantum dots (plunger gates)
    - Qubits (Loss-DiVincenzo type)
    - Qubit pairs
    - Sensor dots with resonators

    Args:
        machine: QuAM instance with wiring defined.
        qubit_pair_sensor_map: Optional mapping specifying which sensors are
            used for each qubit pair.
    """
    _QpuBuilder(machine, qubit_pair_sensor_map=qubit_pair_sensor_map).build()


def add_pulses(machine: AnyQuam) -> None:
    """Add default pulse configurations to qubits and resonators.

    Configures:
    - Single-qubit rotation pulses (X, Y, ±90°, 180°)
    - Readout pulses for sensor resonators
    - Placeholder two-qubit gate pulses

    Args:
        machine: QuAM instance with qubits and sensors registered.
    """
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
    """Resolve and normalize Octave calibration database path.

    Args:
        machine: QuAM instance.
        calibration_db_path: User-provided path or None.

    Returns:
        Resolved Path object for calibration database.
    """
    if calibration_db_path is None:
        serializer = machine.get_serialiser()
        calibration_db_path = serializer._get_state_path().parent

    if isinstance(calibration_db_path, str):
        calibration_db_path = Path(calibration_db_path)

    return calibration_db_path


def add_octaves(
    machine: AnyQuam, calibration_db_path: Optional[Union[Path, str]] = None
) -> AnyQuam:
    """Scan wiring for Octaves and initialize frequency converters.

    Creates Octave component instances for each Octave found in the wiring
    configuration and initializes their frequency converters.

    Args:
        machine: QuAM instance with wiring defined.
        calibration_db_path: Path to Octave calibration database.

    Returns:
        The machine with Octaves registered.
    """
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
    """Scan wiring for external mixers and create frequency converter components.

    Creates mixer components with local oscillators for each external mixer
    referenced in the wiring configuration.

    Args:
        machine: QuAM instance with wiring defined.

    Returns:
        The machine with external mixers registered.
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
