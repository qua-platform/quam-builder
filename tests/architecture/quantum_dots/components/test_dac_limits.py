"""Tests for ``DacSpec.limits`` and how ``VirtualDCSet.set_voltages`` enforces them."""

from __future__ import annotations

import json

import pytest
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import VirtualDCSet, VoltageGate
from quam_builder.architecture.quantum_dots.components.dac_spec import DacSpec, QdacSpec
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

DEFAULT_LIMITS = {"max_voltage": 2.5, "min_voltage": -2.5, "max_step_size": 1}


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

    def test_none_value_is_kept_to_disable_a_check(self):
        spec = DacSpec(output_port=1, limits={"max_step_size": None})
        assert spec.limits["max_step_size"] is None
        assert spec.limits["max_voltage"] == 2.5

    def test_instances_do_not_share_limits(self):
        a = DacSpec(output_port=1)
        b = DacSpec(output_port=2)
        a.limits["max_voltage"] = 0.1
        assert b.limits["max_voltage"] == 2.5

    def test_qdac_spec_inherits_merge(self):
        spec = QdacSpec(output_port=1, limits={"min_voltage": -1.0})
        assert dict(spec.limits) == {**DEFAULT_LIMITS, "min_voltage": -1.0}


class TestDacSpecLimitsPersistence:
    @pytest.fixture
    def machine(self) -> BaseQuamQD:
        machine = BaseQuamQD()
        gates = {f"v{i}": make_gate(i, with_dac_spec=False) for i in (1, 2)}
        machine.create_virtual_gate_set(virtual_channel_mapping=gates, gate_set_id="qpu")
        gates["v1"].dac_spec = DacSpec(output_port=1)
        gates["v2"].dac_spec = DacSpec(
            output_port=2, limits={"max_voltage": 0.5, "max_step_size": None}
        )
        return machine

    @pytest.mark.parametrize("include_defaults", [True, False])
    def test_limits_round_trip(self, machine: BaseQuamQD, tmp_path, include_defaults: bool):
        machine.save(tmp_path, include_defaults=include_defaults)
        loaded = BaseQuamQD.load(tmp_path)

        assert dict(loaded.physical_channels["g1"].dac_spec.limits) == DEFAULT_LIMITS
        assert dict(loaded.physical_channels["g2"].dac_spec.limits) == {
            **DEFAULT_LIMITS,
            "max_voltage": 0.5,
            "max_step_size": None,
        }

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
        loaded.physical_channels["g1"].dac_spec.limits["max_voltage"] = 0.4
        loaded.save(tmp_path)

        reloaded = BaseQuamQD.load(tmp_path)
        assert dict(reloaded.physical_channels["g1"].dac_spec.limits) == {
            **DEFAULT_LIMITS,
            "max_voltage": 0.4,
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
    def test_within_limits_is_applied(self):
        dc = make_dc_set(a=make_gate(1))
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
        dc = make_dc_set(a=make_gate(1))
        dc.set_voltages({"a": 0.9})
        with pytest.raises(ValueError, match="step size"):
            dc.set_voltages({"a": -0.2})

    def test_large_move_succeeds_in_small_steps(self):
        dc = make_dc_set(a=make_gate(1))
        for target in (0.8, 1.6, 2.4):
            dc.set_voltages({"a": target})
        assert dc.channels["a"].offset_parameter() == pytest.approx(2.4)

    def test_none_step_size_allows_large_jumps(self):
        dc = make_dc_set(a=make_gate(1, {"max_step_size": None}))
        dc.set_voltages({"a": 2.4})
        assert dc.channels["a"].offset_parameter() == pytest.approx(2.4)

    def test_none_range_limits_are_unbounded(self):
        limits = {"max_voltage": None, "min_voltage": None, "max_step_size": None}
        dc = make_dc_set(a=make_gate(1, limits))
        dc.set_voltages({"a": 10.0})
        dc.set_voltages({"a": -10.0})
        assert dc.channels["a"].offset_parameter() == pytest.approx(-10.0)

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
        dc.channels["a"].dac_spec.limits["max_voltage"] = 0.5
        with pytest.raises(ValueError, match="channel a"):
            dc.set_voltages({"b": 0.1})
