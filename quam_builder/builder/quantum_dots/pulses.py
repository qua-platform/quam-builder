"""Default pulse configurations for quantum dot qubits and qubit pairs.

.. deprecated::
    This module is superseded by the macro-engine pulse wiring system.
    Use ``wire_machine_macros()`` from
    ``quam_builder.architecture.quantum_dots.macro_engine`` instead.
    Pulse defaults are now registered via ``component_pulse_catalog`` and
    applied automatically during ``wire_machine_macros()``.
"""

import warnings
from typing import Any, Literal
import numpy as np
from quam.components.pulses import GaussianPulse, SquareReadoutPulse, SquarePulse
from quam.components.channels import SingleChannel
from qualang_tools.addons.calibration.calibrations import unit
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.components import ANY_READOUT_RESONATOR, VoltageGate
from quam_builder.tools.voltage_sequence import DEFAULT_PULSE_NAME, MIN_PULSE_DURATION_NS

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


def add_default_resonator_pulses(resonator: ANY_READOUT_RESONATOR) -> None:
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
    if isinstance(resonator, ANY_READOUT_RESONATOR):
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


def add_default_baseband_pulse(voltage_gate: VoltageGate):
    """Add default square pulse to the voltage gate.
    Note that the amplitude of the default pulse is chosen based on the output mode:
        - if OPX1000 & output_mode is "amplified", then the waveform amplitude is 1.25V
        - if OPX1000 & output_mode is "direct", then the waveform amplitude is 0.25V
        - if OPX+, then the waveform amplitude is 0.25V.

        Args:
            voltage_gate: VoltageGate instance to configure.
        """
    if not isinstance(voltage_gate, str):
        if hasattr(voltage_gate.opx_output, "output_mode"):
            if voltage_gate.opx_output.output_mode == "amplified":
                voltage_gate.operations[DEFAULT_PULSE_NAME] = SquarePulse(
                    amplitude=1.25, length=MIN_PULSE_DURATION_NS
                )
            else:
                voltage_gate.operations[DEFAULT_PULSE_NAME] = SquarePulse(
                    amplitude=0.25, length=MIN_PULSE_DURATION_NS
                )
        else:
            voltage_gate.operations[DEFAULT_PULSE_NAME] = SquarePulse(
                amplitude=0.25, length=MIN_PULSE_DURATION_NS
            )
        # Add trigger pulse for the external DAC
        if len(voltage_gate.digital_outputs) > 0:
            voltage_gate.operations["trigger"] = SquarePulse(amplitude=0.0, length=1000, digital_marker="ON")

def update_output_mode_and_default_baseband_pulse(voltage_gate: VoltageGate, output_mode: Literal["amplified", "direct"]):
    """Update default square pulse of the voltage gate.
    Note that the amplitude of the default pulse is chosen based on the output mode:
        - if OPX1000 & output_mode is "amplified", then the waveform amplitude is 1.25V
        - if OPX1000 & output_mode is "direct", then the waveform amplitude is 0.25V
        - if OPX+, then the waveform amplitude is 0.25V.

        Args:
            voltage_gate: VoltageGate instance to configure.
            output_mode: The OPX1000 LF-FEM output mode. Can be "amplified" or "direct".
        """
    if not isinstance(voltage_gate, str):
        if hasattr(voltage_gate.opx_output, "output_mode"):
            voltage_gate.opx_output.output_mode = output_mode
            if voltage_gate.opx_output.output_mode == "amplified":
                voltage_gate.operations[DEFAULT_PULSE_NAME] = SquarePulse(
                    amplitude=1.25, length=MIN_PULSE_DURATION_NS
                )
            else:
                voltage_gate.operations[DEFAULT_PULSE_NAME] = SquarePulse(
                    amplitude=0.25, length=MIN_PULSE_DURATION_NS
                )
