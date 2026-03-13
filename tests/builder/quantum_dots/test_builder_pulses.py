"""End-to-end tests for quantum dot pulse generation.

Builds real machines from the wiring pipeline and verifies that default pulses
are correctly attached to qubits and resonators for each XY drive type.
"""

# pylint: disable=no-member

import shutil
import tempfile

import pytest
from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring

from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ, XYDriveMW
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_base_quam, build_loss_divincenzo_quam
from quam_builder.builder.quantum_dots import build_quam as build_quam_qd


@pytest.fixture
def machine_with_iq_pulses():
    """Build a LossDiVincenzoQuam with XYDriveIQ channels via manual wiring injection.

    The standard QD pipeline never produces IQ drive wiring through allocate_wiring
    (all QD drives produce single-output MW-type ports). XYDriveIQ channels require
    explicit injection via xy_drive_wiring in build_loss_divincenzo_quam.
    """
    instruments = Instruments()
    instruments.add_mw_fem(controller=1, slots=[1])
    instruments.add_lf_fem(controller=1, slots=[2, 3])

    connectivity = Connectivity()
    connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False, use_mw_fem=False)
    connectivity.add_quantum_dots(
        quantum_dots=[1, 2],
        add_drive_lines=False,  # No drive lines allocated — injected manually below
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
    machine = build_base_quam(machine, calibration_db_path=tmp, connect_qdac=False, save=False)

    # Inject IQ drive wiring explicitly — standard QD pipeline never produces IQ wiring
    xy_drive_wiring = {
        "q1": {
            "type": "IQ",
            "wiring_path": "#/wiring/qubits/q1/drive",
            "intermediate_frequency": 500e6,
        },
        "q2": {
            "type": "IQ",
            "wiring_path": "#/wiring/qubits/q2/drive",
            "intermediate_frequency": 500e6,
        },
    }
    machine = build_loss_divincenzo_quam(
        machine,
        xy_drive_wiring=xy_drive_wiring,
        qubit_pair_sensor_map={"q1_q2": ["sensor_1"]},
        save=False,
    )
    yield machine
    shutil.rmtree(tmp)


@pytest.fixture
def machine_with_mw_pulses():
    """Build a LossDiVincenzoQuam with XYDriveMW channels via MW FEM."""
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


class TestAddDefaultLDVQubitPulsesIQ:
    """E2E pulse tests using XYDriveIQ (OPX+/Octave pipeline)."""

    def test_xy_drive_type_is_iq(self, machine_with_iq_pulses):
        for qubit in machine_with_iq_pulses.qubits.values():
            if qubit.xy is not None:
                assert isinstance(
                    qubit.xy, XYDriveIQ
                ), f"Expected XYDriveIQ, got {type(qubit.xy).__name__}"

    def test_gaussian_pulse_present_on_qubits(self, machine_with_iq_pulses):
        for qubit_name, qubit in machine_with_iq_pulses.qubits.items():
            if qubit.xy is None:
                continue
            assert (
                "gaussian" in qubit.xy.operations
            ), f"Pulse 'gaussian' missing from qubit {qubit_name}"

    def test_gaussian_pulse_properties(self, machine_with_iq_pulses):
        qubit = next(q for q in machine_with_iq_pulses.qubits.values() if q.xy is not None)

        gaussian = qubit.xy.operations["gaussian"]
        assert gaussian.length == 1000
        assert gaussian.amplitude == 0.2
        assert gaussian.axis_angle == pytest.approx(0.0)

    def test_readout_pulse_present_on_resonators(self, machine_with_iq_pulses):
        for qubit in machine_with_iq_pulses.qubits.values():
            if hasattr(qubit, "resonator") and qubit.resonator is not None:
                assert "readout" in qubit.resonator.operations

    def test_one_xy_operation_per_qubit(self, machine_with_iq_pulses):
        for qubit in machine_with_iq_pulses.qubits.values():
            if qubit.xy is not None:
                assert len(qubit.xy.operations) == 1


class TestAddDefaultLDVQubitPulsesMW:
    """E2E pulse tests using XYDriveMW (MW FEM pipeline)."""

    def test_xy_drive_type_is_mw(self, machine_with_mw_pulses):
        for qubit in machine_with_mw_pulses.qubits.values():
            if qubit.xy is not None:
                assert isinstance(
                    qubit.xy, XYDriveMW
                ), f"Expected XYDriveMW, got {type(qubit.xy).__name__}"

    def test_gaussian_pulse_present_on_qubits(self, machine_with_mw_pulses):
        for qubit_name, qubit in machine_with_mw_pulses.qubits.items():
            if qubit.xy is None:
                continue
            assert (
                "gaussian" in qubit.xy.operations
            ), f"Pulse 'gaussian' missing from qubit {qubit_name}"

    def test_gaussian_pulse_properties(self, machine_with_mw_pulses):
        qubit = next(q for q in machine_with_mw_pulses.qubits.values() if q.xy is not None)

        gaussian = qubit.xy.operations["gaussian"]
        assert gaussian.length == 1000
        assert gaussian.amplitude == 0.2
        assert gaussian.axis_angle == pytest.approx(0.0)

    def test_readout_pulse_present_on_resonators(self, machine_with_mw_pulses):
        for qubit in machine_with_mw_pulses.qubits.values():
            if hasattr(qubit, "resonator") and qubit.resonator is not None:
                assert "readout" in qubit.resonator.operations

    def test_one_xy_operation_per_qubit(self, machine_with_mw_pulses):
        for qubit in machine_with_mw_pulses.qubits.values():
            if qubit.xy is not None:
                assert len(qubit.xy.operations) == 1
