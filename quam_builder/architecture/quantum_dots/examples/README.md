# Quantum-dot examples

Hands-on scripts for a first quantum-dot QuAM. Read them in the order below. Each script does one job and prints what it built. None of them opens a connection unless you turn a flag on.

Two machines show up in this folder, and they are different on purpose:

- **The tutorial machine** comes from [`tutorial_machine.py`](tutorial_machine.py). It is small (2 dots, 1 sensor, 2 qubits on a shared drive) and already has default macros, pulses, and voltage points. The macro, voltage, and experiment scripts start here and change only the thing they teach.
- **The connectivity device** is built from scratch by the four scripts in [`connectivity/`](connectivity/). It is the machine you would describe for a real chip: 4 dots, 2 sensors, 4 qubits with their own drive lines, and a QDAC. All four scripts produce that same device, so you can compare the wirer path with the hand-built path.

```text
examples/
  tutorial_machine.py          the shared machine
  connectivity/                build your own machine, with or without the wirer
  macros/                      drive, readout, and custom operations
  voltages/                    virtual gates, ramps, and DC bias on a QDAC
  experiments/                 one full experiment on the tutorial machine
  quam_state/                  machines saved by the connectivity scripts
```

## 1. Start from the shared machine

[`tutorial_machine.py`](tutorial_machine.py) is a function, `build_tutorial_machine()`, not a standalone experiment. Call it and you get a `LossDiVincenzoQuam` with:

- 2 quantum dots (`virtual_dot_1`, `virtual_dot_2`) and 1 dot pair
- 1 sensor dot (`virtual_sensor_1`) with an RF readout resonator
- 2 qubits (`q1`, `q2`) on a shared MW drive, and 1 qubit pair (`q1_q2`)
- voltage points `initialize`, `measure`, and `empty`
- the default macros and pulses, already wired

Everything after the connectivity section assumes this machine exists. Open a later script, find `build_tutorial_machine()`, and read only what that script adds.

## 2. Build a machine

The scripts in [`connectivity/`](connectivity/) are the setup path. Use them when the tutorial machine is too small and you need to describe your own chip. Read the wirer scripts first, then the hand-built ones. They land on the same ports, the same QDAC channels, and the same qubit names.

The device, in every script:

- 4 plungers, 2 barriers, 2 sensor gates, each with an OPX output and a QDAC DC output
- QDAC triggers on plunger 1 and plunger 2 only (one QDAC-II unit has 4 trigger inputs)
- 2 sensor resonators, at 115 MHz and 233 MHz, readout 0.3 V for 2500 ns
- 4 qubits on individual MW drive lines, in two pairs

1. [`wiring_combined_example.py`](connectivity/wiring_combined_example.py) builds the whole device in one call. You declare dots, sensors, drive lines, and the QDAC. `allocate_wiring` picks free ports. `build_quam` returns a `LossDiVincenzoQuam` with macros already attached. This is the script to copy when you want one function that returns a finished machine.

2. [`wiring_two_stage_example.py`](connectivity/wiring_two_stage_example.py) is the same device split the way a lab usually works. Stage 1 builds the dots, barriers, sensors, and QDAC, and saves that `BaseQuamQD` under [`quam_state/wiring_two_stage`](quam_state/). Stage 2 loads the file, adds only the MW drive lines, and promotes it to qubits. The dot layer is not rebuilt.

3. [`manual_dots_example.py`](connectivity/manual_dots_example.py) builds that same dot layer with no wirer. Every `VoltageGate`, resonator port, and `QdacSpec` is written out, including the two triggered plungers. It saves a `BaseQuamQD` to [`quam_state/manual_dots`](quam_state/). Read this when you need to see what the wirer was generating.

4. [`manual_qubits_example.py`](connectivity/manual_qubits_example.py) loads that saved dot machine and registers `XYDriveMW` qubits and qubit pairs by hand. Run `manual_dots_example.py` first.

Real `machine.connect()` and `machine.connect_to_external_source()` calls are in the scripts as comments. Running a script prints the machine and, for the manual dot script, writes `quam_state/`.

## 3. Macros and pulses

With a machine in hand, these scripts show how an operation becomes QUA. Each one calls `build_tutorial_machine()`, adjusts macros or pulses, builds a short program, and prints it with `generate_qua_script`. Read them in this order.

1. [`macro_defaults_example.py`](macros/macro_defaults_example.py) uses the macros the machine already has. It sets a parameter on a wired macro and on its reference pulse, then calls `initialize`, `x180`, and `measure` from a QUA program. Start here. The later scripts are variations on this one.

2. [`macro_overrides_example.py`](macros/macro_overrides_example.py) replaces a default. A `TypeOverrideCatalog` changes every qubit of a type, `instance_overrides` changes one qubit, and `DISABLED` removes a macro. `macro.update(...)` writes a calibrated value onto an override that is already wired.

3. [`pulse_overrides_example.py`](macros/pulse_overrides_example.py) is about the waveform, not the macro. Each XY gate is registered for every family (gaussian, square, kaiser, hermite, drag). Editing the anchor pulse of a family updates the gates that reference it. `machine.set_pulse_family(...)` selects which family `x180` plays.

4. [`external_macro_package_example.py`](macros/external_macro_package_example.py) keeps lab macros outside this repository. [`external_macro_demo/`](macros/external_macro_demo/) is a tiny package that exports a catalog. The script passes that catalog to `wire_machine_macros`, which is how a lab catalog survives an upstream update.

The voltage-balanced catalog and the DCZ gate are documented in the [operations README](../operations/README.md). `macro_overrides_example.py` uses that DCZ macro and adds the exchange point it needs.

## 4. Voltages

A gate can carry an OPX pulse and a slow DC bias at the same time. The first two scripts are the OPX half. The third is the DC half.

1. [`virtual_gate_set_example.py`](voltages/virtual_gate_set_example.py) starts from the tutorial machine. The virtual gate set has a compensation layer (cross-talk between gates) and a detuning axis on the dot pair. The script resolves a voltage before and after cross-talk, then steps to the detuning point inside a QUA program.

2. [`voltage_modes_example.py`](voltages/voltage_modes_example.py) is how a later call treats the gates you do not name, and how a ramp differs from a step. With `keep_levels=True` an omitted gate holds its last voltage. With `keep_levels=False` an omitted gate goes to 0 V. The last program ramps to a voltage, ramps to a named point, and closes with `ramp_to_zero`. Set `SIMULATE_ON_OPX = True` to plot a waveform report for each program.

3. [`virtual_dc_set_example.py`](voltages/virtual_dc_set_example.py) is the DC half. A `VirtualDCSet` turns virtual voltages into offsets on an external DAC and checks each channel against its voltage limit. It does not play an OPX pulse. By default the DAC is an in-memory stand-in. Set `QUAM_QDAC=1` to talk to a QDAC-II through QCoDeS.

The connectivity scripts are where the two halves meet on one machine: each gate there has both an OPX output and a `QdacSpec`.

## 5. Run an experiment

[`rabi_chevron.py`](experiments/rabi_chevron.py) is the scripts above used together on the tutorial machine. It adds an `operate` voltage point, then sweeps drive duration and drive detuning:

`initialize` → `operate` with `qubit.x180(duration=t)` → sensor `measure` → compensation pulse

`x180` and `measure` are the default macros from section 3. The voltage points and the compensation pulse are the voltage sequence from section 4. The script prints the QUA program. Set `SIMULATE_ON_OPX = True` to simulate the start of the sweep on an OPX and plot the waveform report. The OPX address comes from `build_tutorial_machine()`.

## Where to go

| You want to… | Open |
| --- | --- |
| See the machine the later scripts share | [`tutorial_machine.py`](tutorial_machine.py) |
| Build a full machine in one call, including a QDAC | [`wiring_combined_example.py`](connectivity/wiring_combined_example.py) |
| Tune dots first, then add qubits | [`wiring_two_stage_example.py`](connectivity/wiring_two_stage_example.py) |
| Place every port and QDAC channel yourself | [`manual_dots_example.py`](connectivity/manual_dots_example.py), then [`manual_qubits_example.py`](connectivity/manual_qubits_example.py) |
| Call the macros a machine already has | [`macro_defaults_example.py`](macros/macro_defaults_example.py) |
| Replace or calibrate a macro | [`macro_overrides_example.py`](macros/macro_overrides_example.py) |
| Change the drive waveform or the pulse family | [`pulse_overrides_example.py`](macros/pulse_overrides_example.py) |
| Keep lab macros in their own package | [`external_macro_package_example.py`](macros/external_macro_package_example.py) |
| Compensate cross-talk and step along a detuning axis | [`virtual_gate_set_example.py`](voltages/virtual_gate_set_example.py) |
| Ramp a gate, hold its level, or drive omitted gates to 0 V | [`voltage_modes_example.py`](voltages/voltage_modes_example.py) |
| Set a QDAC bias from virtual voltages | [`virtual_dc_set_example.py`](voltages/virtual_dc_set_example.py) |
| See a full sweep, from voltage points through readout | [`rabi_chevron.py`](experiments/rabi_chevron.py) |

Longer explanations live next to the code they describe: [architecture README](../README.md), [builder README](../../builder/quantum_dots/README.md), [components README](../components/README.md), [operations README](../operations/README.md), [qpu README](../qpu/README.md), and [voltage-sequence README](../voltage_sequence/README.md).
