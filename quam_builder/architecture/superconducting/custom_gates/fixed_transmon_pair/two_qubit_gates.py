import warnings
from typing import Literal, Optional, Sequence, Union

from qm.qua import *
from qm.qua._expressions import ScalarOfAnyType, VectorOfAnyType
from quam.components.macro import QubitPairMacro
from quam.components.quantum_components import Qubit
from quam.core import quam_dataclass

__all__ = ["CRGate", "StarkInducedCZGate", "CR_DerivedGates"]

AmplitudeScale = Union[ScalarOfAnyType, VectorOfAnyType]
CR_TYPES = [
    "default",
    "direct",
    "2x direct",
    "direct+cancel",
    "2x direct+cancel",
    "direct+echo",
    "direct+cancel+echo",
]


# ============================================================================
# CR derived gates: composed from native pulses / frame shifts, independent of any one CR macro
# ============================================================================
class CR_DerivedGates:
    """Namespace of static gate sequences (virtual Z, Ry, Hadamard, CNOT, SWAP) built on ``CRGate``."""

    @staticmethod
    def get_all_cr_with_qubit_as_target(qubit: Qubit, active_qubit_pairs_only: bool = True) -> list:
        root = qubit.get_root()
        valid_qubit_pairs = root.active_qubit_pairs if active_qubit_pairs_only else root.qubit_pairs
        if isinstance(valid_qubit_pairs, dict):
            valid_qubit_pairs = valid_qubit_pairs.values()
        return [
            qp.cross_resonance
            for qp in valid_qubit_pairs
            if qp.cross_resonance is not None and qp.qubit_target.name == qubit.name
        ]

    @staticmethod
    def virtual_z_2pi(qubit: Qubit, phi: Optional[ScalarOfAnyType]) -> None:
        # virtual z (phi) meant that we need to be shift all the corresponding elements frame by -phi
        qubit.xy.frame_rotation_2pi(-phi)
        for cr in CR_DerivedGates.get_all_cr_with_qubit_as_target(qubit):
            cr.frame_rotation_2pi(-phi)

    @staticmethod
    def ry(qubit: Qubit, phase: ScalarOfAnyType) -> None:
        """Ry(phase) = X(-pi/2) Z(phase) X(pi/2). ``phase`` is in units of 2pi."""
        qubit.xy.play("x90")
        CR_DerivedGates.virtual_z_2pi(qubit, phase)
        qubit.xy.play("-x90")

    @staticmethod
    def hadamard(qubit: Qubit, decomposition_type: Literal["XY", "YZ"] = "XY") -> None:
        if decomposition_type == "XY":
            qubit.xy.play("y90")
            qubit.xy.play("x180")
        elif decomposition_type == "YZ":
            qubit.xy.play("-y90")
            CR_DerivedGates.virtual_z_2pi(qubit, 0.5)
        else:
            raise ValueError(f"Invalid hadamard decomposition type: {decomposition_type}")

    @staticmethod
    def _resolve_cnot_pair(qc: Qubit, qt: Qubit, qubit_pairs: Sequence, allow_reverse: str):
        """Return ``(qp, use_reverse)`` for a logical CNOT qc->qt.

        ``allow_reverse``: ``"auto"`` prefers native, ``"forced"`` requires reverse, ``"error"`` requires native.
        """
        native = reverse = None
        for qp in qubit_pairs:
            cr_gate: CRGate = qp.macros["cr"]
            if (cr_gate.qc.name, cr_gate.qt.name) == (qc.name, qt.name):
                native = native or qp
            elif (cr_gate.qc.name, cr_gate.qt.name) == (qt.name, qc.name):
                reverse = reverse or qp

        names = [qp.name for qp in qubit_pairs]
        pairs_str = ", ".join(names[:5] + (["..."] if len(names) > 5 else []))
        if allow_reverse == "forced":
            if reverse is None:
                raise ValueError(
                    f"No reverse pair for {qc.name}->{qt.name} in active qubit pairs: {pairs_str}"
                )
            return reverse, True
        if native is not None:
            return native, False
        if allow_reverse == "auto" and reverse is not None:
            return reverse, True
        raise ValueError(
            f"No direct pair for {qc.name}->{qt.name} in active qubit pairs: {pairs_str}"
        )

    @staticmethod
    def cnot(
        qc: Qubit,
        qt: Qubit,
        qubit_pairs: Sequence,
        virtual_z: bool = True,
        allow_reverse: Literal["auto", "forced", "error"] = "auto",
        **cr_kwargs,
    ) -> None:
        """Logical CNOT qc->qt; uses the reverse pair with a Hadamard sandwich when needed."""
        qp, use_reverse = CR_DerivedGates._resolve_cnot_pair(qc, qt, qubit_pairs, allow_reverse)
        cr_gate: CRGate = qp.macros["cr"]
        qc, qt = cr_gate.qc, cr_gate.qt
        hadamard_type = "YZ" if virtual_z else "XY"

        if use_reverse:
            cr_gate.align()
            CR_DerivedGates.hadamard(qc, hadamard_type)
            CR_DerivedGates.hadamard(qt, hadamard_type)

        # CNOT decomposition into [Z(-pi/2) x I] * [I x X(-pi/2)] * ZX(pi/2)
        qt.xy.play("-x90")
        if virtual_z:
            CR_DerivedGates.virtual_z_2pi(qc, -0.25)
        else:
            # Z(theta) = X(-pi/2) Y(-theta) X(pi/2)
            # Z(-pi/2) = X(-pi/2) Y(pi/2) X(pi/2)
            qc.xy.play("x90")
            qc.xy.play("y90")
            qc.xy.play("-x90")
        cr_gate.align()
        qp.apply("cr", **cr_kwargs)
        cr_gate.align()

        if use_reverse:
            CR_DerivedGates.hadamard(qc, hadamard_type)
            CR_DerivedGates.hadamard(qt, hadamard_type)
            cr_gate.align()

    @staticmethod
    def swap(qc: Qubit, qt: Qubit, qubit_pairs: Sequence, **cr_kwargs) -> None:
        CR_DerivedGates.cnot(qc, qt, qubit_pairs, **cr_kwargs)
        CR_DerivedGates.cnot(qt, qc, qubit_pairs, **cr_kwargs)
        CR_DerivedGates.cnot(qc, qt, qubit_pairs, **cr_kwargs)


class _QubitPairCrossResonanceDriveHelpers(QubitPairMacro):
    @property
    def qc(self):
        return self.qubit_pair.qubit_control

    @property
    def qt(self):
        return self.qubit_pair.qubit_target

    @property
    def cr(self):
        return self.qubit_pair.cross_resonance

    @property
    def cr_elems(self):
        return [self.qc.xy.name, self.qt.xy.name, self.cr.name]

    @property
    def qubit_detuning(self):
        return self.qc.xy.RF_frequency - self.qt.xy.RF_frequency

    @staticmethod
    def pair_target_wf(prefix: str, wf_type: str, pair_name: str) -> str:
        return f"{prefix}_{wf_type}_{pair_name}"

    def align(self) -> None:
        align(*self.cr_elems)

    @staticmethod
    def _scaled_amplitude(amp_scale: Optional[AmplitudeScale], sign: int) -> AmplitudeScale:
        """Apply echo sign to scalar or DRAG ``amplitude_scale`` lists."""
        if amp_scale is None:
            amp_scale = 1
        if isinstance(amp_scale, (list, tuple)):
            if len(amp_scale) == 4:
                return [
                    sign * amp_scale[0],
                    sign * amp_scale[1],
                    sign * amp_scale[2],
                    sign * amp_scale[3],
                ]
        return sign * amp_scale

    @staticmethod
    def _play_pulse(
        elem,
        wf_type: str,
        amp_scale: Optional[AmplitudeScale] = None,
        *,
        duration: Optional[ScalarOfAnyType] = None,
        truncate: Optional[ScalarOfAnyType] = None,
        sign: int = 1,
    ) -> None:
        scaled_amp: AmplitudeScale = _QubitPairCrossResonanceDriveHelpers._scaled_amplitude(
            amp_scale, sign
        )
        if duration is not None and truncate is not None:
            raise ValueError("duration and truncate cannot be both provided")

        if duration is not None:
            elem.play(wf_type, amplitude_scale=scaled_amp, duration=duration)
        elif truncate is not None:
            elem.play(wf_type, amplitude_scale=scaled_amp, truncate=truncate)
        else:
            elem.play(wf_type, amplitude_scale=scaled_amp)


# ============================================================================
# Cross-Resonance (CR) Gate
# ============================================================================
@quam_dataclass
class CRGate(_QubitPairCrossResonanceDriveHelpers):
    """
    Cross-resonance two-qubit gate macro.

    Drive, cancel, duration, and ZZ-suppression phase are supplied per experiment
    via ``apply()``. Waveform, frame correction, and ``zz_supression_phase_2pi``
    defaults live on the gate macro. ``zz_supression_phase=None`` uses the stored
    phase. A phase of 0 skips the Ry rotations.
    """

    cr_type: Literal[tuple(CR_TYPES)] = "direct+echo"
    wf_type: str = "flattop"
    qc_frame_correction_2pi: float = 0.0
    qt_frame_correction_2pi: float = 0.0
    zz_supression_phase_2pi: float = 0.0

    def get_cr_operation(self, wf_type: Optional[str] = None):
        if not wf_type or wf_type == "default":
            wf_type = self.wf_type

        return self.qubit_pair.cross_resonance.operations[wf_type]

    def apply(
        self,
        cr_type: Optional[Literal[tuple(CR_TYPES)]] = None,
        wf_type: Optional[str] = None,
        duration: Optional[ScalarOfAnyType] = None,
        duration_clock_cycles: Optional[ScalarOfAnyType] = None,
        truncate: Optional[ScalarOfAnyType] = None,
        drive_amp_scaling: Optional[ScalarOfAnyType] = None,
        add_drive_phase: Optional[ScalarOfAnyType] = None,
        cancel_amp_scaling: Optional[ScalarOfAnyType] = None,
        add_cancel_phase: Optional[ScalarOfAnyType] = None,
        add_qc_frame_correction_2pi: Optional[ScalarOfAnyType] = None,
        add_qt_frame_correction_2pi: Optional[ScalarOfAnyType] = None,
        zz_supression_phase: Optional[ScalarOfAnyType] = None,
    ) -> None:
        cr_type = self.resolve_cr_type(cr_type)
        wf_type = self.resolve_wf_type(wf_type)

        # remove redundant values only for phase
        if isinstance(add_drive_phase, float) and add_drive_phase == 0.0:
            add_drive_phase = None
        if isinstance(add_cancel_phase, float) and add_cancel_phase == 0.0:
            add_cancel_phase = None

        # None uses the phase stored on the gate. 0 skips the Ry rotations.
        if zz_supression_phase is None and self.zz_supression_phase_2pi != 0:
            zz_supression_phase = self.zz_supression_phase_2pi

        if duration_clock_cycles is not None:
            warnings.warn(
                "duration_clock_cycles is deprecated. Use duration instead.", DeprecationWarning
            )
            duration = duration_clock_cycles

        # convert frame_correction_2pi to float
        if add_qc_frame_correction_2pi is None:
            add_qc_frame_correction_2pi = 0.0
        if add_qt_frame_correction_2pi is None:
            add_qt_frame_correction_2pi = 0.0
        qc_frame_correction_2pi = self.qc_frame_correction_2pi + add_qc_frame_correction_2pi
        qt_frame_correction_2pi = self.qt_frame_correction_2pi + add_qt_frame_correction_2pi

        pulse_kwargs = {
            "wf_type": wf_type,
            "duration": duration,
            "truncate": truncate,
            "drive_amp_scaling": drive_amp_scaling,
            "cancel_amp_scaling": cancel_amp_scaling,
        }

        # Ry(phi) on the target before the CR interaction to convert ZZ to ZX
        if zz_supression_phase is not None:
            self.align()
            CR_DerivedGates.ry(self.qt, zz_supression_phase)

        # apply dynamic phase update
        if add_drive_phase is not None:
            self.cr.frame_rotation_2pi(add_drive_phase)
        if add_cancel_phase is not None:
            self.qt.xy.frame_rotation_2pi(add_cancel_phase)

        self.align()
        if cr_type == "direct":
            self._direct(**pulse_kwargs)
        elif cr_type == "2x direct":
            self._2x_direct(**pulse_kwargs)
        elif cr_type == "direct+cancel":
            self._direct_cancel(**pulse_kwargs)
        elif cr_type == "2x direct+cancel":
            self._2x_direct_cancel(**pulse_kwargs)
        elif cr_type == "direct+echo":
            self._direct_echo(**pulse_kwargs)
        elif cr_type == "direct+cancel+echo":
            self._direct_cancel_echo(**pulse_kwargs)
        else:
            raise NotImplementedError(f"CR type {cr_type} not implemented")

        # remove dynamic phase update
        if add_drive_phase is not None:
            self.cr.frame_rotation_2pi(-add_drive_phase)
        if add_cancel_phase is not None:
            self.qt.xy.frame_rotation_2pi(-add_cancel_phase)

        # apply static phase correction, propagating to any cr elements that target qc/qt
        CR_DerivedGates.virtual_z_2pi(self.qc, qc_frame_correction_2pi)
        CR_DerivedGates.virtual_z_2pi(self.qt, qt_frame_correction_2pi)

        # Revert ZZ-supression
        if zz_supression_phase is not None:
            self.align()
            CR_DerivedGates.ry(self.qt, -zz_supression_phase)

    def _direct(
        self,
        wf_type: str,
        drive_amp_scaling: Optional[AmplitudeScale] = None,
        *,
        duration: Optional[ScalarOfAnyType] = None,
        truncate: Optional[ScalarOfAnyType] = None,
        **kwargs,
    ) -> None:
        self._play_pulse(
            self.cr,
            wf_type,
            drive_amp_scaling,
            duration=duration,
            truncate=truncate,
        )
        self.align()

    def _2x_direct(
        self,
        wf_type: str,
        drive_amp_scaling: Optional[AmplitudeScale] = None,
        *,
        duration: Optional[ScalarOfAnyType] = None,
        truncate: Optional[ScalarOfAnyType] = None,
        **kwargs,
    ) -> None:
        # wait equivalent to x180 pulse length is added to match the timing of echo type
        x180_duration = self.qc.xy.operations["x180"].length // 4

        self._direct(wf_type, drive_amp_scaling, duration=duration, truncate=truncate)
        self.qc.xy.wait(x180_duration)
        self.align()

        self._direct(wf_type, drive_amp_scaling, duration=duration, truncate=truncate)
        self.qc.xy.wait(x180_duration)
        self.align()

    def _direct_echo(
        self,
        wf_type: str,
        drive_amp_scaling: Optional[AmplitudeScale] = None,
        *,
        duration: Optional[ScalarOfAnyType] = None,
        truncate: Optional[ScalarOfAnyType] = None,
        **kwargs,
    ) -> None:
        self._play_pulse(
            self.cr,
            wf_type,
            drive_amp_scaling,
            duration=duration,
            truncate=truncate,
        )
        self.align()

        self.qc.xy.play("x180")
        self.align()

        self._play_pulse(
            self.cr,
            wf_type,
            drive_amp_scaling,
            duration=duration,
            truncate=truncate,
            sign=-1,
        )
        self.align()

        self.qc.xy.play("x180")

    def _direct_cancel(
        self,
        wf_type: str,
        drive_amp_scaling: Optional[AmplitudeScale] = None,
        cancel_amp_scaling: Optional[AmplitudeScale] = None,
        *,
        duration: Optional[ScalarOfAnyType] = None,
        truncate: Optional[ScalarOfAnyType] = None,
        **kwargs,
    ) -> None:
        cancel_wf = self.pair_target_wf("cr", wf_type, self.qubit_pair.name)

        self._play_pulse(
            self.cr,
            wf_type,
            drive_amp_scaling,
            duration=duration,
            truncate=truncate,
        )
        self._play_pulse(
            self.qt.xy,
            cancel_wf,
            cancel_amp_scaling,
            duration=duration,
            truncate=truncate,
        )
        self.align()

    def _2x_direct_cancel(
        self,
        wf_type: str,
        drive_amp_scaling: Optional[AmplitudeScale] = None,
        cancel_amp_scaling: Optional[AmplitudeScale] = None,
        *,
        duration: Optional[ScalarOfAnyType] = None,
        truncate: Optional[ScalarOfAnyType] = None,
        **kwargs,
    ) -> None:
        # wait equivalent to x180 pulse length is added to match the timing of echo type
        x180_duration = self.qc.xy.operations["x180"].length // 4

        self._direct_cancel(
            wf_type,
            drive_amp_scaling,
            cancel_amp_scaling,
            duration=duration,
            truncate=truncate,
        )
        self.qc.xy.wait(x180_duration)
        self.align()

        self._direct_cancel(
            wf_type,
            drive_amp_scaling,
            cancel_amp_scaling,
            duration=duration,
            truncate=truncate,
        )
        self.qc.xy.wait(x180_duration)

    def _direct_cancel_echo(
        self,
        wf_type: str,
        drive_amp_scaling: Optional[AmplitudeScale] = None,
        cancel_amp_scaling: Optional[AmplitudeScale] = None,
        *,
        duration: Optional[ScalarOfAnyType] = None,
        truncate: Optional[ScalarOfAnyType] = None,
        **kwargs,
    ) -> None:
        cancel_wf = self.pair_target_wf("cr", wf_type, self.qubit_pair.name)

        self._play_pulse(
            self.cr,
            wf_type,
            drive_amp_scaling,
            duration=duration,
            truncate=truncate,
        )
        self._play_pulse(
            self.qt.xy,
            cancel_wf,
            cancel_amp_scaling,
            duration=duration,
            truncate=truncate,
        )
        self.align()

        self.qc.xy.play("x180")
        self.align()

        self._play_pulse(
            self.cr,
            wf_type,
            drive_amp_scaling,
            duration=duration,
            truncate=truncate,
            sign=-1,
        )
        self._play_pulse(
            self.qt.xy,
            cancel_wf,
            cancel_amp_scaling,
            duration=duration,
            truncate=truncate,
            sign=-1,
        )
        self.align()

        self.qc.xy.play("x180")

    @property
    def inferred_duration(self) -> int:
        return self.get_duration(cr_drive_only=False)

    def resolve_cr_type(self, cr_type: Optional[str] = None) -> str:
        cr_type = cr_type if (cr_type and cr_type != "default") else self.cr_type
        if cr_type not in CR_TYPES or cr_type == "default":
            raise ValueError(f"Invalid CR type: {cr_type}")
        return cr_type

    def resolve_wf_type(self, wf_type: Optional[str] = None) -> str:
        wf_type = wf_type if (wf_type and wf_type != "default") else self.wf_type
        return wf_type

    def num_cr_pulses(self, cr_type: Optional[str] = None) -> int:
        """Number of CR drive pulses played by ``apply()`` for ``cr_type``."""
        cr_type = self.resolve_cr_type(cr_type)
        return 1 if cr_type in ("direct", "direct+cancel") else 2

    def get_cr_duration(
        self,
        cr_drive_only: bool = True,
        cr_type: Optional[str] = None,
        wf_type: Optional[str] = None,
        cr_length=None,
    ):
        warnings.warn(
            "get_cr_duration is deprecated. Use get_duration instead.", DeprecationWarning
        )
        return self.get_duration(cr_drive_only, cr_type, wf_type, cr_length)

    def get_duration(
        self,
        cr_drive_only: bool = True,
        cr_type: Optional[str] = None,
        wf_type: Optional[str] = None,
        cr_length=None,
    ):
        """Total CR gate duration in ns.

        Args:
            cr_drive_only: Include the x180 pulses on the control qubit (echo types only).
            cr_type: Overrides the stored ``cr_type``.
            wf_type: Overrides the stored ``wf_type``.
            cr_length: Length of a single CR pulse in ns (scalar or array). Defaults to
                the length of the ``wf_type`` operation.
        """
        cr_type = self.resolve_cr_type(cr_type)
        if cr_length is None:
            cr_length = self.get_cr_operation(wf_type).length
        duration = self.num_cr_pulses(cr_type) * cr_length
        if not cr_drive_only:
            if "echo" in cr_type or cr_type.startswith("2x"):
                duration += 2 * self.qc.xy.operations["x180"].length
            if self.zz_supression_phase_2pi != 0:
                duration += 2 * self.qt.xy.operations["x90"].length
        return duration


# ============================================================================
# Stark-Induced CZ Gate
# ============================================================================
@quam_dataclass
class StarkInducedCZGate(_QubitPairCrossResonanceDriveHelpers):
    qc_correction_phase: Optional[float] = None
    qt_correction_phase: Optional[float] = None

    @property
    def _zz(self):
        return self.qubit_pair.zz

    def apply(
        self,
        wf_type: Optional[Literal["square", "flattop"]] = "flattop",
        duration: Optional[ScalarOfAnyType] = None,
        zz_control_amp_scaling: Optional[AmplitudeScale] = None,
        zz_target_amp_scaling: Optional[AmplitudeScale] = None,
        zz_relative_phase: Optional[AmplitudeScale] = None,
        qc_correction_phase: Optional[ScalarOfAnyType] = None,
        qt_correction_phase: Optional[ScalarOfAnyType] = None,
    ) -> None:
        qc_corr = qc_correction_phase if qc_correction_phase else self.qc_correction_phase
        qt_corr = qt_correction_phase if qt_correction_phase else self.qt_correction_phase

        if zz_relative_phase is not None:
            self.qt.xyd.frame_rotation_2pi(zz_relative_phase)

        align(self._zz.name, self.qt.xyd.name)
        self._play_pulse(self._zz, wf_type, zz_control_amp_scaling, duration=duration)
        self._play_pulse(
            self.qt.xyd,
            self.pair_target_wf("zz", wf_type, self.qubit_pair.name),
            zz_target_amp_scaling,
            duration=duration,
        )

        align(self._zz.name, self.qt.xyd.name, self.qc.xy.name, self.qt.xy.name)

        # apply static phase correction
        self.qc.xy.frame_rotation_2pi(qc_corr)
        self.qt.xy.frame_rotation_2pi(qt_corr)
