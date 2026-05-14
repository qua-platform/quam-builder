"""Test-wide fixtures and helpers."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from quam_builder.architecture.quantum_dots.operations import component_macro_catalog
from quam_builder.architecture.quantum_dots.operations import component_pulse_catalog
from quam_builder.architecture.quantum_dots.operations import macro_registry
from quam_builder.architecture.quantum_dots.operations import pulse_registry

# Make test utilities (test_utils.py) importable from any sub-directory
sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(autouse=True)
def bypass_quam_config_version_check():
    """Bypass the QUAM global config version check.

    The QUAM 0.5.x load() path runs quam_version_validator against the user's
    ~/.quam/config.json. If that file is from an older QUAM version the check
    raises InvalidQuamConfigVersion and aborts. Patching the validator to a
    no-op lets tests call QuamBase.load() without requiring a migrated user
    config on every developer machine.
    """
    with patch("quam.config.resolvers.quam_version_validator"):
        yield


@pytest.fixture
def reset_catalog():
    """Reset catalog and registry before each test that uses it.

    Use this fixture in any test that directly verifies registration behavior
    (e.g., tests that call wire_machine_macros() and then assert macro presence).

    Do NOT use autouse=True — only tests that care about registration state
    should pull this in explicitly. Using autouse=True would break tests that
    rely on registration completing during component construction.
    """
    component_macro_catalog._reset_registration()
    component_pulse_catalog._reset_registration()
    macro_registry._reset_registry()
    pulse_registry._reset_registry()
    yield
