from pathlib import Path
from typing import (
    List,
    Dict,
    Union,
    ClassVar,
    Optional,
    Literal,
    Sequence,
    Mapping,
    Any,
)
from dataclasses import field
import numpy as np
import importlib

from qm import QuantumMachinesManager
from qm.octave import QmOctaveConfig
from qm.qua.type_hints import QuaVariable, StreamType
from qm.qua import declare, fixed, declare_stream

from quam.serialisation import JSONSerialiser
from quam.components import Octave, FrequencyConverter
from quam.components import Channel, pulses
from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer
from quam.core import quam_dataclass, QuamRoot, QuamBase

from quam_builder.architecture.quantum_dots.components import (
    VirtualGateSet,
    QuantumDot,
    VoltageGate,
    SensorDot,
    GlobalGate,
    BarrierGate,
    QuantumDotPair,
    ReadoutResonatorBase,
    ReservoirBase,
    DrainSingle,
    ReadoutTransportBase,
    VirtualDCSet,
)

from quam_builder.architecture.quantum_dots.components.global_gate import GlobalGate
from quam_builder.architecture.quantum_dots.components.dac_spec import QdacSpec
from quam_builder.tools.voltage_sequence import VoltageSequence
from quam_builder.architecture.quantum_dots.qubit import AnySpinQubit

__all__ = ["BaseQuamQD"]


@quam_dataclass
class BaseQuamQD(QuamRoot):
    """
    Example QUAM root component for a Quantum Dot Device

    Attributes:
        octaves (Dict[str, Octave]): A dictionary of Octave components.
        mixers (Dict[str, FrequencyConverter]): A dictionary of frequency converters.
        quantum_dots (Dict[str, QuantumDot]): A dictionary of registered QuantumDot objects.
        sensor_dots (Dict[str, SensorDot]): A dictionary of the registered SensorDot objects.
        barrier_gates (Dict[str, BarrierGate]): A dictionary of the BarrierGate objects.
        virtual_gate_sets (Dict[str, VirtualGateSet]): A dictionary of the VirtualGateSet instances covering your QPU.
        voltage_sequences (Dict[str, VoltageSequence]): A dictionary of the VoltageSequence object associated to each VirtualGateSet. Uniquely mapped.
        global_gates (Dict[str, GlobalGate]): Global gate components associated with back gate, reservoirs, or splitter gates.
        wiring (dict): The wiring configuration.
        network (dict): The network configuration.
        dac_config (dict): Per-DAC driver settings (same structure as passed to :meth:`set_dac_config`),
            serialised alongside ``wiring`` and ``network`` in ``wiring.json``.
        ports (Union[FEMPortsContainer, OPXPlusPortsContainer]): The ports container.
        _data_handler (ClassVar[DataHandler]): The data handler.
        qmm (ClassVar[Optional[QuantumMachinesManager]]): The Quantum Machines Manager.

    Methods:
        get_serialiser: Get the serialiser for the QuamRoot class, which is the JSONSerialiser.
        get_octave_config: Return the Octave configuration.
        connect: Open a Quantum Machine Manager with the credentials ("host" and "cluster_name") as defined in the network file.
        calibrate_octave_ports: Calibrate the Octave ports for all the active qubits.
        declare_qua_variables: Macro to declare the necessary QUA variables for all qubits.
        initialize_qpu: Initialize the QPU with the specified settings.
        create_virtual_gate_set: Creates a VirtualGateSet with the input physical channels, and layers a single compensation layer on top, with a default identity matrix.
        register_quantum_dots: Internally create QuantumDot objects from output physical channels.
        register_sensor_dots: Internally create SensorDot objects from output physical channels, and their associated ReadoutResonator objects.
        register_barrier_gates: Internally create BarrierGate objects from the output physical channels.
        register_channel_elements: Shortcut to run register_quantum_dots, register_sensor_dots, and register_barrier_gates, i.e. a shortcut to register all the HW channel outputs.
        add_point: Adds a named voltage point to a VirtualGateSet instance held internally.
        update_cross_compensation_submatrix: Input a list of virtual gates and a list of HW channels, as well as the associated correction submatrix. Internally it edits the VirtualGateSet matrix stored.
        update_full_cross_compensation: Update the full compensation matrix of the first VirtualGateSet layer.
        step_to_voltage: Steps the associated VoltageSequence to a dict of voltages.
    """

    physical_channels: Dict[str, Channel] = field(default_factory=dict)
    global_gates: Dict[str, GlobalGate] = field(default_factory=dict)

    virtual_gate_sets: Dict[str, VirtualGateSet] = field(default_factory=dict)
    virtual_dc_sets: Dict[str, VirtualDCSet] = field(default_factory=dict)
    voltage_sequences: Dict[str, VoltageSequence] = field(
        default_factory=dict, metadata={"exclude": True}
    )
    reservoirs: Dict[str, ReservoirBase] = field(default_factory=dict)
    dacs: Dict[str, Dict] = field(default_factory=dict, metadata={"exclude": True})

    quantum_dots: Dict[str, QuantumDot] = field(default_factory=dict)
    quantum_dot_pairs: Dict[str, QuantumDotPair] = field(default_factory=dict)
    sensor_dots: Dict[str, SensorDot] = field(default_factory=dict)
    barrier_gates: Dict[str, BarrierGate] = field(default_factory=dict)

    octaves: Dict[str, Octave] = field(default_factory=dict)
    mixers: Dict[str, FrequencyConverter] = field(default_factory=dict)
    wiring: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)
    dac_config: Dict[str, Any] = field(default_factory=dict)

    ports: Union[FEMPortsContainer, OPXPlusPortsContainer] = None

    qmm: ClassVar[Optional[QuantumMachinesManager]] = None

    @classmethod
    def get_serialiser(cls) -> JSONSerialiser:
        """Get the serialiser for the QuamRoot class, which is the JSONSerialiser.

        This method can be overridden by subclasses to provide a custom serialiser.
        """
        return JSONSerialiser(
            content_mapping={
                "wiring": "wiring.json",
                "network": "wiring.json",
                "dac_config": "wiring.json",
            }
        )

    def get_voltage_sequence(self, gate_set_id: str) -> VoltageSequence:
        if gate_set_id not in self.voltage_sequences:
            gate_set = self.virtual_gate_sets[gate_set_id]
            seq = gate_set.new_sequence()

            for qd_id, qd in self.quantum_dots.items():
                try:
                    qd_gate_set_name = self._get_virtual_gate_set(qd.physical_channel).id
                    if qd_gate_set_name == gate_set.id:
                        seq.state_trackers[qd.id].current_level = qd.current_voltage
                except (AttributeError, ValueError, KeyError):
                    pass

            self.voltage_sequences[gate_set_id] = seq
        return self.voltage_sequences[gate_set_id]

    def get_component(self, name: str) -> Union[AnySpinQubit, QuantumDot, SensorDot, BarrierGate]:
        """
        Retrieve a component object by name from qubits, qubit_pairs, quantum_dots, quantum_dot_pairs, sensor_dots, or barrier_gates

        Args:
            name: The name of the object
        """
        collections = [
            self.quantum_dots,
            self.sensor_dots,
            self.barrier_gates,
            self.quantum_dot_pairs,
        ]
        for collection in collections:
            if name in collection:
                return collection[name]

        raise ValueError(f"Element {name} not found in Quam")

    def connect_to_external_source(
        self,
        reset_voltages: bool = False,
    ) -> None:
        """
        Binds the channels to the correct external voltage source functions.

        Args:
            reset_voltages (bool): Whether to reset the voltages of each of the channels to the last-applied voltage, saved in the Quam state.

        DAC entries must be set on :attr:`dac_config` (e.g. via :meth:`set_dac_config`) and are
        stored in ``wiring.json`` when saving. Example entry:

        {
            "driver_module": "qcodes_contrib_drivers.drivers.QDevil.QDAC2",
            "driver_class": "QDac2",
            "connection": {"visalib": "@py", "address": "TCPIP::172.16.33.101::5025::SOCKET"},
            "channel_method": "channel",
            "accessor": "dc_constant_V",
            "is_qdac": true
        }
        """
        if not self.dac_config:
            raise ValueError(
                "No DAC configurations found. Set them with set_dac_config(...) or load from wiring.json."
            )

        dac_instances = self.dacs
        for dac_name, config in self.dac_config.items():
            module = importlib.import_module(config["driver_module"])
            dac_class = getattr(module, config["driver_class"])
            dac_instances[dac_name] = {
                "driver": dac_class(dac_name, **config["connection"]),
                "channel_method": config["channel_method"],
                "accessor": config["accessor"],
                "is_qdac": config.get("is_qdac", False),
            }

        for ch in self.physical_channels.values():
            dac_name = getattr(ch.dac_spec, "dac_name", "main")
            if dac_name not in dac_instances:
                print(f"WARNING: {ch.id} references {dac_name}, but no config found. Skipping")
                continue
            dac_info = dac_instances[dac_name]
            dac_channel = getattr(dac_info["driver"], dac_info["channel_method"])(
                ch.dac_spec.output_port
            )
            ch.offset_parameter = getattr(dac_channel, dac_info["accessor"])

            if (
                reset_voltages
                and hasattr(ch, "current_external_voltage")
                and ch.offset_parameter is not None
            ):
                ch.offset_parameter(ch.current_external_voltage)

    def _get_virtual_gate_set(self, channel: Channel) -> VirtualGateSet:
        """Find the internal VirtualGateSet associated with a particular output channel"""
        virtual_gate_set = None
        for vgs in list(self.virtual_gate_sets.values()):
            if channel in list(vgs.channels.values()):
                virtual_gate_set = vgs
        if virtual_gate_set is None:
            raise ValueError(f"Channel {channel.id} not found in any VirtualGateSet")
        return virtual_gate_set

    def _get_virtual_name(self, channel: Channel) -> str:
        """Return the name of the virtual gate associated with e particular output channel"""
        vgs_name = None
        for name, vgs in list(self.virtual_gate_sets.items()):
            if channel in list(vgs.channels.values()):
                vgs_name = name
                break

        if vgs_name is None:
            raise ValueError(f"Channel {channel.id} not found in any VirtualGateSet")
        vgs = self.virtual_gate_sets[vgs_name]

        physical_name = None
        for key, val in vgs.channels.items():
            if val is channel:
                physical_name = key
                break  # Found it, exit loop

        if physical_name is None:
            raise ValueError(f"Channel {channel.id} not associated with VirtualGateSet {vgs_name}")

        virtual_name = vgs.layers[0].source_gates[vgs.layers[0].target_gates.index(physical_name)]
        return virtual_name

    def reset_voltage_sequence(self, gate_set_id) -> None:
        self.voltage_sequences[gate_set_id] = self.virtual_gate_sets[gate_set_id].new_sequence(
            track_integrated_voltage=True
        )
        return

    def register_global_gates(
        self,
        global_channels: Union[List[VoltageGate], VoltageGate],
    ):
        if isinstance(global_channels, VoltageGate):
            global_channels = [global_channels]
        for ch in global_channels:
            virtual_name = self._get_virtual_name(ch)
            global_gate = GlobalGate(
                id=virtual_name,
                physical_channel=ch.get_reference(),
            )
            self.global_gates[virtual_name] = global_gate

    def register_channel_elements(
        self,
        plunger_channels: List[Channel],
        sensor_resonator_mappings: Dict[Channel, ReadoutResonatorBase],
        barrier_channels: List[Channel],
        sensor_drain_mappings: Dict[Channel, DrainSingle] = None,
        global_gates: Optional[List[VoltageGate]] = None,
    ) -> None:
        self.register_quantum_dots(plunger_channels)
        self.register_barrier_gates(barrier_channels)
        self.register_sensor_dots(sensor_resonator_mappings, sensor_drain_mappings)

        if global_gates is not None:
            self.register_global_gates(global_gates)

    def register_quantum_dots(
        self,
        plunger_channels: Union[List[Channel], Channel],
    ) -> None:
        """
        Creates QuantumDot objects from a list of plunger_channels Channel objects.

        The name of the QuantumDot will be found in the first layer of the corresponding VirtualGateSet.

        """
        if isinstance(plunger_channels, Channel):
            plunger_channels = [plunger_channels]
        for ch in plunger_channels:
            virtual_name = self._get_virtual_name(ch)
            quantum_dot = QuantumDot(
                id=virtual_name,  # Should now be the same as the virtual gate name
                physical_channel=ch.get_reference(),
            )
            self.quantum_dots[virtual_name] = quantum_dot

    def register_sensor_dots(
        self,
        sensor_resonator_mappings: Dict[Channel, ReadoutResonatorBase],
        sensor_drain_mappings: Dict[Channel, DrainSingle] = None,
    ) -> None:
        """
        Creates SensorDot objects from a dictionary mapping sensor channels to their readout channels.

        Args:
            sensor_resonator_mappings (Dict[Channel, ReadoutResonatorBase]):
                Dictionary where keys are sensor channels and values are their associated resonator.
            sensor_drain_mappings (Dict[Channel, DrainSingle]):
                Dictionary where keys are sensor channels and values are their associated transport reservoir objects.
        """
        for ch, res in sensor_resonator_mappings.items():
            virtual_name = self._get_virtual_name(ch)
            sensor_dot = SensorDot(
                id=virtual_name,
                physical_channel=ch.get_reference(),
            )
            self.sensor_dots[virtual_name] = sensor_dot
            sensor_dot.physical_channel.readout = res

        if sensor_drain_mappings is not None:
            for ch, drain in sensor_drain_mappings.items():
                virtual_name = self._get_virtual_name(ch)
                if virtual_name in self.sensor_dots:
                    sensor_dot = self.sensor_dots[virtual_name]
                    # Set the reservoir to the drain, which should already have the readout element attached
                    sensor_dot.readout_reservoir = drain
                else:
                    sensor_dot = SensorDot(
                        id=virtual_name,
                        physical_channel=ch.get_reference(),
                    )
                    sensor_dot.readout_reservoir = drain
                    self.sensor_dots[virtual_name] = sensor_dot

    def register_barrier_gates(self, barrier_channels: List[Channel]) -> None:
        for ch in barrier_channels:
            virtual_name = self._get_virtual_name(ch)
            barrier_gate = BarrierGate(
                id=virtual_name,
                physical_channel=ch.get_reference(),
            )
            self.barrier_gates[virtual_name] = barrier_gate

    def wire_voltage_gate_qdac(
        self,
        voltage_gate: VoltageGate,
        *,
        qdac_output_port: int,
        dac_name: str = "qdac",
        with_trigger_channel: bool = False,
        digital_output_key: str = "qdac_trig_0",
        qdac_trigger_in: Optional[int] = None,
        trigger_pulse_length_ns: int = 100,
    ) -> None:
        """Attach QDAC metadata and optionally move a digital trigger under a wrapper ``Channel``.

        Setting ``digital_outputs[...].parent = None`` before the line is registered under
        the Quam tree causes QUAM to resolve references on an orphan
        ``DigitalOutputChannel`` and emit ``get_root()`` warnings. This method registers
        ``QdacSpec`` (and the optional OPX trigger ``Channel``) **first**, then moves the
        existing digital line in a minimal second step.

        Args:
            voltage_gate: Physical gate (e.g. from ``virtual_gate_sets[id].channels``).
            qdac_output_port: QDAC channel index.
            dac_name: Key under ``machine.dacs`` for the driver.
            with_trigger_channel: If True, move ``digital_output_key`` into a wrapper
                ``Channel`` referenced by ``QdacSpec.opx_trigger_out``.
            digital_output_key: Name of the digital output on the gate (default wiring
                uses ``qdac_trig_0``).
            qdac_trigger_in: Optional QDAC external trigger port.
            trigger_pulse_length_ns: Length of the default ``trigger`` pulse on the
                wrapper channel when ``with_trigger_channel`` is True.
        """
        if with_trigger_channel:
            if digital_output_key not in voltage_gate.digital_outputs:
                raise KeyError(
                    f"{digital_output_key!r} missing from digital_outputs of "
                    f"{getattr(voltage_gate, 'name', voltage_gate)!r}"
                )
            dig = voltage_gate.digital_outputs[digital_output_key]
            digital_ch = Channel(
                id=f"qdac_trig_{qdac_output_port}",
                digital_outputs={},
                operations={
                    "trigger": pulses.Pulse(
                        length=trigger_pulse_length_ns, digital_marker="ON"
                    )
                },
            )
            voltage_gate.dac_spec = QdacSpec(
                dac_name=dac_name,
                qdac_output_port=qdac_output_port,
                opx_trigger_out=digital_ch,
                qdac_trigger_in=qdac_trigger_in,
            )
            del voltage_gate.digital_outputs[digital_output_key]
            dig.parent = None
            digital_ch.digital_outputs["trigger"] = dig
        else:
            voltage_gate.dac_spec = QdacSpec(
                dac_name=dac_name,
                qdac_output_port=qdac_output_port,
                opx_trigger_out=None,
                qdac_trigger_in=qdac_trigger_in,
            )

    def apply_qdac_channel_mapping(
        self,
        gate_set_id: str,
        qdac_mapping: Mapping[str, Mapping[str, Any]],
        *,
        digital_output_key: str = "qdac_trig_0",
        dac_name: str = "qdac",
        qdac_trigger_in: Optional[int] = None,
        trigger_pulse_length_ns: int = 100,
    ) -> None:
        """Apply :meth:`wire_voltage_gate_qdac` to every ``VoltageGate`` listed in ``qdac_mapping``.

        Keys of ``qdac_mapping`` must match :attr:`VoltageGate.name` (same as the prior
        ``quam_config`` loop). Values are dicts with at least ``"ch"`` (QDAC port index,
        or ``None`` to skip) and optional ``"trigger"`` (bool, default ``False``).

        Channel entries are resolved via ``virtual_gate_sets[gate_set_id].channels[key]``
        so ``#/`` references are followed while the gate set is already under this root.
        """
        vgs = self.virtual_gate_sets[gate_set_id]
        for channel_name in list(vgs.channels.keys()):
            gate = vgs.channels[channel_name]
            if not isinstance(gate, VoltageGate):
                continue
            if gate.name not in qdac_mapping:
                continue
            entry = qdac_mapping[gate.name]
            ch_nb = entry.get("ch")
            if ch_nb is None:
                continue
            self.wire_voltage_gate_qdac(
                gate,
                qdac_output_port=ch_nb,
                dac_name=dac_name,
                with_trigger_channel=bool(entry.get("trigger", False)),
                digital_output_key=digital_output_key,
                qdac_trigger_in=qdac_trigger_in,
                trigger_pulse_length_ns=trigger_pulse_length_ns,
            )

    def register_quantum_dot_pair(
        self,
        quantum_dot_ids: List[str],
        sensor_dot_ids: List[str],
        barrier_gate_id: str = None,
        id: str = None,
        dot_coupling: float = 0.0,
    ) -> None:
        """
        Creates QuantumDotPair objects given a list of Channels
        Args:
            quantum_dots (List[QuantumDot]): A list of two Channel objects which are already registered as QuantumDots.

        """

        if len(quantum_dot_ids) != 2:
            raise ValueError(f"Must be 2 QuantumDot objects. Received {len(quantum_dot_ids)}")

        qd_names = quantum_dot_ids
        name_check = self.find_quantum_dot_pair(qd_names[0], qd_names[1])
        if name_check is not None:
            raise ValueError(f"Quantum Dot Pairing already exists with name {name_check}")

        for name in qd_names:
            if name not in self.quantum_dots:
                raise ValueError(f"Quantum Dot {name} not registered. Please register first")
        if id is None:
            id = f"{qd_names[0]}_{qd_names[1]}"

        sensor_names = sensor_dot_ids
        for name in sensor_names:
            if name not in self.sensor_dots:
                raise ValueError(f"Sensor Dot {name} not registered. Please register first")

        if barrier_gate_id is not None:
            barrier_name = barrier_gate_id
            if barrier_name not in self.barrier_gates:
                raise ValueError(
                    f"Barrier Gate {barrier_name} not registered. Please register first"
                )

        quantum_dot_pair = QuantumDotPair(
            id=id,
            quantum_dots=[self.quantum_dots[m].get_reference() for m in qd_names],
            barrier_gate=(
                self.barrier_gates[barrier_name].get_reference()
                if barrier_gate_id is not None
                else None
            ),
            sensor_dots=[self.sensor_dots[n].get_reference() for n in sensor_names],
            dot_coupling=dot_coupling,
        )

        self.quantum_dot_pairs[id] = quantum_dot_pair

    def find_quantum_dot_pair(self, dot1_name: str, dot2_name: str) -> Optional[str]:
        target_dots = {dot1_name, dot2_name}
        for pair_name, dot_pair in self.quantum_dot_pairs.items():
            pair_dots = {dot_pair.quantum_dots[0].id, dot_pair.quantum_dots[1].id}
            if pair_dots == target_dots:
                return pair_name
        return None

    def add_point(
        self,
        gate_set_id: str,
        name: str,
        voltages: Dict,
        duration: int,
        replace_existing_point: bool = False,
    ) -> None:
        """
        Method to add a point to the VirtualGateSet.
        Args:
            gate_set_id (str): The name of the associated VirtualGateSet
            name (str): The name of the added point
            duration (int): The duration that the point should be held
            replace_existing_point (bool): Whether to replace points of the same name in the VirtualGateSet

        Note:
            This method allows qubit names to be entered, and it will process the qubit names by referencing the qubit id. If the qubit id is not in the associated VirtualGateSet,
            this will result in an error.
        """

        if gate_set_id not in self.virtual_gate_sets:
            raise ValueError(
                f"VirtualGateSet id {gate_set_id} not found in list of VirtualGateSets: {list(self.virtual_gate_sets.keys())}"
            )

        if (
            name in list(self.virtual_gate_sets[gate_set_id].get_macros())
            and not replace_existing_point
        ):
            raise ValueError(
                f"Point already exists in VirtualGateSet {gate_set_id}. Please set replace_existing_point = True to replace"
            )

        processed_voltages = {}
        for gate_name, voltage in voltages.items():
            if gate_name in self.qubits:
                gate_name = self.qubits[gate_name].id
            processed_voltages[gate_name] = voltage

        return self.virtual_gate_sets[gate_set_id].add_point(name, processed_voltages, duration)

    def create_virtual_gate_set(
        self,
        virtual_channel_mapping: Dict[str, Channel],
        gate_set_id: str = None,
        compensation_matrix: List[List[float]] = None,
        allow_rectangular_matrices: bool = True,
        adjust_for_attenuation: bool = False,
    ) -> None:
        if gate_set_id is None:
            gate_set_id = f"virtual_gate_set_{len(self.virtual_gate_sets.keys())}"

        virtual_gate_names, physical_gate_names = [], []
        channel_mapping = {}
        for virtual_name, ch in virtual_channel_mapping.items():

            # Store list of virtual gate names and physical gate names to ensure correct indexing for the VirtualizationLayer
            virtual_gate_names.append(virtual_name)
            # physical_name = f"{virtual_name}_physical"
            physical_name = ch.id
            physical_gate_names.append(physical_name)

            # Add the channel to self.physical_channels if it does not already exist
            if ch not in list(self.physical_channels.values()):
                self.physical_channels[ch.id] = ch

            # Add to the channel mapping, which (for the VirtualGateSet) maps the physical channel names to the physical channel objects
            channel_mapping[physical_name] = ch.get_reference()

        # Register an empty gate set first, then fill ``channels`` while ``parent`` is set.
        # Otherwise QUAM may resolve ``#/`` references during construction while this
        # VirtualGateSet is still detached from the QuamRoot, triggering get_root() warnings.
        self.virtual_gate_sets[gate_set_id] = VirtualGateSet(
            id=gate_set_id,
            channels={},
            allow_rectangular_matrices=allow_rectangular_matrices,
            adjust_for_attenuation=adjust_for_attenuation,
        )
        vgs = self.virtual_gate_sets[gate_set_id]
        for physical_name, ref in channel_mapping.items():
            vgs.channels[physical_name] = ref

        if compensation_matrix is None:
            compensation_matrix = np.eye(len(virtual_gate_names)).tolist()

        vgs.add_to_layer(
            layer_id="compensation_layer",
            source_gates=virtual_gate_names,
            target_gates=physical_gate_names,
            matrix=compensation_matrix,
        )
        self.voltage_sequences[gate_set_id] = vgs.new_sequence(
            track_integrated_voltage=True
        )

    def create_virtual_dc_set(
        self,
        gate_set_id: str,
        matrix: List[List[float]] = None,
    ) -> None:
        """
        Method to create a VirtualDCSet, using the same structure as the VirtualGateSet.

        The default matrix will be synced with the VirtualGateSet compensation layer. If a matrix is provided, it will overwrite.
        """
        if gate_set_id not in self.virtual_gate_sets:
            raise ValueError(
                f"Gate set with ID {gate_set_id} not in quam. Available gate sets: {list(self.virtual_gate_sets.keys())}"
            )
        vgs = self.virtual_gate_sets[gate_set_id]

        channel_mapping = {name: ch.get_reference() for name, ch in vgs.channels.items()}

        virtual_names = list(vgs.layers[0].source_gates)
        physical_names = list(vgs.layers[0].target_gates)
        gate_set_matrix = [
            row[:] for row in vgs.layers[0].matrix
        ]  # Copy to avoid any mutability issues, just incase

        allow_rectangular_matrices = vgs.allow_rectangular_matrices

        self.virtual_dc_sets[gate_set_id] = VirtualDCSet(
            id=gate_set_id,
            channels=channel_mapping,
            allow_rectangular_matrices=allow_rectangular_matrices,
        )
        self.virtual_dc_sets[gate_set_id].add_to_layer(
            layer_id="compensation_layer",
            source_gates=virtual_names,
            target_gates=physical_names,
            matrix=gate_set_matrix,
        )
        if matrix:
            self.virtual_dc_sets[gate_set_id].layers[0].matrix = matrix

    def update_cross_compensation_submatrix(
        self,
        virtual_names: List[str],
        channels: List[Channel],
        matrix: Union[List[List[float]], np.ndarray],
        target: Literal["both", "opx", "dc"] = "both",
    ) -> None:
        """
        Updates the a sub-space of the cross-compensation matrix based on the virtual_names and the associated channels.
        Does not have to be a square matrix.

        Args:
            virtual_names (List[str]): A list of the virtual gate names in the sub-space you want to edit. Must be in the same VirtualGateSet
            channels (List[Channel]): The corresponding HW channels that you would like to edit
            matrix (List | np.ndarray): The matrix elements to edit
        """
        sub = np.asarray(matrix)
        if sub.shape != (len(channels), len(virtual_names)):
            raise ValueError(
                f"Sub-matrix shape mismatch: Expected ({len(channels), len(virtual_names)}) but received {sub.shape}"
            )

        # Use the first element in the channels list to find relevant VirtualGateSet. All virtual names and channels should be in the same VirtualGateSet anyway
        vgs = self._get_virtual_gate_set(channels[0])
        source_gates = vgs.layers[0].source_gates

        # Create a mapping of virtual gate : corresponding index in the full matrix.
        source_index = {name: i for i, name in enumerate(source_gates)}

        missing_virtual_names = [v for v in virtual_names if v not in source_gates]
        if missing_virtual_names:
            raise ValueError(
                f"Virtual Gate(s) not in VirtualGateSet {vgs.id}: {missing_virtual_names}"
            )

        def create_new_matrix(full_matrix):
            for subspace_j, v in enumerate(virtual_names):
                # The corresponding index in the full compensation matrix
                full_matrix_j = source_index[v]
                for subspace_i, ch in enumerate(channels):
                    # Get the virtual name associated with the channel
                    virtual_name = self._get_virtual_name(ch)
                    # For the first layer, there should be a 1:1 mapping of channel HW to the virtual gate name, so reuse the same indexing method
                    full_matrix_i = source_index[virtual_name]

                    # Replace the matrix elemeent
                    full_matrix[full_matrix_i][full_matrix_j] = matrix[subspace_i][subspace_j]
            return full_matrix

        if target == "opx" or target == "both":
            full_matrix = create_new_matrix([row[:] for row in vgs.layers[0].matrix])
            vgs.layers[0].matrix = full_matrix
        if target == "dc" or target == "both":
            full_matrix = create_new_matrix(
                [row[:] for row in self.virtual_dc_sets[vgs.id].layers[0].matrix]
            )
            self.virtual_dc_sets[vgs.id].layers[0].matrix = full_matrix

    def update_full_cross_compensation(
        self,
        compensation_matrix: List[List[float]],
        virtual_gate_set_name: str = None,
        target: Literal["both", "opx", "dc"] = "both",
    ) -> None:
        """
        If an already-calculated full cross-compensation matrix exists, use this method to add.
        Args:
            compensation_matrix (List[List[float]]): A full cross-compensation matrix to overwrite the existing matrix in the first VirtualGateSet layer
            virtual_gate_set_name (str): The name of the VirtualGateSet in self.virtual_gate_sets.
        """

        if (
            virtual_gate_set_name is not None
            and virtual_gate_set_name not in self.virtual_gate_sets
        ):
            raise ValueError(f"No such VirtualGateSet. Received {virtual_gate_set_name}")
        if virtual_gate_set_name is None:
            virtual_gate_set_name = next(iter(self.virtual_gate_sets.keys()))

        if target == "opx" or target == "both":
            self.virtual_gate_sets[virtual_gate_set_name].layers[0].matrix = [
                row[:] for row in compensation_matrix
            ]
        if target == "dc" or target == "both":
            self.virtual_dc_sets[virtual_gate_set_name].layers[0].matrix = [
                row[:] for row in compensation_matrix
            ]

    def step_to_voltage(
        self, voltages: Dict, default_to_zero: bool = False, gate_set_name: str = None
    ) -> None:
        """
        Input a dict of {qubit_name : voltage}, which will be resolved internally.
        If default_to_zero = True, then all the unnamed qubit values will be defaulted to zero.
        If default_to_zero = False, then unnamed qubits will be kept at their last tracked level.
        """
        if gate_set_name is not None and gate_set_name not in list(self.virtual_gate_sets.keys()):
            raise ValueError("Gate Set not found in Quam")
        if gate_set_name is None:
            gate_set_name = list(self.virtual_gate_sets.keys())[0]
        new_sequence = self.virtual_gate_sets[gate_set_name].new_sequence()

        actual_voltages = {}
        for name, value in voltages.items():
            if name in self.qubits:
                actual_voltages[self.qubits[name].id] = value
            else:
                actual_voltages[name] = value

        if not default_to_zero:
            for qubit, qubit_obj in self.qubits.items():
                if qubit in voltages:
                    continue
                else:
                    voltages[qubit] = qubit_obj.current_voltage

        new_sequence.step_to_voltages(actual_voltages)

    def initialise(self, qubit_name: str) -> None:
        if qubit_name not in self.qubits:
            raise ValueError(
                f"Qubit {qubit_name} not in registered qubits: {list[self.qubits.keys()]}"
            )

        try:
            self.qubits[qubit_name].initialisation()
        except:
            raise RuntimeError(f"Failed to initialise qubit {qubit_name}")

    def connect(self, reset_voltages: bool = False, skip_dacs: bool=False) -> QuantumMachinesManager:
        """Open a Quantum Machine Manager with the credentials ("host" and "cluster_name") as defined in the network file.

        Args:
            reset_voltages (bool): Whether to reset the voltages of each of the channels to the last-applied voltage, saved in the Quam state.
            skip_dacs (bool): Whether to connect to the da==registered DACs.
        Returns:
            QuantumMachinesManager: The opened Quantum Machine Manager.
        """
        settings = dict(
            host=self.network["host"],
            cluster_name=self.network["cluster_name"],
            octave=self.get_octave_config(),
        )
        if "port" in self.network:
            settings["port"] = self.network["port"]

        self.qmm = QuantumMachinesManager(**settings)

        ## TODO: need to also call self.create_virtual_dc_set("main_qpu") every time?
        if self.dac_config and ~skip_dacs:
            self.connect_to_external_source(reset_voltages)
        return self.qmm

    def get_octave_config(self) -> QmOctaveConfig:
        """Return the Octave configuration."""
        octave_config = None
        for octave in self.octaves.values():
            if octave_config is None:
                octave_config = octave.get_octave_config()
        return octave_config

    def declare_qua_variables(
        self,
        num_IQ_pairs: Optional[int] = None,
    ) -> tuple[
        list[QuaVariable],
        list[StreamType],
        list[QuaVariable],
        list[StreamType],
        QuaVariable,
        StreamType,
    ]:
        """Macro to declare the necessary QUA variables for all qubits.

        Args:
            num_IQ_pairs (Optional[int]): Number of IQ pairs (I and Q variables) to declare.
                If None, it defaults to the number of qubits in `self.quantum_dots`.

        Returns:
            tuple: A tuple containing lists of QUA variables and streams.
        """
        if num_IQ_pairs is None:
            num_IQ_pairs = len(self.quantum_dots)

        n = declare(int)
        n_st = declare_stream()
        I = [declare(fixed) for _ in range(num_IQ_pairs)]
        Q = [declare(fixed) for _ in range(num_IQ_pairs)]
        I_st = [declare_stream() for _ in range(num_IQ_pairs)]
        Q_st = [declare_stream() for _ in range(num_IQ_pairs)]
        return I, I_st, Q, Q_st, n, n_st

    def initialize_qpu(self, **kwargs):
        """Initialize the QPU with the specified settings."""
        pass

    def to_dict(self, follow_references=False, include_defaults=False):
        # Ensure that all the current_external_voltage values in VoltageGates are synchronised to the actual value, right before serialisation. This
        # ensures that the right value is saved.
        for ch in self.physical_channels.values():
            if hasattr(ch, "current_external_voltage") and ch.offset_parameter is not None:
                ch.current_external_voltage = float(ch.offset_parameter())

        d = super().to_dict(follow_references=follow_references, include_defaults=include_defaults)

        # We treat the voltage_sequences as a runtime helper, and not as a Quam component. That way, it does not get serialised.
        # All the relevant information about the sequence (points, macros) are stored on the QuantumDot/Qubit level and/or the VirtualGateSet level.
        d.pop("voltage_sequences", None)
        d.pop("dacs", None)
        return d

    def set_dac_config(self, config: Optional[Dict[str, Any]]) -> None:
        """Set DAC driver entries by name. Persisted in ``wiring.json`` (with ``wiring`` / ``network``).

        Pass a dict mapping logical DAC names (e.g. ``qdac1``, ``main``) to driver specs. If you
        pass a single-driver flat dict (with top-level ``driver_module``), it is wrapped as
        ``{"main": config}``.
        """
        if not config:
            self.dac_config = {}
            return
        if "driver_module" in config:
            self.dac_config = {"main": dict(config)}
        else:
            self.dac_config = {
                k: dict(v) if isinstance(v, Mapping) else v for k, v in config.items()
            }

    @classmethod
    def load(
        cls,
        filepath_or_dict: Optional[Union[str, Path, dict]] = None,
        validate_type: bool = True,
        fix_attrs: bool = True,
    ):
        """Load machine, recreate runtime voltage sequences, and wire macros."""
        instance = super().load(
            filepath_or_dict=filepath_or_dict,
            validate_type=validate_type,
            fix_attrs=fix_attrs,
        )
        instance.voltage_sequences = {}

        # Recreate voltage sequences for each virtual gate set
        for gate_set_id, vgs in instance.virtual_gate_sets.items():
            instance.voltage_sequences[gate_set_id] = vgs.new_sequence(
                track_integrated_voltage=True
            )

        # We can also update the state_tracker here to hold the value held by QuantumDot.current_voltage.

        from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

        wire_machine_macros(instance)

        return instance

    def save(
        self,
        path: Optional[Union[Path, str]] = None,
        content_mapping: Optional[Dict[str, str]] = None,
        include_defaults: bool = False,
        ignore: Optional[Sequence[str]] = None,
    ):
        super().save(
            path,
            content_mapping,
            include_defaults,
            ignore,
        )
