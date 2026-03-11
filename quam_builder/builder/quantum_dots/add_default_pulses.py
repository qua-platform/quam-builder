"""Default pulse configurations for quantum dot qubits and qubit pairs.

.. deprecated::
    This module is superseded by the macro-engine pulse wiring system.
    Use ``wire_machine_macros()`` from
    ``quam_builder.architecture.quantum_dots.macro_engine`` instead.
    Pulse defaults are now registered via ``component_pulse_catalog`` and
    applied automatically during ``wire_machine_macros()``.
"""

import warnings
from typing import Any, Union
import numpy as np
from quam.components.pulses import GaussianPulse, SquareReadoutPulse, DragPulse
from quam.components.channels import SingleChannel
from qualang_tools.addons.calibration.calibrations import unit
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorBase

u = unit(coerce_to_integer=True)


def add_default_ldv_qubit_pulses(qubit: LDQubit) -> None:
    """Add default Gaussian pulses for Loss-DiVincenzo qubit single-qubit gates.

    .. deprecated::
        Use ``wire_machine_macros()`` instead. Pulses are now wired automatically.

    Args:
        qubit: Loss-DiVincenzo qubit instance to configure.
    """
    warnings.warn(
        "add_default_ldv_qubit_pulses() is deprecated. "
        "Use wire_machine_macros() from quam_builder.architecture.quantum_dots.macro_engine instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # ESR/MW drive pulses (if xy exists)
    if hasattr(qubit, "xy") and qubit.xy is not None:
        pulse_length = 1000  # ns
        pulse_amp = 0.2
        sigma = pulse_length / 6

        # SingleChannel (XYDriveSingle) uses real-valued waveforms only.
        # IQ/MW channels use axis_angle for hardware IQ mixing.
        # Y-axis rotations on SingleChannel are handled by the macro engine
        # via virtual_z frame rotation, so no axis_angle is needed.
        is_single = isinstance(qubit.xy, SingleChannel)
        x_angle = None if is_single else 0.0
        y_angle = None if is_single else float(np.pi / 2)

        qubit.xy.operations["x180"] = GaussianPulse(
            id="x180",
            length=pulse_length,
            amplitude=pulse_amp,
            sigma=sigma,
            axis_angle=x_angle,
        )

        qubit.xy.operations["x90"] = GaussianPulse(
            id="x90",
            length=pulse_length,
            amplitude=pulse_amp / 2,
            sigma=sigma,
            axis_angle=x_angle,
        )

        qubit.xy.operations["y180"] = GaussianPulse(
            id="y180",
            length=pulse_length,
            amplitude=pulse_amp,
            sigma=sigma,
            axis_angle=y_angle,
        )

        qubit.xy.operations["y90"] = GaussianPulse(
            id="y90",
            length=pulse_length,
            amplitude=pulse_amp / 2,
            sigma=sigma,
            axis_angle=y_angle,
        )

        qubit.xy.operations["-x90"] = GaussianPulse(
            id="-x90",
            length=pulse_length,
            amplitude=-pulse_amp / 2,
            sigma=sigma,
            axis_angle=x_angle,
        )

        qubit.xy.operations["-y90"] = GaussianPulse(
            id="-y90",
            length=pulse_length,
            amplitude=-pulse_amp / 2,
            sigma=sigma,
            axis_angle=y_angle,
        )


def add_default_resonator_pulses(resonator: ReadoutResonatorBase) -> None:
    """Add default square readout pulse to sensor resonator.

    .. deprecated::
        Use ``wire_machine_macros()`` instead. Pulses are now wired automatically.

    Args:
        resonator: Readout resonator instance to configure.
    """
    warnings.warn(
        "add_default_resonator_pulses() is deprecated. "
        "Use wire_machine_macros() from quam_builder.architecture.quantum_dots.macro_engine instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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

    .. deprecated::
        Use ``wire_machine_macros()`` instead. Pulses are now wired automatically.

    Args:
        qubit_pair: Qubit pair instance to configure.
    """
    warnings.warn(
        "add_default_ldv_qubit_pair_pulses() is deprecated. "
        "Use wire_machine_macros() from quam_builder.architecture.quantum_dots.macro_engine instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    pass
