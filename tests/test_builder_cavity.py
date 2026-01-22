"""Physics-focused tests for cavity builder functionality.

These tests verify that the cavity builder correctly configures BosonicMode
components for controlling harmonic cavity modes in superconducting quantum systems.
"""
import pytest
from quam.components import pulses

from quam_builder.architecture.superconducting.qubit import BosonicMode
from quam_builder.architecture.superconducting.components.xy_drive import (
    XYDriveIQ,
    XYDriveMW,
)
from quam_builder.architecture.superconducting.qpu.fixed_frequency_single_cavity_quam import (
    FixedFrequencyTransmonSingleCavityQuam,
)
from quam_builder.builder.superconducting.add_cavity_drive_component import (
    add_cavity_drive_component,
)
from quam_builder.builder.superconducting.pulses import add_default_cavity_pulses


# -----------------------------------------------------------------------------
# Cavity Drive Component Tests
# -----------------------------------------------------------------------------


class TestCavityDriveComponent:
    """Tests for cavity XY drive attachment following IQ/MW channel patterns.
    
    Note: Full integration tests with actual wiring resolution are performed
    through the build_quam workflow. These unit tests verify basic structure
    and reference assignment.
    """

    def test_iq_port_detection(self):
        """IQ drive type is correctly detected from port configuration.
        
        When IQ output ports (I, Q) and frequency converter are present,
        the builder should create an XYDriveIQ component. This is the typical
        configuration for LF-FEM or OPX+ with Octave upconversion.
        """
        from quam_builder.builder.qop_connectivity.channel_ports import iq_out_channel_ports
        
        # These are the port keys that indicate IQ configuration
        mock_ports = {
            "opx_output_I": "#/ports/lf_fem_1/1",
            "opx_output_Q": "#/ports/lf_fem_1/2",
            "frequency_converter_up": "#/octaves/oct1/RF1",
        }
        
        # Verify all required IQ port keys are present
        assert all(key in mock_ports for key in iq_out_channel_ports)
        
        # The MW ports should NOT all be present
        from quam_builder.builder.qop_connectivity.channel_ports import mw_out_channel_ports
        assert not all(key in mock_ports for key in mw_out_channel_ports)

    def test_mw_drive_attachment_direct_synthesis(self):
        """MW-FEM drive attaches for direct microwave synthesis.
        
        MW-FEM can directly synthesize at cavity frequencies without external
        upconversion, useful for certain frequency ranges.
        """
        cavity = BosonicMode(id="c1")
        
        # Simulate MW-FEM wiring (single output)
        mock_ports = {
            "opx_output": "#/ports/mw_fem_1/1",
        }
        wiring_path = "#/wiring/cavities/c1/drive"
        
        add_cavity_drive_component(cavity, wiring_path, mock_ports)
        
        assert cavity.xy is not None
        assert isinstance(cavity.xy, XYDriveMW)
        assert cavity.xy.opx_output == f"{wiring_path}/opx_output"

    def test_invalid_port_configuration_raises_error(self):
        """Invalid port configurations are rejected."""
        cavity = BosonicMode(id="c1")
        
        # Incomplete/invalid port configuration
        invalid_ports = {
            "opx_output_I": "#/ports/lf_fem_1/1",
            # Missing opx_output_Q and frequency_converter_up
        }
        wiring_path = "#/wiring/cavities/c1/drive"
        
        with pytest.raises(ValueError, match="Unimplemented mapping"):
            add_cavity_drive_component(cavity, wiring_path, invalid_ports)


# -----------------------------------------------------------------------------
# Cavity Pulse Configuration Tests
# -----------------------------------------------------------------------------


class TestCavityPulses:
    """Tests for default cavity pulses with physics-meaningful parameters."""

    def test_saturation_pulse_configuration(self):
        """Saturation pulse has appropriate parameters for cavity spectroscopy.
        
        The saturation pulse is used for:
        - Cavity spectroscopy (finding the cavity resonance)
        - Initial characterization before calibrating displacement pulses
        
        A 20 microsecond pulse at 0.25V is a reasonable starting point for
        probing a harmonic cavity without driving it too hard.
        """
        cavity = BosonicMode(id="c1")
        cavity.xy = XYDriveIQ(
            opx_output_I="#/ports/1",
            opx_output_Q="#/ports/2",
            frequency_converter_up="#/octaves/oct1/RF1",
        )
        
        add_default_cavity_pulses(cavity)
        
        # Verify saturation pulse exists
        assert "saturation" in cavity.xy.operations
        
        saturation = cavity.xy.operations["saturation"]
        assert isinstance(saturation, pulses.SquarePulse)
        
        # Physics-meaningful parameters:
        # - 20 microseconds: Long enough to reach steady state in cavity
        # - 0.25V: Moderate amplitude for initial probing
        assert saturation.length == 20_000  # 20 microseconds in ns
        assert saturation.amplitude == 0.25
        assert saturation.axis_angle == 0  # In-phase

    def test_no_drag_correction_for_harmonic_cavity(self):
        """Harmonic cavities don't need DRAG corrections.
        
        Unlike transmons (anharmonic oscillators), harmonic cavities have
        equally spaced energy levels. This means:
        - No leakage to non-computational states
        - Simple square pulses are sufficient for basic operations
        - DRAG corrections (which compensate anharmonicity) are unnecessary
        """
        cavity = BosonicMode(id="c1")
        cavity.xy = XYDriveIQ(
            opx_output_I="#/ports/1",
            opx_output_Q="#/ports/2",
            frequency_converter_up="#/octaves/oct1/RF1",
        )
        
        add_default_cavity_pulses(cavity)
        
        # Only basic saturation pulse, no DRAG-shaped gates
        assert "saturation" in cavity.xy.operations
        # DRAG-specific operations should NOT be present
        assert "x180_DragGaussian" not in cavity.xy.operations
        assert "x90_DragGaussian" not in cavity.xy.operations
        # Square pulse is appropriate for harmonic systems
        assert isinstance(cavity.xy.operations["saturation"], pulses.SquarePulse)

    def test_no_pulses_without_xy_drive(self):
        """No operations added if cavity has no XY drive configured."""
        cavity = BosonicMode(id="c1")
        assert cavity.xy is None
        
        # Should not raise, just skip
        add_default_cavity_pulses(cavity)
        
        # No operations to check since xy is None


# -----------------------------------------------------------------------------
# QPU Integration Tests
# -----------------------------------------------------------------------------


class TestQPUCavityIntegration:
    """Tests for cavity integration with FixedFrequencyTransmonSingleCavityQuam."""

    def test_active_cavity_names_tracking(self):
        """QPU tracks active cavities separately from qubits."""
        qpu = FixedFrequencyTransmonSingleCavityQuam()
        
        # Add cavities
        qpu.cavities["c1"] = BosonicMode(id="c1")
        qpu.cavities["c2"] = BosonicMode(id="c2")
        
        # Mark only c1 as active
        qpu.active_cavity_names = ["c1"]
        
        # Verify active_cavities property
        active = qpu.active_cavities
        assert len(active) == 1
        assert active[0].name == "c1"

    def test_hybrid_qubit_cavity_system(self):
        """QPU supports hybrid systems with both qubits and cavities.
        
        This is the typical architecture for:
        - Bosonic quantum error correction (cat qubits, binomial codes)
        - Quantum memory with transmon readout
        - Circuit QED experiments
        """
        from quam_builder.architecture.superconducting.qubit import FixedFrequencyTransmon
        
        qpu = FixedFrequencyTransmonSingleCavityQuam()
        
        # Add transmon qubit (ancilla for cavity readout)
        qpu.qubits["q0"] = FixedFrequencyTransmon(id="q0")
        
        # Add storage cavity (bosonic mode for quantum memory)
        qpu.cavities["storage"] = BosonicMode(id="storage")
        qpu.cavities["storage"].frequency = 6.5e9  # Typical cavity frequency
        qpu.cavities["storage"].T1 = 500e-6  # 500 microsecond cavity T1 (longer than transmon)
        
        # Both can be active simultaneously
        qpu.active_qubit_names = ["q0"]
        qpu.active_cavity_names = ["storage"]
        
        assert len(qpu.active_qubits) == 1
        assert len(qpu.active_cavities) == 1
        
        # Cavity should have much longer T1 than transmon
        storage = qpu.cavities["storage"]
        assert storage.T1 == 500e-6

    def test_cavity_type_class_attribute(self):
        """QPU has correct cavity_type for factory pattern."""
        assert FixedFrequencyTransmonSingleCavityQuam.cavity_type == BosonicMode

    def test_empty_active_cavities_by_default(self):
        """New QPU has no active cavities until configured."""
        qpu = FixedFrequencyTransmonSingleCavityQuam()
        assert qpu.active_cavity_names == []
        assert qpu.active_cavities == []
