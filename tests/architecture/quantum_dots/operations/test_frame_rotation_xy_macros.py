"""X and Y macros that select the axis with frame_rotation_2pi."""

from unittest.mock import patch

import numpy as np
import pytest

from quam_builder.architecture.quantum_dots.components.quantum_dot import QuantumDot
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.default_macros.frame_rotation_macros import (
    FrameX90Macro,
    FrameXMacro,
    FrameXNeg90Macro,
    FrameY180Macro,
    FrameY90Macro,
    FrameYMacro,
    FrameYNeg90Macro,
    qua,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    YMacro,
)
from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    FrameRotationXYMacroCatalog,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from tests.builder.quantum_dots.test_macro_wiring import _build_machine


def _wire(machine):
    wire_machine_macros(
        machine,
        catalogs=[FrameRotationXYMacroCatalog()],
        fill_only=False,
    )
    return machine


def test_catalog_replaces_xy_gates_on_ld_qubits_only():
    """The catalog overrides X and Y on LD qubits and leaves other types alone."""
    catalog = FrameRotationXYMacroCatalog()
    assert catalog.priority == 200
    assert catalog.get_factories(LDQubit)["y"] is FrameYMacro
    assert catalog.get_factories(LDQubit)["y90"] is FrameY90Macro
    assert catalog.get_factories(LDQubit)["-y90"] is FrameYNeg90Macro
    assert catalog.get_factories(QuantumDot) == {}

    machine = _wire(_build_machine())
    q1 = machine.qubits["q1"]
    assert isinstance(q1.macros["x"], FrameXMacro)
    assert isinstance(q1.macros["y"], FrameYMacro)
    assert isinstance(q1.macros["y180"], FrameY180Macro)
    assert isinstance(q1.macros["x_neg90"], FrameXNeg90Macro)
    assert not isinstance(q1.y, YMacro)


def test_x_plays_the_pi_pulse_without_a_frame_rotation():
    """X phase is 0, so the macro only plays the calibrated pi pulse."""
    machine = _wire(_build_machine())
    q1 = machine.qubits["q1"]

    with (
        patch.object(qua, "frame_rotation_2pi") as mock_rot,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
    ):
        q1.x(angle=np.pi / 3)

    mock_rot.assert_not_called()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x180"
    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(1.0 / 3.0)


def test_y_rotates_the_frame_around_the_x_pulse():
    """Y is the x180 pulse between frame rotations of -1/4 and +1/4 turn."""
    machine = _wire(_build_machine())
    q1 = machine.qubits["q1"]
    order = []

    def rotate(angle, element):
        order.append(("rotate", angle, element))

    def play(**kwargs):
        order.append(("play", kwargs["pulse_name"], kwargs["amplitude_scale"]))

    with (
        patch.object(qua, "frame_rotation_2pi", side_effect=rotate),
        patch.object(q1.xy, "play", side_effect=play),
    ):
        q1.y(angle=np.pi / 2)

    assert order[0][0] == "rotate"
    assert order[0][1] == pytest.approx(-0.25)
    assert order[0][2] == q1.xy.name
    assert order[1] == ("play", "gaussian_x180", pytest.approx(0.5))
    assert order[2][0] == "rotate"
    assert order[2][1] == pytest.approx(0.25)
    assert order[0][1] + order[2][1] == pytest.approx(0.0)


def test_negative_y_keeps_the_y_phase_and_flips_the_amplitude():
    """A negative angle is a negative scale on the same Y-axis frame."""
    machine = _wire(_build_machine())
    q1 = machine.qubits["q1"]

    with (
        patch.object(qua, "frame_rotation_2pi") as mock_rot,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
    ):
        q1.y(angle=-np.pi / 2)

    assert mock_rot.call_args_list[0].args[0] == pytest.approx(-0.25)
    assert mock_rot.call_args_list[1].args[0] == pytest.approx(0.25)
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x180"
    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(-0.5)


@pytest.mark.parametrize(
    ("gate", "pulse", "before", "after"),
    [
        ("y180", "gaussian_x180", -0.25, 0.25),
        ("y90", "gaussian_x90", -0.25, 0.25),
        ("y_neg90", "gaussian_x90", 0.25, -0.25),
        ("-y90", "gaussian_x90", 0.25, -0.25),
        ("x_neg90", "gaussian_x90", -0.5, 0.5),
        ("-x90", "gaussian_x90", -0.5, 0.5),
    ],
)
def test_fixed_gates_play_the_x_pulse_at_their_axis_phase(gate, pulse, before, after):
    """Fixed Y and negative-X gates play an X pulse inside the phase sandwich."""
    machine = _wire(_build_machine())
    q1 = machine.qubits["q1"]

    with (
        patch.object(qua, "frame_rotation_2pi") as mock_rot,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
    ):
        q1.macros[gate].apply()

    assert mock_rot.call_args_list[0].args[0] == pytest.approx(before)
    assert mock_rot.call_args_list[1].args[0] == pytest.approx(after)
    assert mock_play.call_args.kwargs["pulse_name"] == pulse
    assert mock_play.call_args.kwargs["amplitude_scale"] is None


def test_fixed_frame_gates_reject_angle():
    """The rotation of a fixed gate is the pulse, so angle is rejected."""
    machine = _wire(_build_machine())
    q1 = machine.qubits["q1"]

    with (
        patch.object(qua, "frame_rotation_2pi") as mock_rot,
        pytest.raises(TypeError, match="angle"),
    ):
        q1.y90(angle=np.pi / 2)
    mock_rot.assert_not_called()
    assert isinstance(q1.macros["x90"], FrameX90Macro)


def test_y_update_writes_the_x_pulse_it_plays():
    """y and y90 store duration on the X pulse they play."""
    machine = _wire(_build_machine())
    q1 = machine.qubits["q1"]
    x90 = q1.xy.operations["gaussian_x90"]
    x180 = q1.xy.operations["gaussian_x180"]

    q1.y.update(duration=50)
    assert x180.length == 200

    q1.y90.update(duration=40)
    assert x90.length == 160
    assert q1.macros["y"].inferred_duration == pytest.approx(200e-9)
    assert q1.macros["y90"].inferred_duration == pytest.approx(160e-9)
