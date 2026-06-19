"""Tests for :class:`VoltageBalancedMacroCatalog`."""

from quam_builder.architecture.quantum_dots.components.quantum_dot_pair import (
    QuantumDotPair,
)
from quam_builder.architecture.quantum_dots.components.sensor_dot import SensorDot
from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    VoltageBalancedMacroCatalog,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.operations.voltage_balanced_macros.single_qubit_macros import (
    BalancedXYDriveMacro,
)
from quam_builder.architecture.quantum_dots.operations.voltage_balanced_macros.state_macros import (
    BalancedEmptyMacro,
    BalancedInitializeMacro,
    BalancedMeasurePSBPairMacro,
    BalancedSensorDotMeasureMacro,
)
from quam_builder.architecture.quantum_dots.operations.voltage_balanced_macros.two_qubit_macros import (
    BalancedExchange2QMacro,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair


def test_voltage_balanced_catalog_maps_expected_types() -> None:
    cat = VoltageBalancedMacroCatalog()
    assert cat.priority == 200

    q1 = cat.get_factories(LDQubit)
    assert q1[SingleQubitMacroName.XY_DRIVE.value] is BalancedXYDriveMacro

    qp2 = cat.get_factories(LDQubitPair)
    assert qp2[TwoQubitMacroName.EXCHANGE.value] is BalancedExchange2QMacro

    qdp = cat.get_factories(QuantumDotPair)
    assert qdp[VoltagePointName.INITIALIZE.value] is BalancedInitializeMacro
    assert qdp[VoltagePointName.EMPTY.value] is BalancedEmptyMacro
    assert qdp[VoltagePointName.MEASURE.value] is BalancedMeasurePSBPairMacro

    sensor = cat.get_factories(SensorDot)
    assert sensor[VoltagePointName.MEASURE] is BalancedSensorDotMeasureMacro
