"""Tests for :class:`VoltageBalancedMacroCatalog`."""

from quam_builder.architecture.quantum_dots.components.quantum_dot_pair import (
    QuantumDotPair,
)
from quam_builder.architecture.quantum_dots.components.sensor_dot import SensorDot
from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    VoltageBalancedMacroCatalog,
)
from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName
from quam_builder.architecture.quantum_dots.operations.voltage_balanced_macros.state_macros import (
    BalancedEmptyMacro,
    BalancedHeraldedInitializeMacro,
    BalancedMeasurePSBPairMacro,
    BalancedSensorDotMeasureMacro,
)
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair


def test_voltage_balanced_catalog_maps_expected_types() -> None:
    cat = VoltageBalancedMacroCatalog()
    assert cat.priority == 200

    # LDQubitPair macro mappings are intentionally not asserted here:
    # CZ is a specific calibrated exchange-derived gate, and is not equivalent to
    # a generic "exchange" macro. Keep the catalog free to evolve without
    # conflating these semantics in a type-level test.

    qdp = cat.get_factories(QuantumDotPair)
    assert qdp[VoltagePointName.INITIALIZE.value] is BalancedHeraldedInitializeMacro
    assert qdp[VoltagePointName.EMPTY.value] is BalancedEmptyMacro
    assert qdp[VoltagePointName.MEASURE.value] is BalancedMeasurePSBPairMacro

    sensor = cat.get_factories(SensorDot)
    assert sensor[VoltagePointName.MEASURE] is BalancedSensorDotMeasureMacro
