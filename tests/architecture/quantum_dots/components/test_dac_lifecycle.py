"""Tests for DAC connect/disconnect lifecycle on BaseQuamQD."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.architecture.quantum_dots.components.dac_spec import DacSpec
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD


class CloseableFakeDac:
    """Minimal driver with channel accessor and ``close``."""

    instances: dict[str, CloseableFakeDac] = {}

    def __init__(self, name: str, **_connection: Any) -> None:
        self.name = name
        self.closed = False
        self._voltages: dict[int, float] = {}
        type(self).instances[name] = self

    def channel(self, port: int) -> SimpleNamespace:
        def dc_constant_V(value: float | None = None) -> float:
            if value is not None:
                self._voltages[port] = float(value)
            return self._voltages.get(port, 0.0)

        return SimpleNamespace(dc_constant_V=dc_constant_V)

    def close(self) -> None:
        self.closed = True


class ShutdownFakeDac:
    """Driver that tears down via ``shutdown`` rather than ``close``."""

    instances: dict[str, ShutdownFakeDac] = {}

    def __init__(self, name: str, **_connection: Any) -> None:
        self.name = name
        self.shutdown_called = False
        type(self).instances[name] = self

    def channel(self, port: int) -> SimpleNamespace:
        return SimpleNamespace(dc_constant_V=lambda value=None: 0.0)

    def shutdown(self) -> None:
        self.shutdown_called = True


class NonCloseableFakeDac:
    """Driver with no teardown method."""

    def __init__(self, name: str, **_connection: Any) -> None:
        self.name = name

    def channel(self, port: int) -> SimpleNamespace:
        return SimpleNamespace(dc_constant_V=lambda value=None: 0.0)


@pytest.fixture
def fake_module_name() -> str:
    """Import path used by ``dac_config`` to load the fake drivers in this module."""
    return __name__


@pytest.fixture
def closeable_dac_config(fake_module_name: str) -> dict:
    return {
        "main": {
            "driver_module": fake_module_name,
            "driver_class": "CloseableFakeDac",
            "connection": {},
            "channel_method": "channel",
            "accessor": "dc_constant_V",
            "is_qdac": False,
            "close_method": "close",
        }
    }


@pytest.fixture
def shutdown_dac_config(fake_module_name: str) -> dict:
    return {
        "main": {
            "driver_module": fake_module_name,
            "driver_class": "ShutdownFakeDac",
            "connection": {},
            "channel_method": "channel",
            "accessor": "dc_constant_V",
            "is_qdac": False,
            "close_method": "shutdown",
        }
    }


@pytest.fixture
def non_closeable_dac_config(fake_module_name: str) -> dict:
    return {
        "main": {
            "driver_module": fake_module_name,
            "driver_class": "NonCloseableFakeDac",
            "connection": {},
            "channel_method": "channel",
            "accessor": "dc_constant_V",
            "is_qdac": False,
        }
    }


@pytest.fixture
def machine_with_gated_dac() -> BaseQuamQD:
    CloseableFakeDac.instances.clear()
    ShutdownFakeDac.instances.clear()
    machine = BaseQuamQD()
    gate = VoltageGate(
        id="p1",
        opx_output=LFFEMAnalogOutputPort("con1", 6, port_id=1),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    machine.create_virtual_gate_set(
        virtual_channel_mapping={"v1": gate},
        gate_set_id="qpu",
    )
    gate.dac_spec = DacSpec(output_port=1, dac_name="main")
    return machine


@pytest.fixture
def connected_machine(
    machine_with_gated_dac: BaseQuamQD, closeable_dac_config: dict
) -> BaseQuamQD:
    machine_with_gated_dac.set_dac_config(closeable_dac_config)
    machine_with_gated_dac.connect_to_external_source()
    return machine_with_gated_dac


def test_connect_accepts_driver_without_close_method(
    machine_with_gated_dac: BaseQuamQD, non_closeable_dac_config: dict
):
    machine_with_gated_dac.set_dac_config(non_closeable_dac_config)
    machine_with_gated_dac.connect_to_external_source()
    assert "main" in machine_with_gated_dac.dacs
    assert machine_with_gated_dac.dacs["main"]["close_method"] is None


def test_connect_accepts_closeable_driver(connected_machine: BaseQuamQD):
    assert "main" in connected_machine.dacs
    assert callable(connected_machine.physical_channels["p1"].offset_parameter)
    assert not CloseableFakeDac.instances["main"].closed
    assert connected_machine.dacs["main"]["close_method"] == "close"


def test_disconnect_closes_driver_without_changing_quam_config(
    connected_machine: BaseQuamQD,
):
    driver = CloseableFakeDac.instances["main"]
    offset_before = connected_machine.physical_channels["p1"].offset_parameter

    connected_machine.disconnect_from_external_source()

    assert driver.closed
    assert "main" in connected_machine.dacs
    assert connected_machine.physical_channels["p1"].offset_parameter is offset_before


def test_disconnect_is_noop_when_no_dacs():
    machine = BaseQuamQD()
    machine.disconnect_from_external_source()
    assert machine.dacs == {}


def test_disconnect_skips_driver_without_close_method(
    machine_with_gated_dac: BaseQuamQD, non_closeable_dac_config: dict
):
    machine_with_gated_dac.set_dac_config(non_closeable_dac_config)
    machine_with_gated_dac.connect_to_external_source()
    machine_with_gated_dac.disconnect_from_external_source()
    assert "main" in machine_with_gated_dac.dacs


def test_disconnect_calls_configured_close_method(
    machine_with_gated_dac: BaseQuamQD, shutdown_dac_config: dict
):
    machine_with_gated_dac.set_dac_config(shutdown_dac_config)
    machine_with_gated_dac.connect_to_external_source()
    driver = ShutdownFakeDac.instances["main"]

    machine_with_gated_dac.disconnect_from_external_source()

    assert driver.shutdown_called


def test_disconnect_rejects_missing_configured_method():
    machine = BaseQuamQD()
    machine.dacs["broken"] = {
        "driver": NonCloseableFakeDac("broken"),
        "channel_method": "channel",
        "accessor": "dc_constant_V",
        "is_qdac": False,
        "close_method": "close",
    }
    with pytest.raises(TypeError, match=r"has no callable 'close' method"):
        machine.disconnect_from_external_source()


def test_reconnect_closes_previous_driver(connected_machine: BaseQuamQD):
    first = CloseableFakeDac.instances["main"]

    connected_machine.connect_to_external_source()
    second = CloseableFakeDac.instances["main"]

    assert first.closed
    assert first is not second
    assert not second.closed
