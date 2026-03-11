"""Tests for catalog/registry reset helpers (FOR TESTING ONLY)."""

import pytest

from quam_builder.architecture.quantum_dots.operations import component_macro_catalog
from quam_builder.architecture.quantum_dots.operations import macro_registry


def test_reset_registration_sets_registered_false():
    """_reset_registration() sets _REGISTERED = False so registration can re-run."""
    component_macro_catalog.register_default_component_macro_factories()
    component_macro_catalog._reset_registration()
    assert component_macro_catalog._REGISTERED is False


def test_reset_registry_clears_factories():
    """_reset_registry() empties _COMPONENT_MACRO_FACTORIES."""
    component_macro_catalog.register_default_component_macro_factories()
    assert len(macro_registry._COMPONENT_MACRO_FACTORIES) > 0
    macro_registry._reset_registry()
    assert len(macro_registry._COMPONENT_MACRO_FACTORIES) == 0


def test_reset_allows_fresh_registration():
    """After both resets, register_default_component_macro_factories() can re-run."""
    component_macro_catalog.register_default_component_macro_factories()
    component_macro_catalog._reset_registration()
    macro_registry._reset_registry()
    # Should not raise; idempotent re-registration
    component_macro_catalog.register_default_component_macro_factories()


def test_reset_catalog_fixture_provides_fresh_state(reset_catalog):
    """Tests using reset_catalog fixture see fresh registration state."""
    # After reset_catalog runs, registry should be empty and _REGISTERED False
    assert component_macro_catalog._REGISTERED is False
    assert len(macro_registry._COMPONENT_MACRO_FACTORIES) == 0
