# XY Drive Frequency Model Redesign

## Problem

The LD quantum dot qubit's XY drive frequency management is inconsistent across
three layers (LDQubit, XY channel, XYDriveMacro). Key issues:

1. `LDQubit.set_xy_frequency` directly writes `intermediate_frequency` on the XY
   channel, conflicting with the QuAM reference `"#./inferred_intermediate_frequency"`
   already set as the default.
2. `LDQubit.larmor_frequency` is disconnected from `xy.RF_frequency` — they can
   diverge silently.
3. No IF bounds validation when frequencies are set via property access.
4. `XYDriveMacro.update(frequency=...)` delegates to `set_xy_frequency`, which
   mixes LO recentering logic into a method that should just set the target RF.

## Decisions

| Decision | Choice |
|----------|--------|
| Supported XY drive types | `XYDriveIQ`, `XYDriveMW` only |
| Primary frequency pair | LO + RF (Larmor). IF is always derived. |
| RF source of truth | `LDQubit.larmor_frequency` — single canonical location |
| User-facing API | Property-style: `qubit.larmor_frequency = X`, `qubit.xy.LO_frequency = Y` |
| Macro `update()` | Rewired: `frequency=` sets `qubit.larmor_frequency`; `recenter_LO` removed |
| Implementation approach | Pure QuAM references — no sync logic, no dual state |

## Frequency Model

### The Triad

`RF = LO + IF`, therefore `IF = RF - LO`.

- **RF** lives on `LDQubit.larmor_frequency` (concrete value, user sets this)
- **LO** lives on the XY channel hardware path (inherited from QuAM base classes)
- **IF** is always derived via `inferred_intermediate_frequency` (built-in QuAM property)

### Reference Chain on XY Drive Objects

```
xy.RF_frequency           ── "#../larmor_frequency" ──>  qubit.larmor_frequency
xy.LO_frequency           ── inherited reference    ──>  hardware LO
xy.intermediate_frequency ── "#./inferred_intermediate_frequency" ──>  RF - LO
```

### User Interaction

```python
qubit.larmor_frequency = 5e9
qubit.xy.LO_frequency = 4.8e9
print(qubit.xy.intermediate_frequency)  # => 200_000_000 (200 MHz)
```

### Serialization Round-Trip

With `follow_references=False` (default):

- `larmor_frequency: 5000000000.0` — concrete number on the qubit
- `RF_frequency: "#../larmor_frequency"` — reference string on XY drive
- `intermediate_frequency: "#./inferred_intermediate_frequency"` — reference string
- `LO_frequency` — inherited reference string

On load, all references resolve through the QuAM object graph automatically.

## File-by-File Changes

### `quam_builder/architecture/quantum_dots/components/xy_drive.py`

**`XYDriveBase`** — add IF validation:

```python
@quam_dataclass
class XYDriveBase:
    IF_LIMIT: ClassVar[float] = 400e6

    def validate_intermediate_frequency(self) -> None:
        """Raise ValueError if |IF| exceeds the OPX ±400 MHz band."""
        if_freq = self.intermediate_frequency
        if abs(if_freq) > self.IF_LIMIT:
            raise ValueError(
                f"Intermediate frequency {if_freq / 1e6:.2f} MHz exceeds "
                f"±{self.IF_LIMIT / 1e6:.0f} MHz on '{self.name}'. "
                f"Adjust LO_frequency or larmor_frequency."
            )
```

**`XYDriveIQ`** — override `RF_frequency` default:

```python
class XYDriveIQ(IQChannel, XYDriveBase):
    RF_frequency: float = "#../larmor_frequency"
    intermediate_frequency: int = "#./inferred_intermediate_frequency"  # unchanged
```

**`XYDriveMW`** — override `RF_frequency` default:

```python
class XYDriveMW(MWChannel, XYDriveBase):
    RF_frequency: float = "#../larmor_frequency"
    intermediate_frequency: float = "#./inferred_intermediate_frequency"  # unchanged
```

### `quam_builder/architecture/quantum_dots/qubit/ld_qubit.py`

**Remove `set_xy_frequency`** entirely.

**Extend `__setattr__`** to validate IF when `larmor_frequency` is written.

The validation must compute the would-be IF from the incoming `value` directly,
because at `__setattr__` time the new value has not yet been written — the
reference chain (`xy.RF_frequency → larmor_frequency`) would still resolve to
the old number.

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
                            f"exceeds ±400 MHz. Adjust LO_frequency or "
                            f"larmor_frequency."
                        )
            except AttributeError:
                pass  # LO not yet wired, skip validation
    super().__setattr__(name, value)
```

**Add convenience read-only properties:**

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

### `quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py`

**`XYDriveMacro.update()`** — rewire frequency handling, remove `recenter_LO`:

```python
def update(self, *, amplitude=None, amplitude_scale=None, duration=None,
           frequency=None, frequency_offset=None) -> None:
    # amplitude and duration handling unchanged

    if frequency is not None and frequency_offset is not None:
        raise ValueError("Provide either frequency or frequency_offset, not both.")

    if frequency is not None:
        self.qubit.larmor_frequency = float(frequency)
    elif frequency_offset is not None:
        self.qubit.larmor_frequency = float(
            self.qubit.larmor_frequency + frequency_offset
        )
```

**`XYDriveMacro.apply()`** — runtime `frequency_offset` logic unchanged. The
existing code reads `qubit.xy.intermediate_frequency` (which resolves the
reference to a number) and calls `qubit.xy.update_frequency()` (QUA runtime).
No modifications needed.

## Backward Compatibility

### Breaking Changes

| Change | Migration |
|--------|-----------|
| `qubit.set_xy_frequency(freq)` removed | `qubit.larmor_frequency = freq` |
| `qubit.set_xy_frequency(freq, recenter_LO=True)` removed | `qubit.xy.LO_frequency = freq` then `qubit.larmor_frequency = freq` |
| `macro.update(recenter_LO=True)` removed | Set `qubit.xy.LO_frequency` explicitly before `macro.update(frequency=...)` |

### Non-Breaking

- `qubit.larmor_frequency = X` already works (plain field)
- `qubit.xy.intermediate_frequency` default (`"#./inferred_intermediate_frequency"`) is unchanged
- `XYDriveMacro.apply(frequency_offset=...)` runtime behavior is unchanged
- All macro delegation chains (`_AxisRotationMacro`, `_FixedAxisAngleMacro`) are unaffected
- `qubit.xy.LO_frequency` access patterns are unchanged

### Serialized State Files

Existing saved machines where `xy.RF_frequency` is a concrete number will load
and run fine. On next save, the value stays concrete. To opt into reference-based
wiring, users rebuild the machine or set `xy.RF_frequency = "#../larmor_frequency"`.

## Out of Scope (Pre-existing Issues)

- `LDQubit.calibrate_octave` references `self.drive` which is not defined on
  `LDQubit` (the field is `self.xy`). This is a pre-existing bug unrelated to
  frequency model changes. It should be fixed separately by updating
  `calibrate_octave` to use `self.xy` instead of `self.drive`.
