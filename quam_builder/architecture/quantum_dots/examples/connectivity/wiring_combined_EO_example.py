"""Build a QuAM machine from connectivity, in one stage, including a QDAC.

This is the "wirer" path: describe *what* is connected (dots, sensors,
drive lines, a QDAC) without picking exact ports, let ``allocate_wiring``
choose free channels, then call one builder function to get a fully wired
``LossDiVincenzoQuam``.

Device built here (also used by ``wiring_two_stage_example.py``,
``manual_dots_example.py``, and ``manual_qubits_example.py`` so all four
scripts produce the same machine):

- 6 quantum dots (virtual_dot_1..6), plunger gates on LF-FEM ports 1-6
- 5 quantum dot pairs: (1,2) -> barrier_1, (3,4) -> barrier_2, etc. 
- 2 sensor dots (virtual_sensor_1, virtual_sensor_2), each with its own
  sensor gate and RF-reflectometry resonator (115 MHz and 233 MHz,
  readout pulse 0.3 V for 2500 ns)
- 2 qubits (q1, q2)
- 1 qubit pair: q1_q2
- 1 QDAC-II unit. Every plunger, barrier, and sensor gate gets a QDAC DC
  output alongside its OPX output (see components/README.md "DAC
  integration"). Only plunger_1 and plunger_2 also get a QDAC external
  trigger, since a QDAC-II unit has 4 trigger inputs and 8 gates would
  need more than that -- trigger the gates that step during a sequence,
  leave the rest as a plain DC offset.

Ports are **not** pinned: the allocator picks the first free channel that
satisfies each request. ``manual_dots_example.py`` / ``manual_qubits_example.py``
hardcode the ports this script happens to produce, so run this script first
if you change the connectivity below.
"""

from __future__ import annotations

from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from qualang_tools.wirer.wirer.channel_specs import lf_fem_spec, qdac2_spec

from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, ExchangeOnlyQuam
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_quam

QUANTUM_DOTS = [1, 2, 3, 4, 5, 6]
QUANTUM_DOT_PAIRS = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]
SENSOR_DOTS = [1, 2]
TRIGGERED_DOTS = [1, 2]  # QDAC trigger input is scarce (4 per unit); trigger these only.
QUBITS_SENSOR_MAP = {"q1": ["sensor_1"], "q2": ["sensor_2"]}

# Tank frequencies on the LF-FEM. The readout pulse amplitude is in volts.
SENSOR_RESONATOR_FREQUENCIES_HZ = {1: 115e6, 2: 233e6}
READOUT_AMPLITUDE_V = 0.3
READOUT_DURATION_NS = 2500


def qdac_config(ip: str) -> dict:
    """Driver entry for ``set_dac_config`` / ``build_quam_wiring(dac_config=...)``."""
    return {
        "driver_module": "qcodes_contrib_drivers.drivers.QDevil.QDAC2",
        "driver_class": "QDac2",
        "connection": {"visalib": "@py", "address": f"TCPIP::{ip}::5025::SOCKET"},
        "channel_method": "channel",
        "accessor": "dc_constant_V",
        "is_qdac": True,
    }


def declare_connectivity() -> Connectivity:
    """Step 1: describe the elements and which lines they need. No channels yet."""
    connectivity = Connectivity()

    # Sensor dots: a sensor gate (DC + QDAC) and its own resonator line.
    connectivity.add_sensor_dot_voltage_gate_lines(
        SENSOR_DOTS, constraints=lf_fem_spec() & qdac2_spec()
    )
    connectivity.add_sensor_dot_resonator_line(SENSOR_DOTS, shared_line=False)

    # Quantum dot plunger gates: split so only dots 1-2 request a QDAC trigger.
    connectivity.add_quantum_dot_voltage_gate_lines(
        TRIGGERED_DOTS, triggered=True, constraints=lf_fem_spec() & qdac2_spec()
    )
    remaining_dots = [d for d in QUANTUM_DOTS if d not in TRIGGERED_DOTS]
    connectivity.add_quantum_dot_voltage_gate_lines(
        remaining_dots, constraints=lf_fem_spec() & qdac2_spec()
    )

    # Barrier gates for each quantum dot pair (also DC + QDAC, no trigger).
    connectivity.add_barrier_voltage_gate_lines(
        QUANTUM_DOT_PAIRS, constraints=lf_fem_spec() & qdac2_spec()
    )

    return connectivity


def declare_instruments() -> Instruments:
    """Step 2: declare what hardware is available to allocate from."""
    instruments = Instruments()
    instruments.add_lf_fem(controller=1, slots=[2, 3])  # slot 2: DC gates, slot 3: resonators
    instruments.add_qdac2(indices=[1])  # one QDAC-II unit
    return instruments


def build_machine(connectivity: Connectivity, instruments: Instruments) -> ExchangeOnlyQuam:
    """Step 3: allocate channels, then build the full machine in one call."""
    allocate_wiring(connectivity, instruments)

    machine = build_quam_wiring(
        connectivity,
        host_ip="127.0.0.1",
        cluster_name="tutorial",
        quam_instance=BaseQuamQD(),
        dac_config={"qdac1": qdac_config("127.0.0.2")},
    )
    machine = build_quam(
        machine,
        qubits_sensor_map=QUBITS_SENSOR_MAP,
        save=False,
        target_quam_class=ExchangeOnlyQuam,
    )
    configure_sensor_readout(machine)
    return machine


def configure_sensor_readout(machine) -> None:
    """Set each sensor resonator frequency and the shared readout pulse.

    The builder fills these from ``DEFAULTS.readout``. This device uses a
    115 MHz tank on sensor 1 and a 233 MHz tank on sensor 2.
    """
    for sensor_id, sensor in machine.sensor_dots.items():
        sensor_number = int(sensor_id.rsplit("_", 1)[-1])
        frequency_hz = SENSOR_RESONATOR_FREQUENCIES_HZ[sensor_number]
        resonator = sensor.readout_resonator
        resonator.frequency_bare = frequency_hz
        resonator.intermediate_frequency = int(frequency_hz)
        for pulse in resonator.operations.values():
            if str(getattr(pulse, "id", "")).startswith("readout"):
                pulse.amplitude = READOUT_AMPLITUDE_V
                pulse.length = READOUT_DURATION_NS


def print_summary(machine: ExchangeOnlyQuam) -> None:
    """Step 4: show the ports and QDAC channels the allocator picked."""
    print("=== Quantum dots -> plunger gates ===")
    for dot_id, dot in machine.quantum_dots.items():
        gate = dot.physical_channel
        dac = gate.dac_spec
        print(
            f"  {dot_id}: opx=fem{gate.opx_output.fem_id}/port{gate.opx_output.port_id} "
            f"qdac_out={dac.output_port} trigger={'yes' if dac.opx_trigger_out else 'no'}"
        )

    print("=== Quantum dot pairs -> barrier gates ===")
    for pair_id, pair in machine.quantum_dot_pairs.items():
        gate = pair.barrier_gate.physical_channel
        print(f"  {pair_id}: qdac_out={gate.dac_spec.output_port}")

    print("=== Sensor dots ===")
    for sensor_id, sensor in machine.sensor_dots.items():
        r = sensor.readout_resonator
        readout = r.operations["readout"]
        print(
            f"  {sensor_id}: gate qdac_out={sensor.physical_channel.dac_spec.output_port}, "
            f"resonator=fem{r.opx_output.fem_id}/port{r.opx_output.port_id} "
            f"at {r.intermediate_frequency / 1e6:.0f} MHz, "
            f"readout={readout.amplitude} V for {readout.length} ns"
        )

    print("=== Qubits ===")
    for qubit_id, qubit in machine.qubits.items():
        print(f"  {qubit_id}: Jn_pair = {qubit.jn_pair.name}, Jz_pair = {qubit.jz_pair.name}")

    print("=== Qubit pairs ===")
    print(f"  {list(machine.qubit_pairs.keys())}")

    # Real connection (needs a live QOP + QDAC-II on the network):
    # machine.connect()
    # machine.connect_to_external_source()
    # machine.save()


def main() -> ExchangeOnlyQuam:
    connectivity = declare_connectivity()
    instruments = declare_instruments()
    machine = build_machine(connectivity, instruments)
    print_summary(machine)
    return machine


if __name__ == "__main__":
    main()
