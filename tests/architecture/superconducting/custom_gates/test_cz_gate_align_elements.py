"""Default vs opt-in CZ aligns must be visible in the emitted QUA, not swallowed by kwargs."""

import inspect
import re

from qm import generate_qua_script
from qm.qua import program
from quam.components.channels import Channel
from quam.components.pulses import SquarePulse
from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.components.tunable_coupler import (
    TunableCoupler,
)
from quam_builder.architecture.superconducting.custom_gates.flux_tunable_transmon_pair.two_qubit_gates import (
    CZGate,
)
from quam_builder.architecture.superconducting.qubit.flux_tunable_transmon import (
    FluxTunableTransmon,
)
from quam_builder.architecture.superconducting.qubit_pair.flux_tunable_transmon_pair import (
    FluxTunableTransmonPair,
)


@quam_dataclass
class _NamedChannel(Channel):
    """Minimal named channel so tests can emit play/align/frame without OPX ports."""


def _pulse(pulse_id: str, length: int, amplitude: float) -> SquarePulse:
    return SquarePulse(id=pulse_id, length=length, amplitude=amplitude)


def _qubit(qubit_id: str, *, z_ops: dict) -> FluxTunableTransmon:
    qubit = FluxTunableTransmon(id=qubit_id)
    qubit.xy = _NamedChannel(id=f"{qubit_id}.xy")
    qubit.z = _NamedChannel(id=f"{qubit_id}.z")
    qubit.z.operations.update(z_ops)
    return qubit


def _cz_macro():
    control = _qubit("qC", z_ops={"cz": _pulse("cz", 52, 0.2)})
    target = _qubit("qT", z_ops={})
    flux_spectator = _qubit("qFlux", z_ops={"cz_spectator": _pulse("cz_spectator", 48, 0.04)})
    phase_spectator = _qubit("qPhase", z_ops={})

    coupler = TunableCoupler(id="coupler", opx_output=("con1", 7))
    coupler.operations["cz_coupler"] = _pulse("cz_coupler", 52, 0.1)

    pair = FluxTunableTransmonPair(
        id="qC-qT",
        qubit_control=control,
        qubit_target=target,
        coupler=coupler,
        moving_qubit="control",
    )
    # Separate Pulse instances: quam forbids re-parenting objects already on a channel.
    gate = CZGate(
        flux_pulse_qubit=_pulse("cz", 52, 0.2),
        coupler_flux_pulse=_pulse("cz_coupler", 52, 0.1),
        phase_shift_control=0.1,
        phase_shift_target=0.2,
        spectator_qubits={"qFlux": flux_spectator, "qPhase": phase_spectator},
        spectator_qubits_control={"qFlux": _pulse("cz_spectator", 48, 0.04)},
        spectator_qubits_phase_shift={"qFlux": 0.01, "qPhase": 0.03},
    )
    pair.macros["cz_unipolar"] = gate
    return pair.macros["cz_unipolar"]


def _emitted_script(align_elements: bool | None) -> str:
    gate = _cz_macro()
    with program() as prog:
        if align_elements is None:
            gate.apply()
        else:
            gate.apply(align_elements=align_elements)
    return generate_qua_script(prog)


_ALIGN_RE = re.compile(r"^\s*align\(", re.MULTILINE)
_PLAY_RE = re.compile(r"^\s*play\(", re.MULTILINE)
_FRAME_RE = re.compile(r"^\s*frame_rotation_2pi\(", re.MULTILINE)


def test_align_elements_is_an_explicit_keyword():
    params = inspect.signature(CZGate.apply).parameters
    assert "align_elements" in params
    assert params["align_elements"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["align_elements"].default is True
    assert params["align_elements"].kind is not inspect.Parameter.VAR_KEYWORD


def test_default_apply_emits_three_aligns_and_keeps_flux_and_phase():
    script = _emitted_script(None)
    assert len(_ALIGN_RE.findall(script)) == 3
    assert len(_PLAY_RE.findall(script)) == 3  # spectator flux, moving Z, coupler
    assert len(_FRAME_RE.findall(script)) == 4  # control, target, two spectators
    assert "play(" in script
    assert "qC.z" in script
    assert "qFlux.z" in script
    assert "coupler" in script


def test_align_elements_false_drops_aligns_but_keeps_flux_and_phase():
    default_script = _emitted_script(True)
    opt_in_script = _emitted_script(False)

    assert len(_ALIGN_RE.findall(default_script)) == 3
    assert len(_ALIGN_RE.findall(opt_in_script)) == 0
    assert len(_PLAY_RE.findall(opt_in_script)) == len(_PLAY_RE.findall(default_script))
    assert len(_FRAME_RE.findall(opt_in_script)) == len(_FRAME_RE.findall(default_script))
    assert "play(" in opt_in_script
    assert "frame_rotation_2pi(" in opt_in_script
