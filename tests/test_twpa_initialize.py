"""Tests for ``TWPA.initialize`` program scoping."""

import pytest
from qm.qua import program

from quam.config.models.quam import QuamConfig
from quam.config.resolvers import get_quam_config
from quam.config.vars import CONFIG_PATH_ENV_NAME
from quam.components.ports import FEMPortsContainer

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
    if hasattr(get_quam_config, "cache_clear"):
        get_quam_config.cache_clear()


@pytest.fixture
def machine() -> FixedFrequencyQuam:
    """A machine with one TWPA configured for pump initialization."""
    machine = FixedFrequencyQuam(ports=FEMPortsContainer())
    add_qubit(
        machine,
        "q0",
        {
            "xy": {"opx_output": "#/ports/mw_outputs/con1/1/1"},
            "rr": {
                "opx_output": "#/ports/mw_outputs/con1/2/1",
                "opx_input": "#/ports/mw_inputs/con1/2/1",
            },
        },
    )
    machine.active_qubit_names = ["q0"]
    machine.twpas["twpa1"] = TWPA(
        id="twpa1",
        pump=XYDriveMW(opx_output="#/ports/mw_outputs/con1/7/1"),
        pump_amplitude=0.5,
    )
    return machine


@pytest.fixture
def record_pump_play(machine, monkeypatch):
    """Record every call to the TWPA pump ``play`` method."""
    plays = []

    def record_play(*args, **kwargs):
        plays.append(1)

    monkeypatch.setattr(machine.twpas["twpa1"].pump, "play", record_play)
    return plays


def test_twpa_initialize_once_per_program(machine, record_pump_play):
    """Two initialize_qpu calls in one program block emit TWPA init only once."""
    with program():
        machine.initialize_qpu()
        machine.initialize_qpu()

    assert len(record_pump_play) == 1


def test_twpa_initialize_in_each_program(machine, record_pump_play):
    """Each new program block re-initializes the TWPA pump."""
    with program():
        machine.initialize_qpu()
    assert len(record_pump_play) == 1

    with program():
        machine.initialize_qpu()
    assert len(record_pump_play) == 2
