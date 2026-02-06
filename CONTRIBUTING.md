# Contributing Guide

Welcome! This repository contains the `quam-builder`, a Python tool for programmatically constructing QUAM (Quantum Abstract Machine) configurations for the Quantum Orchestration Platform (QOP). This guide explains how to set up your development environment, how we use pre-commit hooks, how tests are structured, and what we expect from contributions.

---

## 1. Getting Started

### 1.1. Clone the repository

```bash
git clone https://github.com/qua-platform/quam-builder.git
cd quam-builder
```

### 1.2. Create a virtual environment and install dependencies

Using `uv` (recommended):

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh  # Unix/macOS
# Or: pip install uv

# Create venv and install dependencies in one command
uv sync --group dev --prerelease=allow
source .venv/bin/activate
```

Alternatively, with `venv`:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

This installs:

- Runtime deps (`qualang-tools`, `quam`, `qm-qua`, `xarray`, etc.)
- Dev tools: `pre-commit`, `ruff`, `mypy`, `pytest`, `pytest-cov`, `commitizen`, etc.

### 1.3. Branch naming conventions

When creating a new branch, follow these naming conventions:

- **`feature/`** - New features or enhancements
  - Example: `feature/nv-center-support`, `feature/quantum-dots`

- **`bugfix/`** - Bug fixes
  - Example: `bugfix/wiring-generation`, `bugfix/port-mapping`

- **`hotfix/`** - Urgent fixes for production issues
  - Example: `hotfix/critical-quam-build`

- **`chore/`** - Maintenance tasks, dependency updates, tooling
  - Example: `chore/update-dependencies`, `chore/add-pre-commit`

- **`refactor/`** - Code refactoring without changing functionality
  - Example: `refactor/simplify-builder`, `refactor/architecture-components`

- **`experiment/`** - Experimental or exploratory work
  - Example: `experiment/new-component-type`, `experiment/alternative-wiring`

- **`release/`** - Release preparation branches
  - Example: `release/v1.0.0`, `release/v1.1.0`

Use lowercase, hyphen-separated descriptions. Keep branch names concise but descriptive.

---

## 2. Pre-commit Hooks

We use [pre-commit](https://pre-commit.com) to automatically run fast checks before each commit. This ensures consistent style and catches many issues early.

### 2.1. Install the hooks

Run once after cloning:

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

This sets up two things:

- A **pre-commit** hook that runs on staged files before every commit.
- A **commit-msg** hook (via Commitizen) that validates your commit messages.

### 2.2. What runs in pre-commit?

On each commit, the following checks run (on changed files):

- **Formatting and linting**
  - **Black** (`black`) for consistent Python formatting (100 char line length).
  - **Pylint** (`pylint`) for code quality checks, following the `pyproject.toml` configuration.
    - Includes the `pylint_qua_plugin` which suppresses false positive warnings inside QUA code contexts (e.g., `with program()` blocks and QUA functions like `if_()`, `while_()`, `assign()`).

- **Generic hygiene**
  - Strip trailing whitespace.
  - Ensure files end with a newline.
  - Prevent committing merge conflict markers.
  - Check YAML/JSON formatting.
  - Warn on accidental large binary files.

On each **push**, an additional hook runs:

- **mypy**: static type checks on the codebase.

### 2.3. Running pre-commit manually

You can run pre-commit hooks on your staged files at any time:

```bash
pre-commit run
```

Or, if you want to check all files in the repository (useful before opening a PR):

```bash
pre-commit run --all-files
```

Fixes are usually applied automatically (e.g. for formatting). If a hook fails:

1. Read the error message.
2. Apply any suggested code changes.
3. Re-stage your files (`git add ...`).
4. Re-run the command or attempt the commit again.

---

## 3. Commit Messages (Conventional Commits)

We use [Conventional Commits](https://www.conventionalcommits.org/) enforced by Commitizen. The format is:

```text
<type>[:scope]: <short summary>

[optional body]

[optional footer(s)]
```

Common types:

- `feat`: a new feature
- `fix`: a bug fix
- `refactor`: code change that neither fixes a bug nor adds a feature
- `docs`: documentation only changes
- `test`: adding or updating tests only
- `chore`: tooling, build, or other non-product code changes

Examples:

- `feat: add NV center QPU support`
- `fix: correct wiring generation for MW-FEM`
- `refactor: simplify QUAM builder functions`

If your commit message doesn’t follow the convention, the `commit-msg` hook will fail and show an error.

You can also use Commitizen’s CLI to help craft messages and bump versions:

```bash
cz commit
cz bump
```

(See `.cz.toml` or `[tool.commitizen]` in `pyproject.toml` for configuration.)

---

## 4. Tests

We use `pytest` for testing the `quam-builder` functionality. Tests are organized to validate:

- **Architecture definitions**: Ensure QUAM components (qubits, resonators, drives, etc.) are correctly defined.
- **Builder functions**: Verify that `build_quam` and related functions properly construct QUAM objects.
- **Wiring generation**: Test that `build_quam_wiring` correctly maps components to QOP controller ports.
- **Component extensions**: Validate custom components and parameter additions.

Run tests with:

```bash
pytest
```

For coverage reporting:

```bash
pytest --cov=quam_builder --cov-report=html
```

---

## 5. Pull Requests

Before opening a PR:

1. Ensure your branch is up-to-date with the target branch (typically `main`).
2. Stage your changes and run:
   ```bash
   git add .
   pre-commit run
   pytest
   ```
   Note: Pre-commit will only check your staged changes. If you want to check all files, use `pre-commit run --all-files`.
3. Add or update tests for your changes.
4. Ensure your commit messages follow Conventional Commits.

When you open the PR:

- CI will run linting/formatting checks and tests.
- At least one reviewer must approve before merging.
- For changes that affect QUAM components, architecture, or wiring generation, please:
  - Describe the impact on existing QUAM configurations in the PR description.
  - Indicate which tests you added or updated.
  - Link any related GitHub Issues or design docs.
  - If adding new component types, include examples of how to use them.

---

## 6. Questions

If you're unsure about:

- How to extend existing QUAM components or create new ones,
- How to structure tests for builder functions or wiring generation,
- How to interpret pre-commit or CI errors,
- Best practices for QUAM architecture design,

please open an issue on GitHub or tag a maintainer in your PR.
