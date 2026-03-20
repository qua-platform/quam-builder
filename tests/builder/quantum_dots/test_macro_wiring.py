"""Tests for runtime macro wiring and override behavior."""

import numpy as np
import pytest
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from unittest.mock import patch
from qm import qua
from quam.components import pulses

from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    X180Macro,
    XYDriveMacro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    InitializeStateMacro,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
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
        qubit.xy.operations.setdefault(
            "gaussian", pulses.GaussianPulse(length=64, amplitude=0.01, sigma=16)
        )


class TunedX180Macro(X180Macro):
    """Simple marker macro used for instance-level override testing."""

    default_amplitude_scale: float = 0.75


def test_instance_override_path_supports_quam_mappings():
    """Instance overrides should work for collections stored as Quam mappings."""
    machine = _build_machine()

    wire_machine_macros(
        machine,
        macro_overrides={
            "instances": {
                "qubits.q1": {
                    "macros": {
                        "x180": {
                            "factory": TunedX180Macro,
                            "params": {"default_amplitude_scale": 0.75},
                        },
                    }
                }
            }
        },
        strict=True,
    )

    assert isinstance(machine.qubits["q1"].macros["x180"], TunedX180Macro)
    assert machine.qubits["q1"].macros["x180"].default_amplitude_scale == pytest.approx(0.75)
    assert isinstance(machine.qubits["q2"].macros["x180"], X180Macro)


def test_component_type_override_applies_to_all_instances():
    """Component-type overrides should apply to each matching instance."""
    machine = _build_machine()

    wire_machine_macros(
        machine,
        macro_overrides={
            "component_types": {
                "LDQubit": {
                    "macros": {
                        "initialize": {
                            "factory": InitializeStateMacro,
                            "params": {"ramp_duration": 48},
                        }
                    }
                }
            }
        },
        strict=True,
    )

    for qubit in machine.qubits.values():
        assert isinstance(qubit.macros["initialize"], InitializeStateMacro)
        assert qubit.macros["initialize"].ramp_duration == 48


def test_component_type_override_sets_xy_drive_runtime_params():
    """Override params should populate canonical xy_drive attributes after init."""
    machine = _build_machine()

    wire_machine_macros(
        machine,
        macro_overrides={
            "component_types": {
                "LDQubit": {
                    "macros": {
                        "xy_drive": {
                            "factory": XYDriveMacro,
                            "params": {"default_amplitude_scale": 0.85},
                        }
                    }
                }
            }
        },
        strict=True,
    )

    for qubit in machine.qubits.values():
        assert isinstance(qubit.macros["xy_drive"], XYDriveMacro)
        assert qubit.macros["xy_drive"].default_amplitude_scale == pytest.approx(0.85)


def test_canonical_x_and_y_delegate_to_xy_drive():
    """Canonical axis macros should delegate into `xy_drive` with proper phase."""
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with patch.object(q1, "call_macro", return_value=None) as mock_call:
        q1.macros["x"].apply(angle=np.pi / 3)
    mock_call.assert_called_once_with("xy_drive", angle=np.pi / 3, phase=0.0)

    with patch.object(q1, "call_macro", return_value=None) as mock_call:
        q1.macros["y"].apply(angle=np.pi / 4)
    mock_call.assert_called_once_with("xy_drive", angle=np.pi / 4, phase=pytest.approx(np.pi / 2))


def test_runtime_phase_is_added_to_axis_phase():
    """Runtime phase should compose additively with the canonical axis phase."""
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with patch.object(q1, "call_macro", return_value=None) as mock_call:
        q1.macros["y"].apply(angle=np.pi / 4, phase=0.125)
    mock_call.assert_called_once_with(
        "xy_drive",
        angle=np.pi / 4,
        phase=pytest.approx(np.pi / 2 + 0.125),
    )


def test_fixed_angle_macros_delegate_to_canonical_axes():
    """x90/y90/z90 wrappers should dispatch to canonical x/y/z with fixed angles."""
    machine = _build_machine()
    q1 = machine.qubits["q1"]

    with patch.object(q1, "call_macro", return_value=None) as mock_call:
        q1.macros["x90"].apply()
    mock_call.assert_called_once_with("x", angle=pytest.approx(np.pi / 2))

    with patch.object(q1, "call_macro", return_value=None) as mock_call:
        q1.macros["y90"].apply()
    mock_call.assert_called_once_with("y", angle=pytest.approx(np.pi / 2))

    with patch.object(q1, "call_macro", return_value=None) as mock_call:
        q1.macros["z90"].apply()
    mock_call.assert_called_once_with("z", angle=pytest.approx(np.pi / 2))


def test_x180_macro_produces_valid_qua_program():
    """X180Macro.apply() inside qua.program() produces a valid non-None QUA program."""
    machine = _build_machine()
    wire_machine_macros(machine, strict=True)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with qua.program() as prog:
        q1.macros["x180"].apply()

    assert prog is not None


def test_x180_macro_triggers_play():
    """X180Macro.apply() triggers play_xy_pulse via delegation chain."""
    machine = _build_machine()
    wire_machine_macros(machine, strict=True)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with patch.object(q1, "play_xy_pulse", return_value=None) as mock_play:
        with qua.program():
            q1.macros["x180"].apply()

    assert mock_play.call_count >= 1
    assert mock_play.call_args.args[0] == "gaussian"


def test_runtime_amplitude_scale_multiplies_angle_scale():
    """Runtime amplitude scaling should multiply the angle-derived pulse scaling."""
    machine = _build_machine()
    wire_machine_macros(machine, strict=True)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "play_xy_pulse", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.x90(amplitude_scale=0.5)

    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(0.25)


def test_xy_drive_default_amplitude_scale_flows_through_wrappers():
    """The canonical xy_drive default amplitude scale should reach wrapper macros."""
    machine = _build_machine()
    wire_machine_macros(machine, strict=True)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]
    q1.macros["xy_drive"].default_amplitude_scale = 0.8

    with (
        patch.object(q1, "play_xy_pulse", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.x90()

    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(0.4)


def test_fixed_angle_default_scale_composes_with_runtime_scale():
    """Fixed-angle macro defaults should compose multiplicatively with runtime scaling."""
    machine = _build_machine()
    wire_machine_macros(
        machine,
        macro_overrides={
            "instances": {
                "qubits.q1": {
                    "macros": {
                        "x180": {"factory": TunedX180Macro},
                    }
                }
            }
        },
        strict=True,
    )
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "play_xy_pulse", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.x180(amplitude_scale=0.5)

    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(0.375)


def test_fixed_angle_inferred_duration_uses_xy_drive_angle_scaling():
    """Fixed-angle inferred durations should be computed from canonical xy_drive."""
    machine = _build_machine()
    wire_machine_macros(machine, strict=True)
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]
    q1.macros["xy_drive"].max_amplitude_scale = 0.85

    assert q1.macros["x"].inferred_duration == pytest.approx(1.176e-06)
    assert q1.macros["x90"].inferred_duration == pytest.approx(1e-06)
    assert q1.macros["y90"].inferred_duration == pytest.approx(1e-06)


def test_negative_x_rotation_is_phase_shifted_positive_angle_drive():
    """Negative X should map to +pi phase shift with positive amplitude scale."""
    machine = _build_machine()
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "virtual_z", return_value=None) as mock_vz,
        patch.object(q1, "play_xy_pulse", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.x(angle=-np.pi / 2)

    assert mock_vz.call_args_list[0].args[0] == pytest.approx(np.pi)
    assert mock_vz.call_args_list[1].args[0] == pytest.approx(-np.pi)
    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(0.5)


def test_negative_y_rotation_is_phase_shifted_positive_angle_drive():
    """Negative Y should map to (pi/2 + pi) phase shift with positive amplitude scale."""
    machine = _build_machine()
    _seed_reference_pulses(machine)
    q1 = machine.qubits["q1"]

    with (
        patch.object(q1, "virtual_z", return_value=None) as mock_vz,
        patch.object(q1, "play_xy_pulse", return_value=None) as mock_play,
        patch.object(q1.voltage_sequence, "step_to_voltages", return_value=None),
    ):
        q1.y(angle=-np.pi / 2)

    assert mock_vz.call_args_list[0].args[0] == pytest.approx(3 * np.pi / 2)
    assert mock_vz.call_args_list[1].args[0] == pytest.approx(-3 * np.pi / 2)
    assert mock_play.call_args.kwargs["amplitude_scale"] == pytest.approx(0.5)
