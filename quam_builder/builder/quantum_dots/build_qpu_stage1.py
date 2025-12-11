"""Stage 1 QPU builder for quantum dot systems - BaseQuamQD only.

This module provides the Stage 1 QPU building functionality that creates
BaseQuamQD with physical quantum dots, but does NOT create qubits.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorSingle,
    VoltageGate,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

from quam_builder.builder.quantum_dots.build_utils import *

__all__ = ["_BaseQpuBuilder"]

logger = logging.getLogger(__name__)


class _BaseQpuBuilder:
    """Stage 1: Builds BaseQuamQD with quantum dots only (no qubits).

    This builder creates:
    - Physical VoltageGate channels with QDAC mappings
    - Virtual gate set with identity compensation matrix
    - Quantum dots (from plunger gates)
    - Quantum dot pairs (with barriers)
    - Sensor dots with resonators

    Does NOT create:
    - Qubits (Stage 2)
    - XY drive channels (Stage 2)
    - Qubit pairs (Stage 2)
    """

    def __init__(
        self,
        machine: BaseQuamQD,
        resonator_cls: type = ReadoutResonatorSingle,
    ):
        """Initialize Stage 1 builder.

        Args:
            machine: BaseQuamQD instance with wiring defined.
            resonator_cls: Resonator class to use for sensor dots.
        """
        self.machine = machine
        self.resonator_cls = resonator_cls
        self.assembly = None
        self._wiring_by_type = {}

    def build(self) -> BaseQuamQD:
        """Execute Stage 1 build process.

        Steps:
        1. Normalize wiring
        2. Collect physical channels (with QDAC)
        3. Create virtual gate set (identity matrix)
        4. Register channels (quantum dots, sensors, barriers, globals)
        5. Register quantum dot pairs

        Returns:
            Configured BaseQuamQD ready for Stage 2 conversion.
        """
        from quam_builder.builder.quantum_dots.build_qpu import QpuAssembly

        self.assembly = QpuAssembly()

        self._wiring_by_type = self._normalize_wiring(self.machine.wiring or {})
        self._collect_physical_channels()
        self._create_virtual_gate_set()
        self._register_channels()
        self._register_quantum_dot_pairs()

        return self.machine

    def _normalize_wiring(self, wiring: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
        """Normalize wiring structure by element type."""
        normalized = {}
        for element_type_raw, elements in wiring.items():
            element_type = _normalize_element_type(element_type_raw)
            if element_type:
                normalized[element_type] = elements
        return normalized

    def _collect_physical_channels(self):
        """Collect all physical channels from wiring."""
        self._collect_global_gates(self._wiring_by_type.get("globals", {}))
        self._collect_sensor_dots(self._wiring_by_type.get("readout", {}), self.resonator_cls)
        self._collect_qubits(self._wiring_by_type.get("qubits", {}))
        self._collect_qubit_pairs(self._wiring_by_type.get("qubit_pairs", {}))

    def _collect_global_gates(self, wiring_by_element: Mapping[str, Any]):
        """Collect global gate channels with QDAC support."""
        for global_id, line_types in wiring_by_element.items():
            for line_type, line_wiring in line_types.items():
                wiring_path = f"#/wiring/globals/{global_id}/{line_type}"

                # Extract QDAC channel if present
                qdac_channel = _extract_qdac_channel(line_wiring)

                gate = _make_voltage_gate_with_qdac(global_id, wiring_path, qdac_channel)
                self.assembly.global_gates.append(gate)

    def _collect_sensor_dots(self, wiring_by_element: Mapping[str, Any], resonator_cls: Any):
        """Collect sensor gates and resonators with QDAC support."""
        for sensor_id, line_types in wiring_by_element.items():
            sensor_channel = None
            resonator = None

            for line_type, line_wiring in line_types.items():
                _validate_line_type("readout", line_type)
                wiring_path = f"#/wiring/readout/{sensor_id}/{line_type}"

                if line_type == WiringLineType.SENSOR_GATE.value:
                    # Extract QDAC channel if present
                    qdac_channel = _extract_qdac_channel(line_wiring)
                    sensor_channel = _make_voltage_gate_with_qdac(
                        f"{sensor_id}_sensor", wiring_path, qdac_channel
                    )
                elif line_type == WiringLineType.RF_RESONATOR.value:
                    resonator = _make_resonator(sensor_id, wiring_path, resonator_cls)

            if sensor_channel:
                self.assembly.sensor_channels.append(sensor_channel)
                self.assembly.sensor_id_to_channel[sensor_id] = sensor_channel
            if resonator:
                self.assembly.resonators.append(resonator)
                self.assembly.sensor_id_to_resonator[sensor_id] = resonator

    def _collect_qubits(self, wiring_by_element: Mapping[str, Any]):
        """Collect plunger gates (quantum dots) with QDAC support.

        Note: XY drives are NOT collected in Stage 1.
        """
        for qubit_id, line_types in wiring_by_element.items():
            for line_type, line_wiring in line_types.items():
                _validate_line_type("qubits", line_type)
                wiring_path = f"#/wiring/qubits/{qubit_id}/{line_type}"

                if line_type == WiringLineType.PLUNGER_GATE.value:
                    # Extract QDAC channel if present
                    qdac_channel = _extract_qdac_channel(line_wiring)

                    plunger = _make_voltage_gate_with_qdac(
                        f"{qubit_id}_plunger", wiring_path, qdac_channel
                    )
                    self.assembly.plunger_channels.append(plunger)
                    self.assembly.plunger_id_to_channel[qubit_id] = plunger

                # Note: XY drives (DRIVE line type) are NOT collected here

    def _collect_qubit_pairs(self, wiring_by_element: Mapping[str, Any]):
        """Collect barrier gates with QDAC support."""
        for pair_id, line_types in wiring_by_element.items():
            for line_type, line_wiring in line_types.items():
                _validate_line_type("qubit_pairs", line_type)
                wiring_path = f"#/wiring/qubit_pairs/{pair_id}/{line_type}"

                if line_type == WiringLineType.BARRIER_GATE.value:
                    # Extract QDAC channel if present
                    qdac_channel = _extract_qdac_channel(line_wiring)

                    barrier_id = f"barrier_{self.assembly.barrier_counter}"
                    self.assembly.barrier_counter += 1

                    barrier = _make_voltage_gate_with_qdac(barrier_id, wiring_path, qdac_channel)
                    self.assembly.barrier_channels.append(barrier)
                    self.assembly.barrier_id_to_channel[barrier_id] = barrier
                    self.assembly.qubit_pair_id_to_barrier_id[pair_id] = barrier_id

    def _create_virtual_gate_set(self):
        """Create virtual gate set with identity compensation matrix."""
        if not (
            self.assembly.plunger_channels
            or self.assembly.sensor_channels
            or self.assembly.barrier_channels
            or self.assembly.global_gates
        ):
            return

        # Build virtual mapping (physical ID -> virtual name)
        physical_to_virtual, virtual_to_physical = _build_virtual_mapping(
            plunger_ids=list(self.assembly.plunger_id_to_channel.keys()),
            barrier_ids=list(self.assembly.barrier_id_to_channel.keys()),
            sensor_ids=list(self.assembly.sensor_id_to_channel.keys()),
            global_ids=[g.id for g in self.assembly.global_gates],
        )

        # Store virtual names for later use
        self.assembly.plunger_virtual_names = {
            k: physical_to_virtual[k]
            for k in self.assembly.plunger_id_to_channel.keys()
        }
        self.assembly.barrier_virtual_names = {
            k: physical_to_virtual[k]
            for k in self.assembly.barrier_id_to_channel.keys()
        }
        self.assembly.sensor_virtual_names = {
            k: physical_to_virtual[k]
            for k in self.assembly.sensor_id_to_channel.keys()
        }
        self.assembly.global_virtual_names = {
            g.id: physical_to_virtual[g.id] for g in self.assembly.global_gates
        }

        # Create virtual channel mapping for BaseQuamQD.create_virtual_gate_set()
        virtual_channel_mapping = {}

        # Add all channels to mapping
        for qubit_id, plunger in self.assembly.plunger_id_to_channel.items():
            virtual_name = physical_to_virtual[qubit_id]
            virtual_channel_mapping[virtual_name] = plunger

        for barrier_id, barrier in self.assembly.barrier_id_to_channel.items():
            virtual_name = physical_to_virtual[barrier_id]
            virtual_channel_mapping[virtual_name] = barrier

        for sensor_id, sensor in self.assembly.sensor_id_to_channel.items():
            virtual_name = physical_to_virtual[sensor_id]
            virtual_channel_mapping[virtual_name] = sensor

        for global_gate in self.assembly.global_gates:
            virtual_name = physical_to_virtual[global_gate.id]
            virtual_channel_mapping[virtual_name] = global_gate

        # Call machine's create_virtual_gate_set method (uses identity matrix by default)
        self.machine.create_virtual_gate_set(
            virtual_channel_mapping=virtual_channel_mapping,
            gate_set_id=self.assembly.gate_set_id,
        )

    def _register_channels(self):
        """Register quantum dots, sensors, barriers, and global gates with machine."""
        if not (
            self.assembly.plunger_channels
            or self.assembly.sensor_channels
            or self.assembly.barrier_channels
            or self.assembly.global_gates
        ):
            return

        # Create sensor-resonator mapping
        sensor_resonator_mappings = {}
        for sensor_id, channel in self.assembly.sensor_id_to_channel.items():
            resonator = self.assembly.sensor_id_to_resonator.get(sensor_id)
            if resonator is None:
                raise ValueError(f"Missing resonator wiring for sensor gate '{sensor_id}'")
            sensor_resonator_mappings[channel] = resonator

        # Register all channel elements (creates quantum dots, sensor dots, barrier gates)
        self.machine.register_channel_elements(
            plunger_channels=self.assembly.plunger_channels,
            sensor_resonator_mappings=sensor_resonator_mappings,
            barrier_channels=self.assembly.barrier_channels,
            global_gates=self.assembly.global_gates if self.assembly.global_gates else None,
        )

    def _register_quantum_dot_pairs(self):
        """Register quantum dot pairs using the quantum dots created in _register_channels."""
        # For each qubit pair in wiring, register the corresponding quantum dot pair
        for pair_id, barrier_id in self.assembly.qubit_pair_id_to_barrier_id.items():
            # Parse pair ID to get qubit IDs
            control_id, target_id = _parse_qubit_pair_ids(pair_id)

            # Get virtual names for the quantum dots
            control_virtual = self.assembly.plunger_virtual_names.get(control_id)
            target_virtual = self.assembly.plunger_virtual_names.get(target_id)
            barrier_virtual = self.assembly.barrier_virtual_names.get(barrier_id)

            if not control_virtual or not target_virtual:
                logger.warning(
                    f"Skipping quantum dot pair {pair_id}: quantum dots not found "
                    f"(control={control_id}, target={target_id})"
                )
                continue

            if not barrier_virtual:
                logger.warning(
                    f"Skipping quantum dot pair {pair_id}: barrier gate not found"
                )
                continue

            # Find associated sensor dots (if any)
            # For now, we'll use empty list - sensor association can be added later
            sensor_dot_ids = []

            # Register the quantum dot pair
            quantum_dot_pair_id = f"{control_virtual}_{target_virtual}_pair"
            self.machine.register_quantum_dot_pair(
                id=quantum_dot_pair_id,
                quantum_dot_ids=[control_virtual, target_virtual],
                sensor_dot_ids=sensor_dot_ids,
                barrier_gate_id=barrier_virtual,
            )
