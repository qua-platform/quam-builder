"""Exchange-only qubit state macros.

These macros are intended for :class:`ExchangeOnlyQubit` components. Unlike
the LD single-qubit state macros, EO initialization and measurement are
expected to coordinate the qubit's ``jn_pair`` and ``jz_pair`` explicitly
rather than delegating through a single preferred readout pair.
"""

from __future__ import annotations

from typing import Literal

from quam.components.macro import QubitMacro
from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    _owner_component,
    InitializeStateMacro,
    MeasurePSBPairMacro,
    EmptyStateMacro, 
    ExchangeStateMacro,
)

__all__ = [
    "EOExchangeAxisInitializeMacro",
    "EOExchangeAxisMeasureMacro",
    "EOExchangeAxisEmptyMacro", 
    "EOExchangeAxisExchangeMacro",
    "EOInitialize1QMacro",
    "EOMeasure1QMacro",
    "EOEmpty1QMacro",
    "EOExchange1QMacro",
    "EO_STATE_MACROS",
]

EOExchangeAxisInitializeMacro = InitializeStateMacro
EOExchangeAxisMeasureMacro = MeasurePSBPairMacro
EOExchangeAxisEmptyMacro = EmptyStateMacro
EOExchangeAxisExchangeMacro = ExchangeStateMacro


EO_STATE_MACROS = {
    VoltagePointName.INITIALIZE.value: EOExchangeAxisInitializeMacro,
    VoltagePointName.MEASURE.value: EOExchangeAxisMeasureMacro,
    VoltagePointName.EMPTY.value: EOExchangeAxisEmptyMacro,
    SingleQubitMacroName.EXCHANGE.value: EOExchangeAxisExchangeMacro,
}
