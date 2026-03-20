"""Shared machine builder for the macro customization tutorial.

Provides a minimal LossDiVincenzoQuam with quantum_dots, quantum_dot_pairs,
sensor_dots, qubits, and qubit_pairs. Includes voltage step points so default
state macros can run. Does NOT call wire_machine_macros — that is done by
the tutorial notebook.
"""

from __future__ import annotations

from typing import Dict

from quam.components import StickyChannelAddon, pulses
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


def _make_voltage_gate(lf_fem: int, port: int, gate_id: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=port),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )


def build_tutorial_machine() -> LossDiVincenzoQuam:
    """Build a minimal machine for the macro customization tutorial.

    Returns a LossDiVincenzoQuam with:
    - 2 quantum dots, 1 quantum dot pair, 1 sensor dot
    - 2 qubits, 1 qubit pair
    - Voltage gates, readout resonator, virtual gate set
    - Voltage step points (initialize, measure, empty) for state macros

    Does not call wire_machine_macros. The caller (tutorial/script) does that.
    """
    machine = LossDiVincenzoQuam()
    lf = 6

    p1 = _make_voltage_gate(lf, 1, "plunger_1")
    p2 = _make_voltage_gate(lf, 2, "plunger_2")
    b1 = _make_voltage_gate(lf, 5, "barrier_1")
    b2 = _make_voltage_gate(lf, 6, "barrier_2")
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
            "virtual_barrier_1": b1,
            "virtual_barrier_2": b2,
            "virtual_sensor_1": s1,
        },
        gate_set_id="main_qpu",
    )

    machine.register_channel_elements(
        plunger_channels=[p1, p2],
        barrier_channels=[b1, b2],
        sensor_resonator_mappings={s1: resonator},
    )

    machine.register_qubit(quantum_dot_id="virtual_dot_1", qubit_name="Q1")
    machine.register_qubit(quantum_dot_id="virtual_dot_2", qubit_name="Q2")

    machine.register_quantum_dot_pair(
        id="dot1_dot2_pair",
        quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
        sensor_dot_ids=["virtual_sensor_1"],
        barrier_gate_id="virtual_barrier_2",
    )

    machine.quantum_dot_pairs["dot1_dot2_pair"].define_detuning_axis(
        matrix=[[1, -1]],
        detuning_axis_name="dot1_dot2_epsilon",
        set_dc_virtual_axis=False,
    )

    machine.register_qubit_pair(qubit_control_name="Q1", qubit_target_name="Q2", id="Q1_Q2")

    machine.reset_voltage_sequence("main_qpu")
    _add_tutorial_state_points(machine)
    return machine


def _add_tutorial_state_points(machine: LossDiVincenzoQuam) -> None:
    """Add voltage step points so default state macros can run."""
    for qubit in machine.qubits.values():
        dot_id = qubit.quantum_dot.id
        qubit.add_point(VoltagePointName.INITIALIZE, {dot_id: 0.10}, duration=200)
        qubit.add_point(VoltagePointName.MEASURE, {dot_id: 0.15}, duration=200)
        qubit.add_point(VoltagePointName.EMPTY, {dot_id: 0.00}, duration=200)

    # Pairs share voltage sequence with dots; add points for both dots
    for pair in machine.quantum_dot_pairs.values():
        dot_ids = [qd.id for qd in pair.quantum_dots]
        v_init: Dict[str, float] = {d: 0.10 for d in dot_ids}
        v_meas: Dict[str, float] = {d: 0.15 for d in dot_ids}
        v_empty: Dict[str, float] = {d: 0.00 for d in dot_ids}
        pair.add_point(VoltagePointName.INITIALIZE, v_init, duration=200)
        pair.add_point(VoltagePointName.MEASURE, v_meas, duration=200)
        pair.add_point(VoltagePointName.EMPTY, v_empty, duration=200)
