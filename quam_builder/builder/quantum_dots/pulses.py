"""Default pulse configurations for quantum dot qubits and qubit pairs."""

from typing import Union
import numpy as np
from quam.components.pulses import GaussianPulse, SquareReadoutPulse, DragPulse
from qualang_tools.addons.calibration.calibrations import unit
from quam_builder.architecture.quantum_dots.qubit import LDQubit

u = unit(coerce_to_integer=True)


def add_default_ldv_qubit_pulses(qubit: LDQubit):
    """Adds default pulses for Loss-DiVincenzo qubits (ESR/MW drive and readout).

    This function adds a set of standard pulses to a Loss-DiVincenzo qubit, including:
    - Single-qubit rotation pulses (X180, X90, Y180, Y90) on the ESR/MW drive channel
    - Readout pulses on the resonator channel (if present)

    Args:
        qubit (LDQubit): The Loss-DiVincenzo qubit to which pulses will be added.
    """
    # ESR/MW drive pulses (if xy channel exists)
    if hasattr(qubit, "xy") and qubit.xy is not None:
        pulse_length = 1000  # ns
        pulse_amp = 0.2
        sigma = pulse_length / 6

        # X rotations
        qubit.xy.operations["x180"] = GaussianPulse(
            id="x180",
            length=pulse_length,
            amplitude=pulse_amp,
            sigma=sigma,
            axis_angle=0.0,
        )

        qubit.xy.operations["x90"] = GaussianPulse(
            id="x90",
            length=pulse_length,
            amplitude=pulse_amp / 2,
            sigma=sigma,
            axis_angle=0.0,
        )

        # Y rotations
        qubit.xy.operations["y180"] = GaussianPulse(
            id="y180",
            length=pulse_length,
            amplitude=pulse_amp,
            sigma=sigma,
            axis_angle=float(np.pi / 2),
        )

        qubit.xy.operations["y90"] = GaussianPulse(
            id="y90",
            length=pulse_length,
            amplitude=pulse_amp / 2,
            sigma=sigma,
            axis_angle=float(np.pi / 2),
        )

        # Minus rotations (useful for pulse sequences)
        qubit.xy.operations["-x90"] = GaussianPulse(
            id="-x90",
            length=pulse_length,
            amplitude=-pulse_amp / 2,
            sigma=sigma,
            axis_angle=0.0,
        )

        qubit.xy.operations["-y90"] = GaussianPulse(
            id="-y90",
            length=pulse_length,
            amplitude=-pulse_amp / 2,
            sigma=sigma,
            axis_angle=float(np.pi / 2),
        )

    # Readout pulses (if resonator exists)
    if hasattr(qubit, "resonator") and qubit.resonator is not None:
        readout_length = 2000  # ns
        readout_amp = 0.1

        qubit.resonator.operations["readout"] = SquareReadoutPulse(
            id="readout",
            length=readout_length,
            amplitude=readout_amp,
        )


def add_default_ldv_qubit_pair_pulses(qubit_pair):
    """Adds default pulses for Loss-DiVincenzo qubit pairs (two-qubit gates).

    This function adds a set of standard two-qubit gate pulses, such as:
    - Exchange interaction pulses (J-coupling)
    - Virtual Z-rotations for controlling the interaction

    Note: This is a placeholder implementation. The actual pulse parameters depend
    on the specific two-qubit gate mechanism used in your quantum dot system.

    Args:
        qubit_pair: The qubit pair to which pulses will be added.
    """
    # Two-qubit gate pulses (if applicable)
    # This is highly system-dependent and should be customized based on
    # your specific quantum dot coupling mechanism (exchange, tunnel coupling, etc.)

    # Example: Exchange interaction pulse
    if hasattr(qubit_pair, "z") and qubit_pair.z is not None:
        # Placeholder for exchange/coupling pulses
        # In practice, this would involve voltage pulses on the barrier gate
        # to control the exchange interaction between the two quantum dots
        pass

    # Note: For quantum dots, two-qubit gates often involve complex pulse sequences
    # on multiple gates (barrier, plungers) and may require calibration-specific parameters.
    # Users should customize this function based on their specific implementation.