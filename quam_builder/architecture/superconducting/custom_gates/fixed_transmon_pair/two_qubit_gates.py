from typing import Literal, Optional

from qm.qua import *
from qm.qua._dsl import QuaVariable

from quam.components.macro import QubitPairMacro
from quam.components.pulses import Pulse
from quam.core import quam_dataclass

__all__ = ["CRGate"]


qua_T = QuaVariable


@quam_dataclass
class CRGate(QubitPairMacro):    # Gate-level parameters (apply to the entire CR gate as a unit).
    # These parameters are stored under macros in state.json and not each for operation
    zi_correction_phase: Optional[float | qua_T] = 0.0
    iz_correction_phase: Optional[float | qua_T] = 0.0

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def apply(
        self,
        cr_type: Literal["direct", "direct+cancel", "direct+echo", "direct+cancel+echo"] = "direct",
        wf_type: Optional[Literal["square", "cosine", "gauss", "flattop"]] = None,
        cr_duration_clock_cycles: Optional[int | qua_T] = None,
        cr_drive_amp_scaling: Optional[float | qua_T] = None,
        cr_drive_phase: Optional[float | qua_T] = None,
        cr_cancel_amp_scaling: Optional[float | qua_T] = None,
        cr_cancel_phase: Optional[float | qua_T] = None,
        zi_correction_phase: Optional[float | qua_T] = None,
        iz_correction_phase: Optional[float | qua_T] = None,
    ) -> None:
        """
        Thin router that delegates to a dedicated method per CR sequence.
        Any provided kwargs override the instance's gate parameters for this call.
        """
        p = self._merged_params(
            wf_type=wf_type,
            cr_drive_amp_scaling=cr_drive_amp_scaling,
            cr_drive_phase=cr_drive_phase,
            cr_cancel_amp_scaling=cr_cancel_amp_scaling,
            cr_cancel_phase=cr_cancel_phase,
            cr_duration_clock_cycles=cr_duration_clock_cycles,
            zi_correction_phase=zi_correction_phase,
            iz_correction_phase=iz_correction_phase,
        )

        if cr_type == "direct":
            self._direct(**p)
        elif cr_type == "direct+echo":
            self._direct_echo(**p)
        elif cr_type == "direct+cancel":
            self._direct_cancel(**p)
        elif cr_type == "direct+cancel+echo":
            self._direct_cancel_echo(**p)
        else:
            raise ValueError(f"Unknown cr_type '{cr_type}'")

    # -------------------------------------------------------------------------
    # Small helpers
    # -------------------------------------------------------------------------
    @property
    def _qc(self):
        return self.qubit_pair.qubit_control

    @property
    def _qt(self):
        return self.qubit_pair.qubit_target

    @property
    def _cr(self):
        return self.qubit_pair.cross_resonance

    @property
    def _cr_elems(self):
        return [self._qc.xy.name, self._qt.xy.name, self._cr.name]

    def _merged_params(self, **overrides):
        """Merge per-call overrides onto instance defaults."""
        base = dict(
            wf_type=self.wf_type,
            cr_drive_amp_scaling=self.cr_drive_amp_scaling,
            cr_drive_phase=self.cr_drive_phase,
            cr_cancel_amp_scaling=self.cr_cancel_amp_scaling,
            cr_cancel_phase=self.cr_cancel_phase,
            cr_duration_clock_cycles=self.cr_duration_clock_cycles,
            zi_correction_phase=self.zi_correction_phase,
            iz_correction_phase=self.iz_correction_phase,
        )
        base.update({k: v for k, v in overrides.items() if v is not None})
        return base

    # ---- Phase shifts ----
    def _cr_drive_shift_phase(self, cr_drive_phase: Optional[float | qua_T]) -> None:
        if cr_drive_phase is not None:
            self._cr.frame_rotation_2pi(cr_drive_phase)

    def _cr_cancel_shift_phase(self, cr_cancel_phase: Optional[float | qua_T]) -> None:
        if cr_cancel_phase is not None:
            self._qt.xy.frame_rotation_2pi(cr_cancel_phase)

    def _zi_shift_correction_phase(self, zi_correction_phase: Optional[float | qua_T]) -> None:
        if zi_correction_phase is not None:
            self._qc.xy.frame_rotation_2pi(zi_correction_phase)

    def _iz_shift_correction_phase(self, iz_correction_phase: Optional[float | qua_T]) -> None:
        if iz_correction_phase is not None:
            self._qt.xy.frame_rotation_2pi(iz_correction_phase)

    # ---- Low-level play helpers ----
    @staticmethod
    def _play_cr_pulse(
        elem: str,
        wf_type: str,
        amp_scale: Optional[float | qua_T],
        duration: Optional[int | qua_T],
        sgn: int = 1,
    ) -> None:
        # Mirrors the original branching to avoid QUA optional arg issues
        if amp_scale is None and duration is None:
            elem.play(wf_type)
        elif amp_scale is None:
            elem.play(wf_type, duration=duration)
        elif duration is None:
            elem.play(wf_type, amplitude_scale=sgn * amp_scale)
        else:
            elem.play(wf_type, amplitude_scale=sgn * amp_scale, duration=duration)

    def _cr_drive_play(
        self,
        sgn: Literal["direct", "echo"],
        wf_type: str,
        cr_drive_amp_scaling,
        cr_duration_clock_cycles,
    ) -> None:
        self._play_cr_pulse(
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
        self._play_cr_pulse(
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
        cr_drive_amp_scaling,
        cr_drive_phase,
        cr_duration_clock_cycles,
        zi_correction_phase,
        iz_correction_phase,
        **_,
    ) -> None:
        self._cr_drive_shift_phase(cr_drive_phase)
        align(*self._cr_elems)

        # Direct
        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        # Cleanup
        reset_frame(self._cr.name)
        self._zi_shift_correction_phase(zi_correction_phase)
        self._iz_shift_correction_phase(iz_correction_phase)
        align(*self._cr_elems)

    def _direct_echo(
        self,
        wf_type: str,
        cr_drive_amp_scaling,
        cr_drive_phase,
        cr_duration_clock_cycles,
        zi_correction_phase,
        iz_correction_phase,
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
        reset_frame(self._cr.name)
        self._zi_shift_correction_phase(zi_correction_phase)
        self._iz_shift_correction_phase(iz_correction_phase)
        align(*self._cr_elems)

    def _direct_cancel(
        self,
        wf_type: str,
        cr_drive_amp_scaling,
        cr_drive_phase,
        cr_cancel_amp_scaling,
        cr_cancel_phase,
        cr_duration_clock_cycles,
        zi_correction_phase,
        iz_correction_phase,
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
        reset_frame(self._cr.name)
        reset_frame(self._qt.xy.name)
        align(*self._cr_elems)

        self._zi_shift_correction_phase(zi_correction_phase)
        self._iz_shift_correction_phase(iz_correction_phase)
        align(*self._cr_elems)


    def _direct_cancel_echo(
        self,
        wf_type: str,
        cr_drive_amp_scaling,
        cr_drive_phase,
        cr_cancel_amp_scaling,
        cr_cancel_phase,
        cr_duration_clock_cycles,
        zi_correction_phase,
        iz_correction_phase,
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
        reset_frame(self._cr.name)
        reset_frame(self._qt.xy.name)
        align(*self._cr_elems)

        self._zi_shift_correction_phase(zi_correction_phase)
        self._iz_shift_correction_phase(iz_correction_phase)
        align(*self._cr_elems)












    def apply(
        self,
        cr_type: Literal["direct", "direct+cancel", "direct+echo", "direct+cancel+echo"] = "direct",
        wf_type: Literal["square", "cosine", "gauss", "flattop"] = "square",
        cr_drive_amp_scaling: Optional[float | qua_T] = None,
        cr_drive_phase: Optional[float | qua_T] = None,
        cr_cancel_amp_scaling: Optional[float | qua_T] = None,
        cr_cancel_phase: Optional[float | qua_T] = None,
        cr_duration_clock_cycles: Optional[float | qua_T] = None,
        zi_correction_phase: Optional[float | qua_T] = None,
    ) -> None:
        qc = self.qubit_pair.qubit_control
        qt = self.qubit_pair.qubit_target
        cr = self.qubit_pair.cross_resonance
        cr_elems = [qc.xy.name, qt.xy.name, cr.name]

        def _play_cr_pulse(
            elem,
            wf_type: str = wf_type,
            amp_scale: Optional[float | qua_T] = None,
            duration: Optional[float | qua_T] = None,
            sgn: int = 1,
        ):
            if amp_scale is None and duration is None:
                elem.play(wf_type)
            elif amp_scale is None:
                elem.play(wf_type, duration=duration)
            elif duration is None:
                elem.play(wf_type, amplitude_scale=sgn * amp_scale)
            else:
                elem.play(wf_type, amplitude_scale=sgn * amp_scale, duration=duration)


    # ---- Phase shifts ----
        def cr_drive_shift_phase():
            if cr_drive_phase is not None:
                cr.frame_rotation_2pi(cr_drive_phase)

        def cr_cancel_shift_phase():
            if cr_cancel_phase is not None:
                qt.xy.frame_rotation_2pi(cr_cancel_phase)

        def zz_shift_correction_phase():
            if zi_correction_phase is not None:
                qc.xy.frame_rotation_2pi(zi_correction_phase)
                qt.xy.frame_rotation_2pi(zi_correction_phase)

        def cr_drive_play(
            sgn: Literal["direct", "echo"] = "direct",
            wf_type=wf_type,
        ):
            _play_cr_pulse(
                elem=cr,
                wf_type=wf_type,
                amp_scale=cr_drive_amp_scaling,
                duration=cr_duration_clock_cycles,
                sgn=1 if sgn == "direct" else -1,
            )

        def cr_cancel_play(
            sgn: Literal["direct", "echo"] = "direct",
            wf_type=wf_type,
        ):
            _play_cr_pulse(
                elem=qt.xy,
                wf_type=f"cr_{wf_type}_{self.qubit_pair.name}",
                amp_scale=cr_cancel_amp_scaling,
                duration=cr_duration_clock_cycles,
                sgn=1 if sgn == "direct" else -1,
            )

        if cr_type == "direct":
            cr_drive_shift_phase()
            align(*cr_elems)

            cr_drive_play(sgn="direct")
            align(*cr_elems)

            reset_frame(cr.name)
            zz_shift_correction_phase()
            align(*cr_elems)

        elif cr_type == "direct+echo":
            cr_drive_shift_phase()
            align(*cr_elems)

            cr_drive_play(sgn="direct")
            align(*cr_elems)

            qc.xy.play("x180")
            align(*cr_elems)

            cr_drive_play(sgn="echo")
            align(*cr_elems)

            qc.xy.play("x180")
            align(*cr_elems)

            reset_frame(cr.name)
            zz_shift_correction_phase()
            align(*cr_elems)

        elif cr_type == "direct+cancel":
            cr_drive_shift_phase()
            cr_cancel_shift_phase()
            align(*cr_elems)

            cr_drive_play(sgn="direct")
            cr_cancel_play(sgn="direct")
            align(*cr_elems)

            reset_frame(cr.name)
            reset_frame(qt.xy.name)
            zz_shift_correction_phase()
            align(*cr_elems)

        elif cr_type == "direct+cancel+echo":
            cr_drive_shift_phase()
            cr_cancel_shift_phase()
            align(*cr_elems)

            cr_drive_play(sgn="direct")
            cr_cancel_play(sgn="direct")
            align(*cr_elems)

            qc.xy.play("x180")
            align(*cr_elems)

            cr_drive_play(sgn="echo")
            cr_cancel_play(sgn="echo")
            align(*cr_elems)

            qc.xy.play("x180")
            align(*cr_elems)

            reset_frame(cr.name)
            reset_frame(qt.xy.name)
            zz_shift_correction_phase()
            align(*cr_elems)
