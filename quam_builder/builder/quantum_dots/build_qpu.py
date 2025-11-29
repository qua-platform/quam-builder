import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from numpy import ceil, sqrt
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorSingle,
    VoltageGate,
)
from quam_builder.architecture.superconducting.qpu import AnyQuam
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_out_channel_ports,
    mw_out_channel_ports,
)
from quam.components import StickyChannelAddon, pulses

DEFAULT_GATE_SET_ID = "main_qpu"
DEFAULT_STICKY_DURATION = 16
DEFAULT_INTERMEDIATE_FREQUENCY = 500e6
DEFAULT_READOUT_LENGTH = 200
DEFAULT_READOUT_AMPLITUDE = 0.01

_ELEMENT_TYPE_ALIASES = {
    "globals": "globals",
    "global_gates": "globals",
    "readout": "readout",
    "sensor_dots": "readout",
    "qubits": "qubits",
    "qubit_pairs": "qubit_pairs",
}

_ALLOWED_LINE_TYPES = {
    "readout": {WiringLineType.SENSOR_GATE.value, WiringLineType.RF_RESONATOR.value},
    "qubits": {WiringLineType.DRIVE.value, WiringLineType.PLUNGER_GATE.value},
    "qubit_pairs": {WiringLineType.BARRIER_GATE.value},
}


def _natural_sort_key(value: str) -> Tuple[Any, ...]:
    match = re.match(r"(.*?)(\d+)$", value)
    if match:
        prefix, number = match.groups()
        return (prefix, int(number))
    return (value, 0)


def _sorted_items(mapping: Mapping[str, Any]) -> Iterable[Tuple[str, Any]]:
    for key in sorted(mapping, key=_natural_sort_key):
        yield key, mapping[key]


def _normalize_element_type(element_type: str) -> str:
    try:
        return _ELEMENT_TYPE_ALIASES[element_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported element type '{element_type}' in wiring") from exc


def _validate_line_type(element_type: str, line_type: str) -> None:
    allowed = _ALLOWED_LINE_TYPES.get(element_type)
    if allowed is not None and line_type not in allowed:
        raise ValueError(
            f"Unsupported line type '{line_type}' for element type '{element_type}'. "
            f"Allowed: {sorted(allowed)}"
        )


def _set_default_grid_location(qubit_number: int, total_number_of_qubits: int) -> str:
    """Sets a simple grid layout for visualization/placement."""

    if total_number_of_qubits <= 0:
        raise ValueError("total_number_of_qubits must be positive")

    number_of_rows = int(ceil(sqrt(total_number_of_qubits)))
    y = qubit_number % number_of_rows
    x = qubit_number // number_of_rows
    return f"{x},{y}"


def _make_sticky_channel() -> StickyChannelAddon:
    return StickyChannelAddon(duration=DEFAULT_STICKY_DURATION, digital=False)


def _make_voltage_gate(gate_id: str, wiring_path: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=f"{wiring_path}/opx_output",
        sticky=_make_sticky_channel(),
    )


def _make_resonator(sensor_id: str, wiring_path: str, resonator_cls: Any) -> ReadoutResonatorSingle:
    return resonator_cls(
        id=f"{sensor_id}_resonator",
        frequency_bare=0,
        intermediate_frequency=DEFAULT_INTERMEDIATE_FREQUENCY,
        operations={
            "readout": pulses.SquareReadoutPulse(
                length=DEFAULT_READOUT_LENGTH, id="readout", amplitude=DEFAULT_READOUT_AMPLITUDE
            )
        },
        opx_output=f"{wiring_path}/opx_output",
        opx_input=f"{wiring_path}/opx_input",
        sticky=_make_sticky_channel(),
    )


def _validate_drive_ports(qubit_id: str, ports: Mapping[str, Any]) -> str:
    has_iq = all(key in ports for key in iq_out_channel_ports)
    has_mw = all(key in ports for key in mw_out_channel_ports)

    if has_iq and has_mw:
        raise ValueError(f"Qubit {qubit_id} wiring is ambiguous: matches both IQ and MW drive ports")
    if not has_iq and not has_mw:
        raise ValueError(
            f"Qubit {qubit_id} wiring is incomplete: missing IQ ports {iq_out_channel_ports} "
            f"and MW ports {mw_out_channel_ports}"
        )
    return "IQ" if has_iq else "MW"


def _build_virtual_mapping(
    prefix: str, channels: Sequence[VoltageGate]
) -> Tuple[Dict[str, VoltageGate], Dict[str, str]]:
    virtual_to_channel: Dict[str, VoltageGate] = {}
    physical_to_virtual: Dict[str, str] = {}

    for index, channel in enumerate(channels, start=1):
        virtual_name = f"{prefix}_{index}"
        virtual_to_channel[virtual_name] = channel
        physical_to_virtual[channel.id] = virtual_name

    return virtual_to_channel, physical_to_virtual


def _parse_qubit_pair_ids(qubit_pair_id: str) -> Tuple[str, str]:
    if "-" in qubit_pair_id:
        control, target = qubit_pair_id.split("-", 1)
    elif "_" in qubit_pair_id:
        control, target = qubit_pair_id.split("_", 1)
    else:
        raise ValueError(
            f"Qubit pair id '{qubit_pair_id}' is invalid: expected '-' or '_' delimiter"
        )
    def _ensure_q_prefix(qubit_token: str) -> str:
        return qubit_token if qubit_token.startswith("q") else f"q{qubit_token}"

    control = _ensure_q_prefix(control)
    target = _ensure_q_prefix(target)
    return control, target


@dataclass
class QpuAssembly:
    """Holds intermediate channel objects and wiring lookups during QPU build."""

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
    """Handles wiring-to-component translation and QPU registration."""

    def __init__(self, machine: AnyQuam):
        self.machine = machine
        self.assembly = QpuAssembly()
        self._wiring_by_type: Dict[str, Mapping[str, Any]] = {}

    def build(self) -> AnyQuam:
        self.assembly = QpuAssembly()
        self.machine.active_global_gate_names = []
        self.machine.active_sensor_dot_names = []
        self.machine.active_qubit_names = []
        self.machine.active_qubit_pair_names = []

        self._wiring_by_type = self._normalize_wiring(self.machine.wiring or {})
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
            sensor_id = f"sensor_{sensor_dot_id[1:]}" if len(sensor_dot_id) > 1 else f"sensor_{sensor_dot_id}"
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
                qubit_type="loss_divincenzo",
                quantum_dot_id=self.assembly.plunger_virtual_names[plunger_id],
                qubit_name=qubit_name,
                xy_channel=xy_channel,
            )
            self.machine.qubits[qubit_name].grid_location = _set_default_grid_location(
                qubit_number, number_of_qubits
            )
            self.machine.active_qubit_names.append(qubit_name)

    def _register_qubit_pairs(self):
        qubit_pair_wiring = self._wiring_by_type.get("qubit_pairs")
        if not qubit_pair_wiring:
            return

        self.machine.active_qubit_pair_names = []
        for qubit_pair_id in sorted(qubit_pair_wiring, key=_natural_sort_key):
            qc_name, qt_name = _parse_qubit_pair_ids(qubit_pair_id)

            qc_plunger_id = f"plunger_{qc_name[1:]}"
            qt_plunger_id = f"plunger_{qt_name[1:]}"

            sensor_dot_ids = [
                name for _, name in _sorted_items(self.assembly.sensor_virtual_names)
            ]

            barrier_gate_id = None
            physical_barrier_id = self.assembly.qubit_pair_id_to_barrier_id.get(
                qubit_pair_id
            )
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
                qubit_type="loss_divincenzo",
                qubit_control_name=qc_name,
                qubit_target_name=qt_name,
            )
            self.machine.active_qubit_pair_names.append(f"{qc_name}_{qt_name}")
