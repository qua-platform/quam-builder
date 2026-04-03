from quam_builder.architecture.superconducting.qubit import AnyTransmon, BaseTransmon, FixedFrequencyTransmon, FluxTunableTransmon
from quam_builder.architecture.superconducting.qubit_pair import AnyTransmonPair, FixedFrequencyTransmonPair, FluxTunableTransmonPair
from quam_builder.architecture.superconducting.custom_gates import MeasureMacro, ResetMacro, VirtualZMacro, DelayMacro, IdMacro
from quam_builder.architecture.superconducting.custom_gates.flux_tunable_transmon_pair.two_qubit_gates import CZGate
from quam.components.macro import PulseMacro

def add_default_transmon_macros(transmon: AnyTransmon):
    """Adds default macros to a transmon qubit.
    """

    transmon.macros = {
        "x": PulseMacro(pulse="x180"),
        "y": PulseMacro(pulse="y180"),
        "sx": PulseMacro(pulse="x90"),
        "sy": PulseMacro(pulse="y90"),
        "rz": VirtualZMacro(),
        "delay": DelayMacro(),
        "id": IdMacro(),
        "measure": MeasureMacro(pulse="readout"),
        "reset": ResetMacro(reset_type="active", pi_pulse="x180", readout_pulse="readout"),

    }