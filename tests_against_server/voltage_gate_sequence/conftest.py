import pytest

from quam.core import QuamRoot, quam_dataclass
from quam.components import SingleChannel
from quam.components.ports import LFFEMAnalogOutputPort
from quam.components.channels import StickyChannelAddon
from quam_builder.architecture.quantum_dots.components import (
    GateSet,
    VirtualGateSet,
    VirtualizationLayer,
)
from qm import QuantumMachinesManager
import numpy as np


@quam_dataclass
class QuamGateSet(QuamRoot):
    gate_set: GateSet


@quam_dataclass
class QuamVirtualGateSet(QuamRoot):
    virtual_gate_set: VirtualGateSet


@pytest.fixture
def qmm():
    qmm = QuantumMachinesManager(host="172.16.33.115", cluster_name="CS_3")
    return qmm


@pytest.fixture
def machine():
    machine = QuamGateSet(
        gate_set=GateSet(
            id="test_gate_set",
            channels={
                "ch1": SingleChannel(
                    opx_output=LFFEMAnalogOutputPort("con1", 5, 6),
                    sticky=StickyChannelAddon(duration=100, digital=False),
                ),
                "ch2": SingleChannel(
                    opx_output=LFFEMAnalogOutputPort("con1", 5, 3),
                    sticky=StickyChannelAddon(duration=100, digital=False),
                ),
            },
        ),
    )
    return machine


@pytest.fixture
def virtual_machine():
    machine = QuamVirtualGateSet()
    virt_matrix = np.eye(2)

    gate_set = VirtualGateSet(
        id="test_virtual_gate_set",
        channels={
            "ch1": SingleChannel(
                opx_output=LFFEMAnalogOutputPort(
                    "con1", 5, 6, upsampling_mode="pulse", output_mode="direct"
                ),
                sticky=StickyChannelAddon(duration=100, digital=False),
            ),
            "ch2": SingleChannel(
                opx_output=LFFEMAnalogOutputPort(
                    "con1", 5, 3, upsampling_mode="pulse", output_mode="direct"
                ),
                sticky=StickyChannelAddon(duration=100, digital=False),
            ),
        },
        layers=[
            VirtualizationLayer(
                source_gates=["v1", "v2"],
                target_gates=["ch1", "ch2"],
                matrix=virt_matrix.tolist(),
            )
        ],
    )

    machine.virtual_gate_set = gate_set
    return machine
