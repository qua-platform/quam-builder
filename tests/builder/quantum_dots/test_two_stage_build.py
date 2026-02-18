"""Tests for two-stage QuAM build process.

Tests both Stage 1 (BaseQuamQD with quantum dots) and Stage 2
(LossDiVincenzoQuam with qubits), as well as the integration between them.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
from quam_builder.builder.quantum_dots.build_qpu_stage1 import _BaseQpuBuilder
from quam_builder.builder.quantum_dots.build_qpu_stage2 import _LDQubitBuilder
from quam_builder.builder.quantum_dots.build_quam import (
    build_base_quam,
    build_loss_divincenzo_quam,
    build_quam,
)


@pytest.fixture(autouse=True)
def _set_quam_state_path(tmp_path, monkeypatch):
    monkeypatch.setenv("QUAM_STATE_PATH", str(tmp_path / "quam_state"))


def _plunger_ports(qubit_id: str) -> dict:
    """Helper to create plunger gate wiring."""
    return {"opx_output": f"#/wiring/qubits/{qubit_id}/p/opx_output"}


def _barrier_ports(pair_id: str) -> dict:
    """Helper to create barrier gate wiring."""
    return {"opx_output": f"#/wiring/qubit_pairs/{pair_id}/b/opx_output"}


def _sensor_ports(sensor_id: str) -> dict:
    """Helper to create sensor gate wiring."""
    return {"opx_output": f"#/wiring/readout/{sensor_id}/s/opx_output"}


def _resonator_ports(sensor_id: str) -> dict:
    """Helper to create resonator wiring."""
    return {
        "opx_output": f"#/wiring/readout/{sensor_id}/r/opx_output",
        "opx_input": f"#/wiring/readout/{sensor_id}/r/opx_input",
    }


def _mw_drive_ports(qubit_id: str) -> dict:
    """Helper to create MW drive wiring."""
    return {"opx_output": f"#/wiring/qubits/{qubit_id}/xy/opx_output"}


def _iq_drive_ports(qubit_id: str) -> dict:
    """Helper to create IQ drive wiring."""
    return {
        "opx_output_I": f"#/wiring/qubits/{qubit_id}/xy/opx_output_I",
        "opx_output_Q": f"#/wiring/qubits/{qubit_id}/xy/opx_output_Q",
        "frequency_converter_up": f"#/wiring/qubits/{qubit_id}/xy/frequency_converter_up",
    }


class TestStage1Build:
    """Tests for Stage 1: BaseQuamQD builder."""

    def test_creates_quantum_dots_not_qubits(self):
        """Stage 1 should create quantum dots but NOT qubits."""
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1")},
                "q2": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2")},
            }
        }

        builder = _BaseQpuBuilder(machine)
        result = builder.build()

        # Should have quantum dots
        assert len(result.quantum_dots) == 2
        assert "virtual_dot_1" in result.quantum_dots
        assert "virtual_dot_2" in result.quantum_dots

        # BaseQuamQD stage should not register qubits
        assert not getattr(result, "qubits", None)

    def test_qdac_channels_assigned(self):
        """Stage 1 should assign QDAC channels from wiring."""
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: {
                        **_plunger_ports("q1"),
                        "qdac_channel": 5,
                    }
                },
            }
        }

        builder = _BaseQpuBuilder(machine)
        result = builder.build()

        # Find the plunger channel and verify QDAC assignment
        plunger_channel = result.physical_channels["plunger_1"]
        assert hasattr(plunger_channel, "qdac_channel")
        assert plunger_channel.qdac_channel == 5

    def test_identity_compensation_matrix(self):
        """Stage 1 should use identity compensation matrix."""
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1")},
                "q2": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2")},
            }
        }

        builder = _BaseQpuBuilder(machine)
        result = builder.build()

        # Verify identity matrix is used
        virtual_gate_set = result.virtual_gate_sets["main_qpu"]
        matrix = virtual_gate_set.layers[0].matrix

        # Identity matrix for 2 channels
        assert matrix == [[1.0, 0.0], [0.0, 1.0]]

    def test_creates_quantum_dot_pairs(self):
        """Stage 1 should create quantum dot pairs with barriers."""
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1")},
                "q2": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2")},
            },
            "qubit_pairs": {
                "q1_q2": {WiringLineType.BARRIER_GATE.value: _barrier_ports("q1_q2")},
            },
        }

        builder = _BaseQpuBuilder(machine)
        result = builder.build()

        # Should have quantum dot pair
        assert len(result.quantum_dot_pairs) == 1
        assert "virtual_dot_1_virtual_dot_2_pair" in result.quantum_dot_pairs

        pair = result.quantum_dot_pairs["virtual_dot_1_virtual_dot_2_pair"]
        assert len(pair.quantum_dots) == 2
        assert pair.barrier_gate is not None

    def test_creates_sensor_dots_with_resonators(self):
        """Stage 1 should create sensor dots with resonators."""
        machine = BaseQuamQD()
        machine.wiring = {
            "readout": {
                "s1": {
                    WiringLineType.SENSOR_GATE.value: _sensor_ports("s1"),
                    WiringLineType.RF_RESONATOR.value: _resonator_ports("s1"),
                },
            },
            "qubits": {
                "q1": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1")},
            },
        }

        builder = _BaseQpuBuilder(machine)
        result = builder.build()

        # Should have sensor dot
        assert len(result.sensor_dots) == 1
        assert "virtual_sensor_1" in result.sensor_dots

        sensor = result.sensor_dots["virtual_sensor_1"]
        assert sensor.readout_resonator is not None
        assert sensor.readout_resonator.id == "readout_resonator_1"

    def test_does_not_create_xy_drives(self):
        """Stage 1 should NOT create XY drive channels."""
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
                },
            }
        }

        builder = _BaseQpuBuilder(machine)
        result = builder.build()

        # XY drives should NOT be in the quantum dot
        quantum_dot = result.quantum_dots["virtual_dot_1"]
        # BaseQuamQD quantum dots don't have XY channels at this stage
        assert not hasattr(quantum_dot, "xy_channel")


class TestStage2Build:
    """Tests for Stage 2: LossDiVincenzoQuam builder."""

    def test_converts_base_to_ld_quam(self):
        """Stage 2 should convert BaseQuamQD to LossDiVincenzoQuam."""
        # Setup Stage 1 machine
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
                },
            }
        }
        builder1 = _BaseQpuBuilder(machine)
        machine = builder1.build()

        # Run Stage 2
        builder2 = _LDQubitBuilder(machine)
        result = builder2.build()

        # Should be converted to LossDiVincenzoQuam
        assert isinstance(result, LossDiVincenzoQuam)
        assert hasattr(result, "qubits")
        assert hasattr(result, "qubit_pairs")

    def test_implicit_mapping(self):
        """Stage 2 should map q1 → virtual_dot_1 implicitly."""
        # Setup Stage 1 machine
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
            }
        }
        builder1 = _BaseQpuBuilder(machine)
        machine = builder1.build()

        # Run Stage 2 with implicit mapping
        builder2 = _LDQubitBuilder(machine, implicit_mapping=True)
        result = builder2.build()

        # Verify qubits are mapped correctly
        assert "q1" in result.qubits
        assert "q2" in result.qubits

        # Verify qubits reference the correct quantum dots
        assert result.qubits["q1"].quantum_dot.id == "virtual_dot_1"
        assert result.qubits["q2"].quantum_dot.id == "virtual_dot_2"

    def test_loads_from_file(self):
        """Stage 2 should work with BaseQuamQD loaded from file."""
        with TemporaryDirectory() as tmpdir:
            # Setup and save Stage 1 machine
            machine = BaseQuamQD()
            machine.wiring = {
                "qubits": {
                    "q1": {
                        WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                        WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
                    },
                }
            }
            builder1 = _BaseQpuBuilder(machine)
            machine = builder1.build()

            # Save to file
            save_path = Path(tmpdir) / "base_quam"
            machine.save(str(save_path))

            # Run Stage 2 by loading from file
            builder2 = _LDQubitBuilder(str(save_path))
            result = builder2.build()

            # Should have loaded and created qubits
            assert isinstance(result, LossDiVincenzoQuam)
            assert "q1" in result.qubits

    def test_creates_xy_drives(self):
        """Stage 2 should create XY drive channels for qubits."""
        # Setup Stage 1 machine
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
                },
            }
        }
        builder1 = _BaseQpuBuilder(machine)
        machine = builder1.build()

        # Run Stage 2
        builder2 = _LDQubitBuilder(machine)
        result = builder2.build()

        # Verify XY drive is created
        assert "q1" in result.qubits
        qubit = result.qubits["q1"]
        assert getattr(qubit, "xy_channel", None) is not None
        assert qubit.xy_channel.id == "q1_xy"

    def test_creates_qubit_pairs(self):
        """Stage 2 should create qubit pairs from quantum dot pairs."""
        # Setup Stage 1 machine
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
        builder1 = _BaseQpuBuilder(machine)
        machine = builder1.build()

        # Run Stage 2
        builder2 = _LDQubitBuilder(machine)
        result = builder2.build()

        # Verify qubit pair is created
        assert "q1_q2" in result.qubit_pairs
        pair = result.qubit_pairs["q1_q2"]
        assert pair.qubit_control.id == "virtual_dot_1"
        assert pair.qubit_target.id == "virtual_dot_2"

    def test_compensation_matrix_preserved(self):
        """Stage 2 should preserve compensation matrix from Stage 1."""
        # Setup Stage 1 machine
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1")},
                "q2": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2")},
            }
        }
        builder1 = _BaseQpuBuilder(machine)
        machine = builder1.build()

        # Get original matrix
        original_matrix = [row[:] for row in machine.virtual_gate_sets["main_qpu"].layers[0].matrix]

        # Run Stage 2
        builder2 = _LDQubitBuilder(machine)
        result = builder2.build()

        # Verify matrix is preserved
        new_matrix = result.virtual_gate_sets["main_qpu"].layers[0].matrix
        assert new_matrix == original_matrix

    def test_raises_if_no_quantum_dots(self):
        """Stage 2 should raise error if no quantum dots found."""
        # Create empty BaseQuamQD
        machine = BaseQuamQD()

        # Should raise error
        builder = _LDQubitBuilder(machine)
        with pytest.raises(ValueError, match="No quantum dots found"):
            builder.build()


class TestIntegration:
    """Integration tests for the full two-stage flow."""

    def test_full_two_stage_flow(self):
        """Test complete two-stage build process."""
        # Create initial machine with wiring
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
                },
                "q2": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2"),
                    WiringLineType.DRIVE.value: _iq_drive_ports("q2"),
                },
            },
            "qubit_pairs": {
                "q1_q2": {WiringLineType.BARRIER_GATE.value: _barrier_ports("q1_q2")},
            },
            "readout": {
                "s1": {
                    WiringLineType.SENSOR_GATE.value: _sensor_ports("s1"),
                    WiringLineType.RF_RESONATOR.value: _resonator_ports("s1"),
                },
            },
        }

        # Stage 1: Build BaseQuamQD
        builder1 = _BaseQpuBuilder(machine)
        machine = builder1.build()

        # Verify Stage 1 results
        assert isinstance(machine, BaseQuamQD)
        assert len(machine.quantum_dots) == 2
        assert len(machine.quantum_dot_pairs) == 1
        assert len(machine.sensor_dots) == 1
        assert not hasattr(machine, "qubits")

        # Stage 2: Convert to LossDiVincenzoQuam
        builder2 = _LDQubitBuilder(machine)
        machine = builder2.build()

        # Verify Stage 2 results
        assert isinstance(machine, LossDiVincenzoQuam)
        assert len(machine.qubits) == 2
        assert len(machine.qubit_pairs) == 1
        # Quantum dots should still exist
        assert len(machine.quantum_dots) == 2
        assert len(machine.sensor_dots) == 1

    def test_save_and_load_between_stages(self):
        """Test saving after Stage 1 and loading for Stage 2."""
        with TemporaryDirectory() as tmpdir:
            # Create and build Stage 1
            machine = BaseQuamQD()
            machine.wiring = {
                "qubits": {
                    "q1": {
                        WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                        WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
                    },
                }
            }
            builder1 = _BaseQpuBuilder(machine)
            machine = builder1.build()

            # Save Stage 1 result
            save_path = Path(tmpdir) / "base_quam"
            machine.save(str(save_path))

            # Load and build Stage 2
            builder2 = _LDQubitBuilder(str(save_path))
            result = builder2.build()

            # Verify everything works
            assert isinstance(result, LossDiVincenzoQuam)
            assert "q1" in result.qubits
            assert "virtual_dot_1" in result.quantum_dots


class TestHighLevelAPI:
    """Tests for high-level build functions."""

    def test_build_base_quam_function(self):
        """Test build_base_quam() convenience function."""
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1")},
            }
        }

        result = build_base_quam(machine, save=False)

        assert isinstance(result, BaseQuamQD)
        assert len(result.quantum_dots) == 1
        assert not hasattr(result, "qubits")

    def test_build_loss_divincenzo_quam_function(self):
        """Test build_loss_divincenzo_quam() convenience function."""
        # First create BaseQuamQD
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
                },
            }
        }
        machine = build_base_quam(machine, save=False)

        # Then convert to LossDiVincenzoQuam
        result = build_loss_divincenzo_quam(machine, save=False)

        assert isinstance(result, LossDiVincenzoQuam)
        assert "q1" in result.qubits

    def test_build_quam_convenience_wrapper(self):
        """Test build_quam() single-call wrapper."""
        machine = BaseQuamQD()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                    WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
                },
            }
        }

        result = build_quam(machine, save=False)

        # Should execute both stages
        assert isinstance(result, LossDiVincenzoQuam)
        assert "q1" in result.qubits
        assert "virtual_dot_1" in result.quantum_dots
