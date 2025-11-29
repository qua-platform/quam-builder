from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from numpy import ceil, sqrt
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.architecture.superconducting.qpu import AnyQuam
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle
from quam_builder.builder.qop_connectivity.channel_ports import (
    iq_out_channel_ports,
    mw_out_channel_ports,
)
from quam.components import StickyChannelAddon, pulses


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
    barrier_counter: int = 1
    resonators: List = field(default_factory=list)
    plunger_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    barrier_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    sensor_id_to_channel: Dict[str, VoltageGate] = field(default_factory=dict)
    sensor_id_to_resonator: Dict[str, object] = field(default_factory=dict)
    qubit_id_to_xy_info: Dict[str, Tuple[str, str, object]] = field(default_factory=dict)
    qubit_pair_id_to_barrier_id: Dict[str, str] = field(default_factory=dict)


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

        for element_type, wiring_by_element in self.machine.wiring.items():
            if element_type == "globals":
                self._collect_global_gates(wiring_by_element)
            elif element_type == "readout":
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
        element_type='globals'
        self.machine.active_global_gate_names = []
        for global_gate_number, (global_gate_id, wiring_by_line_type) in enumerate(
            wiring_by_element.items()
        ):
            for line_type, ports in wiring_by_line_type.items():

                wiring_path = f"#/wiring/{element_type}/{global_gate_id}/{line_type}"
                self.assembly.global_gates.append(
                    VoltageGate(
                        id=global_gate_id,
                        opx_output=f'{wiring_path}/opx_output',
                        sticky=StickyChannelAddon(duration=16, digital=False),
                    )
                )

    def _collect_sensor_dots(self, wiring_by_element, resonator_cls):
        element_type = 'readout'
        for sensor_dot_id, wiring_by_line_type in wiring_by_element.items():
            for line_type, ports in wiring_by_line_type.items():
                wiring_path = f"#/wiring/{element_type}/{sensor_dot_id}/{line_type}"
                if line_type == WiringLineType.SENSOR_GATE.value:
                    sensor_gate = VoltageGate(
                        id=f'sensor_{sensor_dot_id[1:]}',
                        opx_output=f"{wiring_path}/opx_output",
                        sticky=StickyChannelAddon(duration=16, digital=False),
                    )
                    self.assembly.sensor_channels.append(sensor_gate)
                    self.assembly.sensor_id_to_channel[sensor_gate.id] = sensor_gate

                elif line_type == WiringLineType.RF_RESONATOR.value:
                    resonator = resonator_cls(
                        id=f"sensor_{sensor_dot_id[1:]}_resonator",
                        frequency_bare=0,
                        intermediate_frequency=500e6,
                        operations={
                            "readout": pulses.SquareReadoutPulse(
                                length=200, id="readout", amplitude=0.01
                            )
                        },
                        opx_output=f"{wiring_path}/opx_output",
                        opx_input=f"{wiring_path}/opx_input",
                        sticky=StickyChannelAddon(duration=16, digital=False),
                    )
                    self.assembly.resonators.append(resonator)
                    self.assembly.sensor_id_to_resonator[f'sensor_{sensor_dot_id[1:]}'] = resonator

    def _collect_qubits(self, wiring_by_element, iq_out_channel_ports, mw_out_channel_ports):
        element_type = 'qubits'
        for qubit_id, wiring_by_line_type in wiring_by_element.items():
            qubit_index = qubit_id[1:]
            for line_type, ports in wiring_by_line_type.items():
                wiring_path = f"#/wiring/{element_type}/{qubit_id}/{line_type}"
                if line_type == WiringLineType.DRIVE.value:
                    if all(key in ports for key in iq_out_channel_ports):
                        self.assembly.qubit_id_to_xy_info[qubit_id] = ("IQ", wiring_path, ports)
                    elif all(key in ports for key in mw_out_channel_ports):
                        self.assembly.qubit_id_to_xy_info[qubit_id] = ("MW", wiring_path, ports)
                elif line_type == WiringLineType.PLUNGER_GATE.value:
                    plunger_gate = VoltageGate(
                        id=f'plunger_{qubit_index}',
                        opx_output=f"{wiring_path}/opx_output",
                        sticky=StickyChannelAddon(duration=16, digital=False),
                    )
                    self.assembly.plunger_channels.append(plunger_gate)
                    self.assembly.plunger_id_to_channel[plunger_gate.id] = plunger_gate

    def _collect_qubit_pairs(self, wiring_by_element):
        element_type = 'qubit_pairs'
        for qubit_pair_id, wiring_by_line_type in wiring_by_element.items():
            for line_type, ports in wiring_by_line_type.items():
                wiring_path = f"#/wiring/{element_type}/{qubit_pair_id}/{line_type}"
                if line_type == WiringLineType.BARRIER_GATE.value:
                    barrier_gate = VoltageGate(
                        id=f'barrier_{self.assembly.barrier_counter}',
                        opx_output=f"{wiring_path}/opx_output",
                        sticky=StickyChannelAddon(duration=16, digital=False),
                    )
                    self.assembly.barrier_counter += 1
                    self.assembly.barrier_channels.append(barrier_gate)
                    self.assembly.barrier_id_to_channel[barrier_gate.id] = barrier_gate
                    self.assembly.qubit_pair_id_to_barrier_id[qubit_pair_id] = barrier_gate.id

    def _create_virtual_gate_set(self):

        self.machine.create_virtual_gate_set(
            virtual_channel_mapping={
                **{f"virtual_dot_{i+1}": p for i, p in enumerate(self.assembly.plunger_channels)},
                **{f"virtual_barrier_{i+1}": b for i, b in enumerate(self.assembly.barrier_channels)},
                **{f"virtual_sensor_{i+1}": s for i, s in enumerate(self.assembly.sensor_channels)},
            },
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
            s: r for s, r in zip(self.assembly.sensor_channels, self.assembly.resonators)
        }
        self.machine.register_channel_elements(
            plunger_channels=self.assembly.plunger_channels,
            sensor_resonator_mappings=sensor_resonator_mappings,
            barrier_channels=self.assembly.barrier_channels,
            global_gates=self.assembly.global_gates if self.assembly.global_gates else None,
        )
        self.machine.active_sensor_dot_names = [n.id for n in self.assembly.sensor_channels]

    def _register_qubits(self):
        from quam_builder.architecture.superconducting.components.xy_drive import (
            XYDriveIQ,
            XYDriveMW,
        )

        self.machine.active_qubit_names = []
        number_of_qubits = len(self.assembly.plunger_channels)
        for qubit_number, qubit_id in enumerate(self.assembly.plunger_id_to_channel.keys()):
            _, qubit_id = qubit_id.split("_")
            qubit_name = f"q{qubit_id}"
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
                quantum_dot_id=f'virtual_dot_{qubit_id}',
                qubit_name=qubit_name,
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
            qc_id, qt_id = qubit_pair_id.split("-")
            qc_name = qc_id
            qt_name = f'q{qt_id}'

            # Convert to plunger gate IDs
            qc_plunger_id = f'plunger_{qc_id[1:]}'
            qt_plunger_id = f'plunger_{qt_id}'

            # Get virtual sensor names (matching how they're registered in virtual gate set)
            sensor_dot_ids = [f"virtual_sensor_{i+1}" for i in range(len(self.assembly.sensor_channels))]

            # Get barrier gate ID if it exists and convert to virtual name
            barrier_gate_id = None
            physical_barrier_id = self.assembly.qubit_pair_id_to_barrier_id.get(qubit_pair_id, None)
            if physical_barrier_id:
                # Convert physical barrier ID to virtual name based on its position
                barrier_index = list(self.assembly.barrier_id_to_channel.keys()).index(physical_barrier_id)
                barrier_gate_id = f"virtual_barrier_{barrier_index + 1}"

            if qc_plunger_id in self.assembly.plunger_id_to_channel and qt_plunger_id in self.assembly.plunger_id_to_channel:
                self.machine.register_quantum_dot_pair(
                    id=f"dot{qc_name[1:]}_dot{qt_name[1:]}_pair",
                    quantum_dot_ids=[f'virtual_dot_{qc_name[1:]}', f'virtual_dot_{qt_name[1:]}'],
                    sensor_dot_ids=sensor_dot_ids,
                    barrier_gate_id=barrier_gate_id,
                )
                self.machine.register_qubit_pair(
                    id=f"{qc_name}_{qt_name}",
                    qubit_type="loss_divincenzo",
                    qubit_control_name=qc_name,
                    qubit_target_name=qt_name,
                )
                self.machine.active_qubit_pair_names.append(qubit_pair_id)