from typing import Union, Any
from dataclasses import field

import numpy as np

from quam.components.macro import QubitPairMacro
from quam.components.pulses import Pulse
from quam.core import quam_dataclass

__all__ = ["CZGate"]


def get_pulse_name(pulse: Pulse) -> str:
    """
    Get the name of the pulse. If the pulse has an id, return it.
    """
    if pulse.id is not None:
        return pulse.id
    elif pulse.parent is not None:
        return pulse.parent.get_attr_name(pulse)
    else:
        raise AttributeError(
            f"Cannot infer id of {pulse} because it is not attached to a parent"
        )


@quam_dataclass
class CZGate(QubitPairMacro):
    """
    Implements a flux‑activated controlled-Z (CZ) two‑qubit entangling gate for a
    flux‑tunable transmon pair (optionally mediated by a tunable coupler).

    The CZGate coordinates:
    1. A Z/flux pulse applied to the control qubit.
    2. (Optionally) a simultaneous flux pulse on a tunable coupler.
    3. Frame (virtual Z) phase corrections on control and target qubits.
    4. A final alignment between the involved elements.

    Attributes
    ----------
    flux_pulse_control : Union[Pulse, str]
         Pulse (or its name) applied on the control qubit Z (flux) line to enact the interaction.
    coupler_flux_pulse : Pulse | None
         Optional pulse applied to the tunable coupler during the gate (None for fixed coupler).
    phase_shift_control : float
         Default frame rotation (in units of 2π) applied to the control qubit after flux interaction
         if no per‑call override is provided. Ignored if its magnitude < 1e-6.
    phase_shift_target : float
         Default frame rotation (in units of 2π) applied to the target qubit after flux interaction
         if not overridden and |value| > 1e-6.
    spectator_qubits: list[str]
         Optional list of spectator qubit names.
    spectator_qubits_control: dict[str, Pulse]
         Optional dictionary of spectator qubit control pulses and their parameters.
    spectator_qubits_phase_shift: dict[str, float]
         Optional dictionary of spectator qubit phase shifts and their parameters.
    fidelity: Dict[str, Any]
         Collection of gate fidelity (e.g. fidelity["RB"]=xx, fidelity["XEB"]=xx).
    extras: Dict[str, Any]
         Additional attributes for the CZGate.

    Properties
    ----------
    flux_pulse_control_label : str
         Resolved (final) label of the control qubit flux pulse (name extraction via get_pulse_name).
    coupler_flux_pulse_label : str
         Resolved (final) label of the coupler pulse (if provided).

    Methods
    -------
    apply(*, amplitude_scale_control=None, amplitude_scale_coupler=None,
            phase_shift_control=None, phase_shift_target=None, **kwargs) -> None
         Execute the CZ gate sequence.
         Parameters:
              amplitude_scale_control : float | None
                    Scalar multiplier for the control qubit flux pulse amplitude (passed through to play()).
              amplitude_scale_coupler : float | None
                    Scalar multiplier for the coupler pulse amplitude (only used if coupler_flux_pulse is set).
              phase_shift_control : float | None
                    Per‑call override for control qubit frame rotation (2π units). If None, falls back
                    to phase_shift_control attribute (when significant).
              phase_shift_target : float | None
                    Per‑call override for target qubit frame rotation (2π units). If None, falls back
                    to phase_shift_target attribute (when significant).
              **kwargs :
                    Ignored auxiliary keyword arguments (accepted for interface compatibility).

         Behavior:
              - Plays control qubit flux pulse (with optional amplitude scaling).
              - Optionally plays coupler pulse in parallel.
              - Aligns both resources.
              - Applies virtual Z frame rotations (overrides take precedence; negligible defaults skipped).
              - Inserts zero‑amplitude, fixed‑duration placeholder XY pulses on both qubits for
                 timing / phase bookkeeping.
              - Performs a final align to ensure deterministic end-of-gate synchronization.

    Usage Notes
    -----------
    - Virtual Z rotations are in units of full turns (i.e., value = 0.25 corresponds to π/2).
    - Provide per‑invocation phase_shift_* arguments to dynamically correct accumulated phases
      from calibration drifts or echo structures.
    - amplitude_scale_* enables fast parametric scaling during calibration sweeps without
      reconstructing pulse objects.
    """

    flux_pulse_control: Union[Pulse, str]
    coupler_flux_pulse: Pulse = None

    phase_shift_control: float = 0.0
    phase_shift_target: float = 0.0

    spectator_qubits: list[str] = field(default_factory=list)
    spectator_qubits_control: dict[str, Pulse] = field(default_factory=dict)
    spectator_qubits_phase_shift: dict[str, float] = field(default_factory=dict)
    
    fidelity: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def flux_pulse_control_label(self) -> str:
        pulse = (
            self.qubit_control.get_pulse(self.flux_pulse_control)
            if isinstance(self.flux_pulse_control, str)
            else self.flux_pulse_control
        )
        return get_pulse_name(pulse)

    @property
    def coupler_flux_pulse_label(self) -> str:
        pulse = (
            self.coupler.get_pulse(self.coupler_flux_pulse)
            if isinstance(self.coupler_flux_pulse, str)
            else self.coupler_flux_pulse
        )
        return get_pulse_name(pulse)

    def apply(
        self,
        *,
        amplitude_scale_control=None,
        amplitude_scale_coupler=None,
        phase_shift_control=None,
        phase_shift_target=None,
        **kwargs,
        
    ) -> None:
        
        # control qubit flux
        self.qubit_pair.qubit_control.z.play(
            self.flux_pulse_control_label,
            amplitude_scale=amplitude_scale_control,
        )

        # spectator qubits flux
        for qubit_name, pulse in self.spectator_qubits_control.items():
            self.spectator_qubits[qubit_name].z.play(
                get_pulse_name(pulse)
            )

        # coupler flux
        if self.coupler_flux_pulse is not None:
            self.qubit_pair.coupler.play(
                self.coupler_flux_pulse_label,
                validate=False,
                amplitude_scale=amplitude_scale_coupler,
            )

        self.qubit_pair.qubit_control.align([self.qubit_pair.qubit_target] + list(self.spectator_qubits.values()))
        if phase_shift_control is not None:
            self.qubit_pair.qubit_control.xy.frame_rotation_2pi(phase_shift_control)
        elif np.abs(self.phase_shift_control) > 1e-6:
            self.qubit_pair.qubit_control.xy.frame_rotation_2pi(
                self.phase_shift_control
            )
        if phase_shift_target is not None:
            self.qubit_pair.qubit_target.xy.frame_rotation_2pi(phase_shift_target)
        elif np.abs(self.phase_shift_target) > 1e-6:
            self.qubit_pair.qubit_target.xy.frame_rotation_2pi(self.phase_shift_target)

        for qubit_name, phase_shift in self.spectator_qubits_phase_shift.items():
            self.spectator_qubits[qubit_name].xy.frame_rotation_2pi(phase_shift)

        # final alignment
        self.qubit_pair.qubit_control.align([self.qubit_pair.qubit_target] + list(self.spectator_qubits.values()))
