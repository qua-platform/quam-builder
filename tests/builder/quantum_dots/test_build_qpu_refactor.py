import pytest

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType

from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qpu.loss_divincenzo_quam import (
    LossDiVincenzoQuam,
)
from quam_builder.builder.qop_connectivity.channel_ports import mw_out_channel_ports
from quam_builder.builder.quantum_dots.build_qpu import DEFAULT_GATE_SET_ID, _QpuBuilder


def _mw_drive_ports() -> dict:
    return {mw_out_channel_ports[0]: "#/ports/con1/1"}


def _iq_drive_ports() -> dict:
    return {
        "opx_output_I": "#/ports/con1/2",
        "opx_output_Q": "#/ports/con1/3",
        "frequency_converter_up": "#/ports/con1/4",
    }


def _plunger_ports(qubit_id: str) -> dict:
    return {"opx_output": f"#/wiring/qubits/{qubit_id}/p/opx_output"}


class TestQpuBuilderValidation:
    def test_missing_drive_ports_raise(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: {"unexpected": "value"},
                }
            }
        }

        with pytest.raises(ValueError, match="incomplete"):
            _QpuBuilder(machine).build()

    def test_missing_resonator_for_sensor_raises(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "readout": {
                "s1": {WiringLineType.SENSOR_GATE.value: {"opx_output": "#/ports/con1/8"}}
            },
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                }
            },
        }

        with pytest.raises(ValueError, match="Missing resonator wiring"):
            _QpuBuilder(machine).build()


class TestQpuBuilderBehavior:
    def test_element_aliases_register_sensor_dot(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "sensor_dots": {
                "s1": {
                    WiringLineType.SENSOR_GATE.value: {"opx_output": "#/ports/con1/8"},
                    WiringLineType.RF_RESONATOR.value: {
                        "opx_output": "#/ports/con1/9",
                        "opx_input": "#/ports/con1/10",
                    },
                }
            },
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                }
            },
        }

        builder = _QpuBuilder(machine)
        builder.build()

        assert machine.active_sensor_dot_names == ["virtual_sensor_1"]
        assert "virtual_sensor_1" in machine.sensor_dots

    def test_qubit_ordering_is_deterministic(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "qubits": {
                "q2": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _iq_drive_ports(),
                },
            }
        }

        builder = _QpuBuilder(machine)
        builder.build()

        assert machine.active_qubit_names == ["q1", "q2"]
        assert builder.assembly.plunger_virtual_names["plunger_1"] == "virtual_dot_1"
        assert builder.assembly.plunger_virtual_names["plunger_2"] == "virtual_dot_2"

    def test_barrier_virtual_mapping_used_for_pairs(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
                "q2": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
            },
            "qubit_pairs": {
                "q1_q2": {
                    WiringLineType.BARRIER_GATE.value: {
                        "opx_output": "#/wiring/qubit_pairs/q1_q2/b/opx_output"
                    }
                }
            },
        }

        builder = _QpuBuilder(machine)
        builder.build()

        qd_pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert qd_pair.barrier_gate.id == "virtual_barrier_1"
        assert machine.active_qubit_pair_names == ["q1_q2"]
        assert DEFAULT_GATE_SET_ID in machine.virtual_gate_sets

    def test_qubit_pair_hyphenated_id_converts(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
                "q2": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
            },
            "qubit_pairs": {
                "q1-2": {
                    WiringLineType.BARRIER_GATE.value: {
                        "opx_output": "#/wiring/qubit_pairs/q1-2/b/opx_output"
                    }
                }
            },
        }

        builder = _QpuBuilder(machine)
        builder.build()

        assert "q1_q2" in machine.active_qubit_pair_names
        assert "q1_q2" in machine.qubit_pairs

    def test_qubit_pair_sensor_mapping_applied(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "readout": {
                "s1": {
                    WiringLineType.SENSOR_GATE.value: {"opx_output": "#/ports/con1/8"},
                    WiringLineType.RF_RESONATOR.value: {
                        "opx_output": "#/ports/con1/9",
                        "opx_input": "#/ports/con1/10",
                    },
                },
                "s2": {
                    WiringLineType.SENSOR_GATE.value: {"opx_output": "#/ports/con1/11"},
                    WiringLineType.RF_RESONATOR.value: {
                        "opx_output": "#/ports/con1/12",
                        "opx_input": "#/ports/con1/13",
                    },
                },
            },
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
                "q2": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
            },
            "qubit_pairs": {
                "q1_q2": {
                    WiringLineType.BARRIER_GATE.value: {
                        "opx_output": "#/wiring/qubit_pairs/q1_q2/b/opx_output"
                    }
                }
            },
        }

        builder = _QpuBuilder(
            machine,
            qubit_pair_sensor_map={"q1_q2": ["virtual_sensor_2"]},
        )
        builder.build()

        qd_pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        sensor_ids = {s.id for s in qd_pair.sensor_dots}
        assert sensor_ids == {"virtual_sensor_2"}

    def test_qubit_pair_sensor_mapping_aliases(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "readout": {
                "s1": {
                    WiringLineType.SENSOR_GATE.value: {"opx_output": "#/ports/con1/8"},
                    WiringLineType.RF_RESONATOR.value: {
                        "opx_output": "#/ports/con1/9",
                        "opx_input": "#/ports/con1/10",
                    },
                },
                "s2": {
                    WiringLineType.SENSOR_GATE.value: {"opx_output": "#/ports/con1/11"},
                    WiringLineType.RF_RESONATOR.value: {
                        "opx_output": "#/ports/con1/12",
                        "opx_input": "#/ports/con1/13",
                    },
                },
            },
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
                "q2": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
            },
            "qubit_pairs": {
                "q1_q2": {
                    WiringLineType.BARRIER_GATE.value: {
                        "opx_output": "#/wiring/qubit_pairs/q1_q2/b/opx_output"
                    }
                }
            },
        }

        builder = _QpuBuilder(
            machine,
            qubit_pair_sensor_map={"q1_q2": ["s2", "sensor_1"]},
        )
        builder.build()

        qd_pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        sensor_ids = {s.id for s in qd_pair.sensor_dots}
        assert sensor_ids == {"virtual_sensor_1", "virtual_sensor_2"}

    def test_qubit_pair_sensor_mapping_empty_warns(self, caplog):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
            }
        }

        builder = _QpuBuilder(machine, qubit_pair_sensor_map={})
        with pytest.warns(UserWarning, match="qubit_pair_sensor_map is an empty dict"):
            builder.build()

    def test_qubit_pair_sensor_mapping_non_dict_raises(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports(),
                },
            }
        }

        with pytest.raises(ValueError, match="must be a dict mapping pair ids to sensor lists"):
            _QpuBuilder(machine, qubit_pair_sensor_map="bad").build()
