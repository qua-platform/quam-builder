from typing import Union, Any
from dataclasses import field

import numpy as np

from quam.components.macro import QubitPairMacro
from quam.components.pulses import Pulse
from quam.core import quam_dataclass
from quam.utils.qua_types import (
    ScalarInt
)
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
    fidelity: Dict[str, Any]
         Collection of gate fidelity (e.g. fidelity["RB"]=xx, fidelity["XEB"]=xx).
    extras: Dict[str, Any]
         Additional attributes for the CZGate.
    duration_control: ScalarInt
         Optional duration override for the control qubit flux pulse.

    Spectator Qubits
    ----------------
    Spectator qubits are additional qubits that need to be controlled during the CZ gate operation
    but are not the control or target qubits of the gate. This is useful for:
    - Compensating for crosstalk: applying compensating flux pulses to nearby qubits to prevent
      unwanted frequency shifts during the CZ gate.
    - Maintaining qubit states: keeping spectator qubits in specific states during the gate.
    - Multi-qubit gate synchronization: ensuring all qubits are properly aligned and synchronized.
    
    The three spectator qubit parameters work together:
    - ``spectator_qubits``: Dictionary mapping qubit names (str) to qubit objects. These are the
      qubit instances that will be controlled during the gate.
    - ``spectator_qubits_control``: Dictionary mapping the same qubit names (str) to Pulse objects.
      These pulses are applied to the spectator qubits' Z (flux) lines simultaneously with the
      control qubit flux pulse.
    - ``spectator_qubits_phase_shift``: Dictionary mapping qubit names (str) to phase shift values
      (float, in units of 2π). These frame rotations are applied to the spectator qubits after
      the flux pulses, similar to phase_shift_control and phase_shift_target.
    
    Usage Example:
    ```python
    # Configure spectator qubits for crosstalk compensation
    cz_gate.spectator_qubits = {
        "q1": qubit_q1,  # Nearby qubit that needs compensation
        "q2": qubit_q2   # Another spectator qubit
    }
    cz_gate.spectator_qubits_control = {
        "q1": {
            "id": "cz_spectator_pulse_qD1",
            "length": 48,
            "__class__": "quam.components.pulses.SquarePulse",
            "amplitude": 0.04
        },
        "q2": {
            "id": "cz_spectator_pulse_qD2",
            "length": 44,
            "__class__": "quam.components.pulses.FlatTopGaussianPulse",
            "amplitude": 0.05
        }
    }
    cz_gate.spectator_qubits_phase_shift = {
        "q1": 0.01,  # Small phase correction for q1 (0.01 * 2π)
        "q2": 0.0    # No phase correction needed for q2
    }
    
    # When apply() is called, spectator qubits will:
    # 1. Be aligned with control and target qubits
    # 2. Have their flux pulses played in parallel with the control qubit pulse
    # 3. Receive phase corrections after the gate
    cz_gate.apply()
    ```
    Note: The keys in all three dictionaries must match (same qubit names). Only qubits listed
    in both ``spectator_qubits`` and ``spectator_qubits_control`` will have flux pulses applied.
    
    spectator_qubits: dict[str, Any]
         Optional dictionary of spectator qubit objects.
    spectator_qubits_control: dict[str, Pulse]
         Optional dictionary of spectator qubit control pulses and their parameters.
    spectator_qubits_phase_shift: dict[str, float]
         Optional dictionary of spectator qubit phase shifts and their parameters.


    Properties
    ----------
    flux_pulse_control_label : str
         Resolved (final) label of the control qubit flux pulse (name extraction via get_pulse_name).
    coupler_flux_pulse_label : str
         Resolved (final) label of the coupler pulse (if provided).

    Methods
    -------
    apply(*, amplitude_scale_control=None, amplitude_scale_coupler=None,
            duration_control=None, phase_shift_control=None, phase_shift_target=None, **kwargs) -> None
         Execute the CZ gate sequence.
         Parameters:
              amplitude_scale_control : float | None
                    Scalar multiplier for the control qubit flux pulse amplitude (passed through to play()).
              amplitude_scale_coupler : float | None
                    Scalar multiplier for the coupler pulse amplitude (only used if coupler_flux_pulse is set).
              duration_control : int | None
                    Optional duration override for the control qubit flux pulse.
              phase_shift_control : float | None
                    Per‑call override for control qubit frame rotation (2π units). If None, falls back
                    to phase_shift_control attribute (when significant).
              phase_shift_target : float | None
                    Per‑call override for target qubit frame rotation (2π units). If None, falls back
                    to phase_shift_target attribute (when significant).
              **kwargs :
                    Ignored auxiliary keyword arguments (accepted for interface compatibility).

         Behavior:
              - Aligns all qubits (including spectator qubits) before playing to ensure simultaneous start.
              - Plays control qubit flux pulse (with optional amplitude scaling and duration override).
              - Plays spectator qubit flux pulses in parallel.
              - Optionally plays coupler pulse in parallel.
              - Aligns all resources.
              - Applies virtual Z frame rotations (overrides take precedence; negligible defaults skipped).
              - Applies spectator qubit phase shifts if configured.
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

    spectator_qubits: dict[str, Any] = field(default_factory=dict)
    spectator_qubits_control: dict[str, Pulse] = field(default_factory=dict)
    spectator_qubits_phase_shift: dict[str, float] = field(default_factory=dict)
    
    fidelity: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)
    duration_control: ScalarInt = None

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
        duration_control=None,
        phase_shift_control=None,
        phase_shift_target=None,
        **kwargs,
        
    ) -> None:
        
        # Build list of spectator qubits and their pulse names
        spectator_qubits_list = []
        spectator_pulse_names = {}
        for qubit_name, pulse in self.spectator_qubits_control.items():
            if qubit_name in self.spectator_qubits:
                spectator_qubit = self.spectator_qubits[qubit_name]
                spectator_qubits_list.append(spectator_qubit)
                spectator_pulse_names[qubit_name] = get_pulse_name(pulse)

        # Align all qubits (including spectator qubits) before playing to ensure simultaneous start
        align_list = [self.qubit_pair.qubit_target] + spectator_qubits_list
        self.qubit_pair.qubit_control.align(align_list)

        # Spectator qubit flux pulses
        for qubit_name, spectator_qubit in zip(self.spectator_qubits.keys(), spectator_qubits_list):
            if qubit_name in spectator_pulse_names:
                spectator_qubit.z.play(spectator_pulse_names[qubit_name])
        
        # Control qubit flux
        self.qubit_pair.qubit_control.z.play(
            self.flux_pulse_control_label,
            amplitude_scale=amplitude_scale_control,
            duration=duration_control
        )
        
        # Coupler flux
        if self.coupler_flux_pulse is not None:
            self.qubit_pair.coupler.play(
                self.coupler_flux_pulse_label,
                validate=False,
                amplitude_scale=amplitude_scale_coupler,
            )

        # Align all resources after playing pulses
        self.qubit_pair.qubit_control.align([self.qubit_pair.qubit_target] + spectator_qubits_list)
        
        # Apply phase shifts
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

        # Apply spectator qubit phase shifts
        for qubit_name, phase_shift in self.spectator_qubits_phase_shift.items():
            if qubit_name in self.spectator_qubits and np.abs(phase_shift) > 1e-6:
                self.spectator_qubits[qubit_name].xy.frame_rotation_2pi(phase_shift)

        # Final alignment
        self.qubit_pair.qubit_control.align([self.qubit_pair.qubit_target] + spectator_qubits_list)