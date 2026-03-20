"""Tests for macro persistence across save/load round-trips."""

import pytest

from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD


def test_macro_instances_survive_save_load_roundtrip(qd_machine, reset_catalog, tmp_path):
    """QuantumDot, QuantumDotPair, SensorDot macros persist across save/load."""
    wire_machine_macros(qd_machine)
    qd_machine.save(tmp_path)

    loaded = BaseQuamQD.load(tmp_path)

    for qd in loaded.quantum_dots.values():
        assert "initialize" in qd.macros
        assert "empty" in qd.macros

    for pair in loaded.quantum_dot_pairs.values():
        assert "initialize" in pair.macros
        assert "measure" in pair.macros
        assert "empty" in pair.macros

    for sd in loaded.sensor_dots.values():
        assert "measure" in sd.macros
        assert "initialize" not in sd.macros
        assert "empty" not in sd.macros
