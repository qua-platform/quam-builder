"""Default pulse configurations for quantum dot qubits and qubit pairs.

This module provides functions to add standard pulse configurations to
Loss-DiVincenzo qubits, including:
- Single-qubit rotation pulses (X and Y rotations at 90° and 180°)
- Readout pulses for sensor resonators
- Placeholder two-qubit gate pulses for qubit pairs
"""

from typing import Any, Union
import numpy as np
from quam.components.pulses import GaussianPulse, SquareReadoutPulse, DragPulse
from qualang_tools.addons.calibration.calibrations import unit
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorBase

u = unit(coerce_to_integer=True)


def add_default_ldv_qubit_pulses(qubit: LDQubit) -> None:
    """Add default Gaussian pulses for Loss-DiVincenzo qubit single-qubit gates.

    Configures standard single-qubit rotation pulses using Gaussian envelopes:
    - X and Y rotations at 180° (pi pulses)
    - X and Y rotations at ±90° (pi/2 pulses)

    Default pulse parameters:
    - Length: 1000 ns
    - Amplitude: 0.2 (180°), 0.1 (90°)
    - Sigma: length / 6 (for Gaussian envelope)

    Pulses are added to the qubit's xy_channel (ESR/MW drive) if present.

    Args:
        qubit: Loss-DiVincenzo qubit instance to configure.

    Note:
        These are placeholder values. Actual pulse parameters should be determined
        through calibration for your specific quantum dot device.
    """
    # ESR/MW drive pulses (if xy_channel exists)
    if hasattr(qubit, "xy_channel") and qubit.xy is not None:
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


def add_default_resonator_pulses(resonator: ReadoutResonatorBase) -> None:
    """Add default square readout pulse to sensor resonator.

    Configures a square readout pulse for charge sensing via the readout resonator.

    Default pulse parameters:
    - Length: 2000 ns
    - Amplitude: 0.1

    Args:
        resonator: Readout resonator instance to configure.

    Note:
        These are placeholder values. Actual readout pulse parameters should be
        optimized through calibration to maximize SNR for your sensor dot system.
    """
    readout_length = 2000  # ns
    readout_amp = 0.1
    if isinstance(resonator, ReadoutResonatorBase):
        resonator.operations["readout"] = SquareReadoutPulse(
            id="readout",
            length=readout_length,
            amplitude=readout_amp,
        )


def add_default_ldv_qubit_pair_pulses(qubit_pair: Any) -> None:
    """Placeholder for adding two-qubit gate pulses to qubit pairs.

    Two-qubit gates in quantum dot systems typically involve:
    - Barrier gate voltage pulses to control exchange coupling
    - Coordinated plunger gate adjustments
    - Timing-critical pulse sequences

    This function is currently a placeholder. Implementations are highly
    system-specific and depend on:
    - Exchange coupling mechanism (direct exchange, virtual gates, etc.)
    - Device geometry and materials
    - Operating regime (singlet-triplet, loss-divincenzo, hybrid, etc.)

    Args:
        qubit_pair: Qubit pair instance to configure.

    Note:
        Users should implement custom two-qubit gate calibrations based on
        their specific quantum dot architecture and coupling mechanism.
    """
    # Placeholder implementation
    # In production, this would configure exchange pulses, SWAP gates, CZ gates, etc.
    # Example structure:
    # if hasattr(qubit_pair, "barrier_channel"):
    #     qubit_pair.barrier_channel.operations["exchange"] = pulse_config
    pass
