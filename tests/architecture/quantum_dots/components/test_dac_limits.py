"""Tests for ``DacSpec.limits`` and how ``VirtualDCSet.set_voltages`` enforces them."""

from __future__ import annotations

import inspect
import json

import pytest
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import VirtualDCSet, VoltageGate
from quam_builder.architecture.quantum_dots.components.dac_spec import LIMITS, DacSpec, QdacSpec
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

DEFAULT_LIMITS = {"max_voltage": None, "min_voltage": None, "max_step_size": None}
FULL_LIMITS = {"max_voltage": 2.5, "min_voltage": -2.5, "max_step_size": 1.0}


class FakeOffsetParameter:
    """QCoDeS-like parameter: ``param()`` reads, ``param(v)`` sets."""

    def __init__(self, initial: float = 0.0) -> None:
        self.value = float(initial)
        self.set_calls = 0

    def __call__(self, value: float | None = None) -> float:
        if value is not None:
            self.value = float(value)
            self.set_calls += 1
        return self.value


def make_gate(port: int, limits: dict | None = None, with_dac_spec: bool = True) -> VoltageGate:
    gate = VoltageGate(
        id=f"g{port}",
        opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=port),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    gate.offset_parameter = FakeOffsetParameter()
    if with_dac_spec:
        gate.dac_spec = DacSpec(output_port=port, limits=limits)
    return gate


def make_dc_set(check_max_voltage: bool = True, **channels: VoltageGate) -> VirtualDCSet:
    return VirtualDCSet(id="dc", channels=channels, check_max_voltage=check_max_voltage)


class TestDacSpecLimits:
    def test_defaults_when_not_given(self):
        assert dict(DacSpec(output_port=1).limits) == DEFAULT_LIMITS

    def test_none_is_treated_as_not_given(self):
        assert dict(DacSpec(output_port=1, limits=None).limits) == DEFAULT_LIMITS

    def test_partial_limits_merge_over_defaults(self):
        spec = DacSpec(output_port=1, limits={"max_voltage": 1.0})
        assert dict(spec.limits) == {**DEFAULT_LIMITS, "max_voltage": 1.0}

    def test_complete_limits_are_kept(self):
        assert dict(DacSpec(output_port=1, limits=FULL_LIMITS).limits) == FULL_LIMITS

    @pytest.mark.parametrize("spec_cls", [DacSpec, QdacSpec])
    def test_unrecognised_key_is_rejected(self, spec_cls):
        with pytest.raises(ValueError, match=r"Unrecognised limit\(s\) \['max_voltage_step'\]"):
            spec_cls(output_port=1, limits={"max_voltage": 1.0, "max_voltage_step": 0.1})

    def test_all_unrecognised_keys_are_reported(self):
        with pytest.raises(ValueError, match=r"\['max_votlage', 'step'\]"):
            DacSpec(output_port=1, limits={"step": 0.1, "max_votlage": 1.0})

    def test_limits_keys_match_update_limits_arguments(self):
        params = list(inspect.signature(DacSpec.update_limits).parameters)[1:]
        assert tuple(params) == LIMITS
        assert tuple(DEFAULT_LIMITS) == LIMITS

    def test_instances_do_not_share_limits(self):
        a = DacSpec(output_port=1)
        b = DacSpec(output_port=2)
        a.update_limits(max_voltage=0.1)
        assert b.limits["max_voltage"] is None

    @pytest.mark.parametrize("spec_cls", [DacSpec, QdacSpec])
    def test_limits_cannot_be_reassigned(self, spec_cls):
        spec = spec_cls(output_port=1, limits={"max_voltage": 1.0})
        with pytest.raises(AttributeError, match="update_limits"):
            spec.limits = {"max_voltage": 0.5}
        assert spec.limits["max_voltage"] == 1.0
        spec.output_port = 2
        assert spec.output_port == 2

    def test_qdac_spec_inherits_merge(self):
        spec = QdacSpec(output_port=1, limits={"min_voltage": -1.0})
        assert dict(spec.limits) == {**DEFAULT_LIMITS, "min_voltage": -1.0}


class TestUpdateLimits:
    def test_changes_only_given_keys(self):
        spec = DacSpec(output_port=1, limits=FULL_LIMITS)
        spec.update_limits(max_voltage=0.5)
        assert dict(spec.limits) == {**FULL_LIMITS, "max_voltage": 0.5}

    def test_sets_all_keys(self):
        spec = DacSpec(output_port=1)
        spec.update_limits(max_voltage=1.0, min_voltage=-1.0, max_step_size=0.2)
        assert dict(spec.limits) == {"max_voltage": 1.0, "min_voltage": -1.0, "max_step_size": 0.2}

    def test_none_disables_a_check(self):
        spec = DacSpec(output_port=1, limits=FULL_LIMITS)
        spec.update_limits(max_step_size=None)
        assert dict(spec.limits) == {**FULL_LIMITS, "max_step_size": None}

    def test_no_arguments_changes_nothing(self):
        spec = DacSpec(output_port=1, limits=FULL_LIMITS)
        spec.update_limits()
        assert dict(spec.limits) == FULL_LIMITS

    def test_does_not_add_extra_keys(self):
        spec = DacSpec(output_port=1)
        spec.update_limits(max_step_size=0.1)
        assert set(spec.limits) == set(DEFAULT_LIMITS)

    def test_updated_limit_is_enforced(self):
        dc = make_dc_set(a=make_gate(1))
        dc.channels["a"].dac_spec.update_limits(max_voltage=0.3)
        with pytest.raises(ValueError, match=r"exceeds limit of \+0.3V"):
            dc.set_voltages({"a": 0.4})


class TestDacSpecLimitsPersistence:
    @pytest.fixture
    def machine(self) -> BaseQuamQD:
        machine = BaseQuamQD()
        gates = {f"v{i}": make_gate(i, with_dac_spec=False) for i in (1, 2, 3)}
        machine.create_virtual_gate_set(virtual_channel_mapping=gates, gate_set_id="qpu")
        gates["v1"].dac_spec = DacSpec(output_port=1, limits=FULL_LIMITS)
        gates["v2"].dac_spec = DacSpec(output_port=2, limits={"max_voltage": 0.5})
        gates["v3"].dac_spec = DacSpec(output_port=3)
        return machine

    @pytest.mark.parametrize("include_defaults", [True, False])
    def test_limits_round_trip(self, machine: BaseQuamQD, tmp_path, include_defaults: bool):
        machine.save(tmp_path, include_defaults=include_defaults)
        loaded = BaseQuamQD.load(tmp_path)

        assert dict(loaded.physical_channels["g1"].dac_spec.limits) == FULL_LIMITS
        assert dict(loaded.physical_channels["g2"].dac_spec.limits) == {
            **DEFAULT_LIMITS,
            "max_voltage": 0.5,
        }
        assert dict(loaded.physical_channels["g3"].dac_spec.limits) == DEFAULT_LIMITS

    def test_unrecognised_key_in_state_file_fails_load(self, machine: BaseQuamQD, tmp_path):
        machine.save(tmp_path)
        for state_file in tmp_path.glob("*.json"):
            state = json.loads(state_file.read_text())
            spec = _find_dac_spec(state, output_port=1)
            if spec is None:
                continue
            spec["limits"] = {"max_voltage_step": 0.1}
            state_file.write_text(json.dumps(state))

        with pytest.raises(ValueError, match=r"Unrecognised limit\(s\) \['max_voltage_step'\]"):
            BaseQuamQD.load(tmp_path)

    def test_loaded_limits_are_locked(self, machine: BaseQuamQD, tmp_path):
        machine.save(tmp_path)
        loaded = BaseQuamQD.load(tmp_path)
        with pytest.raises(AttributeError, match="update_limits"):
            loaded.physical_channels["g1"].dac_spec.limits = {}

    def test_partial_limits_in_state_file_are_merged_on_load(
        self, machine: BaseQuamQD, tmp_path
    ):
        machine.save(tmp_path)
        for state_file in tmp_path.glob("*.json"):
            text = state_file.read_text()
            if '"limits"' not in text:
                continue
            state = json.loads(text)
            spec = _find_dac_spec(state, output_port=1)
            spec["limits"] = {"min_voltage": -0.3}
            state_file.write_text(json.dumps(state))

        loaded = BaseQuamQD.load(tmp_path)
        assert dict(loaded.physical_channels["g1"].dac_spec.limits) == {
            **DEFAULT_LIMITS,
            "min_voltage": -0.3,
        }

    def test_edited_limit_survives_second_round_trip(self, machine: BaseQuamQD, tmp_path):
        machine.save(tmp_path)
        loaded = BaseQuamQD.load(tmp_path)
        loaded.physical_channels["g1"].dac_spec.update_limits(max_voltage=0.4, max_step_size=None)
        loaded.save(tmp_path)

        reloaded = BaseQuamQD.load(tmp_path)
        assert dict(reloaded.physical_channels["g1"].dac_spec.limits) == {
            **FULL_LIMITS,
            "max_voltage": 0.4,
            "max_step_size": None,
        }

    def test_loaded_virtual_dc_set_enforces_loaded_limits(self, machine: BaseQuamQD, tmp_path):
        machine.create_virtual_dc_set("qpu")
        machine.save(tmp_path)
        loaded = BaseQuamQD.load(tmp_path)
        for gate in loaded.physical_channels.values():
            gate.offset_parameter = FakeOffsetParameter()

        dc = loaded.virtual_dc_sets["qpu"]
        assert dc.channels["g2"] is loaded.physical_channels["g2"]

        dc.set_voltages({"v2": 0.4})
        with pytest.raises(ValueError, match=r"channel g2 exceeds limit of \+0.5V"):
            dc.set_voltages({"v2": 0.6})
        with pytest.raises(ValueError, match="channel g1 exceeds step size"):
            dc.set_voltages({"v1": 1.5})
        dc.set_voltages({"v2": -2.4})
        assert loaded.physical_channels["g2"].offset_parameter() == pytest.approx(-2.4)

        dc.set_voltages({"v3": 10.0})
        dc.set_voltages({"v3": -10.0})
        assert loaded.physical_channels["g3"].offset_parameter() == pytest.approx(-10.0)


def _find_dac_spec(node, output_port: int):
    if isinstance(node, dict):
        if "limits" in node and node.get("output_port") == output_port:
            return node
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        found = _find_dac_spec(child, output_port)
        if found is not None:
            return found
    return None


class TestSetVoltagesLimits:
    def test_default_spec_enforces_nothing(self):
        dc = make_dc_set(a=make_gate(1))
        dc.set_voltages({"a": 10.0})
        dc.set_voltages({"a": -10.0})
        assert dc.channels["a"].offset_parameter() == pytest.approx(-10.0)

    def test_within_limits_is_applied(self):
        dc = make_dc_set(a=make_gate(1, FULL_LIMITS))
        dc.set_voltages({"a": 0.9})
        assert dc.channels["a"].offset_parameter() == pytest.approx(0.9)

    def test_above_max_voltage_raises(self):
        dc = make_dc_set(a=make_gate(1, {"max_voltage": 0.5}))
        with pytest.raises(ValueError, match=r"exceeds limit of \+0.5V"):
            dc.set_voltages({"a": 0.6})

    def test_below_min_voltage_raises(self):
        dc = make_dc_set(a=make_gate(1, {"min_voltage": -0.5}))
        with pytest.raises(ValueError, match=r"exceeds limit of -0.5V"):
            dc.set_voltages({"a": -0.6})

    def test_step_larger_than_max_step_size_raises(self):
        dc = make_dc_set(a=make_gate(1, {"max_step_size": 1.0}))
        dc.set_voltages({"a": 0.9})
        with pytest.raises(ValueError, match="step size"):
            dc.set_voltages({"a": -0.2})

    def test_large_move_succeeds_in_small_steps(self):
        dc = make_dc_set(a=make_gate(1, FULL_LIMITS))
        for target in (0.8, 1.6, 2.4):
            dc.set_voltages({"a": target})
        assert dc.channels["a"].offset_parameter() == pytest.approx(2.4)

    def test_none_step_size_allows_large_jumps(self):
        dc = make_dc_set(a=make_gate(1, {**FULL_LIMITS, "max_step_size": None}))
        dc.set_voltages({"a": 2.4})
        assert dc.channels["a"].offset_parameter() == pytest.approx(2.4)

    def test_check_max_voltage_false_skips_all_checks(self):
        dc = make_dc_set(check_max_voltage=False, a=make_gate(1, {"max_voltage": 0.1}))
        dc.set_voltages({"a": 2.0})
        assert dc.channels["a"].offset_parameter() == pytest.approx(2.0)

    def test_channel_without_dac_spec_warns_and_is_not_checked(self):
        dc = make_dc_set(a=make_gate(1, with_dac_spec=False))
        with pytest.warns(UserWarning, match="dac_spec for channel a not found"):
            dc.set_voltages({"a": 10.0})
        assert dc.channels["a"].offset_parameter() == pytest.approx(10.0)

    def test_violation_on_one_channel_sets_no_channels(self):
        dc = make_dc_set(a=make_gate(1), b=make_gate(2, {"max_voltage": 0.1}))
        with pytest.raises(ValueError):
            dc.set_voltages({"a": 0.5, "b": 0.5})
        assert dc.channels["a"].offset_parameter.set_calls == 0
        assert dc.channels["b"].offset_parameter.set_calls == 0

    def test_limits_apply_to_resolved_physical_voltages(self):
        dc = make_dc_set(a=make_gate(1, {"max_voltage": 0.5}), b=make_gate(2))
        dc.add_layer(source_gates=["va", "vb"], target_gates=["a", "b"], matrix=[[1, 0], [0, 0.5]])
        dc.set_voltages({"vb": 0.2})
        assert dc.channels["b"].offset_parameter() == pytest.approx(0.4)
        with pytest.raises(ValueError, match="channel a exceeds limit"):
            dc.set_voltages({"va": 0.6})

    def test_channel_already_outside_limits_blocks_all_moves(self):
        dc = make_dc_set(a=make_gate(1), b=make_gate(2))
        dc.set_voltages({"a": 0.8})
        dc.channels["a"].dac_spec.update_limits(max_voltage=0.5)
        with pytest.raises(ValueError, match="channel a"):
            dc.set_voltages({"b": 0.1})
