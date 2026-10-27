from typing import Literal, Optional, Union

from qm.qua import *
from qm.qua._expressions import ScalarOfAnyType, VectorOfAnyType
from quam.components.macro import QubitPairMacro
from quam.components.quantum_components import Qubit
from quam.core import quam_dataclass

__all__ = ["CRGate", "StarkInducedCZGate"]

AmplitudeScale = Union[ScalarOfAnyType, VectorOfAnyType]
CR_TYPES = ["default", "direct", "2x direct", "direct+cancel", "2x direct+cancel", "direct+echo", "direct+cancel+echo"]


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
    def control_target_qubit_detuning(self):
        return self.qc.xy.RF_frequency - self.qt.xy.RF_frequency

    @staticmethod
    def pair_target_wf(prefix: str, wf_type: str, pair_name: str) -> str:
        return f"{prefix}_{wf_type}_{pair_name}"

    @staticmethod
    def _shift_frame(elem, phi: Optional[ScalarOfAnyType]) -> None:
        elem.frame_rotation_2pi(phi)

    def get_all_cr_with_qt(self, active_qubit_pairs_only: bool = True) -> list:
        if active_qubit_pairs_only:
            valid_qubit_pairs = self.get_root().active_qubit_pairs
        else:
            valid_qubit_pairs = self.get_root().qubit_pairs

        cr_list = []
        for qubit_pair in valid_qubit_pairs:
            if qubit_pair.cross_resonance is None:
                continue
            if qubit_pair.qubit_target.name == self.qt.name:
                cr_list.append(qubit_pair.cross_resonance)
        return cr_list

    def virtual_z_2pi(self, qubit: Qubit, phi: Optional[ScalarOfAnyType]) -> None:
        # virtual z (phi) meant that we need to be shift all the corresponding elements frame by -phi
        self._shift_frame(qubit.xy, -phi)
        for cr in self.get_all_cr_with_qt():
            self._shift_frame(cr, -phi)

    def ry(self, qubit: Qubit, phase: ScalarOfAnyType) -> None:
        """Ry(phase) = X(-pi/2) Z(phase) X(pi/2). ``phase`` is in units of 2pi."""
        qubit.xy.play("x90")
        self.virtual_z_2pi(qubit, phase)
        qubit.xy.play("-x90")

    def _align_cr(self) -> None:
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
        duration: Optional[ScalarOfAnyType] = None,
        *,
        sign: int = 1,
    ) -> None:
        scaled_amp: AmplitudeScale = _QubitPairCrossResonanceDriveHelpers._scaled_amplitude(amp_scale, sign)

        if duration is None:
            elem.play(wf_type, amplitude_scale=scaled_amp)
        else:
            elem.play(wf_type, amplitude_scale=scaled_amp, duration=duration)


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
            "drive_amp_scaling": drive_amp_scaling,
            "cancel_amp_scaling": cancel_amp_scaling,
        }

        # Ry(phi) on the target before the CR interaction to convert ZZ to ZX
        if zz_supression_phase is not None:
            self._align_cr()
            self.ry(self.qt, zz_supression_phase)
            self._align_cr()

        # apply dynamic phase update
        if add_drive_phase is not None:
            self._shift_frame(self.cr, add_drive_phase)
        if add_cancel_phase is not None:
            self._shift_frame(self.qt.xy, add_cancel_phase)
        self._align_cr()

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
            self._shift_frame(self.cr, -add_drive_phase)
        if add_cancel_phase is not None:
            self._shift_frame(self.qt.xy, -add_cancel_phase)

        # apply static phase correction
        self.qc.xy.frame_rotation_2pi(qc_frame_correction_2pi)
        self.qt.xy.frame_rotation_2pi(qt_frame_correction_2pi)
        self._align_cr()

        # Revert ZZ-supression
        if zz_supression_phase is not None:
            self.ry(self.qt, -zz_supression_phase)
            self._align_cr()

    def _direct(
        self,
        wf_type: str,
        duration,
        drive_amp_scaling,
        **kwargs,
    ) -> None:
        self._play_pulse(self.cr, wf_type, drive_amp_scaling, duration)
        self._align_cr()

    def _2x_direct(
        self,
        wf_type: str,
        duration,
        drive_amp_scaling,
        **kwargs,
    ) -> None:
        # wait equivalent to x180 pulse length is added to match the timing of echo type
        x180_duration = self.qc.xy.operations["x180"].length // 4

        self._direct(wf_type, duration, drive_amp_scaling)
        self.qc.xy.wait(x180_duration)
        self._align_cr()

        self._direct(wf_type, duration, drive_amp_scaling)
        self.qc.xy.wait(x180_duration)
        self._align_cr()

    def _direct_echo(
        self,
        wf_type: str,
        duration,
        drive_amp_scaling,
        **kwargs,
    ) -> None:
        self._play_pulse(self.cr, wf_type, drive_amp_scaling, duration)
        self._align_cr()

        self.qc.xy.play("x180")
        self._align_cr()

        self._play_pulse(self.cr, wf_type, drive_amp_scaling, duration, sign=-1)
        self._align_cr()

        self.qc.xy.play("x180")

    def _direct_cancel(
        self,
        wf_type: str,
        duration,
        drive_amp_scaling,
        cancel_amp_scaling,
        **kwargs,
    ) -> None:
        cancel_wf = self.pair_target_wf("cr", wf_type, self.qubit_pair.name)

        self._play_pulse(self.cr, wf_type, drive_amp_scaling, duration)
        self._play_pulse(self.qt.xy, cancel_wf, cancel_amp_scaling, duration)

    def _2x_direct_cancel(
        self,
        wf_type: str,
        duration,
        drive_amp_scaling,
        cancel_amp_scaling,
        **kwargs,
    ) -> None:
        # wait equivalent to x180 pulse length is added to match the timing of echo type
        x180_duration = self.qc.xy.operations["x180"].length // 4

        self._direct_cancel(wf_type, duration, drive_amp_scaling, cancel_amp_scaling)
        self.qc.xy.wait(x180_duration)
        self._align_cr()

        self._direct_cancel(wf_type, duration, drive_amp_scaling, cancel_amp_scaling)
        self.qc.xy.wait(x180_duration)
        self._align_cr()

    def _direct_cancel_echo(
        self,
        wf_type: str,
        duration,
        drive_amp_scaling,
        cancel_amp_scaling,
        **kwargs,
    ) -> None:
        cancel_wf = self.pair_target_wf("cr", wf_type, self.qubit_pair.name)

        self._play_pulse(self.cr, wf_type, drive_amp_scaling, duration)
        self._play_pulse(self.qt.xy, cancel_wf, cancel_amp_scaling, duration)
        self._align_cr()

        self.qc.xy.play("x180")
        self._align_cr()

        self._play_pulse(self.cr, wf_type, drive_amp_scaling, duration, sign=-1)
        self._play_pulse(self.qt.xy, cancel_wf, cancel_amp_scaling, duration, sign=-1)
        self._align_cr()

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
            if "echo" in cr_type:
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
            self._shift_frame(self.qt.xyd, zz_relative_phase)

        align(self._zz.name, self.qt.xyd.name)
        self._play_pulse(self._zz, wf_type, zz_control_amp_scaling, duration)
        self._play_pulse(
            self.qt.xyd,
            self.pair_target_wf("zz", wf_type, self.qubit_pair.name),
            zz_target_amp_scaling,
            duration,
        )

        align(self._zz.name, self.qt.xyd.name, self.qc.xy.name, self.qt.xy.name)

        # apply static phase correction
        self.qc.xy.frame_rotation_2pi(qc_corr)
        self.qt.xy.frame_rotation_2pi(qt_corr)
