from typing import Literal, Optional, Union, Tuple, List

from qm.qua import *
from qm.qua._expressions import QuaExpression, QuaVariable

from quam.components.macro import QubitPairMacro
from quam.core import quam_dataclass

__all__ = ["CRGate", "StarkInducedCZGate"]

qua_T = Union[QuaVariable, QuaExpression]
_tuple = Tuple[Union[float, qua_T]]
_list = List[Union[float, qua_T]]


# ============================================================================
# Shared helpers for 2-qubit gates (no dataclass fields here; just utilities)
# ============================================================================
class _QubitPairCrossDriveHelpers:
    # ---- Small helpers (common) ----
    @property
    def _qc(self):
        return self.qubit_pair.qubit_control

    @property
    def _qt(self):
        return self.qubit_pair.qubit_target

    # Generic merge that ignores None (None == "no override")
    def _merge_params(self, defaults: dict, **overrides) -> dict:
        out = dict(defaults)
        for k, v in overrides.items():
            if k in ["qc_correction_phase", "qt_correction_phase"] and v is not None:
                out[k] = v
            else:
                out[k] = v
        return out

    # ---- Phase shifts (common ZI / IZ corrections) ----
    def _qc_shift_correction_phase(self, phi: Optional[float | qua_T]) -> None:
        if phi:
            self._qc.xy.frame_rotation_2pi(phi)

    def _qt_shift_correction_phase(self, phi: Optional[float | qua_T]) -> None:
        if phi:
            self._qt.xy.frame_rotation_2pi(phi)

    # ---- Low-level play helper (common) ----
    @staticmethod
    def _play_pulse(
        elem,
        wf_type: str,
        amp_scale: Optional[Union[float, qua_T, _tuple, _list]],
        duration: Optional[Union[int, float, qua_T]],
        sgn: int = 1,
    ) -> None:
        # Keep the branching explicit to satisfy QUA's optional-kw behavior
        if amp_scale is None and duration is None:
            elem.play(wf_type)
        elif amp_scale is None:
            elem.play(wf_type, duration=duration)
        elif duration is None:
            elem.play(wf_type, amplitude_scale=sgn * amp_scale)
        else:
            elem.play(wf_type, amplitude_scale=sgn * amp_scale, duration=duration)


# ============================================================================
# Cross-Resonance (CR) Gate
# ============================================================================
@quam_dataclass
class CRGate(_QubitPairCrossDriveHelpers, QubitPairMacro):
    # Gate-level parameters (composite CR, stored under macros)
    qc_correction_phase: Optional[float] = None  # ZI correction
    qt_correction_phase: Optional[float] = None  # IZ correction

    # ---- Public API ----
    def apply(
        self,
        cr_type: Literal["direct", "direct+cancel", "direct+echo", "direct+cancel+echo"] = "direct",
        wf_type: Optional[Literal["square", "cosine", "gauss", "flattop"]] = "flattop",
        cr_duration_clock_cycles: Optional[int | qua_T] = None,
        cr_drive_amp_scaling: Optional[float | qua_T] = None,
        cr_drive_phase: Optional[float | qua_T] = None,
        cr_cancel_amp_scaling: Optional[float | qua_T] = None,
        cr_cancel_phase: Optional[float | qua_T] = None,
        qc_correction_phase: Optional[float | qua_T] = None,
        qt_correction_phase: Optional[float | qua_T] = None,
    ) -> None:
        # Relative to the stored CrossResonance component parameters
        if cr_drive_amp_scaling is None:
            cr_drive_amp_scaling = self._cr.drive_amplitude_scaling
        else:
            cr_drive_amp_scaling *= self._cr.drive_amplitude_scaling
        if cr_drive_phase is None:
            cr_drive_phase = self._cr.drive_phase
        else:
            cr_drive_phase += self._cr.drive_phase
        if cr_cancel_amp_scaling is None:
            cr_cancel_amp_scaling = self._cr.cancel_amplitude_scaling
        else:
            cr_cancel_amp_scaling *= self._cr.cancel_amplitude_scaling
        if cr_cancel_phase is None:
            cr_cancel_phase = self._cr.cancel_phase
        else:
            cr_cancel_phase += self._cr.cancel_phase

        params = self._merge_params(
            dict(
                qc_correction_phase=self.qc_correction_phase,
                qt_correction_phase=self.qt_correction_phase,
            ),
            wf_type=wf_type,
            cr_duration_clock_cycles=cr_duration_clock_cycles,
            cr_drive_amp_scaling=cr_drive_amp_scaling,
            cr_drive_phase=cr_drive_phase,
            cr_cancel_amp_scaling=cr_cancel_amp_scaling,
            cr_cancel_phase=cr_cancel_phase,
            qc_correction_phase=qc_correction_phase,
            qt_correction_phase=qt_correction_phase,
        )

        if cr_type == "direct":
            self._direct(**params)
        elif cr_type == "direct+echo":
            self._direct_echo(**params)
        elif cr_type == "direct+cancel":
            self._direct_cancel(**params)
        elif cr_type == "direct+cancel+echo":
            self._direct_cancel_echo(**params)
        else:
            raise ValueError(f"Unknown cr_type '{cr_type}'")

    # hardware elems
    @property
    def _cr(self):
        return self.qubit_pair.cross_resonance

    @property
    def _cr_elems(self):
        return [self._qc.xy.name, self._qt.xy.name, self._cr.name]

    # ---- Phase helpers specific to CR ----
    def _cr_drive_shift_phase(self, phi: Optional[float | qua_T]) -> None:
        if phi is not None:
            self._cr.frame_rotation_2pi(phi)

    def _cr_cancel_shift_phase(self, phi: Optional[float | qua_T]) -> None:
        if phi is not None:
            self._qt.xy.frame_rotation_2pi(phi)

    # ---- Play wrappers ----
    def _cr_drive_play(
        self,
        sgn: Literal["direct", "echo"],
        wf_type: str,
        cr_drive_amp_scaling,
        cr_duration_clock_cycles,
    ) -> None:
        self._play_pulse(
            elem=self._cr,
            wf_type=wf_type,
            amp_scale=cr_drive_amp_scaling,
            duration=cr_duration_clock_cycles,
            sgn=1 if sgn == "direct" else -1,
        )

    def _cr_cancel_play(
        self,
        sgn: Literal["direct", "echo"],
        wf_type: str,
        cr_cancel_amp_scaling,
        cr_duration_clock_cycles,
    ) -> None:
        # Cancel waveform name depends on pair
        cancel_wf = f"cr_{wf_type}_{self.qubit_pair.name}"
        self._play_pulse(
            elem=self._qt.xy,
            wf_type=cancel_wf,
            amp_scale=cr_cancel_amp_scaling,
            duration=cr_duration_clock_cycles,
            sgn=1 if sgn == "direct" else -1,
        )

    # ---- CR Implementations (one per cr_type) ----
    def _direct(
        self,
        wf_type: str,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
    ) -> None:
        self._cr_drive_shift_phase(cr_drive_phase)
        align(*self._cr_elems)

        # Direct
        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        # Cleanup
        # reset_frame(self._cr.name)
        self._cr_drive_shift_phase(-cr_drive_phase)
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    def _direct_echo(
        self,
        wf_type: str,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
    ) -> None:
        self._cr_drive_shift_phase(cr_drive_phase)
        align(*self._cr_elems)

        # Direct
        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._qc.xy.play("x180")
        align(*self._cr_elems)

        # Echo
        self._cr_drive_play("echo", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._qc.xy.play("x180")
        align(*self._cr_elems)

        # Cleanup
        # reset_frame(self._cr.name)
        self._cr_drive_shift_phase(-cr_drive_phase)
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    def _direct_cancel(
        self,
        wf_type: str,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        cr_cancel_amp_scaling,
        cr_cancel_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
    ) -> None:
        self._cr_drive_shift_phase(cr_drive_phase)
        self._cr_cancel_shift_phase(cr_cancel_phase)
        align(*self._cr_elems)

        # Direct (drive + cancel)
        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._cr_cancel_play("direct", wf_type, cr_cancel_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        # Cleanup
        # reset_frame(self._cr.name)
        # reset_frame(self._qt.xy.name)
        align(*self._cr_elems)

        self._cr_drive_shift_phase(-cr_drive_phase)
        self._cr_cancel_shift_phase(-cr_cancel_phase)
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    def _direct_cancel_echo(
        self,
        wf_type: str,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        cr_cancel_amp_scaling,
        cr_cancel_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
    ) -> None:
        self._cr_drive_shift_phase(cr_drive_phase)
        self._cr_cancel_shift_phase(cr_cancel_phase)
        align(*self._cr_elems)

        # Direct (drive + cancel)
        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._cr_cancel_play("direct", wf_type, cr_cancel_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._qc.xy.play("x180")
        align(*self._cr_elems)

        # Echo
        self._cr_drive_play("echo", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._cr_cancel_play("echo", wf_type, cr_cancel_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._qc.xy.play("x180")
        align(*self._cr_elems)

        # Cleanup
        # reset_frame(self._cr.name)
        # reset_frame(self._qt.xy.name)
        self._cr_drive_shift_phase(-cr_drive_phase)
        self._cr_cancel_shift_phase(-cr_cancel_phase)
        align(*self._cr_elems)

        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)


# ============================================================================
# Stark-Induced CZ Gate
# ============================================================================
@quam_dataclass
class StarkInducedCZGate(_QubitPairCrossDriveHelpers, QubitPairMacro):
    # Gate-level parameters (composite CR, stored under macros)
    qc_correction_phase: Optional[float] = None  # ZI correction
    qt_correction_phase: Optional[float] = None  # IZ correction

    # ---- Public API ----
    def apply(
        self,
        wf_type: Optional[Literal["square", "cosine", "gauss", "flattop"]] = "flattop",
        zz_duration_clock_cycles: Optional[Union[float, qua_T]] = None,
        zz_control_amp_scaling: Optional[Union[float, qua_T, _tuple, _list]] = None,
        zz_target_amp_scaling: Optional[Union[float, qua_T, _tuple, _list]] = None,
        zz_relative_phase: Optional[Union[float, qua_T, _tuple, _list]] = None,
        qc_correction_phase: Optional[Union[float, qua_T]] = None,
        qt_correction_phase: Optional[Union[float, qua_T]] = None,
    ) -> None:
        p = self._merge_params(
            dict(
                qc_correction_phase=self.qc_correction_phase,
                qt_correction_phase=self.qt_correction_phase,
            ),
            wf_type=wf_type,
            zz_duration_clock_cycles=zz_duration_clock_cycles,
            zz_control_amp_scaling=zz_control_amp_scaling,
            zz_target_amp_scaling=zz_target_amp_scaling,
            zz_relative_phase=zz_relative_phase,
            qc_correction_phase=qc_correction_phase,
            qt_correction_phase=qt_correction_phase,
        )

        # Relative-phase pre-rotation
        self._zz_shift_relative_phase(zz_relative_phase)

        # Main lobes
        align(self._zz.name, self._qt.xy_detuned.name)
        self._zz_control_drive_play(wf_type, zz_control_amp_scaling, zz_duration_clock_cycles)
        self._zz_target_drive_play(wf_type, zz_target_amp_scaling, zz_duration_clock_cycles)

        # Correct and clean up
        align(self._zz.name, self._qt.xy_detuned.name, self._qc.xy.name, self._qt.xy.name)
        self._qc_shift_correction_phase(qc_correction_phase)  # ZI
        self._qt_shift_correction_phase(qt_correction_phase)  # IZ

    # hardware elem
    @property
    def _zz(self):
        return self.qubit_pair.zz_drive

    # ---- Sequence-specific helpers ----
    def _zz_shift_relative_phase(self, phi: Optional[Union[float, qua_T, _tuple, _list]]) -> None:
        if phi is not None:
            self._qt.xy_detuned.frame_rotation_2pi(phi)

    def _zz_control_drive_play(self, wf_type, zz_control_amp_scaling, zz_duration_clock_cycles) -> None:
        self._play_pulse(
            elem=self._zz,
            wf_type=wf_type,
            amp_scale=zz_control_amp_scaling,
            duration=zz_duration_clock_cycles,
        )

    def _zz_target_drive_play(self, wf_type, zz_target_amp_scaling, zz_duration_clock_cycles) -> None:
        target_wf = f"zz_{wf_type}_{self.qubit_pair.name}"
        self._play_pulse(
            elem=self._qt.xy_detuned,
            wf_type=target_wf,
            amp_scale=zz_target_amp_scaling,
            duration=zz_duration_clock_cycles,
        )
