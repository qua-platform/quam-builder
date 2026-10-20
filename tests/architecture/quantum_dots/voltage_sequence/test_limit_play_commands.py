"""Offline coverage for VoltageSequence(limit_play_commands=True).

When the gate set has an ``influence_map`` (VirtualGateSet), only physical
channels in the influence closure of the *changed* gate names receive
play/ramp commands. Uninfluenced channels keep their previous analog level
(sticky hold) and, if tracking is on, still accumulate hold area.

All sequence tests use ``keep_levels=True``.
"""

from __future__ import annotations

import re

import numpy as np
import pytest
from qm import generate_qua_script, qua
from quam.components import SingleChannel

from quam_builder.architecture.quantum_dots.components.virtual_gate_set import VirtualGateSet
from quam_builder.architecture.quantum_dots.voltage_sequence.sequence_state_tracker import (
    INTEGRATED_VOLTAGE_SCALING_FACTOR,
)
from quam_builder.architecture.quantum_dots.voltage_sequence.voltage_sequence import round_amplitude

# VoltageSequence rounds levels with np.float16 (~1e-3 relative precision).
_APPROX_REL = 1e-3


def _approx(value):
    """Compare analog levels with enough slack for float16 DAC rounding."""
    return pytest.approx(value, rel=_APPROX_REL)


def _play_elements(script: str) -> list[str]:
    """Element names passed as the play target in ``generate_qua_script`` output."""
    return re.findall(r'play\([^;]*?,\s*"([^"]+)"', script)


def _ramp_elements(script: str) -> list[str]:
    """Element names passed as the ramp target in ``generate_qua_script`` output."""
    return re.findall(r'ramp\([^;]*?,\s*"([^"]+)"', script)


def _scaled_area(level: float, duration: int) -> int:
    """Python-mode integrated-voltage counts for holding ``level`` for ``duration``.

    ``VoltageSequence`` rounds analog targets with ``round_amplitude`` (float16)
    before the tracker multiplies by duration and ``INTEGRATED_VOLTAGE_SCALING_FACTOR``.
    Using the unrounded Python float would over-count sticky hold area.
    """
    return int(
        np.round(round_amplitude(level) * duration * INTEGRATED_VOLTAGE_SCALING_FACTOR)
    )


def _limited_sequence(gate_set, *, track_integrated_voltage: bool = False):
    """Build a Python-foldable sequence with ``limit_play_commands`` and keep-levels on."""
    return gate_set.new_sequence(
        keep_levels=True,
        limit_play_commands=True,
        enforce_qua_calcs=False,
        track_integrated_voltage=track_integrated_voltage,
    )


@pytest.fixture
def identity_vgs() -> VirtualGateSet:
    """VirtualGateSet where each virtual gate maps 1:1 onto one physical channel.

    ``v1``/``v2``/``v3`` resolve to ``P1``/``P2``/``P3``. With
    ``limit_play_commands=True``, a step that names only ``v1`` should emit a
    play (or ramp) on ``P1`` and leave ``P2`` and ``P3`` sticky.
    """
    vgs = VirtualGateSet(
        id="identity_vgs",
        channels={
            "P1": SingleChannel(id="P1", opx_output=("con1", 1, 1)),
            "P2": SingleChannel(id="P2", opx_output=("con1", 1, 2)),
            "P3": SingleChannel(id="P3", opx_output=("con1", 1, 3)),
        },
    )
    vgs.add_layer(
        source_gates=["v1", "v2", "v3"],
        target_gates=["P1", "P2", "P3"],
        matrix=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
    )
    return vgs


@pytest.fixture
def coupled_vgs() -> VirtualGateSet:
    """Two-channel virtual layer with one isolated gate and one that fans out.

    Inverse mapping: ``ch1 = 0.5*v_g1 - 0.5*v_g2``, ``ch2 = v_g2``.
    ``influence_map['v_g1']`` is ``{ch1}``; ``influence_map['v_g2']`` is
    ``{ch1, ch2}``. Channels are created here rather than reused from the
    ``machine`` fixture so QUAM does not try to re-parent existing
    ``SingleChannel`` objects.
    """
    vgs = VirtualGateSet(
        id="coupled_vgs",
        channels={
            "ch1": SingleChannel(id="ch1", opx_output=("con1", 1, 1)),
            "ch2": SingleChannel(id="ch2", opx_output=("con1", 1, 2)),
        },
    )
    vgs.add_layer(
        source_gates=["v_g1", "v_g2"],
        target_gates=["ch1", "ch2"],
        matrix=[[2.0, 1.0], [0.0, 1.0]],
    )
    return vgs


def test_new_sequence_forwards_limit_play_commands(identity_vgs):
    """``GateSet.new_sequence`` stores ``limit_play_commands`` and ``keep_levels``."""
    seq = identity_vgs.new_sequence(keep_levels=True, limit_play_commands=True)
    assert seq.limit_play_commands is True
    assert seq._keep_levels is True


def test_influence_map_is_sparse_for_identity_layer(identity_vgs):
    """Each virtual (and physical) gate's influence set is only itself / its 1:1 target."""
    imap = identity_vgs.influence_map
    assert imap["v1"] == {"P1"}
    assert imap["v2"] == {"P2"}
    assert imap["v3"] == {"P3"}
    assert imap["P1"] == {"P1"}


def test_limit_true_skips_play_on_uninfluenced_physical_channels(identity_vgs):
    """A later step of only ``v1`` must not emit plays on ``P2`` or ``P3``.

    First step sets all three virtuals so every physical channel is away from
    0 V. The second step names only ``v1``; keep-levels holds ``v2``/``v3``.
    ``limit_play_commands`` then restricts plays to ``influence_map['v1']``
    (``P1``). ``P2`` and ``P3`` stay at their previous levels without a second
    play command.
    """
    with qua.program() as prog:
        seq = _limited_sequence(identity_vgs)
        seq.step_to_voltages({"v1": 0.1, "v2": 0.2, "v3": 0.3}, duration=100)
        seq.step_to_voltages({"v1": 0.4}, duration=80)
        assert seq.state_trackers["P1"].current_level == _approx(0.4)
        assert seq.state_trackers["P2"].current_level == _approx(0.2)
        assert seq.state_trackers["P3"].current_level == _approx(0.3)
    plays = _play_elements(generate_qua_script(prog, config=None))
    assert plays.count("P1") == 2
    assert plays.count("P2") == 1
    assert plays.count("P3") == 1


def test_uninfluenced_channels_still_accumulate_hold_integral(identity_vgs):
    """Skipped plays still add sticky hold time to integrated voltage.

    After the first step, ``P2`` sits at ``v2``. The second step changes only
    ``v1``, so ``P2`` is outside the play set. Analog sticky hold means ``P2``
    remains at that level for ``duration_2``, and compensation tracking must
    still add ``level * duration_2`` (after float16 rounding) to ``P2``'s
    integral. ``P1`` is played, so its integral is the sum of both step areas.
    """
    duration_1, duration_2 = 100, 80
    v_p2 = 0.2
    with qua.program() as _prog:
        seq = _limited_sequence(identity_vgs, track_integrated_voltage=True)
        seq.step_to_voltages({"v1": 0.1, "v2": v_p2, "v3": 0.3}, duration=duration_1)
        int_after_first = seq.state_trackers["P2"].integrated_voltage
        seq.step_to_voltages({"v1": 0.4}, duration=duration_2)
        assert seq.state_trackers["P2"].current_level == _approx(v_p2)
        assert seq.state_trackers["P2"].integrated_voltage == int_after_first + (
            _scaled_area(v_p2, duration_2)
        )
        expected_p1 = _scaled_area(0.1, duration_1) + _scaled_area(0.4, duration_2)
        assert seq.state_trackers["P1"].integrated_voltage == expected_p1


def test_coupled_virtual_gate_plays_all_influenced_channels(coupled_vgs):
    """A virtual gate that fans out still plays every physical it influences.

    ``v_g2`` contributes to both ``ch1`` and ``ch2``. ``limit_play_commands``
    must not drop ``ch1`` just because the caller only named ``v_g2``.
    Keep-levels fills unspecified ``v_g1`` as 0 V, so the resolved levels are
    ``ch1 = -0.2`` and ``ch2 = 0.4``.
    """
    assert coupled_vgs.influence_map["v_g1"] == {"ch1"}
    assert coupled_vgs.influence_map["v_g2"] == {"ch1", "ch2"}
    with qua.program() as prog:
        seq = _limited_sequence(coupled_vgs)
        seq.step_to_voltages({"v_g2": 0.4}, duration=100)
        # keep_levels fills v_g1 at 0: ch1 = -0.5 * 0.4 = -0.2, ch2 = 0.4
        assert seq.state_trackers["ch1"].current_level == _approx(-0.2)
        assert seq.state_trackers["ch2"].current_level == _approx(0.4)
    plays = _play_elements(generate_qua_script(prog, config=None))
    assert "ch1" in plays
    assert "ch2" in plays


def test_coupled_virtual_gate_limited_to_its_influence(coupled_vgs):
    """Changing only ``v_g1`` must not replay ``ch2``.

    After both virtuals are set, a second step of ``v_g1`` still resolves
    ``ch2`` (keep-levels holds ``v_g2``), but ``ch2`` is not in
    ``influence_map['v_g1']``. ``ch1`` is played twice; ``ch2`` once. ``ch1``
    moves to ``0.5*1.0 - 0.5*0.4 = 0.3`` while ``ch2`` stays at ``0.4``.
    """
    with qua.program() as prog:
        seq = _limited_sequence(coupled_vgs)
        seq.step_to_voltages({"v_g1": 0.0, "v_g2": 0.4}, duration=100)
        seq.step_to_voltages({"v_g1": 1.0}, duration=80)
        # keep_levels holds v_g2=0.4: ch1 = 0.5*1.0 - 0.5*0.4 = 0.3, ch2 = 0.4
        assert seq.state_trackers["ch1"].current_level == _approx(0.3)
        assert seq.state_trackers["ch2"].current_level == _approx(0.4)
    plays = _play_elements(generate_qua_script(prog, config=None))
    assert plays.count("ch1") == 2
    assert plays.count("ch2") == 1


def test_physical_channel_step_only_plays_that_channel(identity_vgs):
    """Physical names use the identity influence map: only the named channel plays.

    After all three physicals are set, stepping only ``P1`` must leave ``P2``
    and ``P3`` sticky (one play each) while ``P1`` gets a second play.
    """
    with qua.program() as prog:
        seq = _limited_sequence(identity_vgs)
        seq.step_to_voltages({"P1": 0.1, "P2": 0.2, "P3": 0.3}, duration=100)
        seq.step_to_voltages({"P1": 0.25}, duration=80)
        assert seq.state_trackers["P2"].current_level == _approx(0.2)
        assert seq.state_trackers["P3"].current_level == _approx(0.3)
        assert seq.state_trackers["P1"].current_level == _approx(0.25)
    plays = _play_elements(generate_qua_script(prog, config=None))
    assert plays.count("P1") == 2
    assert plays.count("P2") == 1
    assert plays.count("P3") == 1


def test_union_of_changed_gates_influence(identity_vgs):
    """Several changed gates play the union of their influence sets.

    Naming ``v1`` and ``v2`` on the second step should replay ``P1`` and
    ``P2`` but not ``P3``, whose virtual is only held by keep-levels.
    """
    with qua.program() as prog:
        seq = _limited_sequence(identity_vgs)
        seq.step_to_voltages({"v1": 0.1, "v2": 0.2, "v3": 0.3}, duration=100)
        seq.step_to_voltages({"v1": 0.15, "v2": 0.25}, duration=80)
        assert seq.state_trackers["P3"].current_level == _approx(0.3)
        assert seq.state_trackers["P1"].current_level == _approx(0.15)
        assert seq.state_trackers["P2"].current_level == _approx(0.25)
    plays = _play_elements(generate_qua_script(prog, config=None))
    assert plays.count("P1") == 2
    assert plays.count("P2") == 2
    assert plays.count("P3") == 1


def test_ramp_also_respects_influence_map(identity_vgs):
    """Ramps use the same influence filter as steps: only ``P1`` gets ``ramp()``.

    After a full step, ``ramp_to_voltages({'v1': 0.4})`` must not emit ramps on
    ``P2`` or ``P3``. Those channels stay at the first-step levels.
    """
    with qua.program() as prog:
        seq = _limited_sequence(identity_vgs)
        seq.step_to_voltages({"v1": 0.1, "v2": 0.2, "v3": 0.3}, duration=100)
        seq.ramp_to_voltages({"v1": 0.4}, duration=80, ramp_duration=40)
        assert seq.state_trackers["P2"].current_level == _approx(0.2)
        assert seq.state_trackers["P1"].current_level == _approx(0.4)
    script = generate_qua_script(prog, config=None)
    ramps = _ramp_elements(script)
    assert ramps.count("P1") == 1
    assert ramps.count("P2") == 0
    assert ramps.count("P3") == 0


def test_sub_threshold_coupling_is_not_in_influence_map_and_is_not_played():
    """Coupling below ``play_threshold`` (2**-16) is treated as no influence.

    The layer inverse maps a 1e-12 coefficient from ``v1`` onto ``P2``, which
    is smaller than OPX fixed-point resolution when probed at 2.5 V.
    ``v1`` therefore influences only ``P1``. After both virtuals are set,
    stepping only ``v1`` must not play ``P2``; ``P2`` stays at the ``v2`` level.
    """
    vgs = VirtualGateSet(
        id="tiny_coupling",
        channels={
            "P1": SingleChannel(id="P1", opx_output=("con1", 1, 1)),
            "P2": SingleChannel(id="P2", opx_output=("con1", 1, 2)),
        },
    )
    tiny = 1e-12
    vgs.add_layer(
        source_gates=["v1", "v2"],
        target_gates=["P1", "P2"],
        matrix=[[1.0, 0.0], [tiny, 1.0]],
    )
    assert "P2" not in vgs.influence_map["v1"]
    assert vgs.influence_map["v1"] == {"P1"}

    with qua.program() as prog:
        seq = _limited_sequence(vgs)
        seq.step_to_voltages({"v1": 0.2, "v2": 0.1}, duration=100)
        seq.step_to_voltages({"v1": 0.3}, duration=80)
        assert seq.state_trackers["P2"].current_level == _approx(0.1)
    plays = _play_elements(generate_qua_script(prog, config=None))
    assert plays.count("P1") == 2
    assert plays.count("P2") == 1
