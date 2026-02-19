"""Shared fixtures for quantum-dot architecture tests."""

import pytest
from quam.components import StickyChannelAddon, pulses
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


def _make_voltage_gate(lf_fem: int, port: int, gate_id: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=port),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )


@pytest.fixture
def qd_machine():
    """Fully wired LossDiVincenzoQuam with 4 dots, 3 barriers, 1 sensor,
    4 qubits, 2 quantum-dot pairs, and 2 qubit pairs."""
    machine = LossDiVincenzoQuam()
    lf = 6

    p1 = _make_voltage_gate(lf, 1, "plunger_1")
    p2 = _make_voltage_gate(lf, 2, "plunger_2")
    p3 = _make_voltage_gate(lf, 3, "plunger_3")
    p4 = _make_voltage_gate(lf, 4, "plunger_4")
    b1 = _make_voltage_gate(lf, 5, "barrier_1")
    b2 = _make_voltage_gate(lf, 6, "barrier_2")
    b3 = _make_voltage_gate(lf, 7, "barrier_3")
    s1 = _make_voltage_gate(lf, 8, "sensor_DC")

    resonator = ReadoutResonatorSingle(
        id="readout_resonator",
        frequency_bare=0,
        intermediate_frequency=500e6,
        operations={"readout": pulses.SquareReadoutPulse(length=200, id="readout", amplitude=0.01)},
        opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        opx_input=LFFEMAnalogInputPort("con1", 5, port_id=2),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

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

    machine.register_channel_elements(
        plunger_channels=[p1, p2, p3, p4],
        barrier_channels=[b1, b2, b3],
        sensor_resonator_mappings={s1: resonator},
    )

    machine.register_qubit(quantum_dot_id="virtual_dot_1", qubit_name="Q1")
    machine.register_qubit(quantum_dot_id="virtual_dot_2", qubit_name="Q2")
    machine.register_qubit(quantum_dot_id="virtual_dot_3", qubit_name="Q3")
    machine.register_qubit(quantum_dot_id="virtual_dot_4", qubit_name="Q4")

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

    machine.quantum_dot_pairs["dot1_dot2_pair"].define_detuning_axis(
        matrix=[[1, -1]],
        detuning_axis_name="dot1_dot2_epsilon",
        set_dc_virtual_axis=False,
    )
    machine.quantum_dot_pairs["dot3_dot4_pair"].define_detuning_axis(
        matrix=[[1, -1]],
        detuning_axis_name="dot3_dot4_epsilon",
        set_dc_virtual_axis=False,
    )

    machine.register_qubit_pair(qubit_control_name="Q1", qubit_target_name="Q2", id="Q1_Q2")
    machine.register_qubit_pair(qubit_control_name="Q3", qubit_target_name="Q4", id="Q3_Q4")

    # QuantumDotPair.__post_init__ eagerly creates the VoltageSequence (cached)
    # before detuning axes are added, so the KeepLevels tracker is stale.
    machine.reset_voltage_sequence("main_qpu")

    return machine
