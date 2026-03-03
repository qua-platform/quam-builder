"""Test-wide fixtures and helpers."""

import pytest

from quam_builder.architecture.quantum_dots.operations import component_macro_catalog
from quam_builder.architecture.quantum_dots.operations import macro_registry


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
    macro_registry._reset_registry()
    yield
