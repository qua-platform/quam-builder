"""Rabi chevron on the tutorial machine.

A Rabi chevron sweeps the drive frequency and the drive duration of one qubit.
The resulting 2D map shows the qubit resonance (centre of the chevron) and the
Rabi frequency (oscillation period along the duration axis).

The script only uses what ``build_tutorial_machine()`` already wires:

- ``qubit.x180(duration=t)``: the default X180 macro, played for ``t`` clock cycles.
- ``sensor.macros["measure"]()``: the default sensor-dot macro. Without a pair id,
  it returns the raw ``(I, Q)`` of the reflectometry readout.
- ``qubit.step_to_point(...)``: voltage navigation. The ``initialize`` and ``measure``
  points come from the tutorial machine. The ``operate`` point, where the qubit
  is driven, is added below.

One shot of the sequence:

    initialize  ->  operate + X180(duration=t)  ->  measure  ->  compensation pulse

By default, the script builds the machine, the QUA config and the program, then
prints a summary and the serialized QUA program. Set ``SIMULATE_ON_OPX = True`` to
simulate the start of the sweep on a real OPX and plot the waveform report. The
OPX address comes from ``cluster_config_path`` in ``build_tutorial_machine()``.
"""

from __future__ import annotations

import numpy as np
from qm import SimulationConfig, generate_qua_script
from qm.qua import align, declare, declare_output_stream, for_, program, save, stream_processing
from qm.qua import update_frequency
from qualang_tools.loops import from_array

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName

SIMULATE_ON_OPX = False
# Clock cycles (4 ns). One shot is a few microseconds, and the full sweep is
# 100 x 48 x 80 shots, so the simulation only covers the beginning of it.
SIMULATION_DURATION_CLK = 10_000

QUBIT_ID = "q1"
SENSOR_ID = "virtual_sensor_1"

N_AVG = 100
DURATIONS_CLK = np.arange(4, 100, 2)  # 1 clock cycle = 4 ns; QUA minimum is 4
DETUNINGS_HZ = np.arange(-20e6, 20e6, 0.5e6)


def build_machine():
    """Tutorial machine, plus integrated-voltage tracking and an ``operate`` point."""
    machine = build_tutorial_machine()

    # apply_compensation_pulse() needs the sequence to track the integrated voltage.
    machine.track_integrated_voltage = True
    machine.reset_voltage_sequence("main_qpu")

    qubit = machine.qubits[QUBIT_ID]
    qubit.add_point("operate", {qubit.quantum_dot.id: 0.12}, duration=200)
    return machine


def rabi_chevron_program(machine):
    qubit = machine.qubits[QUBIT_ID]
    sensor = machine.sensor_dots[SENSOR_ID]
    readout_length_ns = sensor.readout_resonator.operations["readout"].length
    drive_if = int(qubit.xy.intermediate_frequency)

    with program() as prog:
        n = declare(int)
        t = declare(int)
        df = declare(int)
        I_st = declare_output_stream()
        Q_st = declare_output_stream()

        with for_(n, 0, n < N_AVG, n + 1):
            with for_(*from_array(t, DURATIONS_CLK)):
                with for_(*from_array(df, DETUNINGS_HZ.astype(int))):
                    update_frequency(qubit.xy.name, drive_if + df)

                    qubit.step_to_point(VoltagePointName.INITIALIZE)
                    align()

                    # Hold the operate point for the drive (t cycles = 4t ns) plus a margin.
                    qubit.step_to_point("operate", duration=4 * t + 100)
                    qubit.x180(duration=t)
                    align()

                    # Hold the measure point for the whole readout pulse.
                    qubit.step_to_point(VoltagePointName.MEASURE, duration=readout_length_ns)
                    I, Q = sensor.macros["measure"]()
                    save(I, I_st)
                    save(Q, Q_st)
                    align()

                    qubit.voltage_sequence.apply_compensation_pulse()

        with stream_processing():
            shape = (len(DURATIONS_CLK), len(DETUNINGS_HZ))
            I_st.buffer(*shape).average().save("I")
            Q_st.buffer(*shape).average().save("Q")

    return prog


def simulate_on_opx(machine, prog):
    """Simulate on the OPX and plot the waveform report.

    Returns the waveform report, so it can be inspected after ``main()``.
    """
    qmm = machine.connect()
    job = qmm.simulate(machine.generate_config(), prog, SimulationConfig(duration=SIMULATION_DURATION_CLK))
    job.wait_until("Done", timeout=300)
    samples = job.get_simulated_samples()
    waveform_report = job.get_simulated_waveform_report()
    waveform_report.create_plot(samples, plot=True)
    return waveform_report


def main():
    machine = build_machine()
    prog = rabi_chevron_program(machine)
    config = machine.generate_config()

    qubit = machine.qubits[QUBIT_ID]
    print(f"Qubit {QUBIT_ID}: drive element {qubit.xy.name}, IF {qubit.xy.intermediate_frequency / 1e6:.1f} MHz")
    print(f"Readout via {SENSOR_ID}")
    print(f"Sweep: {len(DURATIONS_CLK)} durations x {len(DETUNINGS_HZ)} detunings, {N_AVG} averages")
    print(f"QUA config: {len(config['elements'])} elements")

    print("\nSerialized QUA program:")
    print(generate_qua_script(prog))

    waveform_report = simulate_on_opx(machine, prog) if SIMULATE_ON_OPX else None
    return machine, prog, waveform_report


if __name__ == "__main__":
    main()
