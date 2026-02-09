# pylint-qua-plugin

A Pylint plugin for QUA DSL compatibility that suppresses false positive warnings in QUA code.

This plugin is integrated into the quam-builder repo and automatically loaded via `.pylintrc`.

## The Problem

QUA is a domain-specific language embedded in Python that uses Python syntax to build quantum control programs. However, QUA expressions generate IR at "compile time" rather than executing at Python runtime. This means many pylint rules that assume Python semantics produce false positives.

For example:

```python
with qua.program() as prog:
    n_op = declare(int)

    # Pylint suggests: "n_op & 1 == 0" can be simplified to "not n_op & 1"
    # But this is WRONG for QUA - if_() needs a QUA boolean expression!
    if_(n_op & 1 == 0)
```

The suggested "fix" would break the QUA code because:
1. `if_()` is a QUA function, not Python's `if` statement
2. QUA comparison operators generate QUA IR, they don't evaluate at Python runtime
3. QUA doesn't support Python's `not` operator

## How It Works

The plugin automatically suppresses problematic rules in two contexts:

1. **Inside `with qua.program()` blocks** - the main QUA program context
2. **Inside QUA control flow function calls** - even when outside a program block (e.g., in helper functions)

### Detected QUA Functions

The plugin recognizes these QUA functions and suppresses warnings inside their arguments:

- **Control flow**: `if_`, `else_`, `elif_`, `for_`, `for_each_`, `while_`, `switch_`, `case_`, `default_`
- **Variables**: `assign`, `declare`, `declare_stream`
- **Timing**: `wait`, `align`, `reset_phase`, `frame_rotation`, `update_frequency`
- **Playback**: `play`, `measure`, `save`, `pause`, `ramp`
- **Math**: `Math.abs`, `Math.log`, `Math.sqrt`, `Math.sin`, `Math.cos`, etc.
- **Casting**: `Cast.to_int`, `Cast.to_fixed`, `Cast.to_bool`
- And more...

### Suppressed Rules

| Code | Symbol | Why it conflicts with QUA |
|------|--------|--------------------------|
| C1805 | use-implicit-booleaness-not-comparison-to-zero | QUA needs explicit comparisons for IR generation |
| C1803 | use-implicit-booleaness-not-comparison-to-string | QUA needs explicit comparisons |
| C0121 | singleton-comparison | QUA needs `== True`/`== False` for boolean expressions |
| R1714 | consider-using-in | QUA doesn't support Python's `in` operator |
| W0104 | pointless-statement | QUA statements build IR, they're not pointless |
| W0106 | expression-not-assigned | QUA function calls have side effects on IR |
| R1705 | no-else-return | QUA's `else_()` is a function call, not a clause |
| R1720 | no-else-raise | Similar to above |
| R1709 | consider-using-ternary-expression | QUA doesn't support ternary |
| W0127 | self-assigning-variable | QUA uses `assign(x, x + 1)` pattern |

## Configuration (Already Set Up)

The plugin is already configured in `.pylintrc`:

```ini
[MAIN]
init-hook='import sys; sys.path.insert(0, ".")'
load-plugins=pylint_qua_plugin
```

And in `.pre-commit-config.yaml`, pylint is configured as a local hook to ensure
the plugin is available.

## Running Tests

```bash
pytest tests/pylint_plugin/ -v
```

## Example

```python
# This will still warn (regular Python)
def regular_python():
    n = 5
    if n & 1 == 0:  # C1805 warning - legitimate
        print("even")

# Inside program context - suppressed
with qua.program() as prog:
    n_op = declare(int)
    if_(n_op & 1 == 0)  # No warning

# QUA helper function (outside program) - also suppressed!
def qua_helper():
    n = declare(int)
    if_(n == 0)      # No warning - inside if_() call
    while_(n & 1 == 0)  # No warning - inside while_() call
    assign(n, n + 1)   # No warning - inside assign() call
```

## Extending the Plugin

### Adding More Suppressed Rules

Edit `QUA_SUPPRESSED_MSGIDS` in `pylint_qua_plugin.py`:

```python
QUA_SUPPRESSED_MSGIDS: Set[str] = {
    "C1805",
    "your-new-rule",
    # ...
}
```

### Adding More QUA Functions

Edit `QUA_CONTROL_FLOW_FUNCTIONS` in `pylint_qua_plugin.py`:

```python
QUA_CONTROL_FLOW_FUNCTIONS: Set[str] = {
    "if_", "else_", "elif_",
    "your_new_qua_function",
    # ...
}
```

## Alternatives

If you prefer not to use a plugin:

### 1. Global rule disable

```toml
[tool.pylint.messages_control]
disable = ["C1805", "C0121"]
```

(Disables everywhere, not just QUA contexts)

### 2. Path-based ignore

```toml
[tool.pylint.main]
ignore-paths = ["qualibration_graphs/.*"]
```

### 3. Inline disable

```python
if_(n_op & 1 == 0)  # pylint: disable=C1805
```

## License

Apache-2.0