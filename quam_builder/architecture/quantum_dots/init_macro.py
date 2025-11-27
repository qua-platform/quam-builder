from quam.components import StickyChannelAddon, pulses
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    LFFEMAnalogInputPort,
    MWFEMAnalogOutputPort
)

from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDrive
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle, VoltagePointMacroMixin
from qm.qua import *

from typing import Union
# Import gate-level operations for cleaner QUA code
from quam_builder.architecture.quantum_dots.operations import (
    idle,
    readout,
    x180,
    y180,
    x90,
    y90,
    rabi, operations_registry,
)

from quam_qd_generator_example import machine

config = machine.generate_config()

from quam.components.macro import QubitMacro, QubitPairMacro, PulseMacro
from quam.components.quantum_components import QuantumComponent, Qubit, QubitPair
from quam.components.pulses import Pulse

from quam.utils.qua_types import QuaVariableBool
from quam import quam_dataclass
from qm import qua

@quam_dataclass
class MeasureMacro(QubitPairMacro):
    threshold: float

    def apply(self, **kwargs) -> QuaVariableBool:
        # The macro reads I/Q data from the resonator channel.
        I, Q = self.qubit_pair.quantum_dot_pair.sensor_dots[0].readout_resonator.measure("readout")
        # We declare a QUA variable to store the boolean result of thresholding the I value.
        qubit_state = qua.declare(bool)
        qua.assign(qubit_state, I > self.threshold)
        return qubit_state


qubit_pair_id = 'Q0_Q1'
qubit_pair = machine.qubit_pairs[qubit_pair_id]

(qubit_pair
     .with_ramp_point("load", {"virtual_dot_0": 0.3}, hold_duration=200, ramp_duration=500)
     .with_step_point("sweetspot", {"virtual_dot_0": 0.22}, hold_duration=200)
     .with_sequence("init_ramp", ["load", "sweetspot"])
     )


qubit_pair.quantum_dot_pair.sensor_dots[0].readout_resonator.operations["readout"] = pulses.SquareReadoutPulse(
    length=1000, amplitude=0.1, threshold=0.215
)
qubit_pair.macros["measure"] = MeasureMacro(threshold=0.215)

qubit_pair.qubit_target.xy_channel.operations["x180"] = pulses.SquarePulse(amplitude=0.2, length=100)
qubit_pair.qubit_target.macros["x180"] = PulseMacro(pulse=qubit_pair.qubit_target.xy_channel.operations["x180"].get_reference())

@operations_registry.register_operation
def measure(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    pass

@operations_registry.register_operation
def x180(qubit: Qubit, **kwargs) -> QuaVariableBool:
    pass

@quam_dataclass
class ConditionalMacro(QubitMacro):
    measure_macro: Union[Pulse, str]
    pulse_macro: Union[Pulse, str]

    def apply(self, *, amplitude_scale=None, duration=None, **kwargs):
        state = self.measure_macro.apply()

        # Apply a conditional π-pulse if qubit is in excited state
        with qua.if_(state):
            self.pulse_macro.apply(
                amplitude_scale=amplitude_scale, duration=duration, **kwargs  # type: ignore
            )
        return state

    @property
    def inferred_duration(self) -> float:
        return (self.pulse.length + self.measure.length) * 1e-9

qubit_pair.macros['reset'] = ConditionalMacro(
    measure_macro=qubit_pair.macros['measure'].get_reference(),
    pulse_macro=qubit_pair.qubit_target.macros['x180'].get_reference()
)


qubit_pair.with_sequence(
    'reset_sequence',
    ["init_ramp", "reset"]
)

@operations_registry.register_operation
def measure(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    pass

@operations_registry.register_operation
def x180(qubit: Qubit, **kwargs) -> QuaVariableBool:
    pass

@operations_registry.register_operation
def reset(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    pass

@operations_registry.register_operation
def reset_sequence(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    pass

with program() as prog:
    measure(qubit_pair)
    x180(qubit_pair.qubit_target)
    reset(qubit_pair)
    reset_sequence(qubit_pair)
    qubit_pair.reset_sequence()


from qm import QuantumMachinesManager, SimulationConfig
qmm = QuantumMachinesManager(host = "172.16.33.115", cluster_name="CS_3")

qm = qmm.open_qm(config)


# Send the QUA program to the OPX, which compiles and executes it - Execute does not block python!
job = qm.execute(prog)
