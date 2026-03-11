"""Test-wide fixtures and helpers."""

# This section combines two sets of functionality that are independently useful:

# (1) Make test utilities easily importable from any test location by adding the test directory
#     to sys.path. This is especially helpful for importing helper modules like test_utils.py.
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

# (2) Patch/extend WiringLineType from qualang_tools.wirer.connectivity, if present,
#     to ensure additional quantum-dot gate types (PLUNGER, BARRIER, etc.) are available,
#     maintaining compatibility with older releases of qualang_tools that might not contain them.
try:
    from enum import Enum
    from qualang_tools.wirer.connectivity import wiring_spec

    # Existing enum member names/values
    _existing_members = {member.name: member.value for member in wiring_spec.WiringLineType}
    # Additional enum options for quantum-dot testing
    _extra_members = {
        "PLUNGER_GATE": "plunger_gate",
        "PLUNGER": "plunger_gate",
        "BARRIER_GATE": "barrier_gate",
        "BARRIER": "barrier_gate",
        "GLOBAL_GATE": "global_gate",
        "SENSOR_GATE": "sensor_gate",
        "RF_RESONATOR": "rf_resonator",
    }

    # Only extend if any extra members aren't in the installed version.
    if any(name not in _existing_members for name in _extra_members):
        merged = {
            **_existing_members,
            **{k: v for k, v in _extra_members.items() if k not in _existing_members},
        }
        ExtendedWiringLineType = Enum("WiringLineType", merged)
        wiring_spec.WiringLineType = ExtendedWiringLineType
        # Update future imports so they also see these entries.
        sys.modules["qualang_tools.wirer.connectivity.wiring_spec"].WiringLineType = (
            ExtendedWiringLineType
        )
except ImportError:
    # qualang_tools might not be installed; ignore if not needed.
    pass

# (3) Globally patch quam.config.resolvers.quam_version_validator for the lifetime of each test
#     so that tests never fail due to the developer's local QUAM config version. This allows tests
#     that use QuamBase.load() to always pass regardless of user environment.
import pytest
from unittest.mock import patch

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
