"""Measurement macros for quantum dot qubits."""

from qm import qua
from quam import QuamComponent
from quam.core import quam_dataclass
from quam.core.macro.quam_macro import QuamMacro
from quam.utils.qua_types import QuaVariableBool

__all__ = [
    "MeasureMacro",
]


@quam_dataclass
class MeasureMacro(QuamMacro):
    """Macro for qubit state measurement with threshold discrimination.

    Performs I/Q measurement and thresholds I value to determine qubit state.

    Attributes:
        threshold: Threshold for state discrimination (I > threshold → excited state)
        component: QuamComponent to measure
    """

    threshold: float
    component: QuamComponent

    def apply(self, **kwargs) -> QuaVariableBool:
        """Execute measurement and return qubit state.

        Returns:
            Boolean QUA variable indicating qubit state (True = excited)
        """
        I, Q = self.component.measure("readout")
        state = qua.declare(bool)
        qua.assign(state, I > self.threshold)
        return state