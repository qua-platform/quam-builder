"""
# pylint: disable=duplicate-code,wrong-import-order,import-outside-toplevel,ungrouped-imports,consider-using-with,too-many-lines,too-many-branches

Full Multi-Qubit Circuit Implementation

This script implements the full circuit shown in Picture 1.png panel b:
- Initialization: Read Init sequences for qubit pairs (12, 3, 45)
- Operation: Two-qubit exchange gate
- Readout: Final measurements

The circuit structure:
1. Initialize Q1-Q2 with Read Init 12 (×2)
2. Initialize Q3 with Read Init 3
3. Initialize Q4-Q5 with Read Init 45
4. Apply two-qubit exchange operation
5. Readout all qubits
"""

# ============================================================================
# Imports
# ============================================================================
import os

from qm.qua import *
from qm import qua
from quam import QuamComponent

from quam.components import pulses
from quam.components.macro import PulseMacro
from quam.components.quantum_components import Qubit, QubitPair
from quam.utils.qua_types import QuaVariableBool
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.tools.macros.default_macros import AlignMacro, WaitMacro
from quam_builder.tools.macros.measure_macros import MeasureMacro

from quam_qd_generator_example import machine


# ============================================================================
# Configuration Parameters
# ============================================================================

# Configuration for Q1-Q2 pair (Read Init 12)
CONFIG_Q1_Q2 = {
    "voltage_points": {
        "measure_point": {
            "virtual_dot_0": -0.12,
            "virtual_dot_1": -0.12,
            "virtual_barrier_1": -0.0,
        },
        "load_point": {"virtual_dot_0": 0.12, "virtual_dot_1": 0.12, "virtual_barrier_1": 0.0},
        "exchange_point": {
            "virtual_dot_0": 0.12,
            "virtual_dot_1": 0.12,
            "virtual_barrier_1": 0.9,  # High barrier for exchange
        },
    },
    "readout": {"length": 240, "amplitude": 0.12},
    "x180": {"amplitude": 0.25, "length": 120},
    "timing": {"duration": 100, "wait_duration": 240},
    "threshold": 0.05,
}

# Configuration for Q2-Q3 pair (Read Init 3)
CONFIG_Q2_Q3 = {
    "voltage_points": {
        "measure_point": {
            "virtual_dot_0": -0.12,
            "virtual_dot_1": -0.12,
            "virtual_barrier_1": -0.0,
        },
        "load_point": {"virtual_dot_0": 0.12, "virtual_dot_1": 0.12, "virtual_barrier_1": 0.0},
        "exchange_point": {"virtual_dot_0": 0.12, "virtual_dot_1": 0.12, "virtual_barrier_1": 0.95},
    },
    "readout": {"length": 240, "amplitude": 0.12},
    "x180": {"amplitude": 0.25, "length": 120},
    "timing": {"duration": 100, "wait_duration": 240},
    "threshold": 0.05,
}

# Exchange gate timing parameters
EXCHANGE_PARAMS = {
    "ramp_duration": 50,  # Time to ramp barrier up (ns)
    "exchange_duration": 300,  # Time at high barrier (ns)
}


def configure_qubit_pair_for_reset(qubit_pair, config):
    """
    Configure a qubit pair with voltage points, readout, and conditional reset.
    Same as init_macro_improved.py but with exchange point added.
    """
    # Extract parameters from config dictionary
    voltage_points = config["voltage_points"]
    readout_params = config["readout"]
    x180_params = config["x180"]
    measure_threshold = config["threshold"]
    duration = config["timing"]["duration"]
    wait_duration = config["timing"]["wait_duration"]

    # Add Voltage Points
    for point_name, voltages in voltage_points.items():
        qubit_pair.add_point(point_name, voltages)

    # Configure Macros and Operations
    qubit_pair.macros["align"] = AlignMacro()
    qubit_pair.macros["wait"] = WaitMacro(duration=wait_duration)

    # Readout system configuration
    qubit_pair.resonator = qubit_pair.quantum_dot_pair.sensor_dots[
        0
    ].readout_resonator.get_reference()
    qubit_pair.resonator.operations["readout"] = pulses.SquareReadoutPulse(**readout_params)
    qubit_pair.macros["measure"] = MeasureMacro(
        threshold=measure_threshold, component=qubit_pair.resonator.get_reference()
    )

    # X180 pulse configuration
    qubit_pair.qubit_target.xy_channel.operations["x180"] = pulses.SquarePulse(**x180_params)
    qubit_pair.qubit_target.macros["x180"] = PulseMacro(
        pulse=qubit_pair.qubit_target.xy_channel.operations["x180"].get_reference()
    )
    qubit_pair.qubit_control.xy_channel.operations["x180"] = pulses.SquarePulse(**x180_params)
    qubit_pair.qubit_control.macros["x180"] = PulseMacro(
        pulse=qubit_pair.qubit_control.xy_channel.operations["x180"].get_reference()
    )

    # Build Complete Configuration Using Fluent API Chain
    return (
        qubit_pair
        # Configure step points
        .with_step_point("load", {"virtual_dot_1": 0.1}, duration=duration).with_ramp_point(
            "cnot",
            {"virtual_dot_1": 0.1, "virtual_dot_2": 0.3},
            duration=16,
            ramp_duration=EXCHANGE_PARAMS["exchange_duration"],
        )
    )


def _qubit_sort_key(name: str) -> int:
    try:
        return int(name.lstrip("Q"))
    except ValueError:
        return 0


qubit_names = sorted(machine.qubits.keys(), key=_qubit_sort_key)
if len(qubit_names) < 3:
    raise SystemExit("Need at least 3 qubits to run init circuit example.")

q1 = machine.get_component(qubit_names[0])
q2 = machine.get_component(qubit_names[1])
q3 = machine.get_component(qubit_names[2])

q3.with_step_point(
    "load", {"virtual_dot_1": 0.1, "virtual_dot_2": 0.3, "virtual_dot_3": 0.4}, duration=16
)

for name_a, name_b in zip(qubit_names, qubit_names[1:]):
    configure_qubit_pair_for_reset(
        machine.get_component(name_a) @ machine.get_component(name_b),
        config=CONFIG_Q2_Q3,
    )


@quam_dataclass
class InitPairMacro(QuamMacro):
    q1: str
    q2: str

    def _get_component(self, id):
        return self.parent.parent.machine.get_component(id)

    def apply(self, **kwargs):
        """Execute conditional operation for a qubit pair."""
        q1 = self._get_component(self.q1)
        q2 = self._get_component(self.q2)
        q1_q2 = q1 @ q2
        # Measure PSB
        state = q1_q2.measure()
        # Reload dots
        q1_q2.load()
        # Execute conditional pulse
        with qua.if_(state):
            q1.x180()
        return state


@quam_dataclass
class Init3Macro(QuamMacro):
    q1: str
    q2: str
    q3: str

    def _get_component(self, id):
        return self.parent.parent.machine.get_component(id)

    def apply(self, **kwargs):
        """Execute Read Init 3 sequence."""
        q1 = self._get_component(self.q1)
        q2 = self._get_component(self.q2)
        q3 = self._get_component(self.q3)
        q1_q2 = q1 @ q2
        q2_q3 = q2 @ q3
        # CNOT macro
        q2_q3.cnot()
        # Measure macro
        state = q1_q2.measure()
        # Load dots
        q1_q2.load()
        # Conditional pulse
        with qua.if_(state):
            q3.x180()
            qua.align()
        # Reload dots
        q1_q2.load()
        return state


@quam_dataclass
class InitAllMacro(QuamMacro):
    q1: str
    q2: str
    q3: str
    q4: str
    q5: str

    def _get_component(self, id):
        return self.parent.parent.machine.get_component(id)

    def apply(self, **kwargs):
        # Declare streams for saving results
        state_12_st = declare_stream()
        state_3_st = declare_stream()
        state_45_st = declare_stream()
        # Retrieve components
        q1 = self._get_component(self.q1)
        q2 = self._get_component(self.q2)
        q3 = self._get_component(self.q3)
        q4 = self._get_component(self.q4)
        q5 = self._get_component(self.q5)
        qpu = self.parent.parent
        q1_q2 = q1 @ q2
        q4_q5 = q4 @ q5
        # Load dots
        q1_q2.load()
        q3.load()
        q4_q5.load()
        # Init 12
        state_12 = qpu.init12()
        save(state_12, state_12_st)
        # 2× loop: Read Init 3 → Read Init 12
        with for_(n := declare(int), 0, n < 2, n + 1):
            state_12 = qpu.init3()
            state_3 = qpu.init12()
            save(state_12, state_12_st)
            save(state_3, state_3_st)
        # Init45
        state_45 = qpu.init45()
        save(state_45, state_45_st)
        return state_12_st, state_3_st, state_45_st


machine.qpu.macros["init12"] = InitPairMacro(q1=qubit_names[0], q2=qubit_names[1])
machine.qpu.macros["init3"] = Init3Macro(q1=qubit_names[0], q2=qubit_names[1], q3=qubit_names[2])
if len(qubit_names) >= 5:
    machine.qpu.macros["init45"] = InitPairMacro(q1=qubit_names[3], q2=qubit_names[4])
    machine.qpu.macros["initAll"] = InitAllMacro(
        q1=qubit_names[0],
        q2=qubit_names[1],
        q3=qubit_names[2],
        q4=qubit_names[3],
        q5=qubit_names[4],
    )


def build_init_circuit_program():
    q1 = machine.qubits[qubit_names[0]]
    q2 = machine.qubits[qubit_names[1]]
    q3 = machine.qubits[qubit_names[2]]
    q1_q2 = q1 @ q2

    has_q5 = len(qubit_names) >= 5
    if has_q5:
        q4 = machine.qubits[qubit_names[3]]
        q5 = machine.qubits[qubit_names[4]]
        q4_q5 = q4 @ q5

    with program() as prog:
        state_12_st = declare_stream()
        state_3_st = declare_stream()
        state_45_st = declare_stream()

        q1_q2.load()
        q3.load()
        if has_q5:
            q4_q5.load()

        state_12 = machine.qpu.init12()
        save(state_12, state_12_st)

        with for_(n := declare(int), 0, n < 2, n + 1):
            state_12 = machine.qpu.init3()
            state_3 = machine.qpu.init12()
            save(state_12, state_12_st)
            save(state_3, state_3_st)

        if has_q5:
            state_45 = machine.qpu.init45()
            save(state_45, state_45_st)

        with stream_processing():
            state_12_st.save("state_init_12")
            state_3_st.save("state_init_3")
            if has_q5:
                state_45_st.save("state_init_45")

    return prog


if __name__ == "__main__":
    from qm import QuantumMachinesManager

    prog = build_init_circuit_program()
    config = machine.generate_config()

    try:
        from configs import HOST, CLUSTER  # isort:skip
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing configs.py with HOST and CLUSTER") from exc

    qmm = QuantumMachinesManager(host=HOST, cluster_name=CLUSTER)
    qm = qmm.open_qm(config)
    job = qm.execute(prog)
    job.result_handles.wait_for_all_values()
    qm.close()
