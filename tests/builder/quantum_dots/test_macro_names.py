"""Tests for canonical macro-name catalogs and default macro maps."""

from quam_builder.architecture.quantum_dots.operations import (
    default_operations as operations_module,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    SINGLE_QUBIT_MACROS,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    QPU_STATE_MACROS,
    STATE_POINT_MACROS,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.two_qubit_macros import (
    TWO_QUBIT_MACROS,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    SINGLE_QUBIT_MACRO_ALIAS_MAP,
    SINGLE_QUBIT_MACRO_ALIASES,
    SINGLE_QUBIT_MACRO_NAMES,
    STATE_MACRO_NAMES,
    TWO_QUBIT_MACRO_NAMES,
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)


def test_state_macro_enum_values_are_default_keys():
    """Voltage-point enum values should be used in default state macro maps."""
    state_keys = {name.value for name in VoltagePointName}

    assert state_keys.issubset(STATE_POINT_MACROS.keys())
    assert state_keys.issubset(QPU_STATE_MACROS.keys())
    assert set(STATE_MACRO_NAMES) == state_keys


def test_single_qubit_enum_values_are_default_keys():
    """Canonical 1Q enum names should be present in default 1Q map."""
    canonical_single_qubit_names = {name.value for name in SingleQubitMacroName}

    assert canonical_single_qubit_names.issubset(SINGLE_QUBIT_MACROS.keys())
    assert canonical_single_qubit_names.issubset(SINGLE_QUBIT_MACRO_NAMES)
    assert set(SINGLE_QUBIT_MACRO_ALIASES).issubset(SINGLE_QUBIT_MACRO_NAMES)


def test_single_qubit_aliases_map_to_supported_canonical_names():
    """Each supported alias must map to a known canonical single-qubit name."""
    canonical_single_qubit_names = {name.value for name in SingleQubitMacroName}

    assert set(SINGLE_QUBIT_MACRO_ALIAS_MAP.keys()) == set(SINGLE_QUBIT_MACRO_ALIASES)
    assert set(SINGLE_QUBIT_MACRO_ALIAS_MAP.values()).issubset(canonical_single_qubit_names)


def test_two_qubit_enum_values_are_default_keys():
    """Canonical 2Q enum names should be present in default 2Q map."""
    canonical_two_qubit_names = {name.value for name in TwoQubitMacroName}

    assert canonical_two_qubit_names.issubset(TWO_QUBIT_MACROS.keys())
    assert canonical_two_qubit_names.issubset(TWO_QUBIT_MACRO_NAMES)


def test_default_operations_match_canonical_enums():
    """Default operation registry names should match canonical enum names."""
    expected_operation_names = {
        *(name.value for name in VoltagePointName),
        *(name.value for name in SingleQubitMacroName),
        *(name.value for name in TwoQubitMacroName),
    }
    registered_operation_names = set(operations_module.operations_registry.data.keys())

    assert registered_operation_names == expected_operation_names
    assert registered_operation_names.isdisjoint(SINGLE_QUBIT_MACRO_ALIASES)
    assert expected_operation_names.issubset(operations_module.__all__)
    for operation_name in expected_operation_names:
        assert callable(getattr(operations_module, operation_name))
