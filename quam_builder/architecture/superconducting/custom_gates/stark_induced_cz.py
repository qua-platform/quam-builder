from typing import Optional, Literal, Union, Tuple, List
from qm.qua import *
from quam.core import quam_dataclass
from quam.components.pulses import Pulse
from quam.components.macro import QubitPairMacro
from qm.qua._dsl import QuaExpression, QuaVariable

__all__ = ["StarkInducedCZGate"]


qua_T = Union[QuaVariable, QuaExpression]
# type for rotation matrix amp(c, -s, s, c)
# relative phase between control and target is done by amp(c, -s, s, c) instead
_tuple = Tuple[Union[float, qua_T]]
_list = List[Union[float, qua_T]]

@quam_dataclass
class StarkInducedCZGate(QubitPairMacro):
    qc_correction_phase: float = 0.0
    qt_correction_phase: float = 0.0

    def apply(
        self,
        wf_type: Literal["square", "cosine", "gauss", "flattop"] = "flattop",
        zz_control_amp_scaling: Optional[Union[float, qua_T, _tuple, _list]] = None,
        zz_target_amp_scaling: Optional[Union[float, qua_T, _tuple, _list]] = None,
        qc_correction_phase: Optional[Union[float, qua_T]] = None,
        qt_correction_phase: Optional[Union[float, qua_T]] = None,
        zz_duration_clock_cycles: Optional[Union[float, qua_T]] = None,
    ) -> None:

        qc = self.qubit_pair.qubit_control
        qt = self.qubit_pair.qubit_target
        zz = self.qubit_pair.zz_drive

        def _play_zz_pulse(
            elem,
            wf_type: str = wf_type,
            amp_scale: Optional[Union[float, qua_T, _tuple, _list]] = None,
            duration: Optional[Union[float, qua_T, _tuple, _list]] = None,
        ):
            if amp_scale is None and duration is None:
                elem.play(wf_type)
            elif amp_scale is None:
                elem.play(wf_type, duration=duration)
            elif duration is None:
                elem.play(wf_type, amplitude_scale=amp_scale)
            else:
                elem.play(wf_type, amplitude_scale=amp_scale, duration=duration)

        # ZI phase correction
        def qc_shift_correction_phase():
            if qc_correction_phase is not None:
                qc.xy.frame_rotation_2pi(qc_correction_phase)

        # IZ phase correction
        def qt_shift_correction_phase():
            if qt_correction_phase is not None:
                qt.xy.frame_rotation_2pi(qt_correction_phase)

        def zz_control_drive_play(wf_type=wf_type):
            _play_zz_pulse(
                elem=zz,
                wf_type=wf_type,
                amp_scale=zz_control_amp_scaling,
                duration=zz_duration_clock_cycles,
            )

        def zz_target_drive_play(wf_type=wf_type):
            _play_zz_pulse(
                elem=qt.xy_detuned,
                wf_type=f"zz_{wf_type}_{self.qubit_pair.name}",
                amp_scale=zz_target_amp_scaling,
                duration=zz_duration_clock_cycles,
            )

        # Pulse sequence
        zz_control_drive_play()
        zz_target_drive_play()

        self.qubit_pair.align()

        qt_shift_correction_phase()
        qt_shift_correction_phase()
