# Contributing Guide

Welcome! This repository contains tools for building and analyzing calibration graphs for superconducting qubits. This guide explains how to set up your development environment, how we use pre-commit hooks, how tests are structured, and what we expect from contributions.

---

## 1. Getting Started

### 1.1. Clone the repository

```bash
git clone git@github.com:qua-platform/quam-builder.git
cd quam-builder
```

### 1.2. Create a virtual environment and install dependencies

Using `uv` (recommended):

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh  # Unix/macOS
# Or: pip install uv

# Create venv and install dependencies in one command
uv sync --extra dev
```

Alternatively, with `venv`:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

This installs:

- Runtime deps (numpy, scipy, etc.)
- Dev tools: `pre-commit`, `ruff`, `mypy`, `pytest`, `pytest-cov`, `commitizen`, etc.

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
  - **Ruff formatter** (`ruff-format`) for consistent Python formatting.
  - **Ruff lint** (`ruff`) for style, correctness, and import order (with `--fix` to auto-fix many issues).

- **Generic hygiene**
  - Strip trailing whitespace.
  - Ensure files end with a newline.
  - Prevent committing merge conflict markers.
  - Check YAML/JSON formatting.
  - Warn on accidental large binary files.

On each **push**, an additional hook runs:

- **mypy**: static type checks on the codebase.

### 2.3. Running pre-commit manually

Before opening a pull request, run all hooks on the whole repo:

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

- `feat: add rabi calibration pipeline`
- `fix: handle NaNs in t1 analysis`
- `refactor: simplify pulse sequence builder`

If your commit message doesn’t follow the convention, the `commit-msg` hook will fail and show an error.

You can also use Commitizen’s CLI to help craft messages and bump versions:

```bash
cz commit
cz bump
```

(See `.cz.toml` or `[tool.commitizen]` in `pyproject.toml` for configuration.)

---

## 4. Tests

We use `pytest` and organize tests into tiers that reflect how the calibration and control stack is validated, from pure Python logic up to hardware-in-the-loop checks.

---

## 5. Pull Requests

Before opening a PR:

1. Ensure your branch is up-to-date with the target branch (`main` or `develop`).
2. Run:
   ```bash
   pre-commit run --all-files
   pytest
   ```
3. Add or update tests for your changes following the tiered test structure above.
4. Ensure your commit messages follow Conventional Commits.

When you open the PR:

- CI will run linting/formatting checks and the configured test tiers.
- At least one reviewer must approve before merging.
- For changes that affect calibration logic, signals, or hardware interaction, please:
  - Describe the impact on calibration workflows in the PR description.
  - Indicate which test tiers you updated or verified.
  - Link any related GitHub Issues or design docs.

---

## 6. Questions

If you’re unsure about:

- Which test tier is appropriate for your change,
- How to structure calibration or signal validation tests,
- How to interpret pre-commit or CI errors,

please ask in the development channel or tag a maintainer in your PR.
