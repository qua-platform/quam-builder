"""Tests for ``BaseQuam.twpa_keepalive``.
"""

import pytest

from quam.config.models.quam import QuamConfig
from quam.config.resolvers import get_quam_config
from quam.config.vars import CONFIG_PATH_ENV_NAME
from quam.components.ports import FEMPortsContainer

import quam_builder.architecture.superconducting.qpu.base_quam as base_quam_mod
from quam_builder.architecture.superconducting.qpu import FixedFrequencyQuam
from quam_builder.builder.superconducting.modify_quam import add_qubit
from quam_builder.architecture.superconducting.components.twpa import TWPA
from quam_builder.architecture.superconducting.components.xy_drive import XYDriveMW


@pytest.fixture(autouse=True)
def compatible_quam_config(tmp_path, monkeypatch):
    """Use a qualibrate config that matches the installed quam package version."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(f"[quam]\nversion = {QuamConfig.version}\n")
    monkeypatch.setenv(CONFIG_PATH_ENV_NAME, str(config_file))
    get_quam_config.cache_clear()


@pytest.fixture
def machine() -> FixedFrequencyQuam:
    """A real machine with two qubits (q0 active, q1 inactive) and one TWPA."""
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    for qubit_id, base in (("q0", 1), ("q1", 3)):
        add_qubit(
            machine,
            qubit_id,
            {
                "xy": {"opx_output": f"#/ports/mw_outputs/con1/{base}/1"},
                "rr": {
                    "opx_output": f"#/ports/mw_outputs/con1/{base + 1}/1",
                    "opx_input": f"#/ports/mw_inputs/con1/{base + 1}/1",
                },
            },
        )
    machine.active_qubit_names = ["q0"]
    machine.twpas["twpa1"] = TWPA(
        id="twpa1", pump=XYDriveMW(opx_output="#/ports/mw_outputs/con1/7/1")
    )
    return machine


@pytest.fixture
def record_align(monkeypatch):
    """Capture every call to ``align`` (as element names) instead of emitting QUA."""
    calls = []
    monkeypatch.setattr(base_quam_mod, "align", lambda *names: calls.append(set(names)))
    return calls


def _channel_names(qubit):
    return {ch.name for ch in qubit.channels.values()}


def test_default_aligns_pump_with_active_qubits(machine, record_align):
    machine.twpa_keepalive()

    pump = machine.twpas["twpa1"].pump.name
    assert record_align == [{pump} | _channel_names(machine.qubits["q0"])]
    # inactive qubit must not be dragged into the align
    assert record_align[0].isdisjoint(_channel_names(machine.qubits["q1"]))


def test_explicit_qubits_include_all_given(machine, record_align):
    q0, q1 = machine.qubits["q0"], machine.qubits["q1"]
    machine.twpa_keepalive([q0, q1])

    pump = machine.twpas["twpa1"].pump.name
    assert record_align[0] == {pump} | _channel_names(q0) | _channel_names(q1)


def test_single_qubit_object(machine, record_align):
    q0 = machine.qubits["q0"]
    machine.twpa_keepalive(q0)  # a bare Qubit, not a list

    pump = machine.twpas["twpa1"].pump.name
    assert record_align[0] == {pump} | _channel_names(q0)


def test_skips_uninitialized_twpa(machine, record_align):
    machine.twpas["twpa1"].initialization = False
    machine.twpa_keepalive()

    assert record_align == []  # no initialized pumps -> no align emitted


def test_isolation_flag(machine, record_align):
    twpa = machine.twpas["twpa1"]
    twpa.isolation = XYDriveMW(opx_output="#/ports/mw_outputs/con1/8/1")

    machine.twpa_keepalive(isolation=False)
    assert twpa.isolation.name not in record_align[0]

    record_align.clear()
    machine.twpa_keepalive(isolation=True)
    assert twpa.isolation.name in record_align[0]
