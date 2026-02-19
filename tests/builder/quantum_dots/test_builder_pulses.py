"""End-to-end tests for quantum dot pulse generation.

Builds a real machine from the wiring pipeline and verifies that
default pulses are correctly attached to qubits and resonators.
"""

# pylint: disable=no-member

import shutil
import tempfile

import pytest
from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring

from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_quam as build_quam_qd


@pytest.fixture
def machine_with_pulses():
    """Build a real LossDiVincenzoQuam with XY drives and pulses via the full pipeline."""
    instruments = Instruments()
    instruments.add_mw_fem(controller=1, slots=[1])
    instruments.add_lf_fem(controller=1, slots=[2, 3])

    connectivity = Connectivity()
    connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False, use_mw_fem=False)
    connectivity.add_quantum_dots(
        quantum_dots=[1, 2],
        add_drive_lines=True,
        use_mw_fem=True,
        shared_drive_line=True,
    )
    connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2)])
    allocate_wiring(connectivity, instruments)

    tmp = tempfile.mkdtemp()
    machine = BaseQuamQD()
    machine = build_quam_wiring(
        connectivity,
        host_ip="127.0.0.1",
        cluster_name="test_cluster",
        quam_instance=machine,
        path=tmp,
    )
    machine = build_quam_qd(
        machine,
        calibration_db_path=tmp,
        qubit_pair_sensor_map={"q1_q2": ["sensor_1"]},
        connect_qdac=False,
        save=False,
    )
    yield machine
    shutil.rmtree(tmp)


class TestAddDefaultLDVQubitPulses:
    """Tests for default pulse generation on real qubits from the builder pipeline."""

    def test_xy_pulses_present_on_qubits(self, machine_with_pulses):
        """Verify all expected XY pulses are added to qubits with XY channels."""
        expected_pulses = ["x180", "x90", "y180", "y90", "-x90", "-y90"]

        for qubit_name, qubit in machine_with_pulses.qubits.items():
            if qubit.xy_channel is None:
                continue
            for pulse_name in expected_pulses:
                assert (
                    pulse_name in qubit.xy_channel.operations
                ), f"Pulse {pulse_name} missing from qubit {qubit_name}"

    def test_xy_pulse_properties(self, machine_with_pulses):
        """Verify x180 and y90 pulse properties on a real qubit."""
        qubit = next(q for q in machine_with_pulses.qubits.values() if q.xy_channel is not None)

        x180 = qubit.xy_channel.operations["x180"]
        assert x180.length == 1000
        assert x180.amplitude == 0.2
        assert x180.axis_angle == pytest.approx(0.0)

        y90 = qubit.xy_channel.operations["y90"]
        assert y90.amplitude == 0.1
        assert y90.axis_angle == pytest.approx(1.5707963, rel=1e-5)

    def test_readout_pulse_present_on_resonators(self, machine_with_pulses):
        """Verify readout pulse is added to sensor dot resonators."""
        for qubit in machine_with_pulses.qubits.values():
            if hasattr(qubit, "resonator") and qubit.resonator is not None:
                assert "readout" in qubit.resonator.operations

    def test_six_xy_operations_per_qubit(self, machine_with_pulses):
        """Verify each qubit with an XY channel has exactly 6 default operations."""
        for qubit in machine_with_pulses.qubits.values():
            if qubit.xy_channel is not None:
                assert len(qubit.xy_channel.operations) == 6
