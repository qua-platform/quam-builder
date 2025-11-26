import pytest
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    QuantumDot,
    BarrierGate,
    QuantumDotPair,
    SensorDot,
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair


@pytest.fixture
def machine():
    """
    Creates a BaseQuamQD machine with a full setup including:
    - 4 plunger gates (quantum dots)
    - 3 barrier gates
    - 1 sensor dot with resonator
    - A virtual gate set
    - 4 registered qubits
    - 2 registered quantum dot pairs
    - 2 registered qubit pairs
    """
    # Instantiate Quam
    machine = BaseQuamQD()
    lf_fem = 6

    # Create Physical Channels
    p1 = VoltageGate(
        id="plunger_1",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=1),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    p2 = VoltageGate(
        id="plunger_2",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=2),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    p3 = VoltageGate(
        id="plunger_3",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=3),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    p4 = VoltageGate(
        id="plunger_4",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=4),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    b1 = VoltageGate(
        id="barrier_1",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=5),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    b2 = VoltageGate(
        id="barrier_2",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=6),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    b3 = VoltageGate(
        id="barrier_3",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=7),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    s1 = VoltageGate(
        id="sensor_DC",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=8),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    from quam.components import pulses

    readout_pulse = pulses.SquareReadoutPulse(length=200, id="readout", amplitude=0.01)
    resonator = ReadoutResonatorSingle(
        id="readout_resonator",
        frequency_bare=0,
        intermediate_frequency=500e6,
        operations={"readout": readout_pulse},
        opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        opx_input=LFFEMAnalogInputPort("con1", 5, port_id=2),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    # Create Virtual Gate Set
    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": p1,
            "virtual_dot_2": p2,
            "virtual_dot_3": p3,
            "virtual_dot_4": p4,
            "virtual_barrier_1": b1,
            "virtual_barrier_2": b2,
            "virtual_barrier_3": b3,
            "virtual_sensor_1": s1,
        },
        gate_set_id="main_qpu",
    )

    # Register Quantum Dots, Sensors and Barriers
    machine.register_channel_elements(
        plunger_channels=[p1, p2, p3, p4],
        barrier_channels=[b1, b2, b3],
        sensor_resonator_mapping={s1: resonator},
    )

    # Register Qubits
    machine.register_qubit(
        qubit_type="loss_divincenzo", quantum_dot_id="virtual_dot_1", id="Q1"
    )
    machine.register_qubit(
        qubit_type="loss_divincenzo", quantum_dot_id="virtual_dot_2", id="Q2"
    )
    machine.register_qubit(
        qubit_type="loss_divincenzo", quantum_dot_id="virtual_dot_3", id="Q3"
    )
    machine.register_qubit(
        qubit_type="loss_divincenzo", quantum_dot_id="virtual_dot_4", id="Q4"
    )

    # Register Quantum Dot Pairs
    machine.register_quantum_dot_pair(
        id="dot1_dot2_pair",
        quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
        sensor_dot_ids=["virtual_sensor_1"],
        barrier_gate_id="virtual_barrier_2",
    )
    machine.register_quantum_dot_pair(
        id="dot3_dot4_pair",
        quantum_dot_ids=["virtual_dot_3", "virtual_dot_4"],
        sensor_dot_ids=["virtual_sensor_1"],
        barrier_gate_id="virtual_barrier_3",
    )

    # Define detuning axes for both QuantumDotPairs
    machine.quantum_dot_pairs["dot1_dot2_pair"].define_detuning_axis(
        matrix=[[1, 1], [1, -1]], detuning_axis_name="dot1_dot2_epsilon"
    )
    machine.quantum_dot_pairs["dot3_dot4_pair"].define_detuning_axis(
        matrix=[[1, 1], [1, -1]], detuning_axis_name="dot3_dot4_epsilon"
    )

    # Register Qubit Pairs
    machine.register_qubit_pair(
        id="Q1_Q2",
        qubit_type="loss_divincenzo",
        qubit_control_id="Q1",
        qubit_target_id="Q2",
    )
    machine.register_qubit_pair(
        id="Q3_Q4",
        qubit_type="loss_divincenzo",
        qubit_control_id="Q3",
        qubit_target_id="Q4",
    )

    return machine