# Integrating pylint-qua-plugin into Your CI/CD Pipeline

This guide explains how to integrate the pylint QUA plugin into other projects that use QUA code, preventing false positive linting errors in your CI/CD pipelines.

## The Problem

QUA is a domain-specific language embedded in Python. While it uses Python syntax, QUA expressions generate IR at compile time rather than executing at Python runtime. This causes pylint to suggest "improvements" that break valid QUA code:

```python
# Pylint suggests: "n_op & 1 == 0" can be simplified to "not n_op & 1"
# But this breaks QUA code! if_() needs a QUA boolean expression.
if_(n_op & 1 == 0)
```

The plugin automatically suppresses these false positives inside:
- `with program()` blocks
- QUA control flow functions (`if_()`, `while_()`, `for_()`, `assign()`, etc.)

## Installation Options

### Option 1: Copy the Plugin Files (Recommended for Most Projects)

Copy the `pylint_qua_plugin` directory to your project:

```
your-project/
├── pylint_qua_plugin/
│   ├── __init__.py
│   ├── pylint_qua_plugin.py
│   └── README.md
├── pyproject.toml
└── ...
```

### Option 2: Install as a Package

If you prefer to install it as a dependency:

```bash
# From the quam-builder repo
pip install -e /path/to/quam-builder/pylint_qua_plugin

# Or add to your requirements.txt / pyproject.toml once published
# pip install pylint-qua-plugin
```

## Configuration

### Using `pyproject.toml` (Recommended)

Add the following to your `pyproject.toml`:

```toml
[tool.pylint.main]
# The init-hook finds the repo root and adds it to sys.path so the plugin can be found
init-hook = "import sys, os; d = os.getcwd(); exec('while d != os.path.dirname(d):\\n if os.path.isfile(os.path.join(d, \"pyproject.toml\")): sys.path.insert(0, d); break\\n d = os.path.dirname(d)')"
load-plugins = ["pylint_qua_plugin"]

[tool.pylint."messages control"]
# Your existing pylint configuration
enable = ["E", "R", "F", "C"]
disable = ["W", "I", "import-error", "no-name-in-module"]

[tool.pylint.format]
max-line-length = 120
```

### Using `.pylintrc`

If you prefer a separate `.pylintrc` file:

```ini
[MAIN]
init-hook=import sys, os; d = os.getcwd(); exec('while d != os.path.dirname(d):\n if os.path.isfile(os.path.join(d, "pyproject.toml")): sys.path.insert(0, d); break\n d = os.path.dirname(d)')
load-plugins=pylint_qua_plugin

[MESSAGES CONTROL]
enable=E, R, F, C
disable=W, I, import-error, no-name-in-module

[FORMAT]
max-line-length=120
```

## Pre-commit Setup

Add pylint as a local hook in `.pre-commit-config.yaml`:

```yaml
repos:
  # ... other hooks ...

  # Pylint with QUA plugin
  - repo: local
    hooks:
      - id: pylint
        name: pylint
        entry: python -m pylint
        language: system
        types: [python]
        # Exclude the plugin itself from linting
        exclude: ^pylint_qua_plugin/
```

**Important**: Use `language: system` (not `language: python`) so that pre-commit uses your project's Python environment where the plugin is accessible.

## GitHub Actions

### Basic Setup

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pylint astroid
          # Install your project dependencies
          pip install -e .

      - name: Run pylint
        run: |
          python -m pylint your_package/
```

### With Pre-commit

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pre-commit pylint astroid
          pip install -e .

      - name: Run pre-commit
        run: |
          pre-commit run --all-files
```

### With uv (Fast Package Manager)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --group dev

      - name: Run pre-commit
        run: uv run pre-commit run --all-files
```

## GitLab CI

```yaml
stages:
  - lint

pylint:
  stage: lint
  image: python:3.11
  before_script:
    - pip install pylint astroid
    - pip install -e .
  script:
    - python -m pylint your_package/
```

## Azure Pipelines

```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: |
      pip install pylint astroid
      pip install -e .
    displayName: 'Install dependencies'

  - script: |
      python -m pylint your_package/
    displayName: 'Run pylint'
```

## Suppressed Rules

The plugin suppresses these rules inside QUA contexts:

| Code | Symbol | Why it conflicts with QUA |
|------|--------|---------------------------|
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

## Extending the Plugin

### Adding More Suppressed Rules

Edit `QUA_SUPPRESSED_MSGIDS` in `pylint_qua_plugin.py`:

```python
QUA_SUPPRESSED_MSGIDS: Set[str] = {
    "C1805",
    "your-new-rule-code",
    "your-new-rule-symbol",
    # ...
}
```

### Adding More QUA Functions

Edit `QUA_CONTROL_FLOW_FUNCTIONS` in `pylint_qua_plugin.py`:

```python
QUA_CONTROL_FLOW_FUNCTIONS: Set[str] = {
    "if_", "else_", "elif_",
    "your_custom_qua_function",
    # ...
}
```

## Testing the Integration

Create a test file with both QUA and regular Python code:

```python
from qm.qua import program, declare, if_, while_, assign

# Regular Python - should trigger warnings
def regular_function():
    n = 5
    if n == 0:  # C1805 should appear
        print("zero")

# QUA code - should NOT trigger warnings
with program() as prog:
    x = declare(int)
    if_(x == 0)  # C1805 should be suppressed
    while_(x & 1 == 0)  # C1805 should be suppressed
    assign(x, x + 1)  # W0127 should be suppressed
```

Run pylint and verify:
- Warnings appear for `regular_function()`
- No warnings appear inside the `with program()` block

## Troubleshooting

### Plugin Not Found

If you get `No module named 'pylint_qua_plugin'`:

1. Ensure the `pylint_qua_plugin` directory is in your project root
2. Verify the init-hook is correctly adding the repo root to `sys.path`
3. Try running with explicit PYTHONPATH: `PYTHONPATH=. pylint your_code.py`

### Warnings Still Appearing in QUA Code

1. Check that the plugin is loaded: `pylint --list-plugins` should show `pylint_qua_plugin`
2. Verify you're using `program()` from `qm.qua` (the plugin detects this)
3. For helper functions, ensure you're using QUA functions like `if_()`, `while_()`, etc.

### Pre-commit Using Wrong Python

If pre-commit isn't finding the plugin:

1. Use `language: system` instead of `language: python`
2. Ensure your virtual environment is activated when running pre-commit
3. Or explicitly set the entry: `entry: /path/to/venv/bin/python -m pylint`

## License

Apache-2.0