"""Cross-resonance two-qubit gates.

`CRGate` drives `qubit_pair.cross_resonance` and reads the calibration parameters carried
on that channel (`CrossResonanceBase`). `StarkInducedCZGate` drives `qubit_pair.zz_drive`.
Either channel may be None on a pair that is not wired for it, in which case `apply()`
raises rather than dereferencing None.

Both gates work on any `QubitPair` that exposes those channels -- including a
`FluxTunableTransmonPair`, which can carry a flux-activated CZ and a CR gate at once.
"""

from typing import List, Literal, Optional, Tuple, Union

from qm.qua import *
from qm.qua._expressions import QuaExpression, QuaVariable
from quam.components.macro import QubitPairMacro
from quam.core import quam_dataclass

__all__ = ["CRGate", "StarkInducedCZGate"]

qua_T = Union[QuaVariable, QuaExpression]
_tuple = Tuple[Union[float, qua_T]]
_list = List[Union[float, qua_T]]


class _QubitPairCrossDriveHelpers:
    @property
    def _qc(self):
        return self.qubit_pair.qubit_control

    @property
    def _qt(self):
        return self.qubit_pair.qubit_target

    def _merge_params(self, defaults: dict, **overrides) -> dict:
        """Overlay `overrides` on `defaults`, treating None as 'no override'.

        The original took both branches of its `if` to the same assignment, so a None
        override silently erased the macro's stored correction phase. Here a None
        correction phase leaves the stored value in place, which is what the branch was
        written to do.
        """
        out = dict(defaults)
        for k, v in overrides.items():
            if k in ("qc_correction_phase", "qt_correction_phase") and v is None:
                continue
            out[k] = v
        return out

    @staticmethod
    def _resolve_from_channel(override, stored, combine: Literal["mul", "add"]):
        """Combine a per-call override with the value calibrated on the CR channel.

        `stored` is None on a CR channel that has never been calibrated; the original
        added straight through and raised `TypeError: unsupported operand type(s)`.
        """
        identity = 1.0 if combine == "mul" else 0.0
        if stored is None:
            stored = identity
        if override is None:
            return stored
        return override * stored if combine == "mul" else override + stored

    def _qc_shift_correction_phase(self, phi: Optional[Union[float, qua_T]]) -> None:
        if phi is not None:
            self._qc.xy.frame_rotation_2pi(phi)

    def _qt_shift_correction_phase(self, phi: Optional[Union[float, qua_T]]) -> None:
        if phi is not None:
            self._qt.xy.frame_rotation_2pi(phi)
            self._cr.frame_rotation_2pi(phi)

    @staticmethod
    def _play_pulse(
        elem,
        wf_type: str,
        amp_scale: Optional[Union[float, qua_T, _tuple, _list]],
        duration: Optional[Union[int, float, qua_T]],
        sgn: int = 1,
    ) -> None:
        # Branching stays explicit to satisfy QUA's optional-kw behaviour.
        if amp_scale is None and duration is None:
            elem.play(wf_type)
        elif amp_scale is None:
            elem.play(wf_type, duration=duration)
        elif duration is None:
            elem.play(wf_type, amplitude_scale=sgn * amp_scale)
        else:
            elem.play(wf_type, amplitude_scale=sgn * amp_scale, duration=duration)


@quam_dataclass
class CRGate(_QubitPairCrossDriveHelpers, QubitPairMacro):
    """Cross-resonance gate.

    Attributes:
        qc_correction_phase: ZI correction on the control qubit, in cycles.
        qt_correction_phase: IZ correction on the target qubit, in cycles.
    """

    qc_correction_phase: Optional[float] = None
    qt_correction_phase: Optional[float] = None

    def apply(
        self,
        cr_type: Literal["direct", "direct+cancel", "direct+echo", "direct+cancel+echo"] = "direct",
        wf_type: Optional[Literal["square", "cosine", "gauss", "flattop"]] = "flattop",
        cr_duration_clock_cycles: Optional[Union[int, qua_T]] = None,
        cr_drive_amp_scaling: Optional[Union[float, qua_T]] = None,
        cr_drive_phase: Optional[Union[float, qua_T]] = None,
        cr_cancel_amp_scaling: Optional[Union[float, qua_T]] = None,
        cr_cancel_phase: Optional[Union[float, qua_T]] = None,
        qc_correction_phase: Optional[Union[float, qua_T]] = None,
        qt_correction_phase: Optional[Union[float, qua_T]] = None,
    ) -> None:
        if self._cr is None:
            raise AttributeError(
                f"CRGate on qubit pair '{self.qubit_pair.name}' has no cross_resonance channel. "
                "Wire one on the qubit pair before applying the gate."
            )

        r = self._resolve_from_channel
        cr_drive_amp_scaling = r(cr_drive_amp_scaling, self._cr.drive_amplitude_scaling, "mul")
        cr_drive_phase = r(cr_drive_phase, self._cr.drive_phase, "add")
        cr_cancel_amp_scaling = r(cr_cancel_amp_scaling, self._cr.cancel_amplitude_scaling, "mul")
        cr_cancel_phase = r(cr_cancel_phase, self._cr.cancel_phase, "add")
        qc_correction_phase = r(qc_correction_phase, self._cr.qc_correction_phase, "add")
        qt_correction_phase = r(qt_correction_phase, self._cr.qt_correction_phase, "add")

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

    @property
    def _cr(self):
        return self.qubit_pair.cross_resonance

    @property
    def _cr_elems(self):
        return [self._qc.xy.name, self._qt.xy.name, self._cr.name]

    def _cr_drive_shift_phase(self, phi: Optional[Union[float, qua_T]]) -> None:
        if phi is not None:
            self._cr.frame_rotation_2pi(phi)

    def _cr_cancel_shift_phase(self, phi: Optional[Union[float, qua_T]]) -> None:
        if phi is not None:
            self._qt.xy.frame_rotation_2pi(phi)

    def _cr_drive_play(self, sgn, wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles) -> None:
        self._play_pulse(
            elem=self._cr,
            wf_type=wf_type,
            amp_scale=cr_drive_amp_scaling,
            duration=cr_duration_clock_cycles,
            sgn=1 if sgn == "direct" else -1,
        )

    def _cr_cancel_play(self, sgn, wf_type, cr_cancel_amp_scaling, cr_duration_clock_cycles) -> None:
        cancel_wf = f"cr_{wf_type}_{self.qubit_pair.name}"
        self._play_pulse(
            elem=self._qt.xy,
            wf_type=cancel_wf,
            amp_scale=cr_cancel_amp_scaling,
            duration=cr_duration_clock_cycles,
            sgn=1 if sgn == "direct" else -1,
        )

    def _direct(
        self,
        wf_type,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
    ) -> None:
        self._cr_drive_shift_phase(cr_drive_phase)
        align(*self._cr_elems)

        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._cr_drive_shift_phase(-cr_drive_phase)
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    def _direct_echo(
        self,
        wf_type,
        cr_duration_clock_cycles,
        cr_drive_amp_scaling,
        cr_drive_phase,
        qc_correction_phase,
        qt_correction_phase,
        **_,
    ) -> None:
        self._cr_drive_shift_phase(cr_drive_phase)
        align(*self._cr_elems)

        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._qc.xy.play("x180")
        align(*self._cr_elems)

        self._cr_drive_play("echo", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._qc.xy.play("x180")
        align(*self._cr_elems)

        self._cr_drive_shift_phase(-cr_drive_phase)
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    def _direct_cancel(
        self,
        wf_type,
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

        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._cr_cancel_play("direct", wf_type, cr_cancel_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._cr_drive_shift_phase(-cr_drive_phase)
        self._cr_cancel_shift_phase(-cr_cancel_phase)
        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)

    def _direct_cancel_echo(
        self,
        wf_type,
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

        self._cr_drive_play("direct", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._cr_cancel_play("direct", wf_type, cr_cancel_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._qc.xy.play("x180")
        align(*self._cr_elems)

        self._cr_drive_play("echo", wf_type, cr_drive_amp_scaling, cr_duration_clock_cycles)
        self._cr_cancel_play("echo", wf_type, cr_cancel_amp_scaling, cr_duration_clock_cycles)
        align(*self._cr_elems)

        self._qc.xy.play("x180")
        align(*self._cr_elems)

        self._cr_drive_shift_phase(-cr_drive_phase)
        self._cr_cancel_shift_phase(-cr_cancel_phase)
        align(*self._cr_elems)

        self._qc_shift_correction_phase(qc_correction_phase)
        self._qt_shift_correction_phase(qt_correction_phase)
        align(*self._cr_elems)


@quam_dataclass
class StarkInducedCZGate(_QubitPairCrossDriveHelpers, QubitPairMacro):
    """Stark-induced ZZ (siZZle) gate driven through `qubit_pair.zz_drive`.

    Attributes:
        qc_correction_phase: ZI correction on the control qubit, in cycles.
        qt_correction_phase: IZ correction on the target qubit, in cycles.
    """

    qc_correction_phase: Optional[float] = None
    qt_correction_phase: Optional[float] = None

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
        if self._zz is None:
            raise AttributeError(
                f"StarkInducedCZGate on qubit pair '{self.qubit_pair.name}' has no zz_drive "
                "channel. Wire one on the qubit pair before applying the gate."
            )

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

        self._zz_shift_relative_phase(p["zz_relative_phase"])

        align(self._zz.name, self._qt.xy_detuned.name)
        self._zz_control_drive_play(p["wf_type"], p["zz_control_amp_scaling"], p["zz_duration_clock_cycles"])
        self._zz_target_drive_play(p["wf_type"], p["zz_target_amp_scaling"], p["zz_duration_clock_cycles"])

        align(self._zz.name, self._qt.xy_detuned.name, self._qc.xy.name, self._qt.xy.name)
        self._qc_shift_correction_phase(p["qc_correction_phase"])
        self._qt_shift_correction_phase(p["qt_correction_phase"])

    @property
    def _zz(self):
        return self.qubit_pair.zz_drive

    def _qt_shift_correction_phase(self, phi: Optional[Union[float, qua_T]]) -> None:
        """IZ correction on the target qubit only.

        The shared helper also rotates the CR channel's frame, which this gate does not
        drive — and on a pair with no `cross_resonance` it would raise.
        """
        if phi is not None:
            self._qt.xy.frame_rotation_2pi(phi)

    def _zz_shift_relative_phase(self, phi) -> None:
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
