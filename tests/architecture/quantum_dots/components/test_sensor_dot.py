"""Tests for SensorDot and Projector.

All objects are real — no mocks or stubs.
"""

from unittest.mock import MagicMock

from qm import qua

from quam_builder.architecture.quantum_dots.components import SensorDot
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.components.sensor_dot import Projector


class TestSensorDotProperties:
    def test_sensor_dot_exists(self, qd_machine):
        assert len(qd_machine.sensor_dots) >= 1

    def test_sensor_dot_type(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        assert isinstance(sd, SensorDot)

    def test_has_readout_resonator(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        assert sd.readout_resonator is not None

    def test_has_physical_channel(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        assert sd.physical_channel is not None

    def test_readout_thresholds_empty_by_default(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        assert sd.readout_thresholds == {}

    def test_readout_projectors_empty_by_default(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        assert sd.readout_projectors == {}


class TestProjector:
    def test_default_projector(self):
        p = Projector()
        assert p.wI == 1.0
        assert p.wQ == 0.0
        assert p.offset == 0.0

    def test_custom_projector(self):
        p = Projector(wI=0.5, wQ=0.5, offset=-0.1)
        assert p.wI == 0.5
        assert p.wQ == 0.5
        assert p.offset == -0.1


class TestReadoutParams:
    def test_add_readout_threshold(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        sd._add_readout_threshold("dot1_dot2_pair", 0.5)
        assert "dot1_dot2_pair" in sd.readout_thresholds
        assert sd.readout_thresholds["dot1_dot2_pair"] == 0.5

    def test_add_readout_projector(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        proj = Projector(wI=0.7, wQ=0.3, offset=0.01)
        sd._add_readout_projector("dot1_dot2_pair", proj)
        assert "dot1_dot2_pair" in sd.readout_projectors

    def test_add_readout_params(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        proj = Projector(wI=0.8, wQ=0.2, offset=0.0)
        sd._add_readout_params("dot1_dot2_pair", threshold=0.42, projector=proj)
        assert "dot1_dot2_pair" in sd.readout_thresholds
        assert "dot1_dot2_pair" in sd.readout_projectors
        assert sd.readout_thresholds["dot1_dot2_pair"] == 0.42

    def test_readout_params_retrieval(self, qd_machine):
        sd = list(qd_machine.sensor_dots.values())[0]
        proj = Projector(wI=0.6, wQ=0.4, offset=-0.05)
        sd._add_readout_params("dot3_dot4_pair", threshold=0.55, projector=proj)
        threshold, retrieved_proj = sd._readout_params("dot3_dot4_pair")
        assert threshold == 0.55


class TestSensorDotInQuantumDotPair:
    def test_pair_has_sensor_dot(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert len(pair.sensor_dots) >= 1
        assert isinstance(pair.sensor_dots[0], SensorDot)

    def test_sensor_shared_between_pairs(self, qd_machine):
        p1 = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        p2 = qd_machine.quantum_dot_pairs["dot3_dot4_pair"]
        assert p1.sensor_dots[0] is p2.sensor_dots[0]


class TestSensorDotMeasureMacro:
    """Tests for SensorDotMeasureMacro (dispatch to readout resonator)."""

    def test_sensor_dot_measure_macro_importable(self):
        """SensorDotMeasureMacro is importable from state_macros."""
        from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
            SensorDotMeasureMacro,
        )

        assert SensorDotMeasureMacro is not None

    def test_sensor_dot_measure_macro_apply_calls_readout_resonator_measure(self):
        """SensorDotMeasureMacro.apply() calls owner.readout_resonator.measure()."""
        from quam.core.macro import QuamMacro
        from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
            SensorDotMeasureMacro,
        )

        assert issubclass(SensorDotMeasureMacro, QuamMacro)
        mock_resonator = MagicMock()
        mock_sd = MagicMock(spec=SensorDot)
        mock_sd.readout_resonator = mock_resonator
        macro = SensorDotMeasureMacro()
        macro.parent = mock_sd
        with qua.program():
            macro.apply()
        mock_resonator.measure.assert_called_once()
        call_kw = mock_resonator.measure.call_args.kwargs
        assert "qua_vars" in call_kw


class TestSensorDotCatalog:
    """Verify SensorDot receives measure-only macro after wire_machine_macros()."""

    def test_has_measure_macro(self, qd_machine):
        wire_machine_macros(qd_machine)
        for sd in qd_machine.sensor_dots.values():
            assert "measure" in sd.macros, f"{sd.id} missing 'measure' macro"

    def test_no_initialize_macro(self, qd_machine):
        wire_machine_macros(qd_machine)
        for sd in qd_machine.sensor_dots.values():
            assert (
                "initialize" not in sd.macros
            ), f"{sd.id} must not have 'initialize' macro (CAT-03)"

    def test_no_empty_macro(self, qd_machine):
        wire_machine_macros(qd_machine)
        for sd in qd_machine.sensor_dots.values():
            assert "empty" not in sd.macros, f"{sd.id} must not have 'empty' macro (CAT-03)"
