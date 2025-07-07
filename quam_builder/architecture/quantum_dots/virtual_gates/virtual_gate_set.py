from dataclasses import field
from typing import List, Dict, Sequence
import numpy as np
from quam_builder.hardware.quam_channel import QdacOpxChannel, InOutSingleChannel

from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.voltage_sequence.gate_set import GateSet, QdacGateSet
from quam_builder.architecture.quantum_dots.utils import VoltageLevelType
from quam_builder.architecture.quantum_dots.virtual_gates.virtualisation_layer import (
    VirtualisationLayer,
)


__all__ = ["VirtualGateSet"]


@quam_dataclass
class VirtualGateSet(GateSet):
    """
    A set of virtual gates that can be used to create a virtual gate layer.

    Attributes:
        layers: A list of `VirtualisationLayer` objects, applied sequentially.
    """
    readout: Dict[str,InOutSingleChannel]
    layers: List[VirtualisationLayer] = field(default_factory=list)
    cross_capacitance_matrix: List[List[float]] = field(init = False)

    def __post_init__(self):
        self._all_gates = list(self.channels.keys())
        self._gate_index = {name: idx for idx, name in enumerate(self._all_gates)}
        n = len(self._all_gates)
        M = np.eye(n)

        for name, chan in self.channels.items():
            i = self._gate_index[name]
            for neighbour, coupling in getattr(chan, 'couplings', {}).items():
                j = self._gate_index[neighbour]
                M[i,j] = coupling
                M[j,i] = coupling
        self.cross_capacitance_matrix = M.tolist()

    def get_couplings(self, gate_name, filter_for_zero: bool = True):
        gate_idx = self._gate_index[gate_name]
        couplings_row = self.cross_capacitance_matrix[gate_idx]
        couplings = dict(**zip(self._all_gates, couplings_row))
        couplings.pop(gate_name)
        if filter_for_zero:
            couplings = {k:v for k,v in couplings.items() if v != 0}
        return couplings

    def set_couplings(self, gate_name, couplings):
        gate_idx = self._gate_index[gate_name]
        couplings_row = self.cross_capacitance_matrix[gate_idx]
        for gate, coupling in couplings.items():
            gate_idx = self._gate_index[gate]
            couplings_row[gate_idx] = coupling
        
        self.cross_capacitance_matrix = couplings_row


    @property
    def valid_channel_names(self) -> list[str]:
        """
        Returns a list of valid channel names for the VirtualGateSet.
        """
        # Collect all virtual gate names from all layers
        virtual_channels = set(ch for layer in self.layers for ch in layer.source_gates)
        # Combine physical and virtual gate names
        return list(self.channels) + list(virtual_channels)

    def _validate_new_layer(
        self,
        source_gates: List[str],
        target_gates: List[str],
    ):
        """
        Validates the new layer to be added to the VirtualGateSet.

        Checks:
        - Each target gate must correspond to a lower layer source gate
          or physical channel
        - Each target gate must not be a target gate in any previous layer
        - Each source gate must not be a source gate in any previous layer
        - Each source gate must not be a target gate in any previous layer

        Args:
            source_gates: A list of names for the virtual gates in this layer.
            target_gates: A list of names for the physical (or underlying virtual)
                          gates that this layer maps to.

        Raises:
            ValueError: If any of the checks fail.
        """
        existing_source_gates = set()
        existing_target_gates = set()
        for lyr in self.layers:
            existing_source_gates.update(lyr.source_gates)
            existing_target_gates.update(lyr.target_gates)

        # Check 1: Each target gate must correspond to a lower layer source gate or
        # physical channel.
        # This check is implicitly handled if we consider that target_gates of the
        # first layer must be present in self.channels (physical gates).
        # For subsequent layers, target_gates must be source_gates of previous layers.
        if self.layers:  # Not the first layer
            # Get all source gates from previous layers
            all_previous_source_gates = set()
            for lyr in (
                self.layers
            ):  # Iterate through existing layers before adding the new one
                all_previous_source_gates.update(lyr.source_gates)

            # Combine with physical channels for the very first layer's target check
            valid_target_options = all_previous_source_gates.union(set(self.channels))
        else:  # First layer
            valid_target_options = set(self.channels)

        for tg in target_gates:
            if tg not in valid_target_options:
                raise ValueError(
                    f"Target gate '{tg}' in new layer does not correspond to any "
                    f"source gate of a previous layer or a physical channel. "
                    f"Valid options are: {valid_target_options}"
                )

        # Check 2: Each target gate must not be a target gate in any previous layer
        for tg in target_gates:
            if tg in existing_target_gates:
                raise ValueError(
                    f"Target gate '{tg}' in new layer is already a target gate in a "
                    f"previous layer. Existing target gates: {existing_target_gates}"
                )

        # Check 3: Each source gate must not be a source gate in any previous layer
        for sg in source_gates:
            if sg in existing_source_gates:
                raise ValueError(
                    f"Source gate '{sg}' in new layer is already a source gate in a "
                    f"previous layer. Existing source gates: {existing_source_gates}"
                )

        # Check 4: Each source gate must not be a target gate in any previous layer
        for sg in source_gates:
            if sg in existing_target_gates:
                raise ValueError(
                    f"Source gate '{sg}' in new layer is already a target gate in a "
                    f"previous layer. Existing target gates: {existing_target_gates}"
                )

    def add_layer(
        self,
        source_gates: List[str],
        target_gates: List[str],
        matrix: List[List[float]],
    ) -> VirtualisationLayer:
        """
        Adds a new virtualisation layer to the VirtualGateSet.

        Args:
            source_gates: A list of names for the virtual gates in this layer.
            target_gates: A list of names for the physical (or underlying virtual)
                          gates that this layer maps to.
            matrix: The virtualisation matrix defining the transformation.

        Returns:
            The created VirtualisationLayer object.
        """
        self._validate_new_layer(source_gates, target_gates)

        virtualisation_layer = VirtualisationLayer(
            source_gates=source_gates, target_gates=target_gates, matrix=matrix
        )
        self.layers.append(virtualisation_layer)
        return virtualisation_layer
    
    def get_cross_capacitive_matrix(self):
        return [list(row) for row in self.cross_capacitance_matrix]

    def resolve_voltages(
        self, voltages: Dict[str, VoltageLevelType], allow_extra_entries: bool = False
    ) -> Dict[str, VoltageLevelType]:
        """
        Resolves all virtual gate voltages to physical gate voltages by applying
        all virtualisation layers in reverse order.

        Args:
            voltages: A dictionary mapping gate names (virtual or physical) to
                      voltage levels.
            allow_extra_entries: If True, gates in `voltages` that are not
                part of this VirtualGateSet (neither physical nor virtual)
                will be ignored. If False, a ValueError will be raised.

        Returns:
            A dictionary mapping physical gate names to their fully resolved
            voltage levels.
        """

        # If not allowing extra entries, check that all keys in voltages are either
        # physical channels or virtual channels defined in any layer.
        if not allow_extra_entries:
            # Find any keys in voltages that are not recognized
            extra_channels = set(voltages) - set(self.valid_channel_names)
            if extra_channels:
                raise ValueError(
                    f"Channels {extra_channels} in voltages that are not part of the "
                    f"VirtualGateSet.channels: {self.channels}"
                )

        # Start with a copy of the input voltages to avoid mutating the original
        resolved_voltages = voltages.copy()

        # Apply each virtualisation layer in reverse order (from highest to lowest)
        # Each layer resolves its virtual gates to the next lower layer
        for layer in reversed(self.layers):
            resolved_voltages = layer.resolve_voltages(
                resolved_voltages, allow_extra_entries=True
            )

        # Finally, resolve any remaining voltages using the base class method
        # For example, add any voltages to channels that are undefined
        resolved_voltages = super().resolve_voltages(
            resolved_voltages, allow_extra_entries=True
        )
        return resolved_voltages

@quam_dataclass
class VirtualQdacGateSet(QdacGateSet, VirtualGateSet):
    # def __init__(self, 
    #              channels: Dict[str, QdacOpxChannel],
    #              readout: Dict[str,InOutSingleChannel],
    #              layers: List[VirtualisationLayer] = None, 
    #              ):
        
    #     QdacGateSet.__init__(self, channels=channels, readout = readout)
    #     VirtualGateSet.__init__(self, channels = channels, layers = layers or [])

    channels: Dict[str, QdacOpxChannel]
    readout: Dict[str, InOutSingleChannel]
    layers: List[VirtualisationLayer] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()


        self._all_gates = list(self.channels.keys())
        self._gate_index = {name: idx for idx, name in enumerate(self._all_gates)}
        n = len(self._all_gates)
        M = np.eye(n)

        for name, chan in self.channels.items():
            i = self._gate_index[name]
            for neighbour, coupling in getattr(chan, 'couplings', {}).items():
                j = self._gate_index[neighbour]
                M[i,j] = coupling
                M[j,i] = coupling
        self.cross_capacitance_matrix = M.tolist()

        if self.layers: 
            for layer in self.layers: 
                self.add_layer(layer.source_gates, layer.target_gates, layer.matrix)


    def apply_voltages(self, voltages:Dict[str,float], apply_cc:bool = False, allow_extra_entries:bool = False):
        """
        Apply the correction matrix if the apply_c is true. 
        A function to immediately apply all the resolved DC voltages using the QDAC, not a part of QUA/OPX
        """
        if not apply_cc: 
            super().apply_voltages(voltages, allow_extra_entries)
        
        current_voltages = self.get_voltages()
        N = len(self._all_gates)
        delta_full = np.zeros(N, dtype = float)

        for gate, target_V in voltages.items():
            idx = self._gate_index[gate]

            delta_full[idx] = target_V - current_voltages[gate]

        nonzero_indices = np.nonzero(delta_full)[0]

        sub_cc_matrix = self.cross_capacitance_matrix[np.ix_(nonzero_indices, nonzero_indices)]
        inv_cc_matrix = np.linalg.inv(sub_cc_matrix)

        M = np.eye(N)

        for i, ri in enumerate(nonzero_indices):
            for j, cj in enumerate(nonzero_indices):
                M[ri,cj] = inv_cc_matrix[i,j]

        physical_vec = M @ delta_full

        new_voltages = {
            x: current_voltages[x] + float(physical_vec[self._gate_index[x]]) for x in self._all_gates
        }

        super().apply_voltages(new_voltages, allow_extra_entries)

    # def add_CC_matrix(self, nxnmatrix):
    #     self.cross_capacitance_matrix = nxnmatrix
    

    def resolve_voltages(self, voltages: Dict[str, VoltageLevelType], allow_extra_entries:bool=False, unnamed_gates_to_zero:bool = True) -> Dict[str, VoltageLevelType]:
        virtually_resolved = VirtualGateSet.resolve_voltages(self, voltages, allow_extra_entries=allow_extra_entries)
        #return QdacGateSet.resolve_voltages(self, virtually_resolved, allow_extra_entries=allow_extra_entries, unnamed_gates_to_zero=unnamed_gates_to_zero)
        return virtually_resolved


