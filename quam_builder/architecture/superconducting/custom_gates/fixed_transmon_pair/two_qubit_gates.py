from dataclasses import field
from typing import Literal, Optional, Union, Tuple, List, Set

from qm.qua import *
from qm.qua._expressions import QuaExpression, QuaVariable

from quam.components.macro import QubitPairMacro
from quam.core import quam_dataclass

__all__ = ["CrossResonanceGate", "TwoElementCrossResonanceGate"]

qua_T = Union[QuaVariable, QuaExpression]
_tuple = Tuple[Union[float, qua_T]]
_list = List[Union[float, qua_T]]


# ============================================================================
# Shared helpers for 2-qubit gates (no dataclass fields here; just utilities)
# ============================================================================
class _QubitPairCrossResonanceHelpers:

    # ---- Small helpers (common) ----
    @property
    def _qc(self):
        return self.qubit_pair.qubit_control

    @property
    def _qt(self):
        return self.qubit_pair.qubit_target
    
    @property
    def _pi_len(self):
        return self._qc.xy.operations["x180"].length // 4

    # Generic merge that ignores None (None == "no override")
    def _merge_params(self, defaults: dict, **overrides) -> dict:
        out = dict(defaults)
        for k, v in overrides.items():
            if k in ["qc_correction_phase", "qt_correction_phase"] and v is not None:
                out[k] = v
            else:
                out[k] = v
        return out

    # If override is None -> use base, else multiply by base
    @staticmethod
    def _multiply_or_default(
        override: Optional[Union[float, qua_T]],
        base: Union[float, qua_T],
    ) -> Union[float, qua_T]:
        return base if override is None else override * base

    # If override is None -> use base, else add base
    @staticmethod
    def _add_or_default(
        override: Optional[Union[float, qua_T]],
        base: Union[float, qua_T],
    ) -> Union[float, qua_T]:
        return base if override is None else override + base

    # ---- Phase shifts (common ZI / IZ corrections) ----
    def _qc_shift_correction_phase(self, phi: Optional[float | qua_T]) -> None:
        if phi is not None:
            self._qc.xy.frame_rotation_2pi(phi)

    def _qt_shift_correction_phase(self, phi: Optional[float | qua_T]) -> None:
        if phi is not None:
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
class CrossResonanceGate(_QubitPairCrossResonanceHelpers, QubitPairMacro):
    # Gate-level parameters (composite CR, stored under macros)
    qc_correction_phase: Optional[float] = None  # ZI correction
    qt_correction_phase: Optional[float] = None  # IZ correction

    # ---- Public API ----
    def apply(
        self,
        cr_type: Literal["direct", "direct+cancel", "direct+echo", "direct+cancel+echo"] = "direct",
        wf_type: Optional[Literal["square", "flattop"]] = "flattop",
        cr_duration_clock_cycles: Optional[int | qua_T] = None,
        cr_drive_amp_scaling: Optional[float | qua_T] = None,
        cr_drive_phase: Optional[float | qua_T] = None,
        cr_cancel_amp_scaling: Optional[float | qua_T] = None,
        cr_cancel_phase: Optional[float | qua_T] = None,
        qc_correction_phase: Optional[float | qua_T] = None,
        qt_correction_phase: Optional[float | qua_T] = None,
    ) -> None:
        # Relative to the stored CrossResonance component parameters
        cr_drive_amp_scaling = self._multiply_or_default(cr_drive_amp_scaling, self._cr.drive_amplitude_scaling)
        cr_drive_phase = self._add_or_default(cr_drive_phase, self._cr.drive_phase)

        cr_cancel_amp_scaling = self._multiply_or_default(cr_cancel_amp_scaling, self._cr.cancel_amplitude_scaling)
        cr_cancel_phase = self._add_or_default(cr_cancel_phase, self._cr.cancel_phase)

        qc_correction_phase = self._add_or_default(qc_correction_phase, self._cr.qc_correction_phase)
        qt_correction_phase = self._add_or_default(qt_correction_phase, self._cr.qt_correction_phase)

        # Overwrite the stored CrossResonance component parameters if not None
        params = self._merge_params(
            defaults=dict(
                qc_correction_phase=self.qc_correction_phase,
                qt_correction_phase=self.qt_correction_phase,
            ),
            **dict( # overrides
                wf_type=wf_type,
                cr_duration_clock_cycles=cr_duration_clock_cycles,
                cr_drive_amp_scaling=cr_drive_amp_scaling,
                cr_drive_phase=cr_drive_phase,
                cr_cancel_amp_scaling=cr_cancel_amp_scaling,
                cr_cancel_phase=cr_cancel_phase,
                qc_correction_phase=qc_correction_phase,
                qt_correction_phase=qt_correction_phase,
            ),
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
    
    # Direct Only
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
        self._cr_drive_shift_phase(-cr_drive_phase)
        align(*self._cr_elems)
        
        # Compenstate
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    # Direct + Echo
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
        self._cr_drive_shift_phase(-cr_drive_phase)
        align(*self._cr_elems)
        
        # Compenstate
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    # Direct + Cancel
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
        self._cr_drive_shift_phase(-cr_drive_phase)
        self._cr_cancel_shift_phase(-cr_cancel_phase)
        align(*self._cr_elems)
    
        # Compenstate
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    # (Direct + Echo) + (Cancel + Echo)
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
        self._cr_drive_shift_phase(-cr_drive_phase)
        self._cr_cancel_shift_phase(-cr_cancel_phase)
        align(*self._cr_elems)

        # Compenstate
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)



# ============================================================================
# Two element Cross-Resonance (CR) Gate
# ============================================================================
@quam_dataclass
class TwoElementCrossResonanceGate(_QubitPairCrossResonanceHelpers, QubitPairMacro):
    # Gate-level parameters (composite CR, stored under macros)
    qc_correction_phase: Optional[float] = None  # ZI correction
    qt_correction_phase: Optional[float] = None  # IZ correction
    
    # def __init__(self):
    #     super().__init__()

    # ---- Public API ----
    def apply(
        self,
        cr_type: Literal["direct", "direct+cancel", "direct+echo", "direct+cancel+echo"] = "direct",
        wf_type: Optional[Literal["cosine", "gaussian"]] = "cosine",
        sweep_type: Optional[Literal["amp", "dur", "phase", "amp+dur", "amp+phase", "dur+phase", "amp+dur+phase"]] = "amp",
        sweep_duration: bool = True,
        cr_sweeping_param: Optional[Union[float | qua_T, int | qua_T]] = None,
        cr_duration_clock_cycles: Optional[int | qua_T] = None,
        cr_drive_amp_scaling: Optional[float | qua_T] = None,
        cr_drive_phase: Optional[float | qua_T] = None,
        cr_cancel_amp_scaling: Optional[float | qua_T] = None,
        cr_cancel_phase: Optional[float | qua_T] = None,
        qc_correction_phase: Optional[float | qua_T] = None,
        qt_correction_phase: Optional[float | qua_T] = None,
    ) -> None:

        sweep_tokens = set(sweep_type.split("+")) if sweep_type else set()
        has_amp   = "amp" in sweep_tokens
        has_dur   = "dur" in sweep_tokens
        has_phase = "phase" in sweep_tokens

        # Relative to the stored CrossResonance component parameters
        cr_drive_amp_scaling = self._multiply_or_default(cr_drive_amp_scaling, self._cr.drive_amplitude_scaling)
        cr_drive_phase = self._add_or_default(cr_drive_phase, self._cr.drive_phase)

        cr_cancel_amp_scaling = self._multiply_or_default(cr_cancel_amp_scaling, self._cr.cancel_amplitude_scaling)
        cr_cancel_phase = self._add_or_default(cr_cancel_phase, self._cr.cancel_phase)

        qc_correction_phase = self._add_or_default(qc_correction_phase, self._cr.qc_correction_phase)
        qt_correction_phase = self._add_or_default(qt_correction_phase, self._cr.qt_correction_phase)

        # Overwrite the stored CrossResonance component parameters if not None
        params = self._merge_params(
            defaults=dict(
                qc_correction_phase=self.qc_correction_phase,
                qt_correction_phase=self.qt_correction_phase,
            ),
            **dict( # overrides
                wf_type=wf_type,
                sweep_type=sweep_type,
                sweep_tokens=sweep_tokens,
                has_amp=has_amp,
                has_dur=has_dur,
                has_phase=has_phase,
                sweep_duration=sweep_duration,
                cr_sweeping_param=cr_sweeping_param,
                cr_duration_clock_cycles=cr_duration_clock_cycles,
                cr_drive_amp_scaling=cr_drive_amp_scaling,
                cr_drive_phase=cr_drive_phase,
                cr_cancel_amp_scaling=cr_cancel_amp_scaling,
                cr_cancel_phase=cr_cancel_phase,
                qc_correction_phase=qc_correction_phase,
                qt_correction_phase=qt_correction_phase,
            ),
        )

        if cr_type == "direct":
            self._direct(**params)
        elif cr_type == "direct+echo":
            self._direct_echo(**params)
        elif cr_type == "direct+cancel":
            self._direct_cancel(**params)
        elif cr_type == "direct+echo+cancel":
            self._direct_echo_cancel(**params)
        else:
            raise ValueError(f"Unknown cr_type '{cr_type}'")

    # hardware elems
    @property
    def _cr(self):
        return self.qubit_pair.cross_resonance

    @property
    def _cr_edge(self):
        return self.qubit_pair.cross_resonance_edge
    
    @property
    def _cr_elems(self):
        return [self._qc.xy.name, self._qt.xy.name, self._cr_edge.name, self._cr.name]
    
    @property
    def _rise_fall_time(self):
        return self._cr_edge.operations["rise_cosine"].length // 4

    @property
    def _flattop_time(self):
        return self._cr.operations["square"].length // 4
    



    # ---- Phase helpers specific to CR ----
    def _cr_drive_shift_phase(self, phi: Optional[float | qua_T]) -> None:
        if phi is not None:
            self._cr.frame_rotation_2pi(phi)
            self._cr_edge.frame_rotation_2pi(phi)

    def _cr_cancel_shift_phase(self, phi: Optional[float | qua_T]) -> None:
        if phi is not None:
            self._qt.xy.frame_rotation_2pi(phi)
            self._qt.xy_edge.frame_rotation_2pi(phi)

    # ---- Play wrappers ----
    def _cr_pulse_play(
        self,
        wf_type: str,
        sweep_type: Literal["amplitude", "duration"],
        cr_sweeping_param: Optional[Union[float | qua_T, int | qua_T]] ,
        cancel_pulse: bool = False,
    ) -> None:
        if sweep_type == "amplitude":
            self._cr_edge.play(f"rise_{wf_type}", amplitude_scale=cr_sweeping_param)
            self._qt.xy_edge.play(f"rise_{wf_type}", amplitude_scale=cr_sweeping_param) if cancel_pulse else None
            self._cr.wait(self._rise_fall_time)
            self._qt.xy.wait(self._rise_fall_time) if cancel_pulse else None
            self._cr.play('square',amplitude_scale=cr_sweeping_param)
            self._qt.xy.play('const', amplitude_scale=cr_sweeping_param) if cancel_pulse else None
            self._cr_edge.wait(self._flattop_time)
            self._qt.xy_edge.wait(self._flattop_time) if cancel_pulse else None
            self._cr_edge.play(f"fall_{wf_type}", amplitude_scale=cr_sweeping_param)
            self._qt.xy_edge.play(f"fall_{wf_type}", amplitude_scale=cr_sweeping_param) if cancel_pulse else None

        elif sweep_type == "duration":
            self._cr_edge.play(f"rise_{wf_type}")
            self._qt.xy_edge.play(f"rise_{wf_type}") if cancel_pulse else None
            self._cr.wait(self._rise_fall_time)
            self._qt.xy.wait(self._rise_fall_time) if cancel_pulse else None
            self._cr.play('square',duration=cr_sweeping_param)
            self._qt.xy.play('const', duration=cr_sweeping_param) if cancel_pulse else None
            self._cr_edge.wait(cr_sweeping_param)
            self._qt.xy_edge.wait(cr_sweeping_param) if cancel_pulse else None
            self._cr_edge.play(f"fall_{wf_type}")
            self._qt.xy_edge.play(f"fall_{wf_type}") if cancel_pulse else None
        else:
            raise ValueError(f"Unknown sweep_type '{sweep_type}'")

    def _cr_pulse_play_amp_dur(
        self,
        wf_type: str,
        has_amp: bool,
        has_dur: bool,
        has_phase: bool,
        cr_duration_clock_cycles: Optional[int | qua_T] = None,
        cr_drive_amp_scaling: Optional[float | qua_T] = None,
        cancel_pulse: bool = False,
    ) -> None:
        delay = -2 if has_phase else 0
        print("delay:", delay)
        if has_dur:
            delay -= 2 if has_amp else 0
            self._cr_edge.play(f"rise_{wf_type}", amplitude_scale=cr_drive_amp_scaling)
            self._cr.wait(self._rise_fall_time)
            self._cr.play('square',amplitude_scale=cr_drive_amp_scaling, duration=cr_duration_clock_cycles)
            self._cr_edge.wait(cr_duration_clock_cycles+delay)
            self._cr_edge.play(f"fall_{wf_type}", amplitude_scale=cr_drive_amp_scaling)
            if cancel_pulse:
                self._qt.xy_edge.play(f"rise_{wf_type}",amplitude_scale=cr_drive_amp_scaling) 
                self._qt.xy.wait(self._rise_fall_time) 
                self._qt.xy.play('const',amplitude_scale=cr_drive_amp_scaling, duration=cr_duration_clock_cycles) 
                self._qt.xy_edge.wait(cr_duration_clock_cycles+delay) 
                self._qt.xy_edge.play(f"fall_{wf_type}",amplitude_scale=cr_drive_amp_scaling) 

        else:
            self._cr_edge.play(f"rise_{wf_type}", amplitude_scale=cr_drive_amp_scaling)
            self._cr.wait(self._rise_fall_time)
            self._cr.play('square',amplitude_scale=cr_drive_amp_scaling, duration=cr_duration_clock_cycles)
            self._cr_edge.wait(self._flattop_time)
            self._cr_edge.play(f"fall_{wf_type}", amplitude_scale=cr_drive_amp_scaling)
            if cancel_pulse:
                self._qt.xy_edge.play(f"rise_{wf_type}", amplitude_scale=cr_drive_amp_scaling) 
                self._qt.xy.wait(self._rise_fall_time) 
                self._qt.xy.play('const', amplitude_scale=cr_drive_amp_scaling) 
                self._qt.xy_edge.wait(self._flattop_time) 
                self._qt.xy_edge.play(f"fall_{wf_type}", amplitude_scale=cr_drive_amp_scaling)



    def _cr_echo_pulse_play(
        self,
        wf_type: str,
        sweep_type: Literal["amplitude", "duration"],
        cr_sweeping_param: Optional[Union[float | qua_T, int | qua_T]] ,
        cancel_pulse: bool = False,
    ) -> None:
        if sweep_type == "amplitude":
            self._qc.xy.wait(self._rise_fall_time*2+self._flattop_time)
            self._qc.xy.play("x180")
            self._cr_edge.wait(self._pi_len)
            self._qt.xy_edge.wait(self._pi_len) if cancel_pulse else None
            self._cr_edge.play(f"rise_{wf_type}_echo", amplitude_scale=cr_sweeping_param)
            self._qt.xy_edge.play(f"rise_{wf_type}_echo", amplitude_scale=cr_sweeping_param) if cancel_pulse else None
            self._cr.wait(self._rise_fall_time*2+self._pi_len)
            self._qt.xy.wait(self._rise_fall_time*2+self._pi_len) if cancel_pulse else None
            self._cr.play('square',amplitude_scale=-cr_sweeping_param)
            self._qt.xy.play('const', amplitude_scale=-cr_sweeping_param) if cancel_pulse else None
            self._cr_edge.wait(self._flattop_time)
            self._qt.xy_edge.wait(self._flattop_time) if cancel_pulse else None
            self._cr_edge.play(f"fall_{wf_type}_echo", amplitude_scale=cr_sweeping_param)
            self._qt.xy_edge.play(f"fall_{wf_type}_echo", amplitude_scale=cr_sweeping_param) if cancel_pulse else None
            self._qc.xy.wait(self._rise_fall_time*2+self._flattop_time)
            self._qc.xy.play("x180")
        elif sweep_type == "duration":
            self._qc.xy.wait(self._rise_fall_time*2+cr_sweeping_param)
            self._qc.xy.play("x180")
            self._cr_edge.wait(self._pi_len)
            self._qt.xy_edge.wait(self._pi_len) if cancel_pulse else None
            self._cr_edge.play(f"rise_{wf_type}_echo")
            self._qt.xy_edge.play(f"rise_{wf_type}_echo") if cancel_pulse else None
            self._cr.wait(self._rise_fall_time*2+self._pi_len)
            self._qt.xy.wait(self._rise_fall_time*2+self._pi_len) if cancel_pulse else None
            self._cr.play('square',duration=cr_sweeping_param,amplitude_scale=-1)
            self._qt.xy.play('const',duration=cr_sweeping_param,amplitude_scale=-1) if cancel_pulse else None
            self._cr_edge.wait(cr_sweeping_param)
            self._qt.xy_edge.wait(cr_sweeping_param) if cancel_pulse else None
            self._cr_edge.play(f"fall_{wf_type}_echo")
            self._qt.xy_edge.play(f"fall_{wf_type}_echo") if cancel_pulse else None
            self._qc.xy.wait(self._rise_fall_time*2+cr_sweeping_param)
            self._qc.xy.play("x180")

        else:
            raise ValueError(f"Unknown sweep_type '{sweep_type}'")
    
    def _cr_echo_pulse_play_amp_dur(
        self,
        wf_type: str,
        has_amp: bool,
        has_dur: bool,
        has_phase: bool,
        cr_duration_clock_cycles: Optional[int | qua_T] = None,
        cr_drive_amp_scaling: Optional[float | qua_T] = None,
        cancel_pulse: bool = False,
    ) -> None:
        delay = -2 #wired but works, i don't know why no matter use phase sweep or not the delay is always should be -2. leave it now
        if has_dur:
            # delay -= 2 if  has_amp else 0 # still wired, leave it now
            # echo pi pulse
            self._qc.xy.wait(self._rise_fall_time*2+cr_duration_clock_cycles)
            self._qc.xy.play("x180")
            self._qc.xy.wait(self._rise_fall_time*2+cr_duration_clock_cycles)
            self._qc.xy.play("x180")
            #echo cr pulse
            self._cr_edge.wait(self._pi_len)
            self._cr_edge.play(f"rise_{wf_type}_echo", amplitude_scale=cr_drive_amp_scaling)
            self._cr.wait(self._rise_fall_time*2+self._pi_len)
            self._cr.play('square',amplitude_scale=-cr_drive_amp_scaling,duration=cr_duration_clock_cycles)
            self._cr_edge.wait(cr_duration_clock_cycles+delay)
            self._cr_edge.play(f"fall_{wf_type}_echo", amplitude_scale=cr_drive_amp_scaling)
            if cancel_pulse:
                self._qt.xy_edge.wait(self._pi_len)
                self._qt.xy_edge.play(f"rise_{wf_type}", amplitude_scale=-cr_drive_amp_scaling) 
                self._qt.xy.wait(self._rise_fall_time*2+self._pi_len) 
                self._qt.xy.play('const',amplitude_scale=-cr_drive_amp_scaling, duration=cr_duration_clock_cycles) 
                self._qt.xy_edge.wait(cr_duration_clock_cycles
                                      +delay
                                      ) 
                self._qt.xy_edge.play(f"fall_{wf_type}", amplitude_scale=-cr_drive_amp_scaling) 

        else:
            # echo pi pulse 
            self._qc.xy.wait(self._rise_fall_time*2+self._flattop_time)
            self._qc.xy.play("x180")
            self._qc.xy.wait(self._rise_fall_time*2+self._flattop_time)
            self._qc.xy.play("x180")
            # echo cr pulse
            self._cr_edge.wait(self._pi_len)
            self._cr_edge.play(f"rise_{wf_type}_echo", amplitude_scale=cr_drive_amp_scaling)
            self._cr.wait(self._rise_fall_time*2+self._pi_len)
            self._cr.play('square',amplitude_scale=-cr_drive_amp_scaling)
            self._cr_edge.wait(self._flattop_time)
            self._cr_edge.play(f"fall_{wf_type}_echo", amplitude_scale=cr_drive_amp_scaling)
            if cancel_pulse:
                self._qt.xy_edge.wait(self._pi_len)
                self._qt.xy_edge.play(f"rise_{wf_type}", amplitude_scale=cr_drive_amp_scaling) 
                self._qt.xy.wait(self._rise_fall_time*2+self._pi_len) 
                self._qt.xy.play('const', amplitude_scale=cr_drive_amp_scaling) 
                self._qt.xy_edge.wait(self._flattop_time) 
                self._qt.xy_edge.play(f"fall_{wf_type}", amplitude_scale=cr_drive_amp_scaling)

    # ---- CR Implementations (one per cr_type) ----
    
    # Direct Only
    def _direct(
        self,
        wf_type: str,
        has_amp: bool,
        has_dur: bool,
        has_phase: bool,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
    ) -> None:

        self._cr_drive_shift_phase(cr_drive_phase)
        align(*self._cr_elems)

        # self._cr_pulse_play(
        #     wf_type=wf_type,
        #     sweep_type=sweep_type,
        #     cr_sweeping_param=cr_sweeping_param)

        # DIrect
        self._cr_pulse_play_amp_dur(
            wf_type=wf_type,
            has_amp=has_amp, has_dur=has_dur, has_phase=has_phase,
            cr_duration_clock_cycles=cr_duration_clock_cycles,
            cr_drive_amp_scaling=cr_drive_amp_scaling,
            )

        # Cleanup
        self._cr_drive_shift_phase(-cr_drive_phase)
        align(*self._cr_elems)
        
        # Compenstate
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)



    def _direct_echo(
        self,
        wf_type: str,
        has_amp: bool,
        has_dur: bool,
        has_phase: bool,
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
        self._cr_pulse_play_amp_dur(
            wf_type=wf_type,
            has_amp=has_amp, has_dur=has_dur, has_phase=has_phase,
            cr_duration_clock_cycles=cr_duration_clock_cycles,
            cr_drive_amp_scaling=cr_drive_amp_scaling,
            )

        # Echo
        self._cr_echo_pulse_play_amp_dur(
            wf_type=wf_type,
            has_amp=has_amp, has_dur=has_dur, has_phase=has_phase,
            cr_duration_clock_cycles=cr_duration_clock_cycles,
            cr_drive_amp_scaling=cr_drive_amp_scaling
            )
        # Cleanup
        self._cr_drive_shift_phase(-cr_drive_phase)
        align(*self._cr_elems)
        
        # Compenstate
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)
        align(*self._cr_elems)



    def _direct_cancel(
        self,
        wf_type: str,
        sweep_type: str,
        cr_sweeping_param,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
        ) -> None:

        align(*self._cr_elems)

        self._cr_pulse_play(
            wf_type=wf_type,
            sweep_type=sweep_type,
            cr_sweeping_param=cr_sweeping_param,
            cancel_pulse=True
            )

    def _direct_echo_cancel(
        self,
        wf_type: str,
        has_amp: bool,
        has_dur: bool,
        has_phase: bool,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        cr_cancel_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
        ) -> None:

        self._cr_drive_shift_phase(cr_drive_phase)
        self._cr_cancel_shift_phase(cr_cancel_phase)
        align(*self._cr_elems)

        # Direct
        self._cr_pulse_play_amp_dur(
            wf_type=wf_type,
            has_amp=has_amp, has_dur=has_dur, has_phase=has_phase,
            cr_duration_clock_cycles=cr_duration_clock_cycles,
            cr_drive_amp_scaling=cr_drive_amp_scaling,
            cancel_pulse=True
            )

        # Echo
        self._cr_echo_pulse_play_amp_dur(
            wf_type=wf_type,
            has_amp=has_amp, has_dur=has_dur, has_phase=has_phase,
            cr_duration_clock_cycles=cr_duration_clock_cycles,
            cr_drive_amp_scaling=cr_drive_amp_scaling,
            cancel_pulse=True
            )

        # Cleanup
        self._cr_drive_shift_phase(-cr_drive_phase)
        self._cr_cancel_shift_phase(-cr_cancel_phase)
        align(*self._cr_elems)

        # Compenstate
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)


