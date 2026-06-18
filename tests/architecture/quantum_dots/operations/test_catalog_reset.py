"""Tests for catalog-based macro registration (no global registry state)."""

from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import QuantumDot, VoltageGate
from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    DefaultMacroCatalog,
    MacroRegistry,
    UtilityMacroCatalog,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    ZNeg90Macro,
)
from quam_builder.architecture.quantum_dots.operations.names import SingleQubitMacroName
from quam_builder.architecture.quantum_dots.qubit import LDQubit


def test_default_macro_catalog_fresh_instances_are_independent():
    """Each DefaultMacroCatalog keeps its own type table."""
    a = DefaultMacroCatalog()
    b = DefaultMacroCatalog()
    assert a is not b
    assert a.get_factories(LDQubit) == b.get_factories(LDQubit)


def test_macro_registry_resolve_merges_catalogs_in_priority_order():
    """Later (higher-priority) catalogs override macro keys from earlier ones."""
    low = UtilityMacroCatalog()
    high = DefaultMacroCatalog()
    reg = MacroRegistry()
    reg.register_catalog(low)
    reg.register_catalog(high)

    gate = VoltageGate(
        id="g1",
        opx_output=LFFEMAnalogOutputPort("con1", 1, port_id=1),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    qd = QuantumDot(id="qd1", physical_channel=gate)
    qubit = LDQubit(id="Q1", quantum_dot=qd)

    merged = reg.resolve_factories(qubit)
    assert SingleQubitMacroName.Z_NEG_90.value in merged
    assert merged[SingleQubitMacroName.Z_NEG_90.value] is ZNeg90Macro


def test_default_macro_catalog_register_custom_factory():
    """register() on a fresh catalog adds or replaces entries for a type."""

    class CustomZ(ZNeg90Macro):
        pass

    catalog = DefaultMacroCatalog()
    catalog.register(
        LDQubit,
        {
            **catalog.get_factories(LDQubit),
            SingleQubitMacroName.Z_NEG_90.value: CustomZ,
        },
    )
    factories = catalog.get_factories(LDQubit)
    assert factories[SingleQubitMacroName.Z_NEG_90.value] is CustomZ


def test_macro_registry_fresh_instance_has_no_catalogs():
    reg = MacroRegistry()
    assert reg.catalogs == ()
