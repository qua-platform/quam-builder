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
from quam_builder.builder.quantum_dots.build_qpu_stage1 import _BaseQpuBuilder
from quam_builder.builder.quantum_dots.build_qpu_stage2 import _LDQubitBuilder
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
from quam_builder.builder.quantum_dots.pulses import (
    add_default_ldv_qubit_pair_pulses,
    add_default_ldv_qubit_pulses,
    add_default_resonator_pulses,
)
from quam_builder.architecture.superconducting.qpu import AnyQuam

__all__ = [
    "build_quam",
    "build_base_quam",
    "build_loss_divincenzo_quam",
    "add_octaves",
    "add_external_mixers",
    "add_ports",
    "add_qpu",
    "add_pulses",
    "_resolve_calibration_db_path",
    "_set_default_grid_location",
]


def build_base_quam(
    machine: BaseQuamQD,
    calibration_db_path: Optional[Union[Path, str]] = None,
    qdac_ip: Optional[str] = None,
    connect_qdac: bool = False,
    save: bool = True,
) -> BaseQuamQD:
    """Build Stage 1: BaseQuamQD with physical quantum dots.

    This creates the physical quantum dot layer with:
    - Physical VoltageGate channels with QDAC mappings
    - Virtual gate set with identity compensation matrix
    - Quantum dots (from plunger gates)
    - Quantum dot pairs (with barriers)
    - Sensor dots with resonators
    - Octaves, mixers, and ports

    Does NOT create:
    - Qubits (use build_loss_divincenzo_quam for Stage 2)
    - XY drive channels (Stage 2)
    - Qubit pairs (Stage 2)

    Args:
        machine: BaseQuamQD instance with wiring defined.
        calibration_db_path: Path to Octave calibration database. If None, uses
            the machine's state directory.
        qdac_ip: IP address for QDAC connection. If provided with connect_qdac=True,
            connects to QDAC for external voltage control.
        connect_qdac: If True, connects to QDAC using qdac_ip or machine.network['qdac_ip'].
        save: If True, saves the machine state after building.

    Returns:
        Configured BaseQuamQD ready for Stage 2 conversion.

    Example:
        >>> from quam_builder.builder.quantum_dots import build_base_quam
        >>> machine = BaseQuamQD()
        >>> # ... configure wiring ...
        >>> machine = build_base_quam(machine, connect_qdac=True, qdac_ip="172.16.33.101")
        >>> # Save and load later for Stage 2
        >>> machine.save("base_quam_state")

    Note:
        This function implements Stage 1 only. To add qubits, call
        build_loss_divincenzo_quam() with the resulting machine.
    """
    # Add infrastructure components
    add_octaves(machine, calibration_db_path=calibration_db_path)
    add_external_mixers(machine)
    add_ports(machine)

    # Build Stage 1: Quantum dots only
    _BaseQpuBuilder(machine).build()

    # Optional QDAC connection
    if connect_qdac:
        if qdac_ip:
            machine.network["qdac_ip"] = qdac_ip
        machine.connect_to_external_source(external_qdac=True)

    if save:
        machine.save()

    return machine


def build_loss_divincenzo_quam(
    machine: Union[BaseQuamQD, LossDiVincenzoQuam, str, Path],
    xy_drive_wiring: Optional[dict] = None,
    qubit_pair_sensor_map: Optional[dict] = None,
    implicit_mapping: bool = True,
    save: bool = True,
) -> LossDiVincenzoQuam:
    """Build Stage 2: Convert BaseQuamQD to LossDiVincenzoQuam with qubits.

    This is INDEPENDENT of Stage 1 and works with any BaseQuamQD (file or memory).

    Creates:
    - LDQubits (mapped to quantum dots via implicit numbering: q1 → virtual_dot_1)
    - XY drive channels for each qubit
    - Qubit pairs (mapped to quantum dot pairs)
    - Default pulses

    Args:
        machine: BaseQuamQD, LossDiVincenzoQuam, or path to saved BaseQuamQD state.
        xy_drive_wiring: Optional dict mapping qubit_id → XY drive configuration.
                        Format: {
                            "q1": {
                                "type": "IQ" or "MW",
                                "wiring_path": "#/wiring/qubits/q1/xy",
                                "intermediate_frequency": 500e6  # optional
                            },
                            ...
                        }
                        If None (default), automatically extracts XY drives from
                        machine.wiring if available. Only provide this if:
                        - Loading from file without wiring information, OR
                        - Need to override automatic extraction
        qubit_pair_sensor_map: Sensor mapping for qubit pairs.
                              Format: {"q1_q2": ["sensor_1", "sensor_2"], ...}
        implicit_mapping: If True, uses q1→virtual_dot_1 mapping. If False,
                         requires explicit mapping configuration.
        save: If True, saves the machine state after building.

    Returns:
        LossDiVincenzoQuam with qubits registered.

    Example (from memory - automatic XY extraction):
        >>> from quam_builder.builder.quantum_dots import build_loss_divincenzo_quam
        >>> # Assuming base_machine is a BaseQuamQD from Stage 1 with wiring
        >>> ld_machine = build_loss_divincenzo_quam(base_machine)
        >>> # XY drives are automatically extracted from base_machine.wiring
        >>> print(ld_machine.qubits.keys())  # ['q1', 'q2', ...]

    Example (from file with manual XY drives):
        >>> # Load Stage 1 result from file (may not have wiring)
        >>> xy_wiring = {
        ...     "q1": {"type": "IQ", "wiring_path": "#/wiring/qubits/q1/xy"},
        ...     "q2": {"type": "MW", "wiring_path": "#/wiring/qubits/q2/xy"},
        ... }
        >>> ld_machine = build_loss_divincenzo_quam(
        ...     "path/to/base_quam_state",
        ...     xy_drive_wiring=xy_wiring
        ... )

    Note:
        This function implements Stage 2 only and requires quantum dots to be
        already registered. If starting from scratch, first call build_base_quam().
    """
    # Build Stage 2: Qubits from quantum dots
    builder = _LDQubitBuilder(
        machine,
        xy_drive_wiring=xy_drive_wiring,
        qubit_pair_sensor_map=qubit_pair_sensor_map,
        implicit_mapping=implicit_mapping,
    )
    machine = builder.build()

    # Add default pulses
    add_pulses(machine)

    if save:
        machine.save()

    return machine


def build_quam(
    machine: Union[BaseQuamQD, LossDiVincenzoQuam],
    calibration_db_path: Optional[Union[Path, str]] = None,
    qubit_pair_sensor_map: Optional[dict] = None,
    qdac_ip: Optional[str] = None,
    connect_qdac: bool = False,
    save: bool = True,
) -> LossDiVincenzoQuam:
    """Build complete QuAM configuration using two-stage process.

    This is a convenience wrapper that executes both stages:
    - Stage 1: build_base_quam() - Creates BaseQuamQD with quantum dots
    - Stage 2: build_loss_divincenzo_quam() - Adds qubits

    For more control over the process, call the stage functions separately.

    Args:
        machine: BaseQuamQD or LossDiVincenzoQuam with wiring defined.
        calibration_db_path: Path to Octave calibration database.
        qubit_pair_sensor_map: Sensor mapping for qubit pairs.
        qdac_ip: IP address for QDAC connection.
        connect_qdac: If True, connects to QDAC for external voltage control.
        save: If True, saves the machine state after building.

    Returns:
        Fully configured LossDiVincenzoQuam with qubits.

    Example:
        >>> from quam_builder.builder.quantum_dots import build_quam
        >>> from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
        >>> machine = BaseQuamQD()
        >>> # ... configure wiring ...
        >>> machine = build_quam(machine, connect_qdac=True, qdac_ip="172.16.33.101")
        >>> print(machine.qubits.keys())  # ['q1', 'q2', ...]

    For more control (two separate stages):
        >>> # Stage 1: Physical quantum dots
        >>> machine = build_base_quam(machine, connect_qdac=True)
        >>> machine.save("base_quam_state")
        >>>
        >>> # Stage 2: Add qubits (can be done later)
        >>> machine = build_loss_divincenzo_quam("base_quam_state")
    """
    # Stage 1: Build BaseQuamQD
    if isinstance(machine, BaseQuamQD) and not hasattr(machine, "qubits"):
        machine = build_base_quam(
            machine,
            calibration_db_path=calibration_db_path,
            qdac_ip=qdac_ip,
            connect_qdac=connect_qdac,
            save=False,  # Don't save yet
        )

    # Stage 2: Convert to LossDiVincenzoQuam
    machine = build_loss_divincenzo_quam(
        machine,
        qubit_pair_sensor_map=qubit_pair_sensor_map,
        save=save,
    )

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
                        octave_name = references.get_unreferenced_value(reference).split("/")[2]
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
                        mixer_name = references.get_unreferenced_value(reference).split("/")[2]
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
