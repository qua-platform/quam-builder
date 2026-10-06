"""Tests for runtime macro wiring and override behavior."""

from functools import partial
from unittest.mock import patch

import numpy as np
import pytest

from qm import qua
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components import pulses
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    X180Macro,
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
    """xy_drive() plays the x90 operation and does not rotate the frame."""
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "virtual_z", return_value=None) as mock_vz,
        patch.object(q1.xy, "play", return_value=None) as mock_play,
    ):
        q1.xy_drive()

    mock_vz.assert_not_called()
    assert mock_play.call_args.kwargs["pulse_name"] == "gaussian_x90"
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
    """Each macro reports the length of the operation it plays, in nanoseconds."""
    machine = _build_machine()
    wire_machine_macros(machine)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]
    q1.xy.operations["gaussian_x180"].length = 80
    q1.xy.operations["gaussian_y90"] = pulses.GaussianPulse(length=48, amplitude=0.01, sigma=12)

    assert q1.macros["x"].inferred_duration == pytest.approx(80)
    assert q1.macros["x90"].inferred_duration == pytest.approx(
        q1.xy.operations["gaussian_x90"].length
    )
    assert q1.macros["y90"].inferred_duration == pytest.approx(48)


def test_xy_drive_native_pulse_length_is_converted_to_voltage_tracking_duration():
    """Voltage tracking should advance by the native pulse length."""
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


def test_xy_drive_update_duration_persists_pulse_length_in_ns():
    """Persisted macro duration is specified and stored in ns (samples at 1 GS/s)."""
    machine = _build_machine()
    wire_machine_macros(machine)
    q1 = machine.qubits["q1"]
    xy_macro = q1.macros["xy_drive"]
    pulse = q1.xy.operations["gaussian_x90"]

    xy_macro.update(duration=400)

    assert pulse.length == 400
    assert pulse.sigma == pytest.approx(pulse.length * pulse.sigma_ratio)


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
