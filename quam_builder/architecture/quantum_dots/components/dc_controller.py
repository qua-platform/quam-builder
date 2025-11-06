from quam.core import QuamComponent, quam_dataclass
from quam_builder.architecture.quantum_dots.components import VirtualGateSet
from typing import Dict
from quam_builder.tools.qua_tools import VoltageLevelType
import numpy as np


@quam_dataclass
class DCController(QuamComponent):
    virtual_gate_set: VirtualGateSet

    def __post_init__(self):
        self.num_layers = len(self.virtual_gate_set.layers)
        self.dc_state = self._get_dc()
        self.virtual_state = self._inverse_resolve(self.dc_state)

    def set_dc(self, voltages: Dict[str, VoltageLevelType]):
        # updates internal state to reflect new set virtual dc value
        self.virtual_state.update(voltages)

        resolved_voltages = self.virtual_gate_set.resolve_voltages(
            voltages=self.virtual_state
        )

        self.dc_state.update(resolved_voltages)
        for VoltageGate, value in resolved_voltages.items():
            self.virtual_gate_set.channels[VoltageGate].offset_parameter = value

    def _get_dc(
        self,
    ):
        """
        Queries all VoltageGate.offset_parameters for a value.
        """
        dc_values = {
            ch_name: ch.offset_parameter
            for ch_name, ch in self.virtual_gate_set.channels.items()
        }
        return dc_values

    def _inverse_resolve(self, dc_values):
        """
        Inverse resolve of dc values to virtual gate layers
        """
        resolved_virtual = {}
        first_layer = self._resolve_layer(
            self.virtual_gate_set.layers[0],
            [
                dc_values[target]
                for target in self.virtual_gate_set.layers[0].target_gates
            ],
        )

        resolved_virtual.update(first_layer)

        if self.num_layers > 1:
            for layer in list(self.virtual_gate_set.layers)[1:]:
                layer_adds = self._resolve_layer(
                    layer,
                    [
                        resolved_virtual[target_gate]
                        for target_gate in layer.target_gates
                    ],
                )
                resolved_virtual.update(layer_adds)

        return resolved_virtual

    def _resolve_layer(self, layer, target_voltages):
        layer_resolved = np.array(layer.matrix) @ np.array(target_voltages)
        resolved = {}
        for source_gate, value in zip(
            self.virtual_gate_set.layers[0].source_gates, layer_resolved
        ):
            resolved[source_gate] = value
        return resolved
