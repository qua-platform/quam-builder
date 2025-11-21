import pytest

from quam.core import QuamRoot, quam_dataclass
from quam.components import SingleChannel
from quam.components.ports import LFFEMAnalogOutputPort
from quam.components.channels import StickyChannelAddon
from quam_builder.architecture.quantum_dots.components import (
    GateSet,
    VirtualGateSet,
    VirtualizationLayer,
    VoltageGate,
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
    qmm = QuantumMachinesManager(
        host="172.16.33.114", cluster_name="CS_4"
    )  # CS_4 172.16.33.114 #CS_3 172.16.33.115
    return qmm


@pytest.fixture
def machine():
    machine = QuamGateSet(
        gate_set=GateSet(
            id="test_gate_set",
            channels={
                "ch1": VoltageGate(
                    opx_output=LFFEMAnalogOutputPort(
                        "con1", 5, 6, upsampling_mode="pulse"
                    ),
                    sticky=StickyChannelAddon(duration=100, digital=False),
                    attenuation=10,
                ),
                "ch2": VoltageGate(
                    opx_output=LFFEMAnalogOutputPort(
                        "con1", 5, 3, upsampling_mode="pulse"
                    ),
                    sticky=StickyChannelAddon(duration=100, digital=False),
                    attenuation=10,
                ),
            },
            adjust_for_attenuation=True,
        ),
    )
    return machine


@pytest.fixture
def virtual_machine():
    virt_matrix = np.array([[1, 1], [-1, 1]])
    machine = QuamVirtualGateSet(
        virtual_gate_set=VirtualGateSet(
            id="test_virtual_gate_set",
            channels={
                "ch1": VoltageGate(
                    opx_output=LFFEMAnalogOutputPort(
                        "con1", 5, 6, upsampling_mode="pulse", output_mode="direct"
                    ),
                    sticky=StickyChannelAddon(duration=100, digital=False),
                    attenuation=10,
                ),
                "ch2": VoltageGate(
                    opx_output=LFFEMAnalogOutputPort(
                        "con1", 5, 3, upsampling_mode="pulse", output_mode="direct"
                    ),
                    sticky=StickyChannelAddon(duration=100, digital=False),
                    attenuation=10,
                ),
            },
            layers=[
                VirtualizationLayer(
                    source_gates=["energy", "detuning"],
                    target_gates=["ch1", "ch2"],
                    matrix=virt_matrix.tolist(),
                )
            ],
            adjust_for_attenuation=True,
        )
    )

    # machine.virtual_gate_set = gate_set
    return machine
