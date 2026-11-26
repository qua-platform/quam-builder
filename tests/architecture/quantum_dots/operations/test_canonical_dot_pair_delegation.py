"""Tests for canonical QuantumDotPair macro delegation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    Empty1QMacro,
    Initialize1QMacro,
    Measure1QMacro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.two_qubit_macros import (
    Empty2QMacro,
    Initialize2QMacro,
    Measure2QMacro,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    EmptyStateMacro,
    InitializeStateMacro,
    MeasurePSBPairMacro,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD


class TestInitializeStateMacroUpdate:
    def test_update_ramp_duration(self):
        macro = InitializeStateMacro()
        macro.update(ramp_duration=32)
        assert macro.ramp_duration == 32

    def test_update_hold_duration(self):
        macro = InitializeStateMacro()
        macro.update(hold_duration=200)
        assert macro.hold_duration == 200

    def test_update_point(self):
        macro = InitializeStateMacro()
        macro.update(point="custom_init")
        assert macro.point == "custom_init"

    def test_update_multiple_params(self):
        macro = InitializeStateMacro()
        macro.update(ramp_duration=64, hold_duration=400)
        assert macro.ramp_duration == 64
        assert macro.hold_duration == 400

    def test_update_rejects_unknown_kwargs(self):
        macro = InitializeStateMacro()
        with pytest.raises(TypeError):
            macro.update(nonexistent_param=42)

    def test_update_hold_duration_none_clears_override(self):
        macro = InitializeStateMacro()
        macro.update(hold_duration=200)
        assert macro.hold_duration == 200
        macro.update(hold_duration=None)
        assert macro.hold_duration is None


class TestEmptyStateMacroUpdate:
    def test_update_hold_duration(self):
        macro = EmptyStateMacro()
        macro.update(hold_duration=300)
        assert macro.hold_duration == 300

    def test_update_point(self):
        macro = EmptyStateMacro()
        macro.update(point="custom_empty")
        assert macro.point == "custom_empty"

    def test_update_multiple_params(self):
        macro = EmptyStateMacro()
        macro.update(hold_duration=300, point="custom_empty")
        assert macro.hold_duration == 300
        assert macro.point == "custom_empty"

    def test_update_rejects_unknown_kwargs(self):
        macro = EmptyStateMacro()
        with pytest.raises(TypeError):
            macro.update(nonexistent_param=42)

    def test_update_hold_duration_none_clears_override(self):
        macro = EmptyStateMacro()
        macro.update(hold_duration=300)
        assert macro.hold_duration == 300
        macro.update(hold_duration=None)
        assert macro.hold_duration is None


class TestMeasurePSBPairMacroUpdate:
    def test_update_buffer_duration(self):
        macro = MeasurePSBPairMacro()
        macro.update(buffer_duration=500)
        assert macro.buffer_duration == 500

    def test_update_point(self):
        macro = MeasurePSBPairMacro()
        macro.update(point="custom_measure")
        assert macro.point == "custom_measure"

    def test_update_multiple_params(self):
        macro = MeasurePSBPairMacro()
        macro.update(buffer_duration=500, point="custom_measure")
        assert macro.buffer_duration == 500
        assert macro.point == "custom_measure"

    def test_update_rejects_unknown_kwargs(self):
        macro = MeasurePSBPairMacro()
        with pytest.raises(TypeError):
            macro.update(nonexistent_param=42)


def _mock_qubit_with_pair(pair_macros=None):
    """Build a mock qubit whose preferred readout dot resolves to an LDQubitPair."""
    pair = MagicMock()
    if pair_macros is not None:
        pair.macros = pair_macros
    else:
        pair.macros = {
            "initialize": MagicMock(),
            "empty": MagicMock(),
            "measure": MagicMock(),
        }

    qubit = MagicMock()
    qubit.preferred_readout_quantum_dot = "dot2"
    qubit.quantum_dot.id = "dot1"
    pair.qubit_control = qubit
    pair.qubit_target.quantum_dot.id = "dot2"
    qubit.machine.qubit_pairs = {"Q1_Q2": pair}
    return qubit, pair


class TestInitialize1QMacroDelegation:
    def test_apply_delegates_to_pair(self):
        qubit, pair = _mock_qubit_with_pair()
        macro = Initialize1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            macro.apply(ramp_duration=32)

        pair.macros["initialize"].apply.assert_called_once_with(
            ramp_duration=32, qubit_name=qubit.name
        )

    def test_apply_raises_without_preferred_dot(self):
        qubit = MagicMock()
        qubit.preferred_readout_quantum_dot = None
        macro = Initialize1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            with pytest.raises(ValueError, match="preferred_readout_quantum_dot"):
                macro.apply()

    def test_apply_raises_when_pair_not_found(self):
        qubit = MagicMock()
        qubit.preferred_readout_quantum_dot = "dot2"
        qubit.quantum_dot.id = "dot1"
        qubit.machine.qubit_pairs = {}
        macro = Initialize1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            with pytest.raises(ValueError, match="No QubitPair found"):
                macro.apply()

    def test_update_delegates_to_pair(self):
        init_macro = InitializeStateMacro()
        qubit, pair = _mock_qubit_with_pair({"initialize": init_macro})
        macro = Initialize1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            macro.update(ramp_duration=64)

        assert init_macro.ramp_duration == 64

    def test_callable_dispatches_apply(self):
        qubit, pair = _mock_qubit_with_pair()
        macro = Initialize1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            macro()

        pair.macros["initialize"].apply.assert_called_once()

    def test_inferred_duration_delegates(self):
        init_macro = MagicMock()
        init_macro.inferred_duration = 5e-7
        qubit, pair = _mock_qubit_with_pair({"initialize": init_macro})
        macro = Initialize1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            assert macro.inferred_duration == pytest.approx(5e-7)


class TestEmpty1QMacroDelegation:
    def test_apply_delegates_to_pair(self):
        qubit, pair = _mock_qubit_with_pair()
        macro = Empty1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            macro.apply(hold_duration=100)

        pair.macros["empty"].apply.assert_called_once_with(hold_duration=100)

    def test_apply_raises_without_preferred_dot(self):
        qubit = MagicMock()
        qubit.preferred_readout_quantum_dot = None
        macro = Empty1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            with pytest.raises(ValueError, match="preferred_readout_quantum_dot"):
                macro.apply()

    def test_update_delegates_to_pair(self):
        empty_macro = EmptyStateMacro()
        qubit, pair = _mock_qubit_with_pair({"empty": empty_macro})
        macro = Empty1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            macro.update(hold_duration=200)

        assert empty_macro.hold_duration == 200

    def test_callable_dispatches_apply(self):
        qubit, pair = _mock_qubit_with_pair()
        macro = Empty1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            macro()

        pair.macros["empty"].apply.assert_called_once()

    def test_inferred_duration_delegates(self):
        empty_macro = MagicMock()
        empty_macro.inferred_duration = 3e-7
        qubit, pair = _mock_qubit_with_pair({"empty": empty_macro})
        macro = Empty1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            assert macro.inferred_duration == pytest.approx(3e-7)


class TestMeasure1QMacroDelegation:
    def test_update_delegates_to_pair(self):
        measure_macro = MeasurePSBPairMacro()
        qubit, pair = _mock_qubit_with_pair({"measure": measure_macro})
        macro = Measure1QMacro()

        with patch.object(
            type(macro), "qubit", new_callable=lambda: property(lambda self: qubit)
        ):
            macro.update(buffer_duration=500)

        assert measure_macro.buffer_duration == 500


_2Q_OWNER_PATCH = (
    "quam_builder.architecture.quantum_dots.operations.default_macros"
    ".two_qubit_macros._owner_component"
)


def _mock_qubit_pair_owner(pair_macros=None):
    """Build a mock LDQubitPair owner with a quantum_dot_pair."""
    qd_pair = MagicMock()
    if pair_macros is not None:
        qd_pair.macros = pair_macros
    else:
        qd_pair.macros = {
            "initialize": MagicMock(),
            "empty": MagicMock(),
            "measure": MagicMock(),
        }

    owner = MagicMock()
    owner.quantum_dot_pair = qd_pair
    owner.id = "Q1_Q2"
    return owner, qd_pair


class TestInitialize2QMacroDelegation:
    def test_apply_delegates_to_pair(self):
        owner, qd_pair = _mock_qubit_pair_owner()
        macro = Initialize2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            macro.apply(ramp_duration=32)

        qd_pair.macros["initialize"].apply.assert_called_once_with(
            xy_channel=owner.xy,
            ramp_duration=32,
            qubit_name=owner.qubit_control.name,
            target_state=owner.heralded_initialize_target_state,
        )

    def test_apply_raises_without_quantum_dot_pair(self):
        owner = MagicMock()
        owner.quantum_dot_pair = None
        owner.id = "Q1_Q2"
        macro = Initialize2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            with pytest.raises(ValueError, match="quantum_dot_pair"):
                macro.apply()

    def test_update_delegates_to_pair(self):
        init_macro = InitializeStateMacro()
        owner, qd_pair = _mock_qubit_pair_owner({"initialize": init_macro})
        macro = Initialize2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            macro.update(ramp_duration=128)

        assert init_macro.ramp_duration == 128

    def test_callable_dispatches_apply(self):
        owner, qd_pair = _mock_qubit_pair_owner()
        macro = Initialize2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            macro()

        qd_pair.macros["initialize"].apply.assert_called_once()

    def test_inferred_duration_delegates(self):
        init_macro = MagicMock()
        init_macro.inferred_duration = 1e-6
        owner, qd_pair = _mock_qubit_pair_owner({"initialize": init_macro})
        macro = Initialize2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            assert macro.inferred_duration == pytest.approx(1e-6)


class TestEmpty2QMacroDelegation:
    def test_apply_delegates_to_pair(self):
        owner, qd_pair = _mock_qubit_pair_owner()
        macro = Empty2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            macro.apply(hold_duration=50)

        qd_pair.macros["empty"].apply.assert_called_once_with(hold_duration=50)

    def test_apply_raises_without_quantum_dot_pair(self):
        owner = MagicMock()
        owner.quantum_dot_pair = None
        owner.id = "Q1_Q2"
        macro = Empty2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            with pytest.raises(ValueError, match="quantum_dot_pair"):
                macro.apply()

    def test_update_delegates_to_pair(self):
        empty_macro = EmptyStateMacro()
        owner, qd_pair = _mock_qubit_pair_owner({"empty": empty_macro})
        macro = Empty2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            macro.update(hold_duration=400)

        assert empty_macro.hold_duration == 400

    def test_callable_dispatches_apply(self):
        owner, qd_pair = _mock_qubit_pair_owner()
        macro = Empty2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            macro()

        qd_pair.macros["empty"].apply.assert_called_once()


class TestMeasure2QMacroDelegation:
    def test_update_delegates_to_pair(self):
        measure_macro = MeasurePSBPairMacro()
        owner, qd_pair = _mock_qubit_pair_owner({"measure": measure_macro})
        macro = Measure2QMacro()

        with patch(_2Q_OWNER_PATCH, return_value=owner):
            macro.update(buffer_duration=800)

        assert measure_macro.buffer_duration == 800


class TestSerializationPersistence:
    """Verify that update() changes persist through save/load round-trips."""

    def test_initialize_update_persists(self, qd_machine, tmp_path):
        wire_machine_macros(qd_machine)
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        pair.macros["initialize"].update(ramp_duration=64, hold_duration=400)

        qd_machine.save(tmp_path)
        loaded = BaseQuamQD.load(tmp_path)

        loaded_pair = loaded.quantum_dot_pairs["dot1_dot2_pair"]
        assert loaded_pair.macros["initialize"].ramp_duration == 64
        assert loaded_pair.macros["initialize"].hold_duration == 400

    def test_empty_update_persists(self, qd_machine, tmp_path):
        wire_machine_macros(qd_machine)
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        pair.macros["empty"].update(hold_duration=300)

        qd_machine.save(tmp_path)
        loaded = BaseQuamQD.load(tmp_path)

        loaded_pair = loaded.quantum_dot_pairs["dot1_dot2_pair"]
        assert loaded_pair.macros["empty"].hold_duration == 300

    def test_measure_update_persists(self, qd_machine, tmp_path):
        wire_machine_macros(qd_machine)
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        pair.macros["measure"].update(buffer_duration=500)

        qd_machine.save(tmp_path)
        loaded = BaseQuamQD.load(tmp_path)

        loaded_pair = loaded.quantum_dot_pairs["dot1_dot2_pair"]
        assert loaded_pair.macros["measure"].buffer_duration == 500

    def test_direct_setattr_persists(self, qd_machine, tmp_path):
        wire_machine_macros(qd_machine)
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        pair.macros["initialize"].ramp_duration = 128

        qd_machine.save(tmp_path)
        loaded = BaseQuamQD.load(tmp_path)

        loaded_pair = loaded.quantum_dot_pairs["dot1_dot2_pair"]
        assert loaded_pair.macros["initialize"].ramp_duration == 128
