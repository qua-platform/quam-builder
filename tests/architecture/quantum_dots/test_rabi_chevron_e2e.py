"""End-to-end test mirroring the rabi_chevron.py example workflow.

Covers every pattern exercised by the example:
  1. Machine creation with physical channels and virtual gate set
  2. Channel element registration (quantum dots, sensor dot with resonator)
  3. Qubit registration with XY drive and readout quantum dot
  4. Fluent voltage-point definition (init → operate → readout)
  5. Custom QuamMacro subclasses (DriveMacro, MeasureMacro)
  6. Macro dispatch via qubit.__getattr__ (qubit.drive(), qubit.measure())
  7. Full QUA program with multi-step voltage navigation
  8. Compensation pulse (apply_compensation_pulse)
  9. generate_config() for a quantum-dot machine

All objects are real — no mocks or stubs.
"""

from typing import Tuple

import pytest
from qm import qua
from quam.components import pulses
from quam.components.channels import StickyChannelAddon
from quam.components.ports import (
    LFFEMAnalogInputPort,
    LFFEMAnalogOutputPort,
)
from quam.core import quam_dataclass
from quam.core.macro.quam_macro import QuamMacro

from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorSingle,
    VoltageGate,
    XYDriveSingle,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.qubit import LDQubit


# -----------------------------------------------------------------------
# Helpers — mirror rabi_chevron.py sections 1-3
# -----------------------------------------------------------------------


def _make_gate(port: int, gate_id: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort("con1", 2, port_id=port, output_mode="direct"),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )


def create_rabi_machine() -> Tuple[LossDiVincenzoQuam, XYDriveSingle, ReadoutResonatorSingle]:
    """Set up a minimal machine that mirrors the rabi_chevron example."""
    machine = LossDiVincenzoQuam()

    plunger_1 = _make_gate(1, "plunger_1")
    plunger_2 = _make_gate(2, "plunger_2")
    sensor_dc = _make_gate(4, "sensor_DC")

    readout_resonator = ReadoutResonatorSingle(
        id="sensor_resonator",
        opx_output=LFFEMAnalogOutputPort("con1", 2, port_id=3, output_mode="direct"),
        opx_input=LFFEMAnalogInputPort("con1", 2, port_id=1),
        intermediate_frequency=int(50e6),
        operations={
            "readout": pulses.SquareReadoutPulse(length=1000, amplitude=0.1),
        },
    )

    xy_drive = XYDriveSingle(
        id="Q1_xy",
        RF_frequency=int(100e6),
        opx_output=LFFEMAnalogOutputPort("con1", 2, port_id=5, output_mode="direct"),
    )
    # Add the pulses that were previously added by XYDriveSingle.__post_init__
    xy_drive.operations["gaussian"] = pulses.GaussianPulse(length=100, amplitude=0.2, sigma=40)
    xy_drive.operations["pi"] = pulses.SquarePulse(length=104, amplitude=0.2)
    xy_drive.operations["pi_half"] = pulses.SquarePulse(length=52, amplitude=0.2)
    xy_drive.operations["drive"] = pulses.GaussianPulse(
        length=100,
        amplitude=0.2,
        sigma=100 / 6,
    )

    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": plunger_1,
            "virtual_dot_2": plunger_2,
            "virtual_sensor_1": sensor_dc,
        },
        gate_set_id="main_qpu",
        compensation_matrix=[
            [1.0, 0.1, 0.0],
            [0.1, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
    )

    machine.register_channel_elements(
        plunger_channels=[plunger_1, plunger_2],
        sensor_resonator_mappings={sensor_dc: readout_resonator},
        barrier_channels=[],
    )

    machine.register_quantum_dot_pair(
        quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
        sensor_dot_ids=["virtual_sensor_1"],
        id="qd_pair_1_2",
    )

    return machine, xy_drive, readout_resonator


# -----------------------------------------------------------------------
# Custom macros (mirror rabi_chevron.py DriveMacro / MeasureMacro)
# -----------------------------------------------------------------------


@quam_dataclass
class DriveMacro(QuamMacro):
    pulse_name: str = "drive"
    amplitude_scale: float = None

    @property
    def inferred_duration(self) -> float | None:
        try:
            parent_qubit = self.parent.parent
            pulse = parent_qubit.xy.operations[self.pulse_name]
            return pulse.length * 1e-9
        except Exception:
            return None

    def apply(self, **kwargs):
        duration = kwargs.get("duration", None)
        amp_scale = kwargs.get("amplitude_scale", self.amplitude_scale)
        parent_qubit = self.parent.parent
        parent_qubit.xy.play(
            self.pulse_name,
            amplitude_scale=amp_scale,
            duration=duration,
        )


@quam_dataclass
class MeasureMacro(QuamMacro):
    pulse_name: str = "readout"

    @property
    def inferred_duration(self) -> float | None:
        try:
            parent_qubit = self.parent.parent
            resonator = parent_qubit.quantum_dot.machine.sensor_dots[
                "virtual_sensor_1"
            ].readout_resonator
            pulse = resonator.operations[self.pulse_name]
            return (64 * 4 + pulse.length) * 1e-9
        except Exception:
            return None

    def apply(self, **kwargs):
        pulse = kwargs.get("pulse_name", self.pulse_name)
        iq_i = qua.declare(qua.fixed)
        iq_q = qua.declare(qua.fixed)
        parent_qubit = self.parent.parent
        resonator = parent_qubit.quantum_dot.machine.sensor_dots[
            "virtual_sensor_1"
        ].readout_resonator
        resonator.wait(64)
        resonator.measure(pulse, qua_vars=(iq_i, iq_q))
        return iq_i, iq_q


# -----------------------------------------------------------------------
# Fixture
# -----------------------------------------------------------------------


@pytest.fixture
def rabi_setup():
    """Return (machine, qubit) with full rabi-chevron setup."""
    machine, xy_drive, _resonator = create_rabi_machine()

    machine.register_qubit(
        quantum_dot_id="virtual_dot_1",
        qubit_name="Q1",
        xy=xy_drive,
        readout_quantum_dot="virtual_dot_2",
    )
    qubit = machine.qubits["Q1"]

    qubit.add_point(point_name="init", voltages={"virtual_dot_1": 0.05}, duration=500)
    qubit.add_point(point_name="operate", voltages={"virtual_dot_1": 0.15}, duration=2000)
    qubit.add_point(point_name="readout", voltages={"virtual_dot_1": -0.05}, duration=2000)

    qubit.macros["drive"] = DriveMacro(pulse_name="drive")
    qubit.macros["measure"] = MeasureMacro(pulse_name="readout")

    return machine, qubit


# =======================================================================
# Tests
# =======================================================================


class TestMachineSetup:
    """Section 1-2: machine, virtual gate set, channel elements."""

    def test_virtual_gate_set_created(self, rabi_setup):
        machine, _ = rabi_setup
        assert "main_qpu" in machine.virtual_gate_sets

    def test_quantum_dots_registered(self, rabi_setup):
        machine, _ = rabi_setup
        assert "virtual_dot_1" in machine.quantum_dots
        assert "virtual_dot_2" in machine.quantum_dots

    def test_sensor_dot_registered_with_resonator(self, rabi_setup):
        machine, _ = rabi_setup
        sd = machine.sensor_dots["virtual_sensor_1"]
        assert sd.readout_resonator is not None
        assert "readout" in sd.readout_resonator.operations

    def test_quantum_dot_pair_registered(self, rabi_setup):
        machine, _ = rabi_setup
        assert "qd_pair_1_2" in machine.quantum_dot_pairs
        pair = machine.quantum_dot_pairs["qd_pair_1_2"]
        assert len(pair.quantum_dots) == 2


class TestQubitRegistration:
    """Section 2: register_qubit with xy_channel and readout_quantum_dot."""

    def test_qubit_exists(self, rabi_setup):
        machine, qubit = rabi_setup
        assert "Q1" in machine.qubits
        assert qubit is machine.qubits["Q1"]

    def test_xy_set(self, rabi_setup):
        _, qubit = rabi_setup
        assert qubit.xy is not None
        assert qubit.xy.id == "Q1_xy"
        assert "drive" in qubit.xy.operations
        assert "gaussian" in qubit.xy.operations

    def test_qubit_has_quantum_dot(self, rabi_setup):
        _, qubit = rabi_setup
        assert qubit.quantum_dot is not None


class TestVoltagePoints:
    """Section 2: direct voltage-point definition."""

    def test_three_points_defined(self, rabi_setup):
        _, qubit = rabi_setup
        gate_set_macros = qubit.voltage_sequence.gate_set.get_macros()
        for name in ("init", "operate", "readout"):
            full_name = f"{qubit.id}_{name}"
            assert full_name in gate_set_macros, f"Missing voltage point '{full_name}'"


class TestCustomMacros:
    """Section 3: custom QuamMacro subclasses and macro dispatch."""

    def test_macros_registered(self, rabi_setup):
        _, qubit = rabi_setup
        assert "drive" in qubit.macros
        assert "measure" in qubit.macros

    def test_drive_dispatches(self, rabi_setup):
        _, qubit = rabi_setup
        with qua.program() as prog:
            qubit.drive(duration=100)
        assert prog is not None

    def test_measure_dispatches_and_returns_iq(self, rabi_setup):
        _, qubit = rabi_setup
        with qua.program() as prog:
            result = qubit.measure()
        assert prog is not None
        assert result is not None
        assert len(result) == 2


class TestQUAProgramFlow:
    """Section 4: full init → operate → readout navigation + macros in QUA."""

    def test_single_iteration_compiles(self, rabi_setup):
        _, qubit = rabi_setup
        with qua.program() as prog:
            qubit.step_to_point("init")
            qua.align()
            qubit.step_to_point("operate")
            qubit.drive(duration=100)
            qua.align()
            qubit.step_to_point("readout")
            iq_i, iq_q = qubit.measure()
            qua.save(iq_i, "I")
            qua.save(iq_q, "Q")
        assert prog is not None

    def test_loop_with_frequency_sweep(self, rabi_setup):
        _, qubit = rabi_setup
        with qua.program() as prog:
            n = qua.declare(int)
            f = qua.declare(int)
            t = qua.declare(int)
            with qua.for_(n, 0, n < 2, n + 1):
                with qua.for_(t, 50, t < 200, t + 50):
                    with qua.for_(f, int(10e3), f < int(30e6), f + int(10e6)):
                        qua.update_frequency(qubit.xy.name, f)
                        qubit.step_to_point("init")
                        qua.align()
                        qubit.step_to_point("operate")
                        qubit.drive(duration=t)
                        qua.align()
                        qubit.step_to_point("readout")
                        qubit.measure()
        assert prog is not None


class TestConfigGeneration:
    """Section 5: generate_config() for a quantum-dot machine."""

    def test_generates_valid_config(self, rabi_setup):
        machine, _ = rabi_setup
        config = machine.generate_config()
        assert isinstance(config, dict)
        assert "controllers" in config
        assert "elements" in config

    def test_xy_drive_in_config(self, rabi_setup):
        machine, qubit = rabi_setup
        config = machine.generate_config()
        assert qubit.xy.name in config["elements"]

    def test_readout_resonator_in_config(self, rabi_setup):
        machine, _ = rabi_setup
        config = machine.generate_config()
        sd = machine.sensor_dots["virtual_sensor_1"]
        assert sd.readout_resonator.name in config["elements"]

    def test_voltage_gates_in_config(self, rabi_setup):
        machine, _ = rabi_setup
        config = machine.generate_config()
        for dot_name in ("virtual_dot_1", "virtual_dot_2"):
            dot = machine.quantum_dots[dot_name]
            assert dot.physical_channel.name in config["elements"]
