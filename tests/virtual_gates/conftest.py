import pytest

from quam.components import SingleChannel, StickyChannelAddon
from quam.core import QuamRoot, quam_dataclass
from quam_builder.architecture.quantum_dots.components.gate_set import (
    GateSet,
)
from quam_builder.architecture.quantum_dots.components.virtual_gate_set import (
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
                "ch1": SingleChannel(
                    opx_output=("con1", 1, 1),
                    sticky=StickyChannelAddon(duration=16, digital=False),
                ),
                "ch2": SingleChannel(
                    opx_output=("con1", 1, 2),
                    sticky=StickyChannelAddon(duration=16, digital=False),
                ),
            },
        ),
    )
    return machine


@pytest.fixture
def virtual_gate_set() -> VirtualGateSet:
    """Simple VirtualGateSet with two physical channels for virtual gate tests."""
    return VirtualGateSet(
        id="test_virtual_gate_set",
        channels={
            "ch1": SingleChannel(
                opx_output=("con1", 1, 1),
                sticky=StickyChannelAddon(duration=16, digital=False),
            ),
            "ch2": SingleChannel(
                opx_output=("con1", 1, 2),
                sticky=StickyChannelAddon(duration=16, digital=False),
            ),
        },
    )
