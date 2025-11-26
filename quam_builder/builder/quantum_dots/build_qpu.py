from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from numpy import ceil, sqrt
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.architecture.superconducting.qpu import AnyQuam


def _set_default_grid_location(qubit_number: int, total_number_of_qubits: int) -> str:
    """Sets a simple grid layout for visualization/placement."""

    number_of_rows = int(ceil(sqrt(total_number_of_qubits)))
    y = qubit_number % number_of_rows
    x = qubit_number // number_of_rows
    return f"{x},{y}"


@dataclass
class QpuAssembly:
    """Holds intermediate channel objects and wiring lookups during QPU build."""

    global_gates: List = field(default_factory=list)
    plunger_channels: List[VoltageGate] = field(default_factory=list)
    barrier_channels: List[VoltageGate] = field(default_factory=list)
    sensor_channels: List[VoltageGate] = field(default_factory=list)
    resonators: List = field(default_factory=list)
    plunger_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    barrier_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    sensor_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    sensor_id_to_resonator: Dict[str, object] = field(default_factory=dict)
    qubit_id_to_xy_info: Dict[str, Tuple[str, str, object]] = field(default_factory=dict)


class _QpuBuilder:
    """Handles wiring-to-component translation and QPU registration."""

    def __init__(self, machine: AnyQuam):
        self.machine = machine
        self.assembly = QpuAssembly()

    def build(self) -> AnyQuam:
        self._collect_physical_channels()
        self._create_virtual_gate_set()
        self._register_channels()
        self._register_qubits()
        self._register_qubit_pairs()
        return self.machine

    def _collect_physical_channels(self):
        from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle
        from quam_builder.builder.qop_connectivity.channel_ports import (
            iq_out_channel_ports,
            mw_out_channel_ports,
        )

        for element_type, wiring_by_element in self.machine.wiring.items():
            if element_type == "global_gates":
                self._collect_global_gates(wiring_by_element)
            elif element_type == "sensor_dots":
                self._collect_sensor_dots(wiring_by_element, ReadoutResonatorSingle)
            elif element_type == "qubits":
                self._collect_qubits(
                    wiring_by_element,
                    iq_out_channel_ports=iq_out_channel_ports,
                    mw_out_channel_ports=mw_out_channel_ports,
                )
            elif element_type == "qubit_pairs":
                self._collect_qubit_pairs(wiring_by_element)

    def _collect_global_gates(self, wiring_by_element):
        self.machine.active_global_gate_names = []
        number_of_global_gates = len(wiring_by_element.items())
        for global_gate_number, (global_gate_id, wiring_by_line_type) in enumerate(
            wiring_by_element.items()
        ):
            global_gate_class = self.machine.global_gate_type[global_gate_id]
            global_gate = global_gate_class(id=global_gate_id)
            self.machine.global_gates[global_gate_id] = global_gate
            global_gate.grid_location = _set_default_grid_location(
                global_gate_number, number_of_global_gates
            )
            for line_type, ports in wiring_by_line_type.items():
                wiring_path = self._wiring_path("global_gates", global_gate_id, line_type)
                if line_type == WiringLineType.GLOBAL_GATE.value:
                    self.assembly.global_gates.append(
                        VoltageGate(id=global_gate_id, opx_output=f"{wiring_path}/opx_output")
                    )
                else:
                    raise ValueError(f"Unknown line type: {line_type}")
            self.machine.active_global_gate_names.append(global_gate.name)

    def _collect_sensor_dots(self, wiring_by_element, resonator_cls):
        for sensor_dot_id, wiring_by_line_type in wiring_by_element.items():
            for line_type, ports in wiring_by_line_type.items():
                wiring_path = self._wiring_path("sensor_dots", sensor_dot_id, line_type)
                if line_type == WiringLineType.SENSOR_GATE.value:
                    sensor_gate = VoltageGate(
                        id=sensor_dot_id, opx_output=f"{wiring_path}/opx_output"
                    )
                    self.assembly.sensor_channels.append(sensor_gate)
                    self.assembly.sensor_id_to_channel[sensor_dot_id] = sensor_gate
                elif line_type == WiringLineType.RF_RESONATOR.value:
                    resonator = resonator_cls(
                        id=f"{sensor_dot_id}_resonator",
                        opx_output=f"{wiring_path}/opx_output",
                        opx_input=f"{wiring_path}/opx_input",
                    )
                    self.assembly.resonators.append(resonator)
                    self.assembly.sensor_id_to_resonator[sensor_dot_id] = resonator

    def _collect_qubits(self, wiring_by_element, iq_out_channel_ports, mw_out_channel_ports):
        for qubit_id, wiring_by_line_type in wiring_by_element.items():
            for line_type, ports in wiring_by_line_type.items():
                wiring_path = self._wiring_path("qubits", qubit_id, line_type)
                if line_type == WiringLineType.DRIVE.value:
                    if all(key in ports for key in iq_out_channel_ports):
                        self.assembly.qubit_id_to_xy_info[qubit_id] = ("IQ", wiring_path, ports)
                    elif all(key in ports for key in mw_out_channel_ports):
                        self.assembly.qubit_id_to_xy_info[qubit_id] = ("MW", wiring_path, ports)
                elif line_type == WiringLineType.PLUNGER_GATE.value:
                    plunger_gate = VoltageGate(id=qubit_id, opx_output=f"{wiring_path}/opx_output")
                    self.assembly.plunger_channels.append(plunger_gate)
                    self.assembly.plunger_id_to_channel[qubit_id] = plunger_gate

    def _collect_qubit_pairs(self, wiring_by_element):
        for qubit_pair_id, wiring_by_line_type in wiring_by_element.items():
            for line_type, ports in wiring_by_line_type.items():
                wiring_path = self._wiring_path("qubit_pairs", qubit_pair_id, line_type)
                if line_type == WiringLineType.BARRIER_GATE.value:
                    barrier_gate = VoltageGate(
                        id=qubit_pair_id, opx_output=f"{wiring_path}/opx_output"
                    )
                    self.assembly.barrier_channels.append(barrier_gate)
                    self.assembly.barrier_id_to_channel[qubit_pair_id] = barrier_gate

    def _create_virtual_gate_set(self):
        virtual_channel_mapping: Dict[str, VoltageGate] = {}
        for dot_id, channel in self.assembly.plunger_id_to_channel.items():
            virtual_channel_mapping[dot_id] = channel
        for barrier_id, channel in self.assembly.barrier_id_to_channel.items():
            virtual_channel_mapping[barrier_id] = channel
        for sensor_id, channel in self.assembly.sensor_id_to_channel.items():
            virtual_channel_mapping[sensor_id] = channel

        if virtual_channel_mapping:
            self.machine.create_virtual_gate_set(
                virtual_channel_mapping=virtual_channel_mapping,
                gate_set_id="main_qpu",
            )

    def _register_channels(self):
        if not (
            self.assembly.plunger_channels
            or self.assembly.sensor_channels
            or self.assembly.barrier_channels
        ):
            return

        sensor_resonator_mappings = {
            self.assembly.sensor_id_to_channel[sid]: self.assembly.sensor_id_to_resonator[sid]
            for sid in self.assembly.sensor_id_to_channel.keys()
            if sid in self.assembly.sensor_id_to_resonator
        }
        self.machine.register_channel_elements(
            plunger_channels=self.assembly.plunger_channels,
            sensor_resonator_mappings=sensor_resonator_mappings,
            barrier_channels=self.assembly.barrier_channels,
            global_gates=self.assembly.global_gates if self.assembly.global_gates else None,
        )
        self.machine.active_sensor_dot_names = list(self.assembly.sensor_id_to_channel.keys())

    def _register_qubits(self):
        from quam_builder.architecture.superconducting.components.xy_drive import (
            XYDriveIQ,
            XYDriveMW,
        )

        self.machine.active_qubit_names = []
        number_of_qubits = len(self.assembly.plunger_channels)
        for qubit_number, qubit_id in enumerate(self.assembly.plunger_id_to_channel.keys()):
            qubit_name = self._qubit_name(qubit_id)
            xy_channel = None

            if qubit_id in self.assembly.qubit_id_to_xy_info:
                xy_type, wiring_path, _ = self.assembly.qubit_id_to_xy_info[qubit_id]
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
                quantum_dot_id=qubit_id,
                qubit_name=qubit_name,
                qubit_type="loss_divincenzo",
                xy_channel=xy_channel,
            )
            self.machine.qubits[qubit_name].grid_location = _set_default_grid_location(
                qubit_number, number_of_qubits
            )
            self.machine.active_qubit_names.append(qubit_name)

    def _register_qubit_pairs(self):
        if "qubit_pairs" not in self.machine.wiring:
            return

        self.machine.active_qubit_pair_names = []
        for qubit_pair_id in self.machine.wiring["qubit_pairs"].keys():
            qc_id, qt_id = qubit_pair_id.split("_")
            qc_name = self._qubit_name(qc_id)
            qt_name = self._qubit_name(qt_id)

            sensor_dot_ids = list(self.assembly.sensor_id_to_channel.keys()) if self.assembly.sensor_id_to_channel else []

            if qc_id in self.assembly.plunger_id_to_channel and qt_id in self.assembly.plunger_id_to_channel:
                self.machine.register_quantum_dot_pair(
                    id=f"dot{qc_id}_dot{qt_id}_pair",
                    quantum_dot_ids=[qc_id, qt_id],
                    sensor_dot_ids=sensor_dot_ids,
                    barrier_gate_id=qubit_pair_id if qubit_pair_id in self.assembly.barrier_id_to_channel else None,
                )
                self.machine.register_qubit_pair(
                    id=qubit_pair_id,
                    qubit_type="loss_divincenzo",
                    qubit_control_name=qc_name,
                    qubit_target_name=qt_name,
                )
                self.machine.active_qubit_pair_names.append(qubit_pair_id)

    @staticmethod
    def _wiring_path(element_type: str, element_id: str, line_type: str) -> str:
        return f"#/wiring/{element_type}/{element_id}/{line_type}"

    @staticmethod
    def _qubit_name(qubit_id: str) -> str:
        return f"Q{qubit_id.split('_')[-1] if '_' in qubit_id else qubit_id}"
