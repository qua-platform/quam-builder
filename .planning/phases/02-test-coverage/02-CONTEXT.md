# Phase 2: Test Coverage - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Add test coverage for the macro system: assert correct macro presence and invocation behavior for all three new component types (`QuantumDot`, `QuantumDotPair`, `SensorDot`), cover the `LDQubit` XY delegation chain (`X180Macro → XMacro → XYDriveMacro`) end-to-end, and add save/load round-trip tests for macro instances. No new production code — this phase is tests only.

</domain>

<decisions>
## Implementation Decisions

### Delegation chain test approach (TEST-05)
- **Both** a smoke test (call `x180.apply()` inside `with qua.program()`, assert program is not None) **and** a mock assertion (patch QUA `play()` via `unittest.mock.patch` and assert it was called)
- Use the `qd_machine` fixture — the fully wired machine with real hardware config; matches the "all objects are real" pattern established in all `tests/architecture/quantum_dots/` files
- Add the test to `test_macro_wiring.py` (groups with other macro invocation tests)
- Test `X180Macro.apply()` end-to-end only — if it produces a valid QUA program and triggers the expected `play()` call, the full chain is exercised without redundantly unit-testing XYDriveMacro internals

### Claude's Discretion
- TEST-01/02/03: Phase 1 Plan 02 already added `TestQuantumDotCatalog`, `TestQuantumDotPairCatalog`, `TestSensorDotCatalog` (3 tests each = 9 total). Claude should determine whether these fully satisfy TEST-01/02/03 or whether additional assertions are needed — if satisfied, just update REQUIREMENTS.md to mark them complete.
- TEST-06 (save/load round-trip): Claude determines what "functionally equivalent" means — likely: `machine.save(tmpdir)` → `BaseQuamQD.load(tmpdir)` → verify macro keys are present and each macro instance is of the expected type. Can mirror the `test_stage_workflow_persistence.py` pattern with `tempfile.mkdtemp()`.
- File location for TEST-06: Claude decides (likely alongside existing component tests or a new file in `tests/architecture/quantum_dots/operations/`).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `qd_machine` fixture (tests/architecture/quantum_dots/conftest.py): Fully wired `LossDiVincenzoQuam` with 4 dots, 2 pairs, 1 sensor, 4 qubits — available to any test under `tests/architecture/quantum_dots/`
- `reset_catalog` fixture (tests/conftest.py): Resets `_REGISTERED` and `_COMPONENT_MACRO_FACTORIES` — use for any test that calls `wire_machine_macros()` to ensure clean state
- `_build_machine()` helper in `test_macro_wiring.py`: Lighter machine with XY drive channels configured; already used for macro override tests
- `tempfile.mkdtemp()` + `shutil.rmtree()` pattern: Used in `test_e2e_quantum_dots.py` and `test_stage_workflow_persistence.py` for file-based round-trip tests

### Established Patterns
- **Real objects only**: All `tests/architecture/quantum_dots/` files use real QUAM components — no mocks for QUAM objects; `unittest.mock.patch` acceptable for external QUA API calls
- **QUA program context**: Integration tests use `with qua.program() as prog: ... assert prog is not None`
- **`machine.save()` / `BaseQuamQD.load()`**: Standard persistence round-trip used in `test_stage_workflow_persistence.py`

### Integration Points
- `X180Macro` is in `quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros`; `qd_machine` qubits have XY drive configured via `_build_machine()` helper in test_macro_wiring.py (the `qd_machine` fixture's qubits do NOT have XY; use `_build_machine()` instead for XY-dependent tests)
- `wire_machine_macros` must be called before `.macros` is populated — always combine with `reset_catalog`
- `BaseQuamQD.load(path)` is the correct loader class for round-trip tests on the QD architecture

</code_context>

<specifics>
## Specific Ideas

- For the delegation chain mock: patch `qm.qua.play` (or equivalent QUA emit function) and assert it is called when `x180.apply()` is invoked inside a program context
- X180Macro test should call `qubit.macros["x180"].apply()` (via the wired catalog) rather than constructing the macro directly, to test the full wiring → invocation path

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-test-coverage*
*Context gathered: 2026-03-03*
