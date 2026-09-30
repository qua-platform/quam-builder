# Quantum-dot examples

Runnable scripts for the quantum-dot QuAM. Each script demonstrates one feature so a feature README can point here.

Scripts are grouped by feature. Shared pieces stay in this directory. Each group lives in its own folder.

## Shared starting point

[`tutorial_machine.py`](tutorial_machine.py) builds the machine other examples should start from. Call `build_tutorial_machine()`. It returns a `LossDiVincenzoQuam` with:

- 2 quantum dots (`virtual_dot_1`, `virtual_dot_2`) and 1 dot pair
- 1 sensor dot (`virtual_sensor_1`)
- 2 qubits (`q1`, `q2`) on a shared MW drive, and 1 qubit pair (`q1_q2`)
- voltage points `initialize`, `measure`, and `empty`
- default macros and pulses, wired by `build_quam`

Examples should call that function and then change only what the feature needs. [`quam_state/`](quam_state/) is a separate on-disk wiring snapshot used by the builder script. It is not this machine.

## Layout

```text
examples/
  README.md
  tutorial_machine.py          shared machine
  quam_state/                  on-disk wiring for the builder script
  macros/
    macro_defaults_example.py
    macro_overrides_example.py
    pulse_overrides_example.py
    external_macro_package_example.py
    external_macro_demo/       lab catalog imported by the external-macro example
  connectivity/
    wiring_example.py
    mwe_sensor_resonator_same_port.py
    quam_qd_example.py
    quam_qd_generator_example.py
    quam_ld_example.py
    quam_ld_generator_example.py
  voltages/
    virtual_gate_set_example.py
    virtual_dc_set_example.py
  experiments/
    rabi_chevron.py
    rabi_chevron_transport.py
```

## Feature map

| Example | Feature | Documented in | Starts from `build_tutorial_machine()` |
| --- | --- | --- | --- |
| [`tutorial_machine.py`](tutorial_machine.py) | Shared machine: combined wiring, default macros, voltage points | [architecture README](../README.md), [builder README](../../builder/quantum_dots/README.md) | defines it |
| [`wiring_example.py`](connectivity/wiring_example.py) | Two-stage build, combined build, and adding drive lines on the same instruments | [builder README](../../builder/quantum_dots/README.md) | no — writes [`quam_state/`](quam_state/) |
| [`mwe_sensor_resonator_same_port.py`](connectivity/mwe_sensor_resonator_same_port.py) | Allocating sensor resonators, sensor gates, plungers, and barriers under FEM port constraints | not linked from a feature README | no — connectivity only |
| [`quam_qd_example.py`](connectivity/quam_qd_example.py) | Manual channels, virtual gates, and `register_channel_elements` | [components README](../components/README.md), [builder README](../../builder/quantum_dots/README.md) | no |
| [`quam_qd_generator_example.py`](connectivity/quam_qd_generator_example.py) | Same manual assembly, then `register_qubit` | hub table calls this the builder-first path | no |
| [`quam_ld_example.py`](connectivity/quam_ld_example.py) | Load a saved machine and register Loss-DiVincenzo qubits | [qpu README](../qpu/README.md) | no — `LossDiVincenzoQuam.load()` |
| [`quam_ld_generator_example.py`](connectivity/quam_ld_generator_example.py) | Load a state directory and register MW-FEM qubits | [qpu README](../qpu/README.md) | no — `QUAM_STATE_PATH` |
| [`macro_defaults_example.py`](macros/macro_defaults_example.py) | Parameterize built-in macros and run them in a QUA program | [operations README](../operations/README.md) | yes |
| [`macro_overrides_example.py`](macros/macro_overrides_example.py) | `TypeOverrideCatalog`, `instance_overrides`, `DISABLED`, and calibrating an override with `update(...)` | [operations README](../operations/README.md) | yes |
| [`pulse_overrides_example.py`](macros/pulse_overrides_example.py) | Default XY pulse, anchor edits, and switching pulse family | [operations README](../operations/README.md), [components README](../components/README.md) | yes |
| [`external_macro_package_example.py`](macros/external_macro_package_example.py) | Lab-owned catalog in [`external_macro_demo/`](macros/external_macro_demo/) | [operations README](../operations/README.md) | yes |
| [`virtual_gate_set_example.py`](voltages/virtual_gate_set_example.py) | Compensation layer, cross-talk, detuning, and a QUA step | [voltage-sequence README](../voltage_sequence/README.md) | yes |
| [`virtual_dc_set_example.py`](voltages/virtual_dc_set_example.py) | `VirtualDCSet` with an external DAC offset, no OPX program | [voltage-sequence README](../voltage_sequence/README.md), [components README](../components/README.md) | no |
| [`rabi_chevron.py`](experiments/rabi_chevron.py) | Manual machine, custom macros, resonator readout, cloud simulation | [components README](../components/README.md), [qpu README](../qpu/README.md) | no |
| [`rabi_chevron_transport.py`](experiments/rabi_chevron_transport.py) | Same experiment; filename says transport readout | [components README](../components/README.md) | no |

## Where to point readers

Use one script per feature:

| Question | Open |
| --- | --- |
| What machine do the examples share? | [`tutorial_machine.py`](tutorial_machine.py) |
| How do I build from connectivity? | [`wiring_example.py`](connectivity/wiring_example.py) |
| How do port constraints interact? | [`mwe_sensor_resonator_same_port.py`](connectivity/mwe_sensor_resonator_same_port.py) |
| How do I register dots by hand? | [`quam_qd_example.py`](connectivity/quam_qd_example.py) |
| How do I attach qubits to a loaded machine? | [`quam_ld_example.py`](connectivity/quam_ld_example.py) |
| How do default macros work? | [`macro_defaults_example.py`](macros/macro_defaults_example.py) |
| How do I override a macro, then calibrate it? | [`macro_overrides_example.py`](macros/macro_overrides_example.py) |
| How do I change the XY pulse or switch pulse family? | [`pulse_overrides_example.py`](macros/pulse_overrides_example.py) |
| How do I keep lab macros outside this repo? | [`external_macro_package_example.py`](macros/external_macro_package_example.py) |
| How do virtual layers resolve voltages? | [`virtual_gate_set_example.py`](voltages/virtual_gate_set_example.py) |
| How do I set DC through an external DAC? | [`virtual_dc_set_example.py`](voltages/virtual_dc_set_example.py) |
| How does a resonator readout experiment look? | [`rabi_chevron.py`](experiments/rabi_chevron.py) |

## Inventory notes

These showed up while mapping files to features. Later passes fix them.

- The [architecture README](../README.md) examples table wraps several entries in backticks, so those rows are not links. The same page and the [operations README](../operations/README.md) link to `qm_example.py`, which is not in this folder.
- The hub describes [`quam_qd_generator_example.py`](connectivity/quam_qd_generator_example.py) as the builder-first path. The script constructs `LossDiVincenzoQuam()` and `VoltageGate`s by hand, in the same style as [`quam_qd_example.py`](connectivity/quam_qd_example.py).
- [`quam_ld_generator_example.py`](connectivity/quam_ld_generator_example.py) defaults `QUAM_STATE_PATH` to a personal directory and exits when that directory is missing.
- [`quam_ld_example.py`](connectivity/quam_ld_example.py) calls `LossDiVincenzoQuam.load()` with no path.
- The hub links a `virtual_gates/` guide. That folder is not in `architecture/quantum_dots/`. [`virtual_gate_set_example.py`](voltages/virtual_gate_set_example.py) is the hands-on page for virtual layers.
- [`rabi_chevron_transport.py`](experiments/rabi_chevron_transport.py) is the transport example in the components README. Its docstring and channel setup describe RF reflectometry through `ReadoutResonatorSingle`, and the setup function's return value is named `transport_readout`.
- `full_workflow_example.py` repeated `macro_defaults_example.py`, `macro_overrides_example.py`, and `pulse_overrides_example.py` in one file. Its only unique step, `machine.set_pulse_family("kaiser")`, moved into `pulse_overrides_example.py`. The file was removed.
- `voltage_balanced_macros_example.py` and `dcz_macro_example.py` simulated balanced macros and the DCZ gate on QM SaaS. The macro examples stop once the QUA program is built. `VoltageBalancedMacroCatalog` stays documented in the [operations README](../operations/README.md). Both files were removed.
