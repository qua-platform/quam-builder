# Phase 3: OperationsRegistry Clarification - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a module docstring to `default_operations.py` (OPS-01) and a comparison table to `operations/README.md` (OPS-02) that together clarify when to use `operations_registry.x180(q)` vs `q.x180()` vs `q.macros["x180"].apply()`. No new production logic — documentation only.

</domain>

<decisions>
## Implementation Decisions

### Docstring audience and scope (OPS-01)
- Write for **both** audiences: library users (researchers/engineers calling `operations_registry.x180(q)` in experiment scripts) first, then contributors maintaining the module
- Assume a **fresh reader** — briefly state what `OperationsRegistry` is before explaining when to use it (do not assume familiarity with QuAM dispatch internals)
- Compare **only** `operations_registry.x180(q)` vs `q.x180()` in the module docstring; the full three-way comparison including `q.macros["x180"].apply()` belongs in the README table
- Use **prose with inline backticks** — no code blocks in the module docstring; style like: "use `operations_registry.x180(q)` when writing generic algorithms that work across component types; use `q.x180()` for component-specific code where the component type is known"
- Target length: 3–5 sentences matching OPS-01 requirement

### Claude's Discretion
- Placement of the new comparison table within the existing README (likely a new top-level section near the top, before the deep override documentation)
- Table columns beyond the required "when to use" and "applicable component types" — Claude may add a "dispatch path" or "example" column if it improves clarity
- Whether to include brief inline code per table row or keep it prose-only
- Exact wording of "when to use" for `q.macros["x180"].apply()` (lowest-level access)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `default_operations.py` current module docstring (5 lines): explains OperationsRegistry uses function signatures as metadata and dispatches to `component.macros[operation_name]` — this is the baseline to expand from
- `operations/README.md` (468 lines): comprehensive reference covering macro architecture, component types, override model, and examples — the new table should be a new section that doesn't duplicate existing content

### Established Patterns
- README sections use `##` headings with short code blocks for examples; the comparison table should follow the same markdown style
- Function-level docstrings in `default_operations.py` already say `"""Dispatch to component.macros['x180']."""` — the module docstring should complement not repeat this

### Integration Points
- `default_operations.py` lives at `quam_builder/architecture/quantum_dots/operations/default_operations.py`
- `README.md` lives at `quam_builder/architecture/quantum_dots/operations/README.md`
- The new table covers three rows: `operations_registry.x180(q)`, `q.x180()`, `q.macros["x180"].apply()`

</code_context>

<specifics>
## Specific Ideas

- Prose style for the docstring: "use `operations_registry.x180(q)` when writing generic algorithms that work across component types; use `q.x180()` for component-specific code where the component type is known"
- The docstring should make clear that `OperationsRegistry` is NOT required for most users — `q.x180()` is the natural direct call; the registry is a convenience for protocol-style code

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-operationsregistry-clarification*
*Context gathered: 2026-03-03*
