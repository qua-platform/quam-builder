"""Stage 2 QPU builder for quantum dot systems - LossDiVincenzoQuam.

This module provides the Stage 2 QPU building functionality that converts
BaseQuamQD to LossDiVincenzoQuam with qubits.

This is INDEPENDENT of Stage 1 and works with any BaseQuamQD (file or memory).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union, cast

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam

from quam_builder.builder.quantum_dots.build_utils import (
    DEFAULT_INTERMEDIATE_FREQUENCY,
    _create_xy_drive_from_wiring,
    _extract_qubit_number,
    _implicit_qubit_to_dot_mapping,
    _natural_sort_key,
    _parse_qubit_pair_ids,
    _validate_drive_ports,
)

__all__ = ["_LDQubitBuilder"]

logger = logging.getLogger(__name__)


class _LDQubitBuilder:  # pylint: disable=too-few-public-methods
    """Stage 2: Builds qubits from existing quantum dots.

    This builder converts BaseQuamQD to LossDiVincenzoQuam and creates:
    - LDQubits (mapped to quantum dots)
    - XY drive channels for each qubit
    - Qubit pairs (mapped to quantum dot pairs)

    Requires:
    - BaseQuamQD with quantum_dots already registered
    """

    def __init__(
        self,
        machine: Union[BaseQuamQD, LossDiVincenzoQuam, str, Path],
        xy_drive_wiring: Optional[Dict[str, Dict]] = None,
        qubit_pair_sensor_map: Optional[Dict[str, List[str]]] = None,
        implicit_mapping: bool = True,
    ):
        """Initialize Stage 2 builder.

        Args:
            machine: BaseQuamQD, LossDiVincenzoQuam, or path to saved state.
            xy_drive_wiring: Optional dict mapping qubit_id → XY drive configuration.
                            Format: {
                                "q1": {
                                    "type": "IQ" | "MW",  # Drive type
                                    "wiring_path": "#/wiring/qubits/q1/xy",  # JSON path to ports
                                    "intermediate_frequency": 500e6  # Optional IF (Hz)
                                },
                                ...
                            }
                            If None (default), automatically extracts from machine.wiring.
                            Only needed when loading from file without wiring or to override.
            qubit_pair_sensor_map: Sensor mapping for qubit pairs.
                                  Format: {"q1_q2": ["sensor_1"], ...}
            implicit_mapping: If True, uses q1→virtual_dot_1 mapping.
        """
        # Load machine if path provided
        if isinstance(machine, (str, Path)):
            machine = LossDiVincenzoQuam.load(machine)

        self.machine = machine
        self.xy_drive_wiring = xy_drive_wiring
        self.qubit_pair_sensor_map = qubit_pair_sensor_map or {}
        self.implicit_mapping = implicit_mapping

    def build(self) -> LossDiVincenzoQuam:
        """Execute Stage 2 build process.

        Steps:
        1. Convert BaseQuamQD → LossDiVincenzoQuam if needed
        2. Validate quantum dots exist
        3. Extract XY drive wiring
        4. Register qubits (with implicit mapping)
        5. Register qubit pairs

        Returns:
            LossDiVincenzoQuam with qubits registered.
        """
        # Convert machine class if BaseQuamQD
        if isinstance(self.machine, BaseQuamQD) and not isinstance(
            self.machine, LossDiVincenzoQuam
        ):
            self.machine.__class__ = LossDiVincenzoQuam
            # Initialize LDQuam-specific fields
            if not hasattr(self.machine, "qubits"):
                self.machine.qubits = {}
            if not hasattr(self.machine, "qubit_pairs"):
                self.machine.qubit_pairs = {}
            if not hasattr(self.machine, "active_qubit_names"):
                self.machine.active_qubit_names = []
            if not hasattr(self.machine, "active_qubit_pair_names"):
                self.machine.active_qubit_pair_names = []

        # Validate quantum dots exist
        if not self.machine.quantum_dots:
            raise ValueError(
                "No quantum dots found in machine. " "Please run Stage 1 (build_base_quam) first."
            )

        # Extract XY drive wiring if not provided
        if self.xy_drive_wiring is None:
            self.xy_drive_wiring = self._extract_xy_drive_wiring()

        # Register qubits and qubit pairs
        self._register_qubits()
        self._register_qubit_pairs()

        # Type cast: machine is guaranteed to be LossDiVincenzoQuam at this point
        return cast(LossDiVincenzoQuam, self.machine)

    def _extract_xy_drive_wiring(self) -> Dict[str, Dict]:
        """Extract XY drive wiring from machine.wiring if available.

        Scans machine.wiring for qubit drive lines and automatically determines
        the drive type (IQ or MW) based on the port configuration.

        Returns:
            Dict mapping qubit_id to XY drive configuration:
            {
                "q1": {
                    "type": "IQ" or "MW",
                    "wiring_path": "#/wiring/qubits/q1/xy",
                    "intermediate_frequency": 500e6
                },
                ...
            }
            Returns empty dict if no wiring is available.
        """
        xy_wiring = {}

        if not hasattr(self.machine, "wiring") or not self.machine.wiring:
            logger.info("No wiring found on machine. Qubits will have no XY drives.")
            return xy_wiring

        # Extract qubit wiring section
        qubits_wiring = self.machine.wiring.get("qubits", {})

        # Process each qubit's drive configuration
        for qubit_id, line_types in qubits_wiring.items():
            drive_wiring = line_types.get(WiringLineType.DRIVE.value)
            if drive_wiring:
                # Determine drive type (IQ or MW) by inspecting port configuration
                # IQ drives have opx_output_I/Q + frequency_converter_up
                # MW drives have single opx_output port
                drive_type = _validate_drive_ports(qubit_id, drive_wiring)
                wiring_path = f"#/wiring/qubits/{qubit_id}/{WiringLineType.DRIVE.value}"

                # Build XY drive configuration
                xy_wiring[qubit_id] = {
                    "type": drive_type,  # "IQ" or "MW"
                    "wiring_path": wiring_path,  # JSON reference to ports
                    "intermediate_frequency": drive_wiring.get(
                        "intermediate_frequency", DEFAULT_INTERMEDIATE_FREQUENCY
                    ),
                }

        return xy_wiring

    def _map_qubit_to_dot(self, qubit_id: str) -> str:
        """Map qubit ID to quantum dot ID using implicit or explicit mapping.

        Args:
            qubit_id: Qubit identifier (e.g., 'q1', 'Q2').

        Returns:
            Quantum dot virtual name (e.g., 'virtual_dot_1').

        Raises:
            ValueError: If quantum dot not found.
        """
        if self.implicit_mapping:
            quantum_dot_id = _implicit_qubit_to_dot_mapping(qubit_id)
        else:
            # TODO: Add support for explicit mapping from config
            raise NotImplementedError("Explicit mapping not yet implemented")

        # Validate quantum dot exists
        if quantum_dot_id not in self.machine.quantum_dots:
            raise ValueError(
                f"Quantum dot '{quantum_dot_id}' not found for qubit '{qubit_id}'. "
                f"Available quantum dots: {list(self.machine.quantum_dots.keys())}"
            )

        return quantum_dot_id

    def _create_xy_channel(self, qubit_id: str) -> Optional[Any]:
        """Create XY drive channel for qubit if wiring exists.

        Args:
            qubit_id: Qubit identifier.

        Returns:
            XYDrive instance or None if no XY drive wiring.
        """
        xy_info = self.xy_drive_wiring.get(qubit_id)
        if not xy_info:
            return None

        return _create_xy_drive_from_wiring(
            qubit_id=qubit_id,
            drive_type=xy_info["type"],
            wiring_path=xy_info["wiring_path"],
            intermediate_frequency=xy_info.get(
                "intermediate_frequency", DEFAULT_INTERMEDIATE_FREQUENCY
            ),
        )

    def _register_qubits(self):
        """Register qubits with the machine using implicit mapping."""
        # Get qubit IDs from wiring or XY drive wiring
        qubit_ids = set()

        if hasattr(self.machine, "wiring") and self.machine.wiring:
            qubit_ids.update(self.machine.wiring.get("qubits", {}).keys())

        if self.xy_drive_wiring:
            qubit_ids.update(self.xy_drive_wiring.keys())

        # If no qubit IDs found, infer from quantum dots
        if not qubit_ids:
            logger.info("No qubit IDs found in wiring. Inferring from quantum dot names.")
            # Extract numbers from virtual_dot_N to create qN
            for dot_id in self.machine.quantum_dots.keys():
                try:
                    number = _extract_qubit_number(dot_id)
                    qubit_ids.add(f"q{number}")
                except ValueError:
                    logger.warning(f"Could not infer qubit ID from quantum dot: {dot_id}")

        # Register each qubit
        for qubit_id in sorted(qubit_ids, key=_natural_sort_key):
            # Map to quantum dot
            quantum_dot_id = self._map_qubit_to_dot(qubit_id)

            # Create XY channel
            xy_channel = self._create_xy_channel(qubit_id)

            # Register qubit
            qubit_name = qubit_id
            self.machine.register_qubit(
                qubit_name=qubit_name,
                quantum_dot_id=quantum_dot_id,
                xy_channel=xy_channel,
                readout_quantum_dot=None,  # TODO: Add readout dot support
            )

            logger.info(
                f"Registered qubit {qubit_name} → quantum_dot {quantum_dot_id} "
                f"(XY drive: {xy_channel is not None})"
            )

    def _register_qubit_pairs(self):
        """Register qubit pairs using quantum dot pairs."""
        # Get qubit pair IDs from wiring
        qubit_pair_ids = []
        if hasattr(self.machine, "wiring") and self.machine.wiring:
            qubit_pair_ids = list(self.machine.wiring.get("qubit_pairs", {}).keys())

        # If no qubit pair IDs in wiring, infer from quantum dot pairs
        if not qubit_pair_ids:
            logger.info("No qubit pair IDs found in wiring. Inferring from quantum dot pairs.")
            for dot_pair_id in self.machine.quantum_dot_pairs.keys():
                # Parse quantum dot pair ID to get qubit numbers
                # e.g., "virtual_dot_1_virtual_dot_2_pair" → "q1_q2"
                try:
                    # Extract numbers from quantum dot pair
                    parts = dot_pair_id.replace("_pair", "").split("_")
                    numbers = [p for p in parts if p.isdigit()]
                    if len(numbers) >= 2:
                        qubit_pair_ids.append(f"q{numbers[0]}_q{numbers[1]}")
                except Exception as e:
                    logger.warning(
                        f"Could not infer qubit pair ID from quantum dot pair: {dot_pair_id}"
                    )

        # Register each qubit pair
        for pair_id in qubit_pair_ids:
            try:
                # Parse pair ID
                control_id, target_id = _parse_qubit_pair_ids(pair_id)

                # Validate both qubits exist
                if control_id not in self.machine.qubits:
                    logger.warning(
                        f"Skipping qubit pair {pair_id}: control qubit {control_id} not registered"
                    )
                    continue

                if target_id not in self.machine.qubits:
                    logger.warning(
                        f"Skipping qubit pair {pair_id}: target qubit {target_id} not registered"
                    )
                    continue

                # Register qubit pair
                qubit_pair_name = f"{control_id}_{target_id}"
                self.machine.register_qubit_pair(
                    id=qubit_pair_name,
                    qubit_control_name=control_id,
                    qubit_target_name=target_id,
                )

                logger.info(
                    f"Registered qubit pair {qubit_pair_name} "
                    f"(control={control_id}, target={target_id})"
                )

            except Exception as e:
                logger.error(f"Failed to register qubit pair {pair_id}: {e}")
                continue
