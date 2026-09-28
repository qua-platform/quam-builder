# Quantum-dot examples

Runnable scripts for the quantum-dot QuAM. Each script demonstrates one feature so a feature README can point here.

Scripts currently live side by side in this directory. The sections below are the directory structure: shared pieces first, then one group per feature. A later change will move each group into its own folder and update the links.

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
  external_macro_demo/         lab catalog imported by the external-macro example
  wiring_example.py            building a machine
  mwe_sensor_resonator_same_port.py
  quam_qd_example.py           manual assembly
  quam_qd_generator_example.py
  quam_ld_example.py
  quam_ld_generator_example.py
  macro_defaults_example.py    macros and pulses
  macro_overrides_example.py
  pulse_overrides_example.py
  external_macro_package_example.py
  full_workflow_example.py
  virtual_gate_set_example.py  voltages
  virtual_dc_set_example.py
  voltage_balanced_macros_example.py
  dcz_macro_example.py         experiments
  rabi_chevron.py
  rabi_chevron_transport.py
```

## Feature map

| Example | Feature | Documented in | Starts from `build_tutorial_machine()` |
| --- | --- | --- | --- |
| [`tutorial_machine.py`](tutorial_machine.py) | Shared machine: combined wiring, default macros, voltage points | [architecture README](../README.md), [builder README](../../builder/quantum_dots/README.md) | defines it |
| [`wiring_example.py`](wiring_example.py) | Two-stage build, combined build, and adding drive lines on the same instruments | [builder README](../../builder/quantum_dots/README.md) | no — writes [`quam_state/`](quam_state/) |
| [`mwe_sensor_resonator_same_port.py`](mwe_sensor_resonator_same_port.py) | Allocating sensor resonators, sensor gates, plungers, and barriers under FEM port constraints | not linked from a feature README | no — connectivity only |
| [`quam_qd_example.py`](quam_qd_example.py) | Manual channels, virtual gates, and `register_channel_elements` | [components README](../components/README.md), [builder README](../../builder/quantum_dots/README.md) | no |
| [`quam_qd_generator_example.py`](quam_qd_generator_example.py) | Same manual assembly, then `register_qubit` | hub table calls this the builder-first path | no |
| [`quam_ld_example.py`](quam_ld_example.py) | Load a saved machine and register Loss-DiVincenzo qubits | [qpu README](../qpu/README.md) | no — `LossDiVincenzoQuam.load()` |
| [`quam_ld_generator_example.py`](quam_ld_generator_example.py) | Load a state directory and register MW-FEM qubits | [qpu README](../qpu/README.md) | no — `QUAM_STATE_PATH` |
| [`macro_defaults_example.py`](macro_defaults_example.py) | Parameterize built-in macros and run them in a QUA program | [operations README](../operations/README.md) | yes |
| [`macro_overrides_example.py`](macro_overrides_example.py) | `TypeOverrideCatalog`, `instance_overrides`, and `DISABLED` | [operations README](../operations/README.md) | yes |
| [`pulse_overrides_example.py`](pulse_overrides_example.py) | Default XY pulse and editing it on the channel | [operations README](../operations/README.md), [components README](../components/README.md) | yes |
| [`external_macro_package_example.py`](external_macro_package_example.py) | Lab-owned catalog in [`external_macro_demo/`](external_macro_demo/) | [operations README](../operations/README.md) | yes |
| [`full_workflow_example.py`](full_workflow_example.py) | Capstone: pulse edits, pulse-family switch, type and instance overrides | [operations README](../operations/README.md), [components README](../components/README.md) | yes |
| [`virtual_gate_set_example.py`](virtual_gate_set_example.py) | Compensation layer, cross-talk, detuning, and a QUA step | hub table only | yes |
| [`virtual_dc_set_example.py`](virtual_dc_set_example.py) | `VirtualDCSet` with an external DAC offset, no OPX program | [voltage-sequence README](../voltage_sequence/README.md), [components README](../components/README.md) | no |
| [`voltage_balanced_macros_example.py`](voltage_balanced_macros_example.py) | AC-coupled compensation, chained macros, cloud simulation | [operations README](../operations/README.md) | yes |
| [`dcz_macro_example.py`](dcz_macro_example.py) | Dynamically decoupled CZ, cloud simulation | [operations README](../operations/README.md) | yes |
| [`rabi_chevron.py`](rabi_chevron.py) | Manual machine, custom macros, resonator readout, cloud simulation | [components README](../components/README.md), [qpu README](../qpu/README.md) | no |
| [`rabi_chevron_transport.py`](rabi_chevron_transport.py) | Same experiment; filename says transport readout | [components README](../components/README.md) | no |

## Where to point readers

Use one script per feature:

| Question | Open |
| --- | --- |
| What machine do the examples share? | [`tutorial_machine.py`](tutorial_machine.py) |
| How do I build from connectivity? | [`wiring_example.py`](wiring_example.py) |
| How do port constraints interact? | [`mwe_sensor_resonator_same_port.py`](mwe_sensor_resonator_same_port.py) |
| How do I register dots by hand? | [`quam_qd_example.py`](quam_qd_example.py) |
| How do I attach qubits to a loaded machine? | [`quam_ld_example.py`](quam_ld_example.py) |
| How do default macros work? | [`macro_defaults_example.py`](macro_defaults_example.py) |
| How do I override a macro? | [`macro_overrides_example.py`](macro_overrides_example.py) |
| How do I change the XY pulse? | [`pulse_overrides_example.py`](pulse_overrides_example.py) |
| How do I keep lab macros outside this repo? | [`external_macro_package_example.py`](external_macro_package_example.py) |
| How do the macro pieces fit together? | [`full_workflow_example.py`](full_workflow_example.py) |
| How do virtual layers resolve voltages? | [`virtual_gate_set_example.py`](virtual_gate_set_example.py) |
| How do I set DC through an external DAC? | [`virtual_dc_set_example.py`](virtual_dc_set_example.py) |
| How does voltage balancing work? | [`voltage_balanced_macros_example.py`](voltage_balanced_macros_example.py) |
| How does the DCZ macro run? | [`dcz_macro_example.py`](dcz_macro_example.py) |
| How does a resonator readout experiment look? | [`rabi_chevron.py`](rabi_chevron.py) |

## Inventory notes

These showed up while mapping files to features. Later passes fix them.

- The [architecture README](../README.md) examples table wraps several entries in backticks, so those rows are not links. The same page and the [operations README](../operations/README.md) link to `qm_example.py`, which is not in this folder.
- The hub describes [`quam_qd_generator_example.py`](quam_qd_generator_example.py) as the builder-first path. The script constructs `LossDiVincenzoQuam()` and `VoltageGate`s by hand, in the same style as [`quam_qd_example.py`](quam_qd_example.py).
- [`quam_ld_generator_example.py`](quam_ld_generator_example.py) defaults `QUAM_STATE_PATH` to a personal directory and exits when that directory is missing.
- [`quam_ld_example.py`](quam_ld_example.py) calls `LossDiVincenzoQuam.load()` with no path.
- The hub links a `virtual_gates/` guide. That folder is not in `architecture/quantum_dots/`. [`virtual_gate_set_example.py`](virtual_gate_set_example.py) is the hands-on page for virtual layers.
- [`rabi_chevron_transport.py`](rabi_chevron_transport.py) is the transport example in the components README. Its docstring and channel setup describe RF reflectometry through `ReadoutResonatorSingle`, and the setup function's return value is named `transport_readout`.
- [`full_workflow_example.py`](full_workflow_example.py) repeats the default-macro, override, and pulse examples. Keep it as the capstone and point feature docs at the narrower scripts.
