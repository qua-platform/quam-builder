"""Tests for runtime macro wiring and override behavior."""

from functools import partial
from typing import ClassVar
from unittest.mock import patch

import numpy as np
import pytest

from qm import qua
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components import pulses
from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.components.pulses import ScalableGaussianPulse
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    X180Macro,
    XYDriveMacro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    InitializeStateMacro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.two_qubit_macros import (
    CROTMacro,
)
from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    TypeOverrideCatalog,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
    TwoQubitMacroName,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.builder.quantum_dots.build_qpu_stage1 import _BaseQpuBuilder
from quam_builder.builder.quantum_dots.build_qpu_stage2 import _LDQubitBuilder


def _plunger_ports(qubit_id: str) -> dict:
    return {"opx_output": f"#/wiring/qubits/{qubit_id}/p/opx_output"}


def _mw_drive_ports(qubit_id: str) -> dict:
    return {"opx_output": f"#/ports/mw_outputs/con1/1/{qubit_id[-1]}"}


def _barrier_ports(pair_id: str) -> dict:
    return {"opx_output": f"#/wiring/qubit_pairs/{pair_id}/b/opx_output"}


def _build_machine():
    machine = BaseQuamQD()
    machine.wiring = {
        "qubits": {
            "q1": {
                WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
            },
            "q2": {
                WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2"),
                WiringLineType.DRIVE.value: _mw_drive_ports("q2"),
            },
        },
        "qubit_pairs": {
            "q1_q2": {WiringLineType.BARRIER_GATE.value: _barrier_ports("q1_q2")},
        },
    }
    machine = _BaseQpuBuilder(machine).build()
    machine = _LDQubitBuilder(machine).build()
    return machine


def _seed_reference_pulses(machine):
    for qubit in machine.qubits.values():
        if qubit.xy is None:
            continue
        qubit.xy.operations["gaussian_x90"] = pulses.GaussianPulse(
            length=64, amplitude=0.01, sigma=16
        )
        qubit.xy.operations["gaussian_x180"] = pulses.GaussianPulse(
            length=64, amplitude=0.02, sigma=16
        )


class TunedX180Macro(X180Macro):
    """Simple marker macro used for instance-level override testing."""

    pass


def test_instance_override_path_supports_quam_mappings():
    """Instance overrides should work for collections stored as Quam mappings.

    Only q1 gets the override; q2 keeps the default X180Macro.
    """
    machine = _build_machine()

    wire_machine_macros(
        machine,
        instance_overrides={
            "qubits.q1": {
                SingleQubitMacroName.X_180: TunedX180Macro,
            },
        },
    )

    assert isinstance(machine.qubits["q1"].macros["x180"], TunedX180Macro)
    assert isinstance(machine.qubits["q2"].macros["x180"], X180Macro)


def test_component_type_override_applies_to_all_instances():
    """Component-type overrides should apply to each matching instance.

    Uses TypeOverrideCatalog keyed by the LDQubit class.
    """
    machine = _build_machine()

    wire_machine_macros(
        machine,
        fill_only=False,
        catalogs=[
            TypeOverrideCatalog(
                {
                    LDQubit: {
                        SingleQubitMacroName.INITIALIZE: partial(
                            InitializeStateMacro,
                            ramp_duration=48,
                        ),
                    },
                }
            ),
        ],
    )

    for qubit in machine.qubits.values():
        assert isinstance(qubit.macros["initialize"], InitializeStateMacro)
        assert qubit.macros["initialize"].ramp_duration == 48


def test_default_two_qubit_crot_macro_is_wired():
    """LDQubitPair should receive the default CROT macro via wire_machine_macros."""
    machine = _build_machine()

    wire_machine_macros(machine)

    pair = machine.qubit_pairs["q1_q2"]
    assert isinstance(pair.macros[TwoQubitMacroName.CROT], CROTMacro)


def test_x_and_y_without_angle_match_the_pi_pulse():
    """qubit.x() and qubit.y() play the pi pulse at its calibrated amplitude."""
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with patch.object(q1.xy, "play", return_value=None) as mock_play:
        q1.x()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x180"
    assert mock_play.call_args.kwargs["amplitude_scale"] is None

    with patch.object(q1.xy, "play", return_value=None) as mock_play:
        q1.y()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_y180"
    assert mock_play.call_args.kwargs["amplitude_scale"] is None


def test_canonical_x_and_y_scale_the_pi_pulse():
    """x/y play the calibrated pi pulse with amplitude scale angle/pi.

    The Y axis comes from the y180 operation. Neither call rotates the frame.
    """
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "virtual_z", return_value=None) as mock_vz,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
    ):
        q1.macros["x"].apply(angle=np.pi / 3)

    mock_vz.assert_not_called()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x180"
    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(1.0 / 3.0)

    with (
        patch.object(q1, "virtual_z", return_value=None) as mock_vz,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
    ):
        q1.macros["y"].apply(angle=np.pi / 4)

    mock_vz.assert_not_called()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_y180"
    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(0.25)


def test_fixed_gates_and_arbitrary_axes_reject_phase():
    """Phase shifts belong on z(), not on an XY macro."""
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with pytest.raises(TypeError, match="phase"):
        q1.x90(phase=0.1)
    with pytest.raises(TypeError, match="angle"):
        q1.x90(angle=np.pi / 2)
    with pytest.raises(TypeError, match="phase"):
        q1.y(angle=np.pi / 4, phase=0.125)


def test_xy_drive_plays_its_calibrated_pulse():
    """xy_drive() plays the x180 operation and does not rotate the frame."""
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "virtual_z", return_value=None) as mock_vz,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
    ):
        q1.xy_drive()

    mock_vz.assert_not_called()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x180"
    assert mock_play.call_args.kwargs["amplitude_scale"] is None


def test_fixed_angle_z_macros_use_their_own_angle():
    """z90/z180/z_neg90 rotate by their fixed angle and reject ``angle``."""
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with patch.object(q1, "virtual_z", return_value=None) as mock_vz:
        q1.z90()
    mock_vz.assert_called_once_with(pytest.approx(np.pi / 2))

    with patch.object(q1, "virtual_z", return_value=None) as mock_vz:
        q1.z180()
    mock_vz.assert_called_once_with(pytest.approx(np.pi))

    with patch.object(q1, "virtual_z", return_value=None) as mock_vz:
        q1.z_neg90()
    mock_vz.assert_called_once_with(pytest.approx(-np.pi / 2))

    with pytest.raises(TypeError, match="angle"):
        q1.z90(angle=np.pi)

    with patch.object(q1, "virtual_z", return_value=None) as mock_vz:
        q1.z(angle=-0.3)
    mock_vz.assert_called_once_with(-0.3)


def test_x180_macro_produces_valid_qua_program():
    """X180Macro.apply() inside qua.program() produces a valid non-None QUA program."""
    machine = _build_machine()
    wire_machine_macros(machine)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with qua.program() as prog:
        q1.macros["x180"].apply()

    assert prog is not None


def test_x180_macro_triggers_play():
    """X180Macro.apply() triggers xy.play via delegation chain."""
    machine = _build_machine()
    wire_machine_macros(machine)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with patch.object(q1.xy, "play", return_value=None) as mock_play:
        with qua.program():
            q1.macros["x180"].apply()

    assert mock_play.call_count >= 1
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x180"


def test_runtime_amplitude_scale_is_passed_through_unscaled_for_dedicated_pulse():
    """X90Macro is a dedicated, independently-calibrated pulse (no angle-derived

    baseline scaling), so a runtime amplitude_scale passes straight through
    to xy.play unchanged.
    """
    machine = _build_machine()
    wire_machine_macros(machine)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1.xy, "play", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.x90(amplitude_scale=0.5)

    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(0.5)


def test_dedicated_x90_and_x180_pulses_are_calibrated_independently():
    """x90 and x180 are separate, independently-calibrated operations.

    Unlike the canonical angle-scaled path (which reuses a single
    reference pulse), the dedicated macros each play their own operation,
    so changing one's amplitude must not affect the other.
    """
    machine = _build_machine()
    wire_machine_macros(machine)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]
    original_x180_amplitude = q1.xy.operations["gaussian_x180"].amplitude
    q1.xy.operations["gaussian_x90"].amplitude = 0.15

    with (
        patch.object(q1.xy, "play", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.x180()

    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x180"
    assert q1.xy.operations["gaussian_x180"].amplitude == pytest.approx(
        original_x180_amplitude
    )


def test_inferred_duration_uses_the_played_pulse_length():
    """Each macro reports the played pulse length in seconds."""
    machine = _build_machine()
    wire_machine_macros(machine)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]
    q1.xy.operations["gaussian_x180"].length = 80
    q1.xy.operations["gaussian_y90"] = pulses.GaussianPulse(length=48, amplitude=0.01, sigma=12)

    assert q1.macros["x"].inferred_duration == pytest.approx(80e-9)
    assert q1.macros["x90"].inferred_duration == pytest.approx(
        q1.xy.operations["gaussian_x90"].length * 1e-9
    )
    assert q1.macros["y90"].inferred_duration == pytest.approx(48e-9)


def test_xy_play_tracks_sticky_duration_in_ns():
    """XY apply records the played length, in nanoseconds, for voltage tracking."""
    machine = _build_machine()
    wire_machine_macros(machine)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]
    pulse = q1.xy.operations["gaussian_x90"]

    with (
        patch.object(q1.xy, "play", return_value=None),
        patch.object(q1.voltage_sequence, "track_sticky_duration") as mock_track,
    ):
        q1.x90()

    mock_track.assert_called_once_with(pulse.length)

    with (
        patch.object(q1.xy, "play", return_value=None),
        patch.object(q1.voltage_sequence, "track_sticky_duration") as mock_track,
    ):
        q1.x90(duration=10)

    mock_track.assert_called_once_with(40)


def test_xy_drive_update_duration_persists_pulse_length_in_ns():
    """xy_drive plays x180, so duration is stored on that pulse only."""
    machine = _build_machine()
    wire_machine_macros(machine)
    q1 = machine.qubits["q1"]
    xy_macro = q1.macros["xy_drive"]
    x90 = q1.xy.operations["gaussian_x90"]
    x180 = q1.xy.operations["gaussian_x180"]
    x90_length = x90.length
    x90_sigma = x90.sigma

    xy_macro.update(duration=400)

    assert x180.length == 400
    assert x180.sigma == pytest.approx(x180.length * x180.sigma_ratio)

    xy_macro.update(duration=403)

    assert x180.length == 404
    assert x180.sigma == pytest.approx(404 * x180.sigma_ratio)
    assert x90.length == x90_length
    assert x90.sigma == x90_sigma
    assert q1.xy.operations["gaussian_y90"].length == x90_length
    assert q1.xy.operations["gaussian_y180"].length == 404


def test_x180_update_writes_the_pi_pulse_only():
    """x180 and x() store duration on the x180 pulse."""
    machine = _build_machine()
    wire_machine_macros(machine)
    q1 = machine.qubits["q1"]
    x90 = q1.xy.operations["gaussian_x90"]
    x180 = q1.xy.operations["gaussian_x180"]
    x90_length = x90.length

    q1.x180.update(duration=200)

    assert x180.length == 200
    assert x180.sigma == pytest.approx(200 * x180.sigma_ratio)
    assert x90.length == x90_length
    assert q1.xy.operations["gaussian_y180"].length == 200

    q1.x.update(duration=240)

    assert x180.length == 240
    assert x90.length == x90_length


def test_update_rejects_referenced_length_and_amplitude():
    """A macro whose pulse fields are references does not write the anchor."""
    machine = _build_machine()
    wire_machine_macros(machine)
    q1 = machine.qubits["q1"]
    x90 = q1.xy.operations["gaussian_x90"]
    x180 = q1.xy.operations["gaussian_x180"]
    x90_length = x90.length
    x90_amplitude = x90.amplitude
    x180_length = x180.length
    q1.larmor_frequency = 1.0e9

    with pytest.raises(ValueError, match="gaussian_y90.length references gaussian_x90"):
        q1.y90.update(duration=200, frequency=2.0e9)

    with pytest.raises(ValueError, match="gaussian_y90.amplitude references gaussian_x90"):
        q1.y90.update(amplitude_scale=2)

    with pytest.raises(ValueError, match="gaussian_y180.length references gaussian_x180"):
        q1.y.update(duration=200)

    assert x90.length == x90_length
    assert x90.amplitude == x90_amplitude
    assert x180.length == x180_length
    assert q1.larmor_frequency == 1.0e9


def test_update_frequency_works_when_the_pulse_is_a_reference():
    """Frequency lives on the qubit, so a referenced pulse can still set it."""
    machine = _build_machine()
    wire_machine_macros(machine)
    q1 = machine.qubits["q1"]
    y90 = q1.xy.operations["gaussian_y90"]
    raw_length = y90.get_raw_value("length")

    q1.y90.update(frequency=2.5e9)

    assert q1.larmor_frequency == 2.5e9
    assert y90.get_raw_value("length") == raw_length


def test_x90_update_amplitude_scale_writes_the_played_pulse():
    """amplitude_scale multiplies the pulse this macro plays."""
    machine = _build_machine()
    wire_machine_macros(machine)
    q1 = machine.qubits["q1"]
    x90 = q1.xy.operations["gaussian_x90"]
    x180 = q1.xy.operations["gaussian_x180"]
    x90_amplitude = x90.amplitude
    x180_amplitude = x180.amplitude

    q1.x90.update(amplitude_scale=0.5)

    assert x90.amplitude == pytest.approx(x90_amplitude * 0.5)
    assert q1.xy.operations["gaussian_y90"].amplitude == pytest.approx(x90_amplitude * 0.5)
    assert x180.amplitude == x180_amplitude


@quam_dataclass
class _CustomGateMacro(XYDriveMacro):
    """Test macro whose operation stores its own length and amplitude."""

    _gate_suffix: ClassVar[str] = "_custom"


def test_custom_macro_update_writes_its_own_stored_pulse():
    """A subclass can update a pulse that stores length and amplitude."""
    machine = _build_machine()
    wire_machine_macros(machine)
    q1 = machine.qubits["q1"]
    q1.xy.operations["gaussian_custom"] = ScalableGaussianPulse(
        id="gaussian_custom",
        amplitude=0.05,
        length=80,
        sigma_ratio=0.25,
        axis_angle=0.0,
    )
    q1.set_macro("custom_gate", _CustomGateMacro())
    x90_length = q1.xy.operations["gaussian_x90"].length

    q1.macros["custom_gate"].update(duration=120, amplitude_scale=2)

    custom = q1.xy.operations["gaussian_custom"]
    assert custom.length == 120
    assert custom.amplitude == pytest.approx(0.1)
    assert custom.sigma == pytest.approx(120 * 0.25)
    assert q1.xy.operations["gaussian_x90"].length == x90_length


def test_identity_duration_is_clock_cycles():
    """Identity duration uses QUA clock cycles, and inferred_duration is seconds."""
    machine = _build_machine()
    wire_machine_macros(machine)
    q1 = machine.qubits["q1"]
    identity = q1.macros["I"]

    assert identity.duration == 4
    assert identity.inferred_duration == pytest.approx(16e-9)

    with patch.object(q1, "idle", return_value=None) as mock_idle:
        q1.I()
    mock_idle.assert_called_once_with(duration=identity.duration)

    with patch.object(q1, "idle", return_value=None) as mock_idle:
        q1.I(duration=10)
    mock_idle.assert_called_once_with(duration=10)


def test_negative_x_rotation_uses_negative_amplitude_scale():
    """Negative X is the x180 pulse played at a negative amplitude scale."""
    machine = _build_machine()
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "virtual_z", return_value=None) as mock_vz,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.x(angle=-np.pi / 2)

    mock_vz.assert_not_called()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x180"
    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(-0.5)


def test_negative_y_rotation_uses_negative_amplitude_scale():
    """Negative Y is the y180 pulse played at a negative amplitude scale."""
    machine = _build_machine()
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "virtual_z", return_value=None) as mock_vz,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.y(angle=-np.pi / 2)

    mock_vz.assert_not_called()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_y180"
    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(-0.5)
