from typing import Literal, Optional

from qm.qua import *
from qm.qua._expressions import ScalarOfAnyType, VectorOfAnyType
from quam.components.macro import QubitPairMacro
from quam.components.quantum_components import Qubit
from quam.core import quam_dataclass

__all__ = ["CRGate", "StarkInducedCZGate"]

AmplitudeScale = ScalarOfAnyType | VectorOfAnyType


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
            if qubit_pair.qubit_target.name == self.qt.name:
                cr_list.append(qubit_pair.cross_resonance)
        return cr_list

    def virtual_z_2pi(self, qubit: Qubit, phi: Optional[ScalarOfAnyType]) -> None:
        # virtual z (phi) meant that we need to be shift all the corresponding elements frame by -phi
        self._shift_frame(qubit.xy, -phi)
        for cr in self.get_all_cr_with_qt():
            self._shift_frame(cr, -phi)

    def _align_cr(self) -> None:
        align(*self.cr_elems)
        # self.qc.align()
        # self.qt.align()

    @staticmethod
    def _scaled_amplitude(amp_scale: Optional[AmplitudeScale], sign: int):
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
        scaled_amp: AmplitudeScale | None = _QubitPairCrossResonanceDriveHelpers._scaled_amplitude(
            amp_scale, sign
        )

        if scaled_amp is None and duration is None:
            elem.play(wf_type)
        elif scaled_amp is None:
            elem.play(wf_type, duration=duration)
        elif duration is None:
            elem.play(wf_type, amplitude_scale=scaled_amp)
        else:
            elem.play(wf_type, amplitude_scale=scaled_amp, duration=duration)

    def _apply_qc_correction(self, phi: Optional[ScalarOfAnyType]) -> None:
        if phi is not None:
            self.qc.xy.frame_rotation_2pi(phi)

    def _apply_qt_correction(self, phi: Optional[ScalarOfAnyType]) -> None:
        if phi is not None:
            self.qt.xy.frame_rotation_2pi(phi)
            self._shift_frame(self.cr, phi)


# ============================================================================
# Cross-Resonance (CR) Gate
# ============================================================================
@quam_dataclass
class CRGate(_QubitPairCrossResonanceDriveHelpers):
    """
    Cross-resonance two-qubit gate macro.

    Drive, cancel, and duration parameters are supplied per experiment via
    ``apply()``. Waveform and frame correction defaults live on the gate macro.
    """

    cr_type: Literal["direct", "direct+cancel", "direct+echo", "direct+cancel+echo"] = "direct+echo"
    wf_type: str = "flattop"
    qc_frame_correction_2pi: float = 0.0
    qt_frame_correction_2pi: float = 0.0

    def get_cr_operation(self, wf_type: Optional[str] = None):
        if not wf_type or wf_type == "default":
            wf_type = self.wf_type

        return self.qubit_pair.cross_resonance.operations[wf_type]

    def apply(
        self,
        cr_type: Optional[
            Literal["direct", "direct+cancel", "direct+echo", "direct+cancel+echo"]
        ] = None,
        wf_type: Optional[str] = None,
        duration_clock_cycles: Optional[ScalarOfAnyType] = None,
        drive_amp_scaling: Optional[ScalarOfAnyType] = None,
        add_drive_phase: Optional[ScalarOfAnyType] = None,
        cancel_amp_scaling: Optional[ScalarOfAnyType] = None,
        add_cancel_phase: Optional[ScalarOfAnyType] = None,
        add_qc_frame_correction_2pi: Optional[ScalarOfAnyType] = None,
        add_qt_frame_correction_2pi: Optional[ScalarOfAnyType] = None,
    ) -> None:
        cr_type = cr_type if (cr_type and cr_type != "default") else self.cr_type
        wf_type = wf_type if (wf_type and wf_type != "default") else self.wf_type

        # remove redundant values only for phase
        if isinstance(add_drive_phase, float) and add_drive_phase == 0.0:
            add_drive_phase = None
        if isinstance(add_cancel_phase, float) and add_cancel_phase == 0.0:
            add_cancel_phase = None

        # convert frame_correction_2pi to float
        if add_qc_frame_correction_2pi is None:
            add_qc_frame_correction_2pi = 0.0
        if add_qt_frame_correction_2pi is None:
            add_qt_frame_correction_2pi = 0.0
        qc_frame_correction_2pi = self.qc_frame_correction_2pi + add_qc_frame_correction_2pi
        qt_frame_correction_2pi = self.qt_frame_correction_2pi + add_qt_frame_correction_2pi

        pulse_kwargs = {
            "wf_type": wf_type,
            "cr_duration_clock_cycles": duration_clock_cycles,
            "cr_drive_amp_scaling": drive_amp_scaling,
            "cancel_amp_scaling": cancel_amp_scaling,
        }

        # apply dynamic phase update
        if add_drive_phase is not None:
            self._shift_frame(self.cr, add_drive_phase)
        if add_cancel_phase is not None:
            self._shift_frame(self.qt.xy, add_cancel_phase)
        self._align_cr()

        if cr_type == "direct":
            self._direct(**pulse_kwargs)
        elif cr_type == "direct+echo":
            self._direct_echo(**pulse_kwargs)
        elif cr_type == "direct+cancel":
            self._direct_cancel(**pulse_kwargs)
        elif cr_type == "direct+cancel+echo":
            self._direct_cancel_echo(**pulse_kwargs)

        # remove dynamic phase update
        if add_drive_phase is not None:
            self._shift_frame(self.cr, -add_drive_phase)
        if add_cancel_phase is not None:
            self._shift_frame(self.qt.xy, -add_cancel_phase)

        # apply static phase correction
        self.qc.xy.frame_rotation_2pi(qc_frame_correction_2pi)
        self.qt.xy.frame_rotation_2pi(qt_frame_correction_2pi)
        self._align_cr()

    def _direct(
        self,
        wf_type: str,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        **kwargs,
    ) -> None:
        self._play_pulse(self.cr, wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._align_cr()

    def _direct_echo(
        self,
        wf_type: str,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        **kwargs,
    ) -> None:
        self._play_pulse(self.cr, wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._align_cr()

        self.qc.xy.play("x180")
        self._align_cr()

        self._play_pulse(self.cr, wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles, sign=-1)
        self._align_cr()

        self.qc.xy.play("x180")

    def _direct_cancel(
        self,
        wf_type: str,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cancel_amp_scaling,
        **kwargs,
    ) -> None:
        cancel_wf = self.pair_target_wf("cr", wf_type, self.qubit_pair.name)

        self._play_pulse(self.cr, wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._play_pulse(self.qt.xy, cancel_wf, cancel_amp_scaling, cr_duration_clock_cycles)

    def _direct_cancel_echo(
        self,
        wf_type: str,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cancel_amp_scaling,
        **kwargs,
    ) -> None:
        cancel_wf = self.pair_target_wf("cr", wf_type, self.qubit_pair.name)

        self._play_pulse(self.cr, wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._play_pulse(self.qt.xy, cancel_wf, cancel_amp_scaling, cr_duration_clock_cycles)
        self._align_cr()

        self.qc.xy.play("x180")
        self._align_cr()

        self._play_pulse(self.cr, wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles, sign=-1)
        self._play_pulse(
            self.qt.xy, cancel_wf, cancel_amp_scaling, cr_duration_clock_cycles, sign=-1
        )
        self._align_cr()

        self.qc.xy.play("x180")

    @property
    def inferred_duration(self) -> int:
        return self.get_cr_duration(with_echo=True)

    def get_cr_duration(self, with_echo: bool = False) -> int:
        cr_duration = self.cr.operations[self.wf_type].length
        if self.cr_type in ["direct", "direct+cancel"]:
            return cr_duration
        elif self.cr_type in ["direct+echo", "direct+cancel+echo"]:
            if with_echo:
                return 2 * (cr_duration + self.qc.xy.operations["x180"].length)
            else:
                return 2 * cr_duration
        else:
            raise ValueError(f"Invalid CR type: {self.cr_type}")


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
        wf_type: Optional[Literal["square", "cosine", "gauss", "flattop"]] = "flattop",
        zz_duration_clock_cycles: Optional[ScalarOfAnyType] = None,
        zz_control_amp_scaling: Optional[AmplitudeScale] = None,
        zz_target_amp_scaling: Optional[AmplitudeScale] = None,
        zz_relative_phase: Optional[AmplitudeScale] = None,
        qc_correction_phase: Optional[ScalarOfAnyType] = None,
        qt_correction_phase: Optional[ScalarOfAnyType] = None,
    ) -> None:
        qc_corr = qc_correction_phase if qc_correction_phase else self.qc_correction_phase
        qt_corr = qt_correction_phase if qt_correction_phase else self.qt_correction_phase

        self._shift_frame(self.qt.xy_detuned, zz_relative_phase)

        align(self._zz.name, self.qt.xy_detuned.name)
        self._play_pulse(self._zz, wf_type, zz_control_amp_scaling, zz_duration_clock_cycles)
        self._play_pulse(
            self.qt.xy_detuned,
            self.pair_target_wf("zz", wf_type, self.qubit_pair.name),
            zz_target_amp_scaling,
            zz_duration_clock_cycles,
        )

        align(self._zz.name, self.qt.xy_detuned.name, self.qc.xy.name, self.qt.xy.name)
        self._apply_qc_correction(qc_corr)
        self._apply_qt_correction(qt_corr)
