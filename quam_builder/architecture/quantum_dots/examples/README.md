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

Macro, voltage, and experiment scripts should call that function and then change only what the feature needs. The connectivity scripts build a machine from scratch; that is the setup they teach. [`quam_state/`](quam_state/) holds the snapshots written by [`wiring_two_stage_example.py`](connectivity/wiring_two_stage_example.py) and [`manual_dots_example.py`](connectivity/manual_dots_example.py).

## Layout

```text
examples/
  README.md
  tutorial_machine.py          shared machine
  quam_state/                  saved machines from the connectivity scripts
  macros/
    macro_defaults_example.py
    macro_overrides_example.py
    pulse_overrides_example.py
    external_macro_package_example.py
    external_macro_demo/       lab catalog imported by the external-macro example
  connectivity/
    wiring_combined_example.py
    wiring_two_stage_example.py
    manual_dots_example.py
    manual_qubits_example.py
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
| [`wiring_combined_example.py`](connectivity/wiring_combined_example.py) | Wirer, one stage: dots, sensors, QDAC, and MW qubits | [builder README](../../builder/quantum_dots/README.md) | no |
| [`wiring_two_stage_example.py`](connectivity/wiring_two_stage_example.py) | Save a dot machine, reload it, then add drive lines and qubits | [builder README](../../builder/quantum_dots/README.md) | no — writes [`quam_state/wiring_two_stage`](quam_state/) |
| [`manual_dots_example.py`](connectivity/manual_dots_example.py) | Hand-placed ports and `QdacSpec`, same dot machine | [components README](../components/README.md), [builder README](../../builder/quantum_dots/README.md) | no — writes [`quam_state/manual_dots`](quam_state/) |
| [`manual_qubits_example.py`](connectivity/manual_qubits_example.py) | Load that state and register `XYDriveMW` qubits | [qpu README](../qpu/README.md) | no — loads `manual_dots` |
| [`macro_defaults_example.py`](macros/macro_defaults_example.py) | Parameterize built-in macros and run them in a QUA program | [operations README](../operations/README.md) | yes |
| [`macro_overrides_example.py`](macros/macro_overrides_example.py) | `TypeOverrideCatalog`, `instance_overrides`, `DISABLED`, and calibrating an override with `update(...)` | [operations README](../operations/README.md) | yes |
| [`pulse_overrides_example.py`](macros/pulse_overrides_example.py) | Default XY pulse, anchor edits, and switching pulse family | [operations README](../operations/README.md), [components README](../components/README.md) | yes |
| [`external_macro_package_example.py`](macros/external_macro_package_example.py) | Lab-owned catalog in [`external_macro_demo/`](macros/external_macro_demo/) | [operations README](../operations/README.md) | yes |
| [`virtual_gate_set_example.py`](voltages/virtual_gate_set_example.py) | Compensation layer, cross-talk, detuning, and a QUA step | [voltage-sequence README](../voltage_sequence/README.md) | yes |
| [`virtual_dc_set_example.py`](voltages/virtual_dc_set_example.py) | `VirtualDCSet` DC offsets and voltage limits for an external DAC (the DC half of a QDAC + OPX experiment) | [voltage-sequence README](../voltage_sequence/README.md), [components README](../components/README.md) | no |
| [`rabi_chevron.py`](experiments/rabi_chevron.py) | Manual machine, custom macros, resonator readout, cloud simulation | [components README](../components/README.md), [qpu README](../qpu/README.md) | no |
| [`rabi_chevron_transport.py`](experiments/rabi_chevron_transport.py) | Same experiment; filename says transport readout | [components README](../components/README.md) | no |

## Where to point readers

Use one script per feature:

| Question | Open |
| --- | --- |
| What machine do the examples share? | [`tutorial_machine.py`](tutorial_machine.py) |
| How do I build a machine from connectivity, including a QDAC? | [`wiring_combined_example.py`](connectivity/wiring_combined_example.py) |
| How do I calibrate dots first, then add qubits? | [`wiring_two_stage_example.py`](connectivity/wiring_two_stage_example.py) |
| How do I place ports and QDAC channels by hand? | [`manual_dots_example.py`](connectivity/manual_dots_example.py) |
| How do I add qubits to a saved dot machine by hand? | [`manual_qubits_example.py`](connectivity/manual_qubits_example.py) |
| How do default macros work? | [`macro_defaults_example.py`](macros/macro_defaults_example.py) |
| How do I override a macro, then calibrate it? | [`macro_overrides_example.py`](macros/macro_overrides_example.py) |
| How do I change the XY pulse or switch pulse family? | [`pulse_overrides_example.py`](macros/pulse_overrides_example.py) |
| How do I keep lab macros outside this repo? | [`external_macro_package_example.py`](macros/external_macro_package_example.py) |
| How do virtual layers resolve voltages? | [`virtual_gate_set_example.py`](voltages/virtual_gate_set_example.py) |
| How do I set a QDAC (or other external DAC) bias alongside the OPX? | [`virtual_dc_set_example.py`](voltages/virtual_dc_set_example.py) |
| How does a resonator readout experiment look? | [`rabi_chevron.py`](experiments/rabi_chevron.py) |

## Inventory notes

These showed up while mapping files to features. Later passes fix them.

- The [architecture README](../README.md) examples table wraps several entries in backticks, so those rows are not links. The same page and the [operations README](../operations/README.md) link to `qm_example.py`, which is not in this folder.
- `wiring_example.py`, `mwe_sensor_resonator_same_port.py`, `quam_qd_example.py`, `quam_qd_generator_example.py`, `quam_ld_example.py`, and `quam_ld_generator_example.py` were removed. The four scripts in [`connectivity/`](connectivity/) are the machine-setup path: wirer combined, wirer two-stage, manual dots, manual qubits.
- The hub links a `virtual_gates/` guide. That folder is not in `architecture/quantum_dots/`. [`virtual_gate_set_example.py`](voltages/virtual_gate_set_example.py) is the hands-on page for virtual layers.
- [`rabi_chevron_transport.py`](experiments/rabi_chevron_transport.py) is the transport example in the components README. Its docstring and channel setup describe RF reflectometry through `ReadoutResonatorSingle`, and the setup function's return value is named `transport_readout`.
- `full_workflow_example.py` repeated `macro_defaults_example.py`, `macro_overrides_example.py`, and `pulse_overrides_example.py` in one file. Its only unique step, `machine.set_pulse_family("kaiser")`, moved into `pulse_overrides_example.py`. The file was removed.
- `voltage_balanced_macros_example.py` and `dcz_macro_example.py` simulated balanced macros and the DCZ gate on QM SaaS. The macro examples stop once the QUA program is built. `VoltageBalancedMacroCatalog` stays documented in the [operations README](../operations/README.md). Both files were removed.
