"""``update_cross_compensation_submatrix`` writes the compensation matrix in the
``add_layer`` layout: rows are ``virtual_names``, columns are ``channels``, and
``resolve_voltages`` returns physical voltages for ``V_virtual = M @ V_physical``.
"""

from __future__ import annotations

import numpy as np
import pytest
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam

# Rows follow virtual_names, columns follow the paired physical channels.
SOURCE_BY_TARGET = [
    [1.0, 0.25],
    [0.10, 1.0],
]


def _gate(port: int, gate_id: str) -> VoltageGate:
    return VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort("con1", 6, port_id=port),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )


def _machine():
    machine = LossDiVincenzoQuam()
    plunger_1 = _gate(1, "p1")
    plunger_2 = _gate(2, "p2")
    machine.create_virtual_gate_set(
        virtual_channel_mapping={"vd1": plunger_1, "vd2": plunger_2},
        gate_set_id="compensation",
    )
    return machine, plunger_1, plunger_2


def _compensation_matrix(machine: LossDiVincenzoQuam) -> np.ndarray:
    return np.asarray(machine.virtual_gate_sets["compensation"].layers[0].matrix, dtype=float)


def _resolve(machine: LossDiVincenzoQuam, voltages: dict[str, float]) -> dict:
    return machine.virtual_gate_sets["compensation"].resolve_voltages(voltages)


def test_full_cross_compensation_update_resolves_to_physical_voltages():
    """A full update stores the given matrix, and resolve inverts it.

    With M = [[1, 0.25], [0.1, 1]], V_virtual = M @ V_physical. A pure plunger
    voltage therefore shows up on the other virtual gate.
    """
    machine, plunger_1, plunger_2 = _machine()

    before = _resolve(machine, {"vd1": 0.2, "vd2": 0.02})
    assert before["p1"] == pytest.approx(0.2)
    assert before["p2"] == pytest.approx(0.02)

    machine.update_cross_compensation_submatrix(
        virtual_names=["vd1", "vd2"],
        channels=[plunger_1, plunger_2],
        matrix=SOURCE_BY_TARGET,
        target="opx",
    )
    np.testing.assert_allclose(_compensation_matrix(machine), SOURCE_BY_TARGET)

    # V_physical = [0.2, 0] -> V_virtual = [0.2, 0.02]
    only_p1 = _resolve(machine, {"vd1": 0.2, "vd2": 0.02})
    assert only_p1["p1"] == pytest.approx(0.2)
    assert only_p1["p2"] == pytest.approx(0.0)

    # V_physical = [0, 0.4] -> V_virtual = [0.1, 0.4]
    only_p2 = _resolve(machine, {"vd1": 0.1, "vd2": 0.4})
    assert only_p2["p1"] == pytest.approx(0.0)
    assert only_p2["p2"] == pytest.approx(0.4)


def test_partial_cross_compensation_update_resolves_to_physical_voltages():
    """One updated entry changes only that term of V_virtual = M @ V_physical.

    matrix [[0.3]] for virtual vd2 and channel p1 is written at (vd2, p1), so
    M = [[1, 0], [0.3, 1]].
    """
    machine, plunger_1, _plunger_2 = _machine()
    machine.update_cross_compensation_submatrix(
        virtual_names=["vd2"],
        channels=[plunger_1],
        matrix=[[0.3]],
        target="opx",
    )
    np.testing.assert_allclose(
        _compensation_matrix(machine),
        [[1.0, 0.0], [0.3, 1.0]],
    )

    # V_physical = [1, 0] -> V_virtual = [1, 0.3]
    moved_p1 = _resolve(machine, {"vd1": 1.0, "vd2": 0.3})
    assert moved_p1["p1"] == pytest.approx(1.0)
    assert moved_p1["p2"] == pytest.approx(0.0)

    # V_physical = [0, 0.5] -> V_virtual = [0, 0.5]
    moved_p2 = _resolve(machine, {"vd2": 0.5})
    assert moved_p2["p1"] == pytest.approx(0.0)
    assert moved_p2["p2"] == pytest.approx(0.5)


def test_reordered_submatrix_update_resolves_to_physical_voltages():
    """Rows follow virtual_names and columns follow channels, not layer order.

    virtual_names=[vd2, vd1], channels=[p2], matrix=[[0.4], [0.7]] writes
    M[vd2, p2] = 0.4 and M[vd1, p2] = 0.7, so M = [[1, 0.7], [0, 0.4]].
    """
    machine, _plunger_1, plunger_2 = _machine()
    machine.update_cross_compensation_submatrix(
        virtual_names=["vd2", "vd1"],
        channels=[plunger_2],
        matrix=[[0.4], [0.7]],
        target="opx",
    )
    np.testing.assert_allclose(
        _compensation_matrix(machine),
        [[1.0, 0.7], [0.0, 0.4]],
    )

    # V_physical = [1, 0] -> V_virtual = [1, 0]
    moved_p1 = _resolve(machine, {"vd1": 1.0})
    assert moved_p1["p1"] == pytest.approx(1.0)
    assert moved_p1["p2"] == pytest.approx(0.0)

    # V_physical = [0, 1] -> V_virtual = [0.7, 0.4]
    moved_p2 = _resolve(machine, {"vd1": 0.7, "vd2": 0.4})
    assert moved_p2["p1"] == pytest.approx(0.0)
    assert moved_p2["p2"] == pytest.approx(1.0)
