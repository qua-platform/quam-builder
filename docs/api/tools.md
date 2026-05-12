# Tools

The `quam_builder.tools` package provides cross-cutting utilities used across qubit architectures.

## Power Tools

Helpers for setting and retrieving output power on `MWChannel` and `IQChannel` components.

::: quam_builder.tools.power_tools
    options:
      heading_level: 3

---

## QUA Tools

Helpers for working with QUA types, durations, and runtime values.

::: quam_builder.tools.qua_tools
    options:
      heading_level: 3

---

## Voltage Sequence

State-tracking voltage sequencer used by `GateSet` / `VirtualGateSet`.

::: quam_builder.tools.voltage_sequence.voltage_sequence
    options:
      heading_level: 3

::: quam_builder.tools.voltage_sequence.sequence_state_tracker
    options:
      heading_level: 3

::: quam_builder.tools.voltage_sequence.exceptions
    options:
      heading_level: 3

---

## Macros

Shared QuAM macros (`AlignMacro`, measurement helpers, point macros).

::: quam_builder.tools.macros.composable_macros
    options:
      heading_level: 3

::: quam_builder.tools.macros.default_macros
    options:
      heading_level: 3

::: quam_builder.tools.macros.measure_macros
    options:
      heading_level: 3

::: quam_builder.tools.macros.point_macros
    options:
      heading_level: 3
