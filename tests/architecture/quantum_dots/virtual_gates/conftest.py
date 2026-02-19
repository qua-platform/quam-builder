import pytest

from quam.core import QuamRoot, quam_dataclass
from quam.components import SingleChannel
from quam_builder.architecture.quantum_dots.voltage_sequence.gate_set import (
    GateSet,
)
from quam_builder.architecture.quantum_dots.virtual_gates.virtual_gate_set import (
    VirtualGateSet,
)


@quam_dataclass
class QuamGateSet(QuamRoot):
    gate_set: GateSet


@pytest.fixture
def machine():
    machine = QuamGateSet(
        gate_set=GateSet(
            id="test_gate_set",
            channels={
                "ch1": SingleChannel(opx_output=("con1", 1, 1)),
                "ch2": SingleChannel(opx_output=("con1", 1, 2)),
            },
        ),
    )
    return machine
