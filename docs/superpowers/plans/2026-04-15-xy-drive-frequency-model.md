# XY Drive Frequency Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign XY drive frequency management so `LDQubit.larmor_frequency` is the single source of truth for RF, with IF always derived via QuAM references.

**Architecture:** Pure QuAM reference wiring. `xy.RF_frequency` references `qubit.larmor_frequency`, `xy.intermediate_frequency` references `inferred_intermediate_frequency` (RF - LO). No sync logic, no dual state. IF bounds validation on write.

**Tech Stack:** Python dataclasses, quam-sdk (QuAM references, `@quam_dataclass`), pytest, QUA (qm.qua)

**Spec:** `docs/superpowers/specs/2026-04-15-xy-drive-frequency-model-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `quam_builder/architecture/quantum_dots/components/xy_drive.py` | Modify | Add IF validation to `XYDriveBase`, override `RF_frequency` on IQ/MW |
| `quam_builder/architecture/quantum_dots/qubit/ld_qubit.py` | Modify | Remove `set_xy_frequency`, add `__setattr__` validation, add convenience properties |
| `quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py` | Modify | Rewire `XYDriveMacro.update()`, remove `recenter_LO` |
| `tests/architecture/quantum_dots/components/test_xy_drive.py` | Modify | Add frequency reference and validation tests |
| `tests/architecture/quantum_dots/components/test_ld_qubit.py` | Modify | Add frequency property and validation tests |
| `tests/architecture/quantum_dots/test_xy_drive_macro_frequency.py` | Create | Test macro frequency update/apply rewiring |
| `quam_builder/architecture/quantum_dots/examples/quam_ld_example.py` | Modify | Update to new frequency API |
| `tutorials/calibration_workflow.ipynb` | Modify | Update frequency cells to new API |

---

### Task 1: Add IF validation to `XYDriveBase`

**Files:**
- Modify: `quam_builder/architecture/quantum_dots/components/xy_drive.py`
- Test: `tests/architecture/quantum_dots/components/test_xy_drive.py`

- [ ] **Step 1: Write failing tests for `validate_intermediate_frequency`**

Add to `tests/architecture/quantum_dots/components/test_xy_drive.py`:

```python
import pytest
from quam.components.ports import MWFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import XYDriveMW


class TestXYDriveValidation:
    def _make_mw_drive(self, upconverter_freq: int, if_freq: int) -> XYDriveMW:
        return XYDriveMW(
            id="xy_mw",
            opx_output=MWFEMAnalogOutputPort(
                controller_id="con1",
                fem_id=1,
                port_id=1,
                band=2,
                upconverter_frequency=upconverter_freq,
                full_scale_power_dbm=10,
            ),
            intermediate_frequency=if_freq,
        )

    def test_valid_if_passes(self):
        drive = self._make_mw_drive(int(5e9), int(100e6))
        drive.validate_intermediate_frequency()

    def test_if_exceeds_400mhz_raises(self):
        drive = self._make_mw_drive(int(5e9), int(500e6))
        with pytest.raises(ValueError, match="exceeds"):
            drive.validate_intermediate_frequency()

    def test_negative_if_within_limit_passes(self):
        drive = self._make_mw_drive(int(5e9), int(-200e6))
        drive.validate_intermediate_frequency()

    def test_negative_if_exceeds_limit_raises(self):
        drive = self._make_mw_drive(int(5e9), int(-500e6))
        with pytest.raises(ValueError, match="exceeds"):
            drive.validate_intermediate_frequency()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/architecture/quantum_dots/components/test_xy_drive.py::TestXYDriveValidation -v`
Expected: FAIL with `AttributeError: ... has no attribute 'validate_intermediate_frequency'`

- [ ] **Step 3: Implement `validate_intermediate_frequency` on `XYDriveBase`**

In `quam_builder/architecture/quantum_dots/components/xy_drive.py`, add to imports:

```python
from typing import ClassVar, Dict, Optional
```

Then add to `XYDriveBase`:

```python
@quam_dataclass
class XYDriveBase:
    """
    QUAM component for a XY drive line.
    """

    IF_LIMIT: ClassVar[float] = 400e6

    def validate_intermediate_frequency(self) -> None:
        """Raise ValueError if |IF| exceeds the OPX +-400 MHz band."""
        if_freq = self.intermediate_frequency
        if abs(if_freq) > self.IF_LIMIT:
            name = getattr(self, "name", self.__class__.__name__)
            raise ValueError(
                f"Intermediate frequency {if_freq / 1e6:.2f} MHz exceeds "
                f"\u00b1{self.IF_LIMIT / 1e6:.0f} MHz on '{name}'. "
                f"Adjust LO_frequency or larmor_frequency."
            )

    @staticmethod
    def calculate_voltage_scaling_factor(fixed_power_dBm: float, target_power_dBm: float):
        # ... existing code unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/architecture/quantum_dots/components/test_xy_drive.py::TestXYDriveValidation -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add quam_builder/architecture/quantum_dots/components/xy_drive.py tests/architecture/quantum_dots/components/test_xy_drive.py
git commit -m "feat(xy-drive): add IF bounds validation to XYDriveBase"
```

---

### Task 2: Override `RF_frequency` default on `XYDriveIQ` and `XYDriveMW`

**Files:**
- Modify: `quam_builder/architecture/quantum_dots/components/xy_drive.py`
- Test: `tests/architecture/quantum_dots/components/test_xy_drive.py`

- [ ] **Step 1: Write failing tests for RF_frequency reference**

Add to `tests/architecture/quantum_dots/components/test_xy_drive.py`:

```python
from quam.components.ports import LFFEMAnalogOutputPort, MWFEMAnalogOutputPort
from quam.components import pulses, StickyChannelAddon
from quam.components.hardware import FrequencyConverter, LocalOscillator

from quam_builder.architecture.quantum_dots.components import (
    XYDriveIQ,
    XYDriveMW,
    QuantumDot,
    VoltageGate,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


class TestXYDriveRFReference:
    def test_mw_rf_frequency_references_larmor(self):
        """XYDriveMW.RF_frequency should resolve to qubit.larmor_frequency."""
        machine = LossDiVincenzoQuam()

        gate = VoltageGate(
            id="plunger_1",
            opx_output=LFFEMAnalogOutputPort("con1", 2, port_id=1),
            sticky=StickyChannelAddon(duration=16, digital=False),
        )
        machine.create_virtual_gate_set(
            virtual_channel_mapping={"vdot1": gate},
            gate_set_id="main",
        )
        machine.register_channel_elements(
            plunger_channels=[gate],
            barrier_channels=[],
            sensor_resonator_mappings={},
        )
        machine.register_qubit(quantum_dot_id="vdot1", qubit_name="Q1")

        qubit = machine.qubits["Q1"]
        qubit.larmor_frequency = 5.1e9

        xy = XYDriveMW(
            id="xy_mw",
            opx_output=MWFEMAnalogOutputPort(
                controller_id="con1",
                fem_id=1,
                port_id=1,
                band=2,
                upconverter_frequency=int(5e9),
                full_scale_power_dbm=10,
            ),
        )
        qubit.xy = xy

        assert xy.RF_frequency == 5.1e9
        assert xy.intermediate_frequency == pytest.approx(0.1e9)

    def test_mw_rf_tracks_larmor_change(self):
        """Changing larmor_frequency should be reflected in xy.RF_frequency."""
        machine = LossDiVincenzoQuam()

        gate = VoltageGate(
            id="plunger_1",
            opx_output=LFFEMAnalogOutputPort("con1", 2, port_id=1),
            sticky=StickyChannelAddon(duration=16, digital=False),
        )
        machine.create_virtual_gate_set(
            virtual_channel_mapping={"vdot1": gate},
            gate_set_id="main",
        )
        machine.register_channel_elements(
            plunger_channels=[gate],
            barrier_channels=[],
            sensor_resonator_mappings={},
        )
        machine.register_qubit(quantum_dot_id="vdot1", qubit_name="Q1")

        qubit = machine.qubits["Q1"]
        qubit.larmor_frequency = 5.1e9

        xy = XYDriveMW(
            id="xy_mw",
            opx_output=MWFEMAnalogOutputPort(
                controller_id="con1",
                fem_id=1,
                port_id=1,
                band=2,
                upconverter_frequency=int(5e9),
                full_scale_power_dbm=10,
            ),
        )
        qubit.xy = xy

        qubit.larmor_frequency = 5.2e9
        assert xy.RF_frequency == 5.2e9
        assert xy.intermediate_frequency == pytest.approx(0.2e9)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/architecture/quantum_dots/components/test_xy_drive.py::TestXYDriveRFReference -v`
Expected: FAIL — `RF_frequency` still defaults to `#./inferred_RF_frequency` (not `#../larmor_frequency`)

- [ ] **Step 3: Override RF_frequency on XYDriveIQ and XYDriveMW**

In `quam_builder/architecture/quantum_dots/components/xy_drive.py`:

For `XYDriveIQ` (line 64), add `@quam_dataclass` decorator (currently missing — `XYDriveMW` already has it) and `RF_frequency` field:

```python
@quam_dataclass
class XYDriveIQ(IQChannel, XYDriveBase):
    """
    QUAM component for a XY drive line through an IQ channel.
    """

    RF_frequency: float = "#../larmor_frequency"
    intermediate_frequency: int = "#./inferred_intermediate_frequency"
```

For `XYDriveMW` (line 126), add `RF_frequency` field:

```python
@quam_dataclass
class XYDriveMW(MWChannel, XYDriveBase):
    RF_frequency: float = "#../larmor_frequency"
    intermediate_frequency: float = "#./inferred_intermediate_frequency"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/architecture/quantum_dots/components/test_xy_drive.py::TestXYDriveRFReference -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full existing test suite to check for regressions**

Run: `pytest tests/architecture/quantum_dots/components/test_xy_drive.py -v`
Expected: All tests pass. The `TestXYDriveMWCreation` tests explicitly pass `intermediate_frequency=int(100e6)` which overrides the reference default, so they should still work.

- [ ] **Step 6: Commit**

```bash
git add quam_builder/architecture/quantum_dots/components/xy_drive.py tests/architecture/quantum_dots/components/test_xy_drive.py
git commit -m "feat(xy-drive): wire RF_frequency to qubit.larmor_frequency via QuAM reference"
```

---

### Task 3: Update `LDQubit` — remove `set_xy_frequency`, add validation and properties

**Files:**
- Modify: `quam_builder/architecture/quantum_dots/qubit/ld_qubit.py`
- Test: `tests/architecture/quantum_dots/components/test_ld_qubit.py`

- [ ] **Step 1: Write failing tests for new frequency behaviour**

Add to `tests/architecture/quantum_dots/components/test_ld_qubit.py`:

```python
import pytest
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort, MWFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDriveMW
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


def _make_qubit_with_xy():
    """Helper: build a minimal machine with one qubit wired to an XYDriveMW."""
    machine = LossDiVincenzoQuam()

    gate = VoltageGate(
        id="plunger_1",
        opx_output=LFFEMAnalogOutputPort("con1", 2, port_id=1),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    machine.create_virtual_gate_set(
        virtual_channel_mapping={"vdot1": gate},
        gate_set_id="main",
    )
    machine.register_channel_elements(
        plunger_channels=[gate],
        barrier_channels=[],
        sensor_resonator_mappings={},
    )
    machine.register_qubit(quantum_dot_id="vdot1", qubit_name="Q1")

    qubit = machine.qubits["Q1"]
    qubit.larmor_frequency = 5.1e9

    xy = XYDriveMW(
        id="xy_mw",
        opx_output=MWFEMAnalogOutputPort(
            controller_id="con1",
            fem_id=1,
            port_id=1,
            band=2,
            upconverter_frequency=int(5e9),
            full_scale_power_dbm=10,
        ),
    )
    qubit.xy = xy
    return machine, qubit


class TestLDQubitDriveFrequency:
    def test_drive_IF_property(self):
        _, qubit = _make_qubit_with_xy()
        assert qubit.drive_IF == pytest.approx(0.1e9)

    def test_drive_LO_property(self):
        _, qubit = _make_qubit_with_xy()
        assert qubit.drive_LO == int(5e9)

    def test_larmor_frequency_propagates_to_IF(self):
        _, qubit = _make_qubit_with_xy()
        qubit.larmor_frequency = 5.3e9
        assert qubit.drive_IF == pytest.approx(0.3e9)

    def test_if_validation_rejects_over_400mhz(self):
        _, qubit = _make_qubit_with_xy()
        with pytest.raises(ValueError, match="exceeds"):
            qubit.larmor_frequency = 6e9  # IF = 1 GHz, over 400 MHz

    def test_if_validation_allows_within_limit(self):
        _, qubit = _make_qubit_with_xy()
        qubit.larmor_frequency = 5.3e9  # IF = 300 MHz, within limit

    def test_set_xy_frequency_removed(self):
        _, qubit = _make_qubit_with_xy()
        assert not hasattr(qubit, "set_xy_frequency")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/architecture/quantum_dots/components/test_ld_qubit.py::TestLDQubitDriveFrequency -v`
Expected: FAIL — `drive_IF`, `drive_LO` not defined; `set_xy_frequency` still exists

- [ ] **Step 3: Implement LDQubit changes**

In `quam_builder/architecture/quantum_dots/qubit/ld_qubit.py`:

**Remove** the `set_xy_frequency` method (lines 170–192).

**Extend `__setattr__`** — replace the existing `__setattr__` (lines 208–212) with:

```python
def __setattr__(self, name, value):
    if name == "preferred_readout_quantum_dot" and value is not None:
        if hasattr(self, "quantum_dot") and not isinstance(self.quantum_dot, str):
            self._validate_readout_quantum_dot(value)
    if name == "larmor_frequency" and value is not None:
        if hasattr(self, "xy") and self.xy is not None:
            try:
                lo = self.xy.LO_frequency
                if isinstance(lo, (int, float)) and isinstance(value, (int, float)):
                    if_freq = value - lo
                    if abs(if_freq) > 400e6:
                        raise ValueError(
                            f"Intermediate frequency {if_freq / 1e6:.2f} MHz "
                            f"exceeds \u00b1400 MHz. Adjust LO_frequency or "
                            f"larmor_frequency."
                        )
            except AttributeError:
                pass
    super().__setattr__(name, value)
```

**Add convenience properties** after the `voltage_sequence` property:

```python
@property
def drive_IF(self) -> float:
    """Current intermediate frequency of the XY drive (derived, read-only)."""
    return self.xy.intermediate_frequency

@property
def drive_LO(self) -> float:
    """Current LO frequency of the XY drive."""
    return self.xy.LO_frequency
```

**Remove unused imports** that were only used by `set_xy_frequency`:
- Remove `from qm import logger` if no other usage
- Remove `from qm import QuantumMachine` if no other usage (check `calibrate_octave` — it uses `QuantumMachine` in its signature, so keep it)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/architecture/quantum_dots/components/test_ld_qubit.py -v`
Expected: All tests pass (existing + new)

- [ ] **Step 5: Commit**

```bash
git add quam_builder/architecture/quantum_dots/qubit/ld_qubit.py tests/architecture/quantum_dots/components/test_ld_qubit.py
git commit -m "feat(ld-qubit): replace set_xy_frequency with property-based frequency model"
```

---

### Task 4: Rewire `XYDriveMacro.update()` frequency handling

**Files:**
- Modify: `quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py`
- Create: `tests/architecture/quantum_dots/test_xy_drive_macro_frequency.py`

- [ ] **Step 1: Write failing tests for rewired `update()`**

Create `tests/architecture/quantum_dots/test_xy_drive_macro_frequency.py`:

```python
"""Tests for XYDriveMacro frequency update/apply behaviour."""

import pytest
from quam.components import StickyChannelAddon, pulses
from quam.components.ports import LFFEMAnalogOutputPort, MWFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDriveMW
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


@pytest.fixture
def wired_qubit():
    """Qubit with XY drive and macros wired."""
    machine = LossDiVincenzoQuam()

    gate = VoltageGate(
        id="plunger_1",
        opx_output=LFFEMAnalogOutputPort("con1", 2, port_id=1),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    machine.create_virtual_gate_set(
        virtual_channel_mapping={"vdot1": gate},
        gate_set_id="main",
    )
    machine.register_channel_elements(
        plunger_channels=[gate],
        barrier_channels=[],
        sensor_resonator_mappings={},
    )
    machine.register_qubit(quantum_dot_id="vdot1", qubit_name="Q1")

    qubit = machine.qubits["Q1"]
    qubit.larmor_frequency = 5.1e9

    xy = XYDriveMW(
        id="xy_mw",
        opx_output=MWFEMAnalogOutputPort(
            controller_id="con1",
            fem_id=1,
            port_id=1,
            band=2,
            upconverter_frequency=int(5e9),
            full_scale_power_dbm=10,
        ),
    )
    qubit.xy = xy

    machine.reset_voltage_sequence("main")
    qubit.add_point(VoltagePointName.INITIALIZE, {"vdot1": 0.1}, duration=200)
    qubit.add_point(VoltagePointName.MEASURE, {"vdot1": 0.15}, duration=200)
    qubit.add_point(VoltagePointName.EMPTY, {"vdot1": 0.0}, duration=200)

    wire_machine_macros(machine)
    return qubit


class TestXYDriveMacroFrequencyUpdate:
    def test_update_frequency_sets_larmor(self, wired_qubit):
        qubit = wired_qubit
        xy_macro = qubit.macros[SingleQubitMacroName.XY_DRIVE]

        xy_macro.update(frequency=5.2e9)
        assert qubit.larmor_frequency == 5.2e9

    def test_update_frequency_offset_adjusts_larmor(self, wired_qubit):
        qubit = wired_qubit
        xy_macro = qubit.macros[SingleQubitMacroName.XY_DRIVE]

        original = qubit.larmor_frequency
        xy_macro.update(frequency_offset=10e6)
        assert qubit.larmor_frequency == pytest.approx(original + 10e6)

    def test_update_frequency_and_offset_raises(self, wired_qubit):
        qubit = wired_qubit
        xy_macro = qubit.macros[SingleQubitMacroName.XY_DRIVE]

        with pytest.raises(ValueError, match="either frequency or frequency_offset"):
            xy_macro.update(frequency=5.2e9, frequency_offset=10e6)

    def test_update_no_recenter_lo_parameter(self, wired_qubit):
        """recenter_LO parameter should no longer exist."""
        qubit = wired_qubit
        xy_macro = qubit.macros[SingleQubitMacroName.XY_DRIVE]

        with pytest.raises(TypeError):
            xy_macro.update(frequency=5.2e9, recenter_LO=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/architecture/quantum_dots/test_xy_drive_macro_frequency.py -v`
Expected: FAIL — `update()` still calls `set_xy_frequency` which no longer exists

- [ ] **Step 3: Rewire `XYDriveMacro.update()`**

In `quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py`, replace the `update` method on `XYDriveMacro` (lines 259–317). The new version:

```python
def update(
    self,
    *,
    amplitude: float | None = None,
    amplitude_scale: float | None = None,
    duration: int | None = None,
    frequency: float | None = None,
    frequency_offset: float | None = None,
) -> None:
    """Persistently update calibrated pulse parameters.

    Changes are applied to the QuAM state objects directly and are
    captured by subsequent serialisation (``machine.save``).

    Args:
        amplitude: Set ``reference_amplitude`` to this absolute value.
        amplitude_scale: Multiply current ``reference_amplitude`` by
            this factor.  Mutually exclusive with *amplitude*.
        duration: Set the reference pulse length in **nanoseconds**
            (quantised to 4 ns).  For ``ScalableGaussianPulse`` the
            sigma auto-scales via ``sigma_ratio``; for plain
            ``GaussianPulse`` sigma is rescaled proportionally.
        frequency: Set ``qubit.larmor_frequency`` to this absolute
            value (Hz).  Mutually exclusive with *frequency_offset*.
        frequency_offset: Add this offset (Hz) to the current
            ``qubit.larmor_frequency``.
    """
    if amplitude is not None and amplitude_scale is not None:
        raise ValueError("Provide either amplitude or amplitude_scale, not both.")
    if frequency is not None and frequency_offset is not None:
        raise ValueError("Provide either frequency or frequency_offset, not both.")

    if amplitude is not None:
        self.reference_amplitude = float(amplitude)
    elif amplitude_scale is not None:
        self.reference_amplitude *= float(amplitude_scale)

    if duration is not None:
        pulse = self.reference_pulse
        new_length = _quantize_ns(duration)
        old_length = int(pulse.length)

        if hasattr(pulse, "sigma_ratio"):
            pulse.length = new_length
            pulse.sigma = pulse.length * pulse.sigma_ratio
        else:
            sigma = getattr(pulse, "sigma", None)
            pulse.length = new_length
            if sigma is not None and old_length > 0 and hasattr(pulse, "sigma"):
                pulse.sigma = sigma * new_length / old_length

    if frequency is not None:
        self.qubit.larmor_frequency = float(frequency)
    elif frequency_offset is not None:
        self.qubit.larmor_frequency = float(
            self.qubit.larmor_frequency + frequency_offset
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/architecture/quantum_dots/test_xy_drive_macro_frequency.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run full test suite to catch regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass. Pay special attention to `test_macro_persistence.py` and `test_rabi_chevron_e2e.py`.

- [ ] **Step 6: Commit**

```bash
git add quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py tests/architecture/quantum_dots/test_xy_drive_macro_frequency.py
git commit -m "feat(xy-macro): rewire XYDriveMacro.update() to set larmor_frequency directly"
```

---

### Task 5: Update examples to new frequency API

**Files:**
- Modify: `quam_builder/architecture/quantum_dots/examples/quam_ld_example.py`
- Modify: `quam_builder/architecture/quantum_dots/examples/rabi_chevron.py`
- Modify: `quam_builder/architecture/quantum_dots/examples/rabi_chevron_transport.py`
- Modify: `quam_builder/architecture/quantum_dots/examples/quam_ld_generator_example.py`
- Modify: `quam_builder/architecture/quantum_dots/examples/quam_qd_generator_example.py`
- Modify: `quam_builder/architecture/quantum_dots/examples/full_workflow_example.py`

- [ ] **Step 1: Grep all examples for old API usage**

Run: `rg "set_xy_frequency|recenter_LO" quam_builder/architecture/quantum_dots/examples/`
Expected: Zero matches (none of the examples currently call `set_xy_frequency`).

Run: `rg "intermediate_frequency" quam_builder/architecture/quantum_dots/examples/`
Review each match: examples that pass `intermediate_frequency=` as a constructor arg to XY drives are fine (they override the reference default). No changes needed there since they're constructing standalone objects with explicit IF values.

- [ ] **Step 2: Review `quam_ld_example.py` — already uses `larmor_frequency`**

In `quam_builder/architecture/quantum_dots/examples/quam_ld_example.py` line 117:
```python
machine.qubits[f"Q{i}"].larmor_frequency = 5e6 + 1e6 * i
```
This is already the new API. No change needed.

Verify the XY drives in this file pass `intermediate_frequency=` at construction. Since the new default is `"#../larmor_frequency"` for `RF_frequency`, and `"#./inferred_intermediate_frequency"` for `intermediate_frequency`, passing an explicit `intermediate_frequency=10e6` at construction overrides the reference. This is fine — it's a standalone example where the IF is known upfront.

- [ ] **Step 3: Review remaining examples**

Check `rabi_chevron.py`, `rabi_chevron_transport.py`, `quam_ld_generator_example.py`, `quam_qd_generator_example.py`, and `full_workflow_example.py`. All of these construct XY drives with explicit `intermediate_frequency=` — no changes needed.

- [ ] **Step 4: Commit (if any changes were made)**

If changes were needed:
```bash
git add quam_builder/architecture/quantum_dots/examples/
git commit -m "docs(examples): update examples to new frequency API"
```

If no changes needed, skip this commit.

---

### Task 6: Update calibration workflow tutorial

**Files:**
- Modify: `tutorials/calibration_workflow.ipynb`

- [ ] **Step 1: Identify cells using old API**

The notebook has a cell calling `xy.update(frequency=50e6, recenter_LO=True)` which will fail because `recenter_LO` is removed. This cell needs updating.

- [ ] **Step 2: Update the cell**

Replace the `xy.update(...)` call that uses `recenter_LO=True` with the new pattern:

Before:
```python
xy.update(
    amplitude=0.35,
    duration=40,
    frequency=50e6,
    recenter_LO=True,
)
```

After:
```python
q1.xy.LO_frequency = 50e6  # Set LO first if recentering is needed
xy.update(
    amplitude=0.35,
    duration=40,
    frequency=50e6,
)
```

Also update any surrounding print statements or markdown cells that reference the old frequency model.

- [ ] **Step 3: Verify notebook runs without errors**

Run the notebook cells manually or via:
```bash
jupyter nbconvert --to notebook --execute tutorials/calibration_workflow.ipynb --output /dev/null
```
Expected: No `TypeError` or `AttributeError` related to `recenter_LO` or `set_xy_frequency`.

- [ ] **Step 4: Commit**

```bash
git add tutorials/calibration_workflow.ipynb
git commit -m "docs(tutorial): update calibration workflow to new frequency API"
```

---

### Task 7: Final regression check and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass.

- [ ] **Step 2: Run linter**

Run: `ruff check quam_builder/architecture/quantum_dots/components/xy_drive.py quam_builder/architecture/quantum_dots/qubit/ld_qubit.py quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py`
Expected: No new lint errors.

- [ ] **Step 3: Verify no remaining references to removed API**

Run: `rg "set_xy_frequency" quam_builder/ tests/`
Expected: Zero matches (only the design spec in `docs/` should reference it).

Run: `rg "recenter_LO" quam_builder/ tests/`
Expected: Zero matches.

- [ ] **Step 4: Final commit (if cleanup needed)**

```bash
git add -A
git commit -m "chore: final cleanup after frequency model redesign"
```
