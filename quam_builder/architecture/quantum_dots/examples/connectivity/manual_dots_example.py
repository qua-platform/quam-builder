"""Build the dot layer by hand: no ``Connectivity`` / ``Instruments`` / wirer.

Same device as ``wiring_combined_example.py`` and ``wiring_two_stage_example.py``
(same ids, same OPX ports, same QDAC channels) but every ``VoltageGate`` and
port is written out explicitly. Use this path when you want full control over
port placement, or when integrating hardware the wirer does not model.

Ends on a ``BaseQuamQD``: 4 quantum dots, 2 quantum dot pairs, 2 sensor dots,
a QDAC output on every gate (trigger on plunger_1/plunger_2 only -- see
``wiring_combined_example.py`` for why). No qubits yet: that is
``manual_qubits_example.py``, which loads the state this script saves.
"""

from __future__ import annotations

import os
from pathlib import Path

from quam.components import Channel, DigitalOutputChannel, StickyChannelAddon, pulses
from quam.components.ports import LFFEMAnalogInputPort, LFFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import (
    QdacSpec,
    ReadoutResonatorSingle,
    VoltageGate,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.examples.connectivity.wiring_combined_LD_example import (
    READOUT_AMPLITUDE_V,
    READOUT_DURATION_NS,
    SENSOR_RESONATOR_FREQUENCIES_HZ,
    configure_sensor_readout,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

EXAMPLES_DIR = Path(__file__).resolve().parents[1]
STATE_PATH = EXAMPLES_DIR / "quam_state" / "manual_dots"

CON = "con1"
LF_FEM_GATES = [2, 3]  # plungers, barriers, sensor gates
LF_FEM_RESONATORS = 4
QDAC_NAME = "qdac1"


def make_gate(gate_id: str, port: int, *, trigger_in: int | None = None) -> VoltageGate:
    """One physical VoltageGate: an OPX sticky output plus a QDAC DC output.

    Port numbers below (1-8 across plungers/barriers/sensor gates, matching
    QDAC output 1-8) are exactly what ``wiring_combined_example.py`` allocates
    for the same elements, so this script produces the same machine.
    """
    if port > 8: 
        lf_fem_id = LF_FEM_GATES[1] 
        port = port - 8
    else:
        lf_fem_id = LF_FEM_GATES[0]
    dac_spec = QdacSpec(dac_name=QDAC_NAME, output_port=port)
    if trigger_in is not None:
        # A digital marker on the same LF-FEM port triggers the QDAC to step
        # in sync with the OPX sequence. Only plunger_1/plunger_2 get one here
        # -- a QDAC-II unit has 4 trigger inputs, not enough for all 8 gates.
        dac_spec.qdac_trigger_in = trigger_in
        dac_spec.opx_trigger_out = Channel(
            id=f"{gate_id}_qdac_trigger",
            digital_outputs={
                "trigger": DigitalOutputChannel(
                    opx_output=(CON, lf_fem_id, port), delay=0, buffer=0
                )
            },
            operations={"trigger": pulses.Pulse(length=100, digital_marker="ON")},
        )
    return VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort(CON, lf_fem_id, port_id=port),
        sticky=StickyChannelAddon(duration=16, digital=False),
        dac_spec=dac_spec,
    )


def build_physical_channels() -> dict:
    """Step 1: one VoltageGate per plunger, barrier, and sensor gate."""
    plungers = [make_gate(f"plunger_{i}", i, trigger_in=i if i <= 2 else None) for i in range(1, 7)]
    barriers = [make_gate(f"barrier_{i}", 6 + i) for i in range(1, 6)]
    sensors = [make_gate(f"sensor_{i}", 11 + i) for i in range(1, 3)]
    return {"plungers": plungers, "barriers": barriers, "sensors": sensors}


def build_resonators() -> list[ReadoutResonatorSingle]:
    """Step 2: one RF-reflectometry resonator per sensor dot.

    Sensor 1 is a 115 MHz tank, sensor 2 is 233 MHz. The readout pulse is
    0.3 V for 2500 ns on both.
    """
    return [
        ReadoutResonatorSingle(
            id=f"readout_resonator_{i}",
            frequency_bare=SENSOR_RESONATOR_FREQUENCIES_HZ[i],
            intermediate_frequency=int(SENSOR_RESONATOR_FREQUENCIES_HZ[i]),
            operations={
                "readout": pulses.SquareReadoutPulse(
                    length=READOUT_DURATION_NS,
                    id="readout",
                    amplitude=READOUT_AMPLITUDE_V,
                )
            },
            opx_output=LFFEMAnalogOutputPort(CON, LF_FEM_RESONATORS, port_id=i),
            opx_input=LFFEMAnalogInputPort(CON, LF_FEM_RESONATORS, port_id=i),
            sticky=StickyChannelAddon(duration=16, digital=False),
        )
        for i in [1, 2]
    ]


def register_gate_set_and_elements(
    machine: BaseQuamQD, channels: dict, resonators: list[ReadoutResonatorSingle]
) -> None:
    """Step 3: virtual gate set, then QuantumDot / BarrierGate / SensorDot."""
    plungers, barriers, sensors = channels["plungers"], channels["barriers"], channels["sensors"]

    # create_virtual_gate_set adds these channels to machine.physical_channels;
    # no need to register them separately.
    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": plungers[0],
            "virtual_dot_2": plungers[1],
            "virtual_dot_3": plungers[2],
            "virtual_dot_4": plungers[3],
            "virtual_dot_5": plungers[4],
            "virtual_dot_6": plungers[5],
            "virtual_barrier_1": barriers[0],
            "virtual_barrier_2": barriers[1],
            "virtual_barrier_3": barriers[2],
            "virtual_barrier_4": barriers[3],
            "virtual_barrier_5": barriers[4],
            "virtual_sensor_1": sensors[0],
            "virtual_sensor_2": sensors[1],
        },
        gate_set_id="main_qpu",
    )

    machine.register_channel_elements(
        plunger_channels=plungers,
        barrier_channels=barriers,
        sensor_resonator_mappings={sensors[0]: resonators[0], sensors[1]: resonators[1]},
    )


def register_quantum_dot_pairs(machine: BaseQuamQD) -> None:
    """Step 4: pair (1,2) on barrier_1, pair (3,4) on barrier_2.

    register_quantum_dot_pair() also defines the pair's detuning axis
    (epsilon = dot_a - dot_b) by default -- no separate call needed.
    """
    quantum_dot_pairs = [
        (1, 2), 
        (2, 3), 
        (3, 4), 
        (4, 5), 
        (5, 6), 
    ]
    for qdp in quantum_dot_pairs: 
        machine.register_quantum_dot_pair(
            id=f"virtual_dot_{qdp[0]}_virtual_dot_{qdp[1]}_pair",
            quantum_dot_ids=[f"virtual_dot_{qdp[0]}", f"virtual_dot_{qdp[1]}"],
            sensor_dot_ids = [f"virtual_sensor_{1 if qdp[0] > 3 else 2}"], 
            barrier_gate_id = f"virtual_barrier_{qdp[0]}"
        )


def set_qdac_config(machine: BaseQuamQD) -> None:
    """Step 5: store the QDAC driver entry on the machine.

    ``connect_to_external_source()`` reads this entry when a real connection
    is opened. This call only records it.
    """
    machine.set_dac_config(
        {
            QDAC_NAME: {
                "driver_module": "qcodes_contrib_drivers.drivers.QDevil.QDAC2",
                "driver_class": "QDac2",
                "connection": {"visalib": "@py", "address": "TCPIP::127.0.0.2::5025::SOCKET"},
                "channel_method": "channel",
                "accessor": "dc_constant_V",
                "is_qdac": True,
                "close_method": "close",
            }
        }
    )


def main() -> BaseQuamQD:
    machine = BaseQuamQD()
    machine.network = {"host": "127.0.0.1", "cluster_name": "tutorial"}

    channels = build_physical_channels()
    resonators = build_resonators()
    register_gate_set_and_elements(machine, channels, resonators)
    register_quantum_dot_pairs(machine)
    set_qdac_config(machine)

    # Default macros/pulses, same as the wirer path (build_base_quam calls this
    # too), so downstream examples work the same regardless of how the
    # machine was built.
    wire_machine_macros(machine)
    # Pair-specific readout pulses are added by wire_machine_macros. Apply the
    # same 0.3 V / 2500 ns pulse to every readout operation.
    configure_sensor_readout(machine)

    os.makedirs(STATE_PATH, exist_ok=True)
    machine.save(str(STATE_PATH))
    print(f"Saved BaseQuamQD to {STATE_PATH}")
    print(f"quantum_dots: {list(machine.quantum_dots)}")
    print(f"quantum_dot_pairs: {list(machine.quantum_dot_pairs)}")
    print(f"sensor_dots: {list(machine.sensor_dots)}")

    # Real connection (needs a live QOP + QDAC-II on the network):
    # machine.connect()
    # machine.connect_to_external_source()
    return machine


if __name__ == "__main__":
    main()
