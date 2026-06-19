# Plan: Mixin Improvements

## Current Issues

### 1. Duration Parameter Redundancy
Currently there are multiple duration parameters that overlap:

- **VoltageTuningPoint.duration**: Default duration stored with the voltage point
- **StepPointMacro.hold_duration**: Duration override in the macro
- **add_point_with_step_macro(hold_duration, point_duration)**: Two parameters that confuse users

The flow is:
```
VoltageTuningPoint(duration=X)  →  StepPointMacro(hold_duration=Y)  →  apply(hold_duration=Z)
```
Each layer can override the previous, but this is confusing and error-prone.

### 2. VoltageTuningPoint vs Point Macros Redundancy
`VoltageTuningPoint` and `StepPointMacro`/`RampPointMacro` have overlapping purposes:
- Both store duration information
- `StepPointMacro` essentially wraps `VoltageTuningPoint` with a reference

### 3. Macro Invocation Inconsistency
- `BasePointMacro` has `__call__` that handles parameter aliases (`duration` → `hold_duration`)
- Custom macros (e.g., `MeasureMacro`) don't have `__call__`
- Mixin's `macro_method` has fragile detection logic

---

## Proposed Changes

### Phase 1: Simplify Duration Parameters

**Goal**: Single `duration` parameter throughout the chain.

#### 1.1 Update VoltageTuningPoint
Keep `VoltageTuningPoint.duration` as the single source of truth for default duration.

#### 1.2 Update Point Macros
Change `StepPointMacro` and `RampPointMacro`:
```python
@quam_dataclass
class StepPointMacro(BasePointMacro):
    # Remove hold_duration attribute - use VoltageTuningPoint.duration as default
    # Allow runtime override via apply(duration=...)

    def apply(self, duration: int | None = None, **kwargs):
        """Execute step operation.

        Args:
            duration: Override for hold duration (ns). If None, uses point's default.
        """
        point = self._resolve_point(self)
        effective_duration = duration if duration is not None else point.duration
        self.voltage_sequence.step_to_point(self._get_point_name(), duration=effective_duration)
```

#### 1.3 Update Mixin Methods
Simplify `add_point_with_step_macro` and `with_step_point`:
```python
def add_point_with_step_macro(
    self,
    macro_name: str,
    voltages: Optional[Dict[str, float]] = None,
    duration: int = 100,  # Single duration parameter
    replace_existing_point: bool = True,
) -> StepPointMacro:
```

Remove `hold_duration` and `point_duration` - use single `duration`.

---

### Phase 2: Move __call__ Logic to apply()

**Goal**: Consistent macro invocation without relying on `__call__`.

#### 2.1 Update BasePointMacro.apply()
Use `duration` directly (no aliasing needed since not rolled out):
```python
def apply(self, *args, duration: int | None = None, **kwargs):
    effective_duration = duration if duration is not None else self._resolve_point(self).duration
    # ... rest of implementation
```

#### 2.2 Remove __call__ from BasePointMacro
Delete `__call__` entirely - not needed since `apply()` handles everything.

#### 2.3 Simplify Mixin's macro_method
Revert to simple `apply()` call:
```python
def macro_method(**kwargs):
    return macros_dict[name].apply(**kwargs)
```

---

### Phase 3: Clarify VoltageTuningPoint vs Point Macros Roles

**Goal**: Clear separation of concerns.

#### Current Confusion
- `VoltageTuningPoint`: Data class storing voltages + duration
- `StepPointMacro`: Wrapper that references a VoltageTuningPoint and can override duration

#### Proposed Clarification

**VoltageTuningPoint** = "What voltages to apply" (stored in `gate_set.macros`)
- `voltages: Dict[str, float]`
- `duration: int` (default hold duration)

**StepPointMacro/RampPointMacro** = "How to get there" (stored in `component.macros`)
- References a VoltageTuningPoint
- Defines transition behavior (step vs ramp)
- Can override duration at call time

This is actually a reasonable separation - keep it but document clearly.

---

## Implementation Order

1. **Phase 2 first** - Move `__call__` logic to `apply()` (lowest risk, enables Phase 1)
2. **Phase 1** - Simplify duration parameters (breaking change, needs migration)
3. **Phase 3** - Documentation clarification (no code changes)

---

## Files to Modify

1. `quam_builder/architecture/quantum_dots/macros/point_macros.py`
   - Remove `hold_duration` attribute from `StepPointMacro` and `RampPointMacro`
   - Update `apply()` to use `duration` parameter, defaulting to point's duration
   - Remove `__call__` from `BasePointMacro`

2. `quam_builder/architecture/quantum_dots/components/mixin.py`
   - Simplify `macro_method` to always use `apply()`
   - Update `add_point_with_step_macro()`: remove `hold_duration` and `point_duration`, use single `duration`
   - Update `add_point_with_ramp_macro()`: same simplification
   - Update `with_step_point()`: remove `hold_duration` and `point_duration`, use single `duration`
   - Update `with_ramp_point()`: same simplification

3. `quam_builder/architecture/quantum_dots/components/gate_set.py`
   - No changes needed to `VoltageTuningPoint` (already has single `duration`)

4. Tests and examples
   - Update to use new `duration` parameter name
