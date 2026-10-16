"""Example: ramps, hold levels, and stateless voltage calls.

``virtual_gate_set_example.py`` steps to a voltage. This script is about how
a call moves the other gates, and how a ramp differs from a step.

``GateSet.new_sequence(keep_levels=...)`` chooses the mode:

* ``keep_levels=True`` (the default). A gate you leave out of a call stays at
  its last voltage.
* ``keep_levels=False``. A gate you leave out is driven to 0 V. Every call
  states the whole voltage dict.

A ramp takes a ``ramp_duration`` (ns, multiple of 4, longer than 16). The
channel slews to the target over that time, then holds for ``duration``.
``ramp_to_zero`` brings every physical channel back to 0 V. Close a sequence
with it.

Each step builds a short QUA program on the tutorial machine and prints it
with ``generate_qua_script``. Set ``SIMULATE_ON_OPX = True`` to simulate each
program on an OPX and plot its waveform report. The OPX address comes from
``build_tutorial_machine()``.
"""

from __future__ import annotations

from qm import SimulationConfig, generate_qua_script, qua

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.builder.quantum_dots.build_utils import DEFAULT_GATE_SET_ID

SIMULATE_ON_OPX = False
# Clock cycles (4 ns). The longest program here is about 1 us.
SIMULATION_DURATION_CLK = 2_000

_DOT_PREFIX = "virtual_dot_"
HOLD_NS = 200
RAMP_NS = 100


def print_gates(gate_set, dot_names: list[str]) -> None:
    """Step 1: the two virtual plungers the later programs move."""
    print("=== 1. Gates on the tutorial machine ===")
    print(f"gate set: {gate_set.id}")
    print(f"physical channels: {list(gate_set.channels)}")
    print(f"virtual plungers used below: {dot_names}")
    print(
        "Each program sets the first plunger, then a call that names only the second."
    )


def play_holding_levels(gate_set, first: str, second: str):
    """Step 2: keep_levels=True. The first plunger stays put on the second call."""
    print("\n=== 2. Holding levels (keep_levels=True, the default) ===")
    print(f"Call 1 sets {first}. Call 2 names only {second}, so {first} stays.")
    sequence = gate_set.new_sequence(keep_levels=True)
    with qua.program() as program:
        sequence.step_to_voltages({first: 0.10}, duration=HOLD_NS)
        sequence.step_to_voltages({second: 0.05}, duration=HOLD_NS)
    _print_program(program)
    return program


def play_stateless(gate_set, first: str, second: str):
    """Step 3: keep_levels=False. Omitting a gate drives it back to 0 V."""
    print("\n=== 3. Stateless calls (keep_levels=False) ===")
    print(f"Same two calls. Call 2 omits {first}, so that plunger goes to 0 V.")
    sequence = gate_set.new_sequence(keep_levels=False)
    with qua.program() as program:
        sequence.step_to_voltages({first: 0.10}, duration=HOLD_NS)
        sequence.step_to_voltages({second: 0.05}, duration=HOLD_NS)
    _print_program(program)
    return program


def play_ramps(gate_set, first: str, second: str):
    """Step 4: ramp to a voltage, ramp to a named point, ramp every gate to 0."""
    print("\n=== 4. Ramps ===")
    print(
        f"Each move slews for {RAMP_NS} ns, then holds. "
        "ramp_to_zero ends the sequence with every physical channel at 0 V."
    )
    gate_set.add_point("biased", {first: 0.10, second: -0.10}, duration=HOLD_NS)
    sequence = gate_set.new_sequence(keep_levels=True)
    with qua.program() as program:
        sequence.ramp_to_voltages({first: 0.10}, duration=HOLD_NS, ramp_duration=RAMP_NS)
        sequence.ramp_to_point("biased", ramp_duration=RAMP_NS)
        sequence.ramp_to_zero(ramp_duration=RAMP_NS)
    _print_program(program)
    return program


def simulate_on_opx(machine, programs: dict):
    """Simulate each program on the OPX and plot its waveform report.

    Returns ``{name: waveform_report}``, so the reports can be inspected
    after ``main()``.
    """
    qmm = machine.connect()
    config = machine.generate_config()
    reports = {}
    for name, program in programs.items():
        print(f"\nSimulating {name}...")
        job = qmm.simulate(config, program, SimulationConfig(duration=SIMULATION_DURATION_CLK))
        job.wait_until("Done", timeout=300)
        samples = job.get_simulated_samples()
        report = job.get_simulated_waveform_report()
        report.create_plot(samples, plot=True)
        reports[name] = report
    return reports


def main():
    machine = build_tutorial_machine()
    gate_set = machine.virtual_gate_sets[DEFAULT_GATE_SET_ID]
    dot_names = _dot_names(gate_set)

    print_gates(gate_set, dot_names)
    programs = {
        "holding levels": play_holding_levels(gate_set, dot_names[0], dot_names[1]),
        "stateless": play_stateless(gate_set, dot_names[0], dot_names[1]),
        "ramps": play_ramps(gate_set, dot_names[0], dot_names[1]),
    }
    reports = simulate_on_opx(machine, programs) if SIMULATE_ON_OPX else None
    return machine, programs, reports


def _dot_names(gate_set) -> list[str]:
    """Virtual plunger names, in compensation-layer order."""
    layer = gate_set.layers[0]
    return [
        virtual_name
        for virtual_name in layer.source_gates
        if str(virtual_name).startswith(_DOT_PREFIX)
    ]


def _print_program(program) -> None:
    print(generate_qua_script(program))


if __name__ == "__main__":
    main()
