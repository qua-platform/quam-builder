"""Tests for WiringLineType.CAVITY handling in create_wiring and add_cavities.

These tests verify that the cavity line type is correctly routed through
the wiring creation and cavity builder pipeline, ensuring compatibility
with py-qua-tools add_cavity_lines().
"""

import pytest
from unittest.mock import MagicMock

from qualang_tools.wirer import Connectivity
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from qualang_tools.wirer.connectivity.element import QubitReference

from quam_builder.builder.qop_connectivity.create_wiring import (
    create_wiring,
    set_nested_value_with_path,
)


class TestCreateWiringCavity:
    """Tests for create_wiring() handling of WiringLineType.CAVITY."""

    def test_cavity_line_type_routes_to_cavities_path(self):
        """CAVITY line type should route wiring to cavities/ path, not qubits/.

        When py-qua-tools add_cavity_lines() is used, it creates a wiring spec
        with WiringLineType.CAVITY. The create_wiring() function must route
        this to the 'cavities/{element_id}/cavity/' path structure.

        This test uses a mock connectivity to simulate allocated channels.
        """
        # Create a mock connectivity with allocated channels
        mock_connectivity = MagicMock(spec=Connectivity)

        # Create a mock element with CAVITY channels
        mock_channel = MagicMock()
        mock_channel.instrument_id = "mw-fem"
        mock_channel.signal_type = "analog"
        mock_channel.io_type = "output"
        mock_channel.con = 1
        mock_channel.slot = 1
        mock_channel.port = 1

        # Create element with QubitReference-like id
        mock_element = MagicMock()
        mock_element.channels = {
            WiringLineType.CAVITY: [mock_channel]
        }

        # Set up connectivity.elements as a dict
        element_id = QubitReference(0)
        mock_connectivity.elements = {element_id: mock_element}

        # Call create_wiring
        wiring = create_wiring(mock_connectivity)

        # Verify the wiring is routed to 'cavities/' not 'qubits/'
        assert "cavities" in wiring, "Cavity wiring should be under 'cavities' key"
        assert "qubits" not in wiring, \
            "Cavity-only wiring should not have qubits section"

        # Verify the cavity path uses WiringLineType.CAVITY.value
        element_key = str(element_id)
        assert element_key in wiring["cavities"], f"Element {element_key} should exist"
        assert WiringLineType.CAVITY.value in wiring["cavities"][element_key], \
            f"Wiring should use '{WiringLineType.CAVITY.value}' as path"

    def test_cavity_and_qubit_wiring_separation(self):
        """Cavity and qubit wiring should be in separate sections.

        When a system has both qubits with drive lines and cavities,
        they should be routed to separate sections in the wiring dict.
        """
        # Create a mock connectivity with both DRIVE and CAVITY channels
        mock_connectivity = MagicMock(spec=Connectivity)

        # Mock channels
        mock_drive_channel = MagicMock()
        mock_drive_channel.instrument_id = "mw-fem"
        mock_drive_channel.signal_type = "analog"
        mock_drive_channel.io_type = "output"
        mock_drive_channel.con = 1
        mock_drive_channel.slot = 1
        mock_drive_channel.port = 1

        mock_cavity_channel = MagicMock()
        mock_cavity_channel.instrument_id = "mw-fem"
        mock_cavity_channel.signal_type = "analog"
        mock_cavity_channel.io_type = "output"
        mock_cavity_channel.con = 1
        mock_cavity_channel.slot = 1
        mock_cavity_channel.port = 2

        # Create elements - one with DRIVE, one with CAVITY
        mock_qubit_element = MagicMock()
        mock_qubit_element.channels = {
            WiringLineType.DRIVE: [mock_drive_channel]
        }

        mock_cavity_element = MagicMock()
        mock_cavity_element.channels = {
            WiringLineType.CAVITY: [mock_cavity_channel]
        }

        qubit_id = QubitReference(0)
        cavity_id = QubitReference(1)
        mock_connectivity.elements = {
            qubit_id: mock_qubit_element,
            cavity_id: mock_cavity_element,
        }

        # Call create_wiring
        wiring = create_wiring(mock_connectivity)

        # Verify both sections exist
        assert "qubits" in wiring, "Qubit wiring should be under 'qubits' key"
        assert "cavities" in wiring, "Cavity wiring should be under 'cavities' key"

        # Verify they contain the right elements
        assert str(qubit_id) in wiring["qubits"]
        assert str(cavity_id) in wiring["cavities"]

    def test_cavity_line_type_value_is_cavity(self):
        """Verify WiringLineType.CAVITY has the expected string value.

        This is a regression test to ensure the enum value matches
        what add_cavities() expects.
        """
        assert WiringLineType.CAVITY.value == "cavity"
        # Verify it's different from DRIVE
        assert WiringLineType.CAVITY.value != WiringLineType.DRIVE.value


class TestAddCavitiesLineType:
    """Tests for add_cavities() handling of CAVITY line type."""

    def test_add_cavities_accepts_cavity_line_type(self):
        """add_cavities() should accept wiring with CAVITY line type.

        Previously, add_cavities() checked for DRIVE line type ("xy"),
        but py-qua-tools uses CAVITY line type ("cavity").
        """
        from quam_builder.architecture.superconducting.qubit import BosonicMode
        from quam_builder.architecture.superconducting.qpu.fixed_frequency_single_cavity_quam import (
            FixedFrequencyTransmonSingleCavityQuam,
        )
        from quam_builder.builder.superconducting.build_quam import add_cavities

        # Create a machine with cavity support
        machine = FixedFrequencyTransmonSingleCavityQuam()

        # Set up wiring with CAVITY line type (matching py-qua-tools output)
        machine.wiring = {
            "cavities": {
                "c0": {
                    WiringLineType.CAVITY.value: {  # "cavity"
                        "opx_output": "#/ports/mw_fem_1/1",
                    }
                }
            }
        }

        # This should not raise ValueError
        add_cavities(machine)

        # Verify cavity was created
        assert "c0" in machine.cavities
        assert isinstance(machine.cavities["c0"], BosonicMode)
        assert "c0" in machine.active_cavity_names

    def test_add_cavities_rejects_unknown_line_type(self):
        """add_cavities() should reject unknown line types."""
        from quam_builder.architecture.superconducting.qpu.fixed_frequency_single_cavity_quam import (
            FixedFrequencyTransmonSingleCavityQuam,
        )
        from quam_builder.builder.superconducting.build_quam import add_cavities

        machine = FixedFrequencyTransmonSingleCavityQuam()

        # Set up wiring with an incorrect line type
        machine.wiring = {
            "cavities": {
                "c0": {
                    "unknown_type": {
                        "opx_output": "#/ports/mw_fem_1/1",
                    }
                }
            }
        }

        with pytest.raises(ValueError, match="Unknown line type for cavity"):
            add_cavities(machine)

    def test_add_cavities_rejects_drive_line_type(self):
        """add_cavities() should reject DRIVE line type (it expects CAVITY).

        This is the inverse of the original bug - we now expect CAVITY,
        so DRIVE should be rejected.
        """
        from quam_builder.architecture.superconducting.qpu.fixed_frequency_single_cavity_quam import (
            FixedFrequencyTransmonSingleCavityQuam,
        )
        from quam_builder.builder.superconducting.build_quam import add_cavities

        machine = FixedFrequencyTransmonSingleCavityQuam()

        # Set up wiring with DRIVE line type (the old incorrect expectation)
        machine.wiring = {
            "cavities": {
                "c0": {
                    WiringLineType.DRIVE.value: {  # "xy" - should be rejected
                        "opx_output": "#/ports/mw_fem_1/1",
                    }
                }
            }
        }

        with pytest.raises(ValueError, match="Unknown line type for cavity"):
            add_cavities(machine)
