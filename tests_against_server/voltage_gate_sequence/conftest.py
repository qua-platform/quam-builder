import pytest

from quam.core import QuamRoot, quam_dataclass
from quam.components import SingleChannel
from quam.components.ports import LFFEMAnalogOutputPort
from quam.components.channels import StickyChannelAddon
from quam_builder.architecture.quantum_dots.voltage_sequence.gate_set import (
    GateSet,
)
from qm import QuantumMachinesManager


@quam_dataclass
class QuamGateSet(QuamRoot):
    gate_set: GateSet

@pytest.fixture
def qmm():
    qmm = QuantumMachinesManager(host="172.16.33.115", cluster_name="CS_4")
    return qmm

@pytest.fixture
def machine():
    machine = QuamGateSet(
        gate_set=GateSet(
            id="test_gate_set",
            channels={
                "ch1": SingleChannel(opx_output=LFFEMAnalogOutputPort("con1", 5, 6), sticky=StickyChannelAddon(duration=100, digital=False)),
                "ch2": SingleChannel(opx_output=LFFEMAnalogOutputPort("con1", 5, 3), sticky=StickyChannelAddon(duration=100, digital=False)),
            },
        ),
    )
    machine.gate_set.channels["ch1"].opx_output.output_mode = "amplified"
    machine.gate_set.channels["ch1"].opx_output.upsampling_mode = "pulse"
    machine.gate_set.channels["ch2"].opx_output.upsampling_mode = "pulse"
    return machine