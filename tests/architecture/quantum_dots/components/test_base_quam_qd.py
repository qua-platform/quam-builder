"""Tests for BaseQuamQD and LossDiVincenzoQuam registration workflows.

All objects are real — no mocks or stubs.
"""

import pytest
from qm import qua
from quam.components import StickyChannelAddon, pulses
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    QuantumDot,
    BarrierGate,
    SensorDot,
    QuantumDotPair,
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair


def _gate(port: int, gate_id: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort("con1", 6, port_id=port),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )


def _resonator() -> ReadoutResonatorSingle:
    return ReadoutResonatorSingle(
        id="rr",
        frequency_bare=0,
        intermediate_frequency=500e6,
        operations={"readout": pulses.SquareReadoutPulse(length=200, id="readout", amplitude=0.01)},
        opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1),
        opx_input=LFFEMAnalogInputPort("con1", 5, port_id=2),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )


def _two_dot_machine_with_readout() -> LossDiVincenzoQuam:
    machine = LossDiVincenzoQuam()
    p1 = _gate(1, "p1")
    p2 = _gate(2, "p2")
    b1 = _gate(3, "b1")
    s1 = _gate(4, "s1")

    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "vd1": p1,
            "vd2": p2,
            "vb1": b1,
            "vs1": s1,
        },
        gate_set_id="qpu",
    )
    machine.register_channel_elements(
        plunger_channels=[p1, p2],
        barrier_channels=[b1],
        sensor_resonator_mappings={s1: _resonator()},
    )
    machine.register_quantum_dot_pair(
        id="pair_12",
        quantum_dot_ids=["vd1", "vd2"],
        sensor_dot_ids=["vs1"],
        barrier_gate_id="vb1",
    )
    return machine


class TestMachineCreation:
    def test_empty_machine(self):
        machine = LossDiVincenzoQuam()
        assert machine.quantum_dots == {}
        assert machine.sensor_dots == {}
        assert machine.barrier_gates == {}
        assert machine.qubits == {}
        assert machine.qubit_pairs == {}
        assert machine.virtual_gate_sets == {}
        assert machine.quantum_dot_pairs == {}

    def test_default_fields(self):
        machine = LossDiVincenzoQuam()
        assert machine.b_field == 0
        assert machine.active_qubit_names == []
        assert machine.active_qubit_pair_names == []


class TestVirtualGateSetCreation:
    def test_create_virtual_gate_set(self):
        machine = LossDiVincenzoQuam()
        p1 = _gate(1, "p1")
        p2 = _gate(2, "p2")

        machine.create_virtual_gate_set(
            virtual_channel_mapping={"vd1": p1, "vd2": p2},
            gate_set_id="test_set",
        )

        assert "test_set" in machine.virtual_gate_sets
        vgs = machine.virtual_gate_sets["test_set"]
        assert "vd1" in vgs.valid_channel_names
        assert "vd2" in vgs.valid_channel_names

    def test_physical_channels_registered(self):
        machine = LossDiVincenzoQuam()
        p1 = _gate(1, "p1")
        machine.create_virtual_gate_set(
            virtual_channel_mapping={"vd1": p1},
            gate_set_id="s",
        )
        assert len(machine.physical_channels) >= 1

    def test_compensation_matrix_defaults_to_identity(self):
        machine = LossDiVincenzoQuam()
        p1 = _gate(1, "p1")
        p2 = _gate(2, "p2")
        machine.create_virtual_gate_set(
            virtual_channel_mapping={"vd1": p1, "vd2": p2},
            gate_set_id="s",
        )
        vgs = machine.virtual_gate_sets["s"]
        assert len(vgs.layers) == 1
        comp = vgs.layers[0].matrix
        assert comp[0][0] == 1.0
        assert comp[1][1] == 1.0
        assert comp[0][1] == 0.0


class TestRegistration:
    @pytest.fixture
    def machine_with_vgs(self):
        machine = LossDiVincenzoQuam()
        self.p1 = _gate(1, "p1")
        self.p2 = _gate(2, "p2")
        self.b1 = _gate(3, "b1")
        self.s1 = _gate(4, "s1")
        machine.create_virtual_gate_set(
            virtual_channel_mapping={
                "vd1": self.p1,
                "vd2": self.p2,
                "vb1": self.b1,
                "vs1": self.s1,
            },
            gate_set_id="qpu",
        )
        return machine

    def test_register_quantum_dots(self, machine_with_vgs):
        machine_with_vgs.register_quantum_dots([self.p1, self.p2])
        assert len(machine_with_vgs.quantum_dots) == 2
        for name, qd in machine_with_vgs.quantum_dots.items():
            assert isinstance(qd, QuantumDot)

    def test_register_barrier_gates(self, machine_with_vgs):
        machine_with_vgs.register_barrier_gates([self.b1])
        assert len(machine_with_vgs.barrier_gates) == 1
        bg = list(machine_with_vgs.barrier_gates.values())[0]
        assert isinstance(bg, BarrierGate)

    def test_register_sensor_dots(self, machine_with_vgs):
        rr = _resonator()
        machine_with_vgs.register_sensor_dots({self.s1: rr})
        assert len(machine_with_vgs.sensor_dots) == 1
        sd = list(machine_with_vgs.sensor_dots.values())[0]
        assert isinstance(sd, SensorDot)
        assert sd.readout_resonator is rr

    def test_register_channel_elements_all_at_once(self, machine_with_vgs):
        rr = _resonator()
        machine_with_vgs.register_channel_elements(
            plunger_channels=[self.p1, self.p2],
            barrier_channels=[self.b1],
            sensor_resonator_mappings={self.s1: rr},
        )
        assert len(machine_with_vgs.quantum_dots) == 2
        assert len(machine_with_vgs.barrier_gates) == 1
        assert len(machine_with_vgs.sensor_dots) == 1

    def test_register_quantum_dot_pair(self, machine_with_vgs):
        rr = _resonator()
        machine_with_vgs.register_channel_elements(
            plunger_channels=[self.p1, self.p2],
            barrier_channels=[self.b1],
            sensor_resonator_mappings={self.s1: rr},
        )
        dot_ids = list(machine_with_vgs.quantum_dots.keys())
        sensor_ids = list(machine_with_vgs.sensor_dots.keys())
        barrier_id = list(machine_with_vgs.barrier_gates.keys())[0]
        machine_with_vgs.register_quantum_dot_pair(
            id="pair_12",
            quantum_dot_ids=dot_ids[:2],
            sensor_dot_ids=sensor_ids,
            barrier_gate_id=barrier_id,
        )
        assert "pair_12" in machine_with_vgs.quantum_dot_pairs
        pair = machine_with_vgs.quantum_dot_pairs["pair_12"]
        assert isinstance(pair, QuantumDotPair)
        assert len(pair.quantum_dots) == 2
        assert len(pair.sensor_dots) == 1


class TestComponentRetrieval:
    def test_get_component_quantum_dot(self, qd_machine):
        comp = qd_machine.get_component("virtual_dot_1")
        assert isinstance(comp, QuantumDot)

    def test_get_component_barrier(self, qd_machine):
        comp = qd_machine.get_component("virtual_barrier_1")
        assert isinstance(comp, BarrierGate)

    def test_get_component_sensor(self, qd_machine):
        comp = qd_machine.get_component("virtual_sensor_1")
        assert isinstance(comp, SensorDot)

    def test_get_component_qubit(self, qd_machine):
        comp = qd_machine.get_component("Q1")
        assert isinstance(comp, LDQubit)

    def test_get_component_not_found(self, qd_machine):
        with pytest.raises(ValueError):
            qd_machine.get_component("nonexistent")

    def test_find_quantum_dot_pair(self, qd_machine):
        pair_name = qd_machine.find_quantum_dot_pair("virtual_dot_1", "virtual_dot_2")
        assert pair_name is not None

    def test_find_quantum_dot_pair_returns_none(self, qd_machine):
        result = qd_machine.find_quantum_dot_pair("virtual_dot_1", "virtual_dot_4")
        assert result is None


class TestVoltageSequence:
    def test_get_voltage_sequence(self, qd_machine):
        vs = qd_machine.get_voltage_sequence("main_qpu")
        assert vs is not None

    def test_reset_voltage_sequence(self, qd_machine):
        vs1 = qd_machine.get_voltage_sequence("main_qpu")
        qd_machine.reset_voltage_sequence("main_qpu")
        vs2 = qd_machine.get_voltage_sequence("main_qpu")
        assert vs1 is not vs2


class TestQubitRegistration:
    def test_qubits_registered(self, qd_machine):
        assert set(qd_machine.qubits.keys()) == {"Q1", "Q2", "Q3", "Q4"}
        for q in qd_machine.qubits.values():
            assert isinstance(q, LDQubit)

    def test_register_qubit_stores_preferred_readout_quantum_dot(self):
        machine = _two_dot_machine_with_readout()
        machine.register_qubit(
            quantum_dot_id="vd1",
            qubit_name="Q1",
            readout_quantum_dot="vd2",
        )

        assert machine.qubits["Q1"].preferred_readout_quantum_dot == "vd2"

    def test_qubit_pairs_registered(self, qd_machine):
        assert set(qd_machine.qubit_pairs.keys()) == {"Q1_Q2", "Q3_Q4"}
        for qp in qd_machine.qubit_pairs.values():
            assert isinstance(qp, LDQubitPair)

    def test_active_qubits(self, qd_machine):
        qd_machine.active_qubit_names = ["Q1", "Q3"]
        active = qd_machine.active_qubits
        assert len(active) == 2
        assert all(isinstance(q, LDQubit) for q in active)

    def test_active_qubit_pairs(self, qd_machine):
        qd_machine.active_qubit_pair_names = ["Q1_Q2"]
        active = qd_machine.active_qubit_pairs
        assert len(active) == 1
        assert isinstance(active[0], LDQubitPair)


class TestQuaVariables:
    def test_declare_qua_variables(self, qd_machine):
        with qua.program() as _prog:
            iq_i, _i_st, iq_q, _q_st, _n, _n_st = qd_machine.declare_qua_variables()

        assert len(iq_i) == len(qd_machine.qubits)
        assert len(iq_q) == len(qd_machine.qubits)

    def test_declare_qua_variables_custom_count(self, qd_machine):
        with qua.program() as _prog:
            iq_i, _i_st, iq_q, _q_st, _n, _n_st = qd_machine.declare_qua_variables(num_IQ_pairs=2)

        assert len(iq_i) == 2
        assert len(iq_q) == 2


class TestSerialization:
    def test_to_dict_excludes_voltage_sequences(self, qd_machine):
        _ = qd_machine.get_voltage_sequence("main_qpu")
        d = qd_machine.to_dict()
        assert "voltage_sequences" not in d

    def test_to_dict_contains_qubits(self, qd_machine):
        d = qd_machine.to_dict()
        assert "qubits" in d
        assert "Q1" in d["qubits"]

    def test_to_dict_contains_quantum_dots(self, qd_machine):
        d = qd_machine.to_dict()
        assert "quantum_dots" in d

    def test_round_trip_preserves_preferred_readout_quantum_dot(self, tmp_path):
        machine = _two_dot_machine_with_readout()
        machine.register_qubit(
            quantum_dot_id="vd1",
            qubit_name="Q1",
            readout_quantum_dot="vd2",
        )

        machine.save(tmp_path, include_defaults=False)
        loaded = LossDiVincenzoQuam.load(tmp_path)

        assert loaded.qubits["Q1"].preferred_readout_quantum_dot == "vd2"
