import pytest
from quam.components.channels import IQChannel
from quam_builder.architecture.superconducting.qubit.bosonic_mode import BosonicMode


def test_class_attribute():
    """Verify BosonicMode has expected attributes with correct defaults."""
    cavity = BosonicMode(id="c1")
    attrs = [
        "xy",
        "frequency",
        "T1",
        "T2ramsey",
        "T2echo",
        "thermalization_time_factor",
        "grid_location",
    ]
    initial_values = [None, None, None, None, None, 5, None]
    for i, attr in enumerate(attrs):
        assert hasattr(cavity, attr)
        assert getattr(cavity, attr) == initial_values[i]


def test_no_anharmonic_attributes():
    """BosonicMode is a harmonic oscillator - no anharmonicity, no f_01/f_12."""
    cavity = BosonicMode(id="c1")
    # These are transmon-specific (anharmonic) attributes
    assert not hasattr(cavity, "anharmonicity")
    assert not hasattr(cavity, "f_01")
    assert not hasattr(cavity, "f_12")
    assert not hasattr(cavity, "chi")
    assert not hasattr(cavity, "resonator")
    assert not hasattr(cavity, "GEF_frequency_shift")
    assert not hasattr(cavity, "sigma_time_factor")
    assert not hasattr(cavity, "gate_fidelity")
    # Instead, has single frequency (harmonic)
    assert hasattr(cavity, "frequency")


def test_thermalization_time():
    """Thermalization time scales with T1 (5x by default)."""
    cavity = BosonicMode(id="c1")
    # Default: 5 * 10us = 50us = 50000ns
    assert cavity.thermalization_time == 50000
    # With explicit T1
    cavity.T1 = 200e-6  # 200 microseconds (typical cavity T1)
    assert cavity.thermalization_time == 1000000  # 5 * 200us = 1ms


def test_name():
    """Test cavity naming follows same pattern as qubits."""
    for name in ["cavity1", "c1", 0, 3]:
        cavity = BosonicMode(id=name)
        if type(name) == str:
            assert cavity.name == name
        else:
            assert cavity.name == f"q{name}"  # Uses Qubit base class naming


def test_xy_drive_channel():
    """Cavity can have an XY drive for control."""
    cavity = BosonicMode(id="c1")
    cavity.xy = IQChannel(
        opx_output_I="{wiring_path}/opx_output_I",
        opx_output_Q="{wiring_path}/opx_output_Q",
        frequency_converter_up="{wiring_path}/frequency_converter_up",
        intermediate_frequency=50e6,
    )
    assert cavity.xy is not None
    assert "xy" in cavity.channels
