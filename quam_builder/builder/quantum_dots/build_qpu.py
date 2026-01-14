"""QPU builder for quantum dot systems.

This module provides the core QPU building functionality for quantum dot systems,
including:
- Collection and organization of physical channels (gates, resonators)
- Virtual gate mapping and registration
- Qubit and qubit pair registration
- Sensor dot association with qubit pairs
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import warnings

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorSingle,
    VoltageGate,
)
from quam_builder.architecture.superconducting.qpu import AnyQuam

from quam_builder.builder.quantum_dots.build_utils import *

__all__ = [
    "QpuAssembly",
    "_QpuBuilder",
    "_set_default_grid_location",
    "_natural_sort_key",
    "_sorted_items",
    "_normalize_element_type",
    "_validate_line_type",
    "_make_sticky_channel",
    "_make_voltage_gate",
    "_make_resonator",
    "_validate_drive_ports",
    "_build_virtual_mapping",
    "_parse_qubit_pair_ids",
    "DEFAULT_GATE_SET_ID",
    "DEFAULT_STICKY_DURATION",
    "DEFAULT_INTERMEDIATE_FREQUENCY",
    "DEFAULT_READOUT_LENGTH",
    "DEFAULT_READOUT_AMPLITUDE",
]

logger = logging.getLogger(__name__)


@dataclass
class QpuAssembly:
    """Container for intermediate QPU components during build process.

    Stores physical channels, resonators, and mappings between physical and virtual
    elements as they are collected from wiring specifications.

    Attributes:
        global_gates: Global voltage gates affecting all quantum dots.
        plunger_channels: Plunger gate channels for individual quantum dots.
        barrier_channels: Barrier gate channels for coupling between dots.
        sensor_channels: Sensor gate channels for charge sensing.
        resonators: Readout resonators associated with sensor dots.
        barrier_counter: Counter for generating unique barrier gate IDs.
        plunger_id_to_channel: Map from plunger IDs to channel objects.
        barrier_id_to_channel: Map from barrier IDs to channel objects.
        sensor_id_to_channel: Map from sensor IDs to gate channel objects.
        sensor_id_to_resonator: Map from sensor IDs to resonator objects.
        qubit_id_to_xy_info: Map from qubit IDs to XY drive configuration.
        qubit_pair_id_to_barrier_id: Map from qubit pair IDs to barrier gate IDs.
        plunger_virtual_names: Map from physical plunger IDs to virtual names.
        barrier_virtual_names: Map from physical barrier IDs to virtual names.
        sensor_virtual_names: Map from physical sensor IDs to virtual names.
        global_virtual_names: Map from physical global gate IDs to virtual names.
        gate_set_id: Identifier for the virtual gate set.
    """

    global_gates: List[VoltageGate] = field(default_factory=list)
    plunger_channels: List[VoltageGate] = field(default_factory=list)
    barrier_channels: List[VoltageGate] = field(default_factory=list)
    sensor_channels: List[VoltageGate] = field(default_factory=list)
    resonators: List[ReadoutResonatorSingle] = field(default_factory=list)

    barrier_counter: int = 1
    plunger_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    barrier_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    sensor_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    sensor_id_to_resonator: Dict[str, ReadoutResonatorSingle] = field(default_factory=dict)
    qubit_id_to_xy_info: Dict[str, Tuple[str, str, Mapping[str, Any]]] = field(default_factory=dict)
    qubit_pair_id_to_barrier_id: Dict[str, str] = field(default_factory=dict)

    plunger_virtual_names: Dict[str, str] = field(default_factory=dict)
    barrier_virtual_names: Dict[str, str] = field(default_factory=dict)
    sensor_virtual_names: Dict[str, str] = field(default_factory=dict)
    global_virtual_names: Dict[str, str] = field(default_factory=dict)
    gate_set_id: str = DEFAULT_GATE_SET_ID


class _QpuBuilder:
    """Orchestrates QPU construction from wiring specifications.

    Translates wiring specifications into physical components, creates virtual gate
    mappings, and registers qubits and qubit pairs with the machine.

    Attributes:
        machine: The QuAM machine being configured.
        assembly: Container for intermediate build state and components.
    """

    def __init__(
        self,
        machine: AnyQuam,
        qubit_pair_sensor_map: Optional[Mapping[str, Sequence[str]]] = None,
    ) -> None:
        """Initialize the QPU builder.

        Args:
            machine: QuAM machine instance to populate with QPU components.
            qubit_pair_sensor_map: Optional mapping from qubit pair IDs to sensor
                dot lists. If provided, restricts which sensors are associated with
                each pair. If None, all sensors are associated with all pairs.
        """
        self.machine = machine
        self.assembly = QpuAssembly()
        self._wiring_by_type: Dict[str, Mapping[str, Any]] = {}
        self._qubit_pair_sensor_map = qubit_pair_sensor_map
        self._normalized_pair_sensor_map: Dict[str, Sequence[str]] = {}

    def build(self) -> AnyQuam:
        """Execute the full QPU build process.

        Performs the following steps in order:
        1. Normalize wiring and sensor map specifications
        2. Collect physical channels from wiring
        3. Create virtual gate set and mappings
        4. Register channels with machine
        5. Register qubits with machine
        6. Register qubit pairs with machine

        Returns:
            The configured QuAM machine with registered QPU elements.
        """
        self.assembly = QpuAssembly()
        self.machine.active_global_gate_names = []
        self.machine.active_sensor_dot_names = []
        self.machine.active_qubit_names = []
        self.machine.active_qubit_pair_names = []

        self._wiring_by_type = self._normalize_wiring(self.machine.wiring or {})
        self._normalized_pair_sensor_map = self._normalize_sensor_map(self._qubit_pair_sensor_map)
        self._collect_physical_channels()
        self._create_virtual_gate_set()
        self._register_channels()
        self._register_qubits()
        self._register_qubit_pairs()
        return self.machine

    def _normalize_wiring(self, wiring: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
        normalized: Dict[str, Mapping[str, Any]] = {}
        for element_type, wiring_by_element in wiring.items():
            canonical_type = _normalize_element_type(element_type)
            if canonical_type in normalized:
                raise ValueError(
                    f"Duplicate wiring entries for element type '{canonical_type}' detected"
                )
            normalized[canonical_type] = wiring_by_element
        return normalized

    def _normalize_sensor_map(
        self, sensor_map: Optional[Mapping[str, Sequence[str]]]
    ) -> Dict[str, Sequence[str]]:
        normalized: Dict[str, Sequence[str]] = {}
        if sensor_map is None:
            return normalized
        if not isinstance(sensor_map, dict):
            raise ValueError(
                "qubit_pair_sensor_map must be a dict mapping pair ids to sensor lists. "
                "Pair formats: q1_q2 or q1-2. Sensor formats: virtual_sensor_<n>, sensor_<n>, s<n>."
            )
        if not sensor_map:
            msg = "qubit_pair_sensor_map is an empty dict; defaulting to all registered sensors for each pair."
            logger.warning(msg)
            warnings.warn(msg, UserWarning)
            return normalized
        for pair_id, sensors in sensor_map.items():
            qc, qt = _parse_qubit_pair_ids(pair_id)
            normalized_pair_id = f"{qc}_{qt}"
            if not isinstance(sensors, (list, tuple, set)):
                raise ValueError(
                    f"Sensor map for pair '{pair_id}' must be a list/tuple/set of sensor identifiers. "
                    "Supported pair formats: q1_q2 or q1-2. "
                    "Supported sensor formats: virtual_sensor_<n>, sensor_<n>, s<n>."
                )
            normalized[normalized_pair_id] = list(sensors)
        return normalized

    def _collect_physical_channels(self):
        for element_type in ("globals", "readout", "qubits", "qubit_pairs"):
            wiring_by_element = self._wiring_by_type.get(element_type)
            if wiring_by_element is None:
                continue

            if element_type == "globals":
                self._collect_global_gates(wiring_by_element)
            elif element_type == "readout":
                self._collect_sensor_dots(wiring_by_element, ReadoutResonatorSingle)
            elif element_type == "qubits":
                self._collect_qubits(wiring_by_element)
            elif element_type == "qubit_pairs":
                self._collect_qubit_pairs(wiring_by_element)

    def _collect_global_gates(self, wiring_by_element: Mapping[str, Any]):
        element_type = "globals"
        for global_gate_id, wiring_by_line_type in _sorted_items(wiring_by_element):
            for line_type, ports in _sorted_items(wiring_by_line_type):
                _validate_line_type(element_type, line_type)
                wiring_path = f"#/wiring/{element_type}/{global_gate_id}/{line_type}"
                self.assembly.global_gates.append(_make_voltage_gate(global_gate_id, wiring_path))

    def _collect_sensor_dots(self, wiring_by_element: Mapping[str, Any], resonator_cls: Any):
        element_type = "readout"
        for sensor_dot_id, wiring_by_line_type in _sorted_items(wiring_by_element):
            sensor_number = _extract_qubit_number(sensor_dot_id)
            sensor_id = f"sensor_{sensor_number}"
            for line_type, ports in _sorted_items(wiring_by_line_type):
                _validate_line_type(element_type, line_type)
                wiring_path = f"#/wiring/{element_type}/{sensor_dot_id}/{line_type}"
                if line_type == WiringLineType.SENSOR_GATE.value:
                    sensor_gate = _make_voltage_gate(sensor_id, wiring_path)
                    self.assembly.sensor_channels.append(sensor_gate)
                    self.assembly.sensor_id_to_channel[sensor_gate.id] = sensor_gate
                elif line_type == WiringLineType.RF_RESONATOR.value:
                    resonator = _make_resonator(sensor_id, wiring_path, resonator_cls)
                    self.assembly.resonators.append(resonator)
                    self.assembly.sensor_id_to_resonator[sensor_id] = resonator

    def _collect_qubits(self, wiring_by_element: Mapping[str, Any]):
        element_type = "qubits"
        for qubit_id, wiring_by_line_type in _sorted_items(wiring_by_element):
            qubit_index = qubit_id[1:]
            for line_type, ports in _sorted_items(wiring_by_line_type):
                _validate_line_type(element_type, line_type)
                wiring_path = f"#/wiring/{element_type}/{qubit_id}/{line_type}"
                if line_type == WiringLineType.DRIVE.value:
                    drive_type = _validate_drive_ports(qubit_id, ports)
                    self.assembly.qubit_id_to_xy_info[qubit_id] = (drive_type, wiring_path, ports)
                elif line_type == WiringLineType.PLUNGER_GATE.value:
                    plunger_gate = _make_voltage_gate(f"plunger_{qubit_index}", wiring_path)
                    self.assembly.plunger_channels.append(plunger_gate)
                    self.assembly.plunger_id_to_channel[plunger_gate.id] = plunger_gate

    def _collect_qubit_pairs(self, wiring_by_element: Mapping[str, Any]):
        element_type = "qubit_pairs"
        for qubit_pair_id, wiring_by_line_type in _sorted_items(wiring_by_element):
            for line_type, ports in _sorted_items(wiring_by_line_type):
                _validate_line_type(element_type, line_type)
                wiring_path = f"#/wiring/{element_type}/{qubit_pair_id}/{line_type}"
                if line_type == WiringLineType.BARRIER_GATE.value:
                    barrier_gate = _make_voltage_gate(
                        f"barrier_{self.assembly.barrier_counter}", wiring_path
                    )
                    self.assembly.barrier_counter += 1
                    self.assembly.barrier_channels.append(barrier_gate)
                    self.assembly.barrier_id_to_channel[barrier_gate.id] = barrier_gate
                    self.assembly.qubit_pair_id_to_barrier_id[qubit_pair_id] = barrier_gate.id

    def _create_virtual_gate_set(self):
        virtual_channel_mapping: Dict[str, VoltageGate] = {}

        plunger_virtual, plunger_physical_to_virtual = _build_virtual_mapping(
            "virtual_dot", self.assembly.plunger_channels
        )
        barrier_virtual, barrier_physical_to_virtual = _build_virtual_mapping(
            "virtual_barrier", self.assembly.barrier_channels
        )
        sensor_virtual, sensor_physical_to_virtual = _build_virtual_mapping(
            "virtual_sensor", self.assembly.sensor_channels
        )
        global_virtual, global_physical_to_virtual = _build_virtual_mapping(
            "virtual_global", self.assembly.global_gates
        )

        virtual_channel_mapping.update(plunger_virtual)
        virtual_channel_mapping.update(barrier_virtual)
        virtual_channel_mapping.update(sensor_virtual)
        virtual_channel_mapping.update(global_virtual)

        self.assembly.plunger_virtual_names = plunger_physical_to_virtual
        self.assembly.barrier_virtual_names = barrier_physical_to_virtual
        self.assembly.sensor_virtual_names = sensor_physical_to_virtual
        self.assembly.global_virtual_names = global_physical_to_virtual

        if not virtual_channel_mapping:
            return

        self.machine.create_virtual_gate_set(
            virtual_channel_mapping=virtual_channel_mapping,
            gate_set_id=self.assembly.gate_set_id,
        )

    def _register_channels(self):
        if not (
            self.assembly.plunger_channels
            or self.assembly.sensor_channels
            or self.assembly.barrier_channels
            or self.assembly.global_gates
        ):
            return

        sensor_resonator_mappings = {}
        for sensor_id, channel in self.assembly.sensor_id_to_channel.items():
            resonator = self.assembly.sensor_id_to_resonator.get(sensor_id)
            if resonator is None:
                raise ValueError(f"Missing resonator wiring for sensor gate '{sensor_id}'")
            sensor_resonator_mappings[channel] = resonator

        self.machine.register_channel_elements(
            plunger_channels=self.assembly.plunger_channels,
            sensor_resonator_mappings=sensor_resonator_mappings,
            barrier_channels=self.assembly.barrier_channels,
            global_gates=self.assembly.global_gates if self.assembly.global_gates else None,
        )

        self.machine.active_sensor_dot_names = [
            name for _, name in _sorted_items(self.assembly.sensor_virtual_names)
        ]
        self.machine.active_global_gate_names = [
            name for _, name in _sorted_items(self.assembly.global_virtual_names)
        ]

    def _register_qubits(self):
        from quam_builder.architecture.superconducting.components.xy_drive import (
            XYDriveIQ,
            XYDriveMW,
        )

        if not self.assembly.plunger_channels:
            if self._wiring_by_type.get("qubits"):
                raise ValueError("No plunger gates collected while qubit wiring is defined")
            return

        number_of_qubits = len(self.assembly.plunger_channels)
        for qubit_number, plunger_id in enumerate(
            sorted(self.assembly.plunger_id_to_channel, key=_natural_sort_key)
        ):
            _, qubit_suffix = plunger_id.split("_", 1)
            qubit_name = f"q{qubit_suffix}"
            xy_channel = None

            if qubit_name in self.assembly.qubit_id_to_xy_info:
                xy_type, wiring_path, _ = self.assembly.qubit_id_to_xy_info[qubit_name]
                if xy_type == "IQ":
                    xy_channel = XYDriveIQ(
                        id=f"{qubit_name}_xy",
                        opx_output_I=f"{wiring_path}/opx_output_I",
                        opx_output_Q=f"{wiring_path}/opx_output_Q",
                        frequency_converter_up=f"{wiring_path}/frequency_converter_up",
                    )
                elif xy_type == "MW":
                    xy_channel = XYDriveMW(
                        id=f"{qubit_name}_xy",
                        opx_output=f"{wiring_path}/opx_output",
                    )

            self.machine.register_qubit(
                quantum_dot_id=self.assembly.plunger_virtual_names[plunger_id],
                qubit_name=qubit_name,
                xy_channel=xy_channel,
            )
            self.machine.qubits[qubit_name].grid_location = _set_default_grid_location(
                qubit_number, number_of_qubits
            )
            self.machine.active_qubit_names.append(qubit_name)

    def _register_qubit_pairs(self):
        """
        Register all qubit pairs in the assembly, and both combinations
        of control and target qubits for each pair.
        :return:
        """
        qubit_pair_wiring = self._wiring_by_type.get("qubit_pairs")
        if not qubit_pair_wiring:
            return

        self.machine.active_qubit_pair_names = []
        for qubit_pair_id in sorted(qubit_pair_wiring, key=_natural_sort_key):
            q0_name, q1_name = _parse_qubit_pair_ids(qubit_pair_id)
            pairs = [[q0_name, q1_name], [q1_name, q0_name]]
            for pair in pairs:
                qc_name, qt_name = pair
                self._register_qubit_pairs_by_name(qc_name, qt_name, qubit_pair_id)

    def _register_qubit_pairs_by_name(self, qc_name, qt_name, qubit_pair_id):
        qc_plunger_id = f"plunger_{qc_name[1:]}"
        qt_plunger_id = f"plunger_{qt_name[1:]}"

        normalized_pair_id = f"{qc_name}_{qt_name}"
        if normalized_pair_id in self._normalized_pair_sensor_map:
            requested_sensors = self._normalized_pair_sensor_map[normalized_pair_id]
            sensor_dot_ids = [
                self._resolve_sensor_virtual_name(normalized_pair_id, sensor)
                for sensor in requested_sensors
            ]
        else:
            sensor_dot_ids = [name for _, name in _sorted_items(self.assembly.sensor_virtual_names)]

        barrier_gate_id = None
        physical_barrier_id = self.assembly.qubit_pair_id_to_barrier_id.get(qubit_pair_id)
        if physical_barrier_id:
            barrier_gate_id = self.assembly.barrier_virtual_names.get(physical_barrier_id)
            if barrier_gate_id is None:
                raise ValueError(
                    f"Barrier gate '{physical_barrier_id}' has no registered virtual mapping"
                )

        if (
            qc_plunger_id not in self.assembly.plunger_virtual_names
            or qt_plunger_id not in self.assembly.plunger_virtual_names
        ):
            raise ValueError(
                f"Plunger gates for qubit pair '{qubit_pair_id}' not registered: "
                f"missing {qc_plunger_id if qc_plunger_id not in self.assembly.plunger_virtual_names else qt_plunger_id}"
            )

        self.machine.register_quantum_dot_pair(
            id=f"dot{qc_name[1:]}_dot{qt_name[1:]}_pair",
            quantum_dot_ids=[
                self.assembly.plunger_virtual_names[qc_plunger_id],
                self.assembly.plunger_virtual_names[qt_plunger_id],
            ],
            sensor_dot_ids=sensor_dot_ids,
            barrier_gate_id=barrier_gate_id,
        )
        self.machine.register_qubit_pair(
            id=f"{qc_name}_{qt_name}",
            qubit_control_name=qc_name,
            qubit_target_name=qt_name,
        )
        self.machine.active_qubit_pair_names.append(f"{qc_name}_{qt_name}")

    def _resolve_sensor_virtual_name(self, pair_id: str, sensor: str) -> str:
        allowed_formats = (
            "virtual_sensor_<n>, sensor_<n>, or s<n> (e.g., virtual_sensor_1, sensor_1, s1)"
        )
        if not isinstance(sensor, str):
            raise ValueError(
                f"Sensor mapping for pair '{pair_id}' must contain string identifiers; "
                f"supported formats: {allowed_formats}"
            )

        normalized_sensor = sensor
        if sensor.startswith("s") and sensor[1:].isdigit():
            normalized_sensor = f"sensor_{sensor[1:]}"

        if normalized_sensor.startswith("sensor_") and normalized_sensor[7:].isdigit():
            if normalized_sensor not in self.assembly.sensor_virtual_names:
                raise ValueError(
                    f"Sensor '{sensor}' for pair '{pair_id}' is not registered. "
                    f"Use {allowed_formats} and ensure the sensor exists in wiring."
                )
            return self.assembly.sensor_virtual_names[normalized_sensor]

        if (
            normalized_sensor.startswith("virtual_sensor_")
            and normalized_sensor[len("virtual_sensor_") :].isdigit()
        ):
            if normalized_sensor not in self.assembly.sensor_virtual_names.values():
                raise ValueError(
                    f"Sensor '{sensor}' for pair '{pair_id}' is not registered. "
                    f"Use {allowed_formats} and ensure the sensor exists in wiring."
                )
            return normalized_sensor

        raise ValueError(
            f"Sensor identifier '{sensor}' for pair '{pair_id}' is invalid. "
            f"Supported formats: {allowed_formats}"
        )
