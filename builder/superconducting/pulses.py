from quam.components import pulses
from qualang_tools.units import unit
from quam_builder.architecture.superconducting.qubit import FixedFrequencyTransmon, FluxTunableTransmon
import numpy as np
from typing import Union

# Class containing tools to help handling units and conversions.
u = unit(coerce_to_integer=True)


def add_default_transmon_pulses(transmon: Union[FixedFrequencyTransmon, FluxTunableTransmon]):
    # TODO: Make gates amplitude a reference to x180 amplitude
    if transmon.xy is not None:
        transmon.xy.operations["x180_DragCosine"] = pulses.DragCosinePulse(
            amplitude=0.1,
            alpha=0.0,
            anharmonicity=f"#/qubits/{transmon.name}/anharmonicity",
            length=32,
            axis_angle=0,
            detuning=0,
            digital_marker="ON",
        )
        transmon.xy.operations["x90_DragCosine"] = pulses.DragCosinePulse(
            amplitude=0.1 / 2,
            alpha="#../x180_DragCosine/alpha",
            anharmonicity="#../x180_DragCosine/anharmonicity",
            length="#../x180_DragCosine/length",
            axis_angle=0,
            detuning=0,
            digital_marker="ON",
        )
        transmon.xy.operations["-x90_DragCosine"] = pulses.DragCosinePulse(
            amplitude="#../x90_DragCosine/amplitude",
            alpha="#../x90_DragCosine/alpha",
            anharmonicity="#../x180_DragCosine/anharmonicity",
            length="#../x180_DragCosine/length",
            axis_angle=np.pi,
            detuning="#../x180_DragCosine/detuning",
            digital_marker="ON",
        )
        transmon.xy.operations["y180_DragCosine"] = pulses.DragCosinePulse(
            amplitude="#../x180_DragCosine/amplitude",
            alpha="#../x180_DragCosine/alpha",
            anharmonicity="#../x180_DragCosine/anharmonicity",
            length="#../x180_DragCosine/length",
            axis_angle=np.pi / 2,
            detuning="#../x180_DragCosine/detuning",
            digital_marker="ON",
        )
        transmon.xy.operations["y90_DragCosine"] = pulses.DragCosinePulse(
            amplitude="#../x90_DragCosine/amplitude",
            alpha="#../x90_DragCosine/alpha",
            anharmonicity="#../x180_DragCosine/anharmonicity",
            length="#../x180_DragCosine/length",
            axis_angle=np.pi / 2,
            detuning="#../x90_DragCosine/detuning",
            digital_marker="ON",
        )
        transmon.xy.operations["-y90_DragCosine"] = pulses.DragCosinePulse(
            amplitude="#../x90_DragCosine/amplitude",
            alpha="#../x90_DragCosine/alpha",
            anharmonicity="#../x180_DragCosine/anharmonicity",
            length="#../x180_DragCosine/length",
            detuning="#../x90_DragCosine/detuning",
            axis_angle=-np.pi / 2,
            digital_marker="ON",
        )
        transmon.xy.operations["x180_Square"] = pulses.SquarePulse(
            amplitude=0.25, length=100, axis_angle=0, digital_marker="ON"
        )
        transmon.xy.operations["x90_Square"] = pulses.SquarePulse(
            amplitude=0.25 / 2, length="#../x180_Square/length", axis_angle=0, digital_marker="ON"
        )
        transmon.xy.operations["-x90_Square"] = pulses.SquarePulse(
            amplitude=-0.25 / 2, length="#../x180_Square/length", axis_angle=0, digital_marker="ON"
        )
        transmon.xy.operations["y180_Square"] = pulses.SquarePulse(
            amplitude=0.25, length="#../x180_Square/length", axis_angle=90, digital_marker="ON"
        )
        transmon.xy.operations["y90_Square"] = pulses.SquarePulse(
            amplitude=0.25 / 2, length="#../x180_Square/length", axis_angle=90, digital_marker="ON"
        )
        transmon.xy.operations["-y90_Square"] = pulses.SquarePulse(
            amplitude=-0.25 / 2, length="#../x180_Square/length", axis_angle=90, digital_marker="ON"
        )
        transmon.set_gate_shape("DragCosine")

        transmon.xy.operations["saturation"] = pulses.SquarePulse(
            amplitude=0.25, length=20 * u.us, axis_angle=0, digital_marker="ON"
        )

    if hasattr(transmon, "z"):  # TODO: maybe these two line can be combined...
        if transmon.z is not None:
            transmon.z.operations["const"] = pulses.SquarePulse(amplitude=0.1, length=100)

    if hasattr(transmon, "resonator"):
        if transmon.resonator is not None:
            transmon.resonator.operations["readout"] = pulses.SquareReadoutPulse(
                length=1024 * u.ns, amplitude=0.01, threshold=0.0, digital_marker="ON"
            )
            transmon.resonator.operations["const"] = pulses.SquarePulse(amplitude=0.125, length=100)


def add_default_transmon_pair_pulses(transmon_pair):
    if hasattr(transmon_pair, "coupler"):
        if transmon_pair.coupler is not None:
            transmon_pair.coupler.operations["const"] = pulses.SquarePulse(amplitude=0.1, length=100)
    if hasattr(transmon_pair, "cross_resonance"):
        if transmon_pair.cross_resonance is not None:
            transmon_pair.cross_resonance.operations["square"] = pulses.SquarePulse(amplitude=0.1, length=100)
    if hasattr(transmon_pair, "zz_drive"):
        if transmon_pair.zz_drive is not None:
            transmon_pair.zz_drive.operations["square"] = pulses.SquarePulse(amplitude=0.1, length=100)
