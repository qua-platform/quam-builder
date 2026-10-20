"""End-to-end tests for superconducting QUAM construction using the wiring tools.

Tests the full workflow from instrument definition → connectivity setup →
wiring allocation → QUAM construction for superconducting qubit architectures
(OPX+/Octave, LF-FEM/MW-FEM, LF-FEM/Octave).

These tests exercise the interoperability with py-qua-tools (qualang-tools)
wiring infrastructure.
"""

import shutil
import tempfile

import pytest
from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from qualang_tools.wirer.wirer.channel_specs import mw_fem_spec, octave_spec

from quam_builder.architecture.superconducting.qpu import (
    FixedFrequencyQuam,
    FluxTunableQuam,
)
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.superconducting import build_quam as build_quam_sc


@pytest.fixture
def temp_dir():
    """Create and clean up a temporary directory for test artifacts."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


class TestSuperconductingOPXPlusOctave:
    """OPX+ with Octave: flux-tunable transmons (mirrors wiring_opxp_octave.py)."""

    @pytest.fixture
    def instruments(self):
        instruments = Instruments()
        instruments.add_opx_plus(controllers=[1, 2])
        instruments.add_octave(indices=1)
        return instruments

    @staticmethod
    def _make_connectivity(qubits, qubit_pairs, instruments):
        connectivity = Connectivity()
        connectivity.add_resonator_line(
            qubits=qubits,
            constraints=octave_spec(index=1, rf_out=1, rf_in=1),
        )
        connectivity.add_qubit_drive_lines(qubits=qubits)
        connectivity.add_qubit_flux_lines(qubits=qubits)
        connectivity.add_qubit_pair_flux_lines(qubit_pairs=qubit_pairs)
        allocate_wiring(connectivity, instruments)
        return connectivity

    def test_four_qubit_full_workflow(self, instruments, temp_dir):
        """Build a 4-qubit flux-tunable system with OPX+/Octave from scratch."""
        qubits = [1, 2, 3, 4]
        qubit_pairs = [(1, 2), (2, 3), (3, 4)]
        connectivity = self._make_connectivity(qubits, qubit_pairs, instruments)

        machine = FluxTunableQuam()
        build_quam_wiring(connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir)

        machine = FluxTunableQuam.load(temp_dir)
        build_quam_sc(machine, calibration_db_path=temp_dir, save=False)

        assert len(machine.qubits) == 4
        assert len(machine.qubit_pairs) == 3
        assert len(machine.active_qubit_names) == 4
        assert len(machine.active_qubit_pair_names) == 3

        for qid, qubit in machine.qubits.items():
            assert qubit.xy is not None, f"{qid} missing xy drive"
            assert qubit.resonator is not None, f"{qid} missing resonator"
            assert qubit.z is not None, f"{qid} missing flux line"
            assert len(qubit.xy.operations) > 0, f"{qid} xy has no pulses"
            assert len(qubit.resonator.operations) > 0, f"{qid} resonator has no pulses"

    def test_two_qubit_minimal(self, instruments, temp_dir):
        """Minimal 2-qubit setup to verify basic wiring + build."""
        qubits = [1, 2]
        qubit_pairs = [(1, 2)]
        connectivity = self._make_connectivity(qubits, qubit_pairs, instruments)

        machine = FluxTunableQuam()
        build_quam_wiring(connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir)

        machine = FluxTunableQuam.load(temp_dir)
        build_quam_sc(machine, calibration_db_path=temp_dir, save=False)

        assert len(machine.qubits) == 2
        assert len(machine.qubit_pairs) == 1
        assert machine.network["host"] == "127.0.0.1"
        assert machine.network["cluster_name"] == "test_cluster"

    def test_drive_only_no_flux_no_pairs(self, temp_dir):
        """Qubits with drive and resonator but no flux lines (fixed-frequency)."""
        instruments = Instruments()
        instruments.add_opx_plus(controllers=[1])
        instruments.add_octave(indices=1)

        qubits = [1, 2, 3]
        connectivity = Connectivity()
        connectivity.add_resonator_line(
            qubits=qubits,
            constraints=octave_spec(index=1, rf_out=1, rf_in=1),
        )
        connectivity.add_qubit_drive_lines(qubits=qubits)
        allocate_wiring(connectivity, instruments)

        machine = FixedFrequencyQuam()
        build_quam_wiring(connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir)

        machine = FixedFrequencyQuam.load(temp_dir)
        build_quam_sc(machine, calibration_db_path=temp_dir, save=False)

        assert len(machine.qubits) == 3
        assert len(machine.qubit_pairs) == 0
        for qid, qubit in machine.qubits.items():
            assert qubit.xy is not None, f"{qid} missing xy drive"
            assert qubit.resonator is not None, f"{qid} missing resonator"

    def test_config_generation_mwfem(self, temp_dir):
        """The built QUAM with MW-FEM must produce a valid QUA config dict.

        MW-FEM does not use Octave frequency converters (which require LO_frequency
        to be populated), so generate_config succeeds without extra calibration data.
        """
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1])
        instruments.add_lf_fem(controller=1, slots=[2])

        qubits = [1, 2]
        qubit_pairs = [(1, 2)]
        connectivity = Connectivity()
        connectivity.add_resonator_line(
            qubits=qubits,
            constraints=mw_fem_spec(con=1, slot=1, in_port=1, out_port=1),
        )
        connectivity.add_qubit_drive_lines(qubits=qubits)
        connectivity.add_qubit_flux_lines(qubits=qubits)
        connectivity.add_qubit_pair_flux_lines(qubit_pairs=qubit_pairs)
        allocate_wiring(connectivity, instruments)

        machine = FluxTunableQuam()
        build_quam_wiring(connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir)
        machine = FluxTunableQuam.load(temp_dir)
        build_quam_sc(machine, calibration_db_path=temp_dir, save=False)

        config = machine.generate_config()
        assert isinstance(config, dict)
        assert "controllers" in config
        assert "elements" in config
        assert "pulses" in config

    def test_wiring_structure_opxp_octave(self, instruments, temp_dir):
        """Verify wiring dict structure after OPX+/Octave allocation."""
        qubits = [1, 2]
        qubit_pairs = [(1, 2)]
        connectivity = self._make_connectivity(qubits, qubit_pairs, instruments)

        machine = FluxTunableQuam()
        build_quam_wiring(connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir)

        assert "qubits" in machine.wiring
        assert "qubit_pairs" in machine.wiring
        assert len(machine.wiring["qubits"]) == 2


class TestSuperconductingLFFEMMWFEM:
    """LF-FEM + MW-FEM: flux-tunable transmons (mirrors wiring_lffem_mwfem.py)."""

    @pytest.fixture
    def instruments(self):
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1, 2])
        instruments.add_lf_fem(controller=1, slots=[3, 5])
        return instruments

    def test_eight_qubit_two_feedlines(self, instruments, temp_dir):
        """8-qubit setup with two MW-FEM feedlines and individual drives."""
        qubits = [1, 2, 3, 4, 5, 6, 7, 8]
        qubit_pairs = [(qubits[i], qubits[i + 1]) for i in range(len(qubits) - 1)]

        q1to4_res_ch = mw_fem_spec(con=1, slot=1, in_port=1, out_port=1)
        q5to8_res_ch = mw_fem_spec(con=1, slot=2, in_port=1, out_port=1)
        q1to4_drive_ch = mw_fem_spec(con=1, slot=1, in_port=None, out_port=None)
        q5to8_drive_ch = mw_fem_spec(con=1, slot=2, in_port=None, out_port=4)

        connectivity = Connectivity()
        connectivity.add_resonator_line(qubits=qubits[:4], constraints=q1to4_res_ch)
        connectivity.add_resonator_line(qubits=qubits[4:], constraints=q5to8_res_ch)
        connectivity.add_qubit_drive_lines(qubits=qubits[:4], constraints=q1to4_drive_ch)
        for qubit in qubits[4:]:
            connectivity.add_qubit_drive_lines(qubits=qubit, constraints=q5to8_drive_ch)
            allocate_wiring(connectivity, instruments, block_used_channels=False)
        connectivity.add_qubit_flux_lines(qubits=qubits)
        connectivity.add_qubit_pair_flux_lines(qubit_pairs=qubit_pairs)
        allocate_wiring(connectivity, instruments)

        machine = FluxTunableQuam()
        build_quam_wiring(connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir)

        machine = FluxTunableQuam.load(temp_dir)
        build_quam_sc(machine, calibration_db_path=temp_dir, save=False)

        assert len(machine.qubits) == 8
        assert len(machine.qubit_pairs) == 7

        for qid, qubit in machine.qubits.items():
            assert qubit.xy is not None, f"{qid} missing xy drive"
            assert qubit.resonator is not None, f"{qid} missing resonator"
            assert qubit.z is not None, f"{qid} missing flux line"

    def test_four_qubit_mwfem(self, instruments, temp_dir):
        """4-qubit setup with single MW-FEM feedline."""
        qubits = [1, 2, 3, 4]
        qubit_pairs = [(1, 2), (2, 3), (3, 4)]

        connectivity = Connectivity()
        connectivity.add_resonator_line(
            qubits=qubits,
            constraints=mw_fem_spec(con=1, slot=1, in_port=1, out_port=1),
        )
        connectivity.add_qubit_drive_lines(qubits=qubits)
        connectivity.add_qubit_flux_lines(qubits=qubits)
        connectivity.add_qubit_pair_flux_lines(qubit_pairs=qubit_pairs)
        allocate_wiring(connectivity, instruments)

        machine = FluxTunableQuam()
        build_quam_wiring(connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir)
        machine = FluxTunableQuam.load(temp_dir)
        build_quam_sc(machine, calibration_db_path=temp_dir, save=False)

        assert len(machine.qubits) == 4
        assert len(machine.qubit_pairs) == 3

        config = machine.generate_config()
        assert isinstance(config, dict)
        assert "elements" in config


class TestSuperconductingLFFEMOctave:
    """LF-FEM + Octave (mirrors wiring_lffem_octave.py)."""

    def test_three_qubit_lffem_octave(self, temp_dir):
        """3-qubit LF-FEM + Octave with flux lines and tunable couplers."""
        instruments = Instruments()
        instruments.add_lf_fem(controller=1, slots=[1, 2])
        instruments.add_octave(indices=1)

        qubits = [1, 2, 3]
        qubit_pairs = [(1, 2), (2, 3)]

        connectivity = Connectivity()
        connectivity.add_resonator_line(
            qubits=qubits,
            constraints=octave_spec(index=1, rf_out=1, rf_in=1),
        )
        connectivity.add_qubit_drive_lines(qubits=qubits)
        connectivity.add_qubit_flux_lines(qubits=qubits)
        connectivity.add_qubit_pair_flux_lines(qubit_pairs=qubit_pairs)
        allocate_wiring(connectivity, instruments)

        machine = FluxTunableQuam()
        build_quam_wiring(connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir)
        machine = FluxTunableQuam.load(temp_dir)
        build_quam_sc(machine, calibration_db_path=temp_dir, save=False)

        assert len(machine.qubits) == 3
        assert len(machine.qubit_pairs) == 2

        for qid, qubit in machine.qubits.items():
            assert qubit.xy is not None
            assert qubit.resonator is not None
            assert qubit.z is not None
