"""Unit tests for quantum dot builder component functions.

These helpers were removed during refactor; tests are skipped when unavailable.
"""

import pytest
from unittest.mock import MagicMock
from quam.components.ports import LFFEMAnalogOutputPort, LFFEMAnalogInputPort, MWFEMAnalogOutputPort

try:
    from quam_builder.builder.quantum_dots.add_gate_voltage_component import add_gate_voltage_component
    from quam_builder.builder.quantum_dots.add_esr_drive_component import add_esr_drive_component
    from quam_builder.builder.quantum_dots.add_rf_resonator_component import add_rf_resonator_component
except ModuleNotFoundError:
    pytest.skip("Component helpers removed after refactor", allow_module_level=True)

from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.components import VoltageGate


class TestAddGateVoltageComponent:
    """Tests for add_gate_voltage_component function."""

    def test_add_voltage_gate_with_lf_fem_port(self):
        """Test adding a voltage gate with LF-FEM port."""
        # Create a mock qubit
        qubit = MagicMock(spec=LDQubit)

        # Mock wiring path and ports
        wiring_path = "#/wiring/qubits/q1/p"
        ports = {"opx_output": f"{wiring_path}/opx_output"}

        # Call the function
        add_gate_voltage_component(qubit, wiring_path, ports)

        # Verify that the voltage gate was added
        assert hasattr(qubit, 'z')
        assert qubit.z is not None

    def test_add_voltage_gate_raises_error_for_invalid_ports(self):
        """Test that invalid ports raise a ValueError."""
        qubit = MagicMock(spec=LDQubit)
        wiring_path = "#/wiring/qubits/q1/p"
        ports = {"invalid_port": "some_value"}  # Invalid port key

        with pytest.raises(ValueError, match="Unimplemented mapping"):
            add_gate_voltage_component(qubit, wiring_path, ports)


class TestAddESRDriveComponent:
    """Tests for add_esr_drive_component function."""

    def test_add_iq_drive_component(self):
        """Test adding an IQ drive component (LF-FEM + Octave or OPX+)."""
        qubit = MagicMock(spec=LDQubit)

        wiring_path = "#/wiring/qubits/q1/xy"
        ports = {
            "opx_output_I": f"{wiring_path}/opx_output_I",
            "opx_output_Q": f"{wiring_path}/opx_output_Q",
            "frequency_converter_up": f"{wiring_path}/frequency_converter_up",
        }

        add_esr_drive_component(qubit, wiring_path, ports)

        # Verify XY drive was added
        assert hasattr(qubit, 'xy')
        assert qubit.xy is not None

    def test_add_mw_drive_component(self):
        """Test adding a MW-FEM drive component."""
        qubit = MagicMock(spec=LDQubit)

        wiring_path = "#/wiring/qubits/q1/xy"
        ports = {
            "opx_output": f"{wiring_path}/opx_output",
        }

        add_esr_drive_component(qubit, wiring_path, ports)

        # Verify XY drive was added
        assert hasattr(qubit, 'xy')
        assert qubit.xy is not None

    def test_add_drive_raises_error_for_invalid_ports(self):
        """Test that invalid ports raise a ValueError."""
        qubit = MagicMock(spec=LDQubit)
        wiring_path = "#/wiring/qubits/q1/xy"
        ports = {"invalid_port": "some_value"}

        with pytest.raises(ValueError, match="Unimplemented mapping"):
            add_esr_drive_component(qubit, wiring_path, ports)


class TestAddRFResonatorComponent:
    """Tests for add_rf_resonator_component function."""

    def test_add_iq_resonator_component(self):
        """Test adding an IQ resonator component."""
        qubit = MagicMock(spec=LDQubit)

        wiring_path = "#/wiring/sensor_dots/s1/rf"
        ports = {
            "opx_output_I": f"{wiring_path}/opx_output_I",
            "opx_output_Q": f"{wiring_path}/opx_output_Q",
            "opx_input_I": f"{wiring_path}/opx_input_I",
            "opx_input_Q": f"{wiring_path}/opx_input_Q",
            "frequency_converter_up": f"{wiring_path}/frequency_converter_up",
            "frequency_converter_down": f"{wiring_path}/frequency_converter_down",
        }

        add_rf_resonator_component(qubit, wiring_path, ports)

        # Verify resonator was added
        assert hasattr(qubit, 'resonator')
        assert qubit.resonator is not None

    def test_add_mw_resonator_component(self):
        """Test adding a MW-FEM resonator component."""
        qubit = MagicMock(spec=LDQubit)

        wiring_path = "#/wiring/sensor_dots/s1/rf"
        ports = {
            "opx_output": f"{wiring_path}/opx_output",
            "opx_input": f"{wiring_path}/opx_input",
        }

        add_rf_resonator_component(qubit, wiring_path, ports)

        # Verify resonator was added
        assert hasattr(qubit, 'resonator')
        assert qubit.resonator is not None

    def test_add_resonator_raises_error_for_invalid_ports(self):
        """Test that invalid ports raise a ValueError."""
        qubit = MagicMock(spec=LDQubit)
        wiring_path = "#/wiring/sensor_dots/s1/rf"
        ports = {"invalid_port": "some_value"}

        with pytest.raises(ValueError, match="Unimplemented mapping"):
            add_rf_resonator_component(qubit, wiring_path, ports)
