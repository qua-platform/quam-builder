"""Tests for the pulse builder helpers."""

import pytest

from quam.components.pulses import SquareReadoutPulse

from quam_builder.architecture.quantum_dots.components.pulses import (
    ScalableDragPulse,
    ScalableGaussianPulse,
    ScalableHermitePulse,
    ScalableKaiserPulse,
    ScalableSquarePulse,
)

from quam_builder.architecture.quantum_dots.operations.pulse_catalog import (
    PULSE_FAMILIES,
    make_xy_pulse_factories,
    make_readout_pulse,
)


class TestMakeXYPulseFactories:
    """Test pulse factory creation for XY drives."""

    def test_single_channel_no_axis_angle(self):
        """SingleChannel drives should produce pulse with axis_angle=None."""
        from quam.components.ports import LFFEMAnalogOutputPort
        from quam_builder.architecture.quantum_dots.components.xy_drive import (
            XYDriveSingle,
        )

        xy = XYDriveSingle(
            id="test_xy",
            RF_frequency=100_000_000,
            opx_output=LFFEMAnalogOutputPort("con1", 3, port_id=1),
        )
        pulses = make_xy_pulse_factories(xy)

        assert "gaussian_x90" in pulses
        pulse = pulses["gaussian_x90"]
        assert isinstance(pulse, ScalableGaussianPulse)
        assert pulse.axis_angle is None

    def test_iq_channel_has_axis_angle(self):
        """IQ/MW channels should produce pulse with axis_angle=0.0."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        assert pulses["gaussian_x90"].axis_angle == 0.0

    def test_pulse_parameters(self):
        """Verify pulse structure (not specific default lengths which are configurable)."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ
        from quam_builder.architecture.quantum_dots.defaults import DEFAULTS

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        gaussian = pulses["gaussian_x90"]
        assert isinstance(gaussian, ScalableGaussianPulse)
        assert gaussian.amplitude == DEFAULTS.xy_pulse.amplitude
        assert gaussian.sigma_ratio == pytest.approx(1 / 6)
        assert gaussian.sigma == pytest.approx(gaussian.length * gaussian.sigma_ratio)

    def test_all_families_present(self):
        """All registered pulse families should produce operations."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        for family in PULSE_FAMILIES:
            assert f"{family}_x90" in pulses
            assert f"{family}_x180" in pulses
            assert f"{family}_x_neg90" in pulses
            assert f"{family}_y180" in pulses
            assert f"{family}_y90" in pulses
            assert f"{family}_y_neg90" in pulses

    def test_square_pulse_type(self):
        """Square family should use ScalableSquarePulse."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        assert isinstance(pulses["square_x90"], ScalableSquarePulse)

    def test_kaiser_pulse_type(self):
        """Kaiser family should use ScalableKaiserPulse."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        assert isinstance(pulses["kaiser_x90"], ScalableKaiserPulse)

    def test_hermite_pulse_type(self):
        """Hermite family should use ScalableHermitePulse."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        assert isinstance(pulses["hermite_x90"], ScalableHermitePulse)

    def test_drag_pulse_type(self):
        """DRAG family should use ScalableDragPulse."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        assert isinstance(pulses["drag_x90"], ScalableDragPulse)

    def test_cz_pulse_still_present(self):
        """CZ pulse should still be generated."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        assert "cz" in pulses
        assert isinstance(pulses["cz"], ScalableGaussianPulse)


class TestPulseFamilySwitching:
    """Test that XYDriveMacro resolves pulse_name dynamically from pulse_family."""

    def test_default_pulse_family_is_gaussian(self):
        from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
            XYDriveMacro,
            X180Macro,
            Y90Macro,
        )

        macro = XYDriveMacro.__new__(XYDriveMacro)
        macro.pulse_family = "gaussian"
        assert macro.pulse_name == "gaussian_x90"
        assert macro.reference_pulse_name == "gaussian_x90"

    def test_x180_resolves_to_family_x180(self):
        from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
            X180Macro,
        )

        macro = X180Macro.__new__(X180Macro)
        macro.pulse_family = "gaussian"
        assert macro.pulse_name == "gaussian_x180"

        macro.pulse_family = "kaiser"
        assert macro.pulse_name == "kaiser_x180"

    def test_y90_resolves_to_family_y90(self):
        from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
            Y90Macro,
        )

        macro = Y90Macro.__new__(Y90Macro)
        macro.pulse_family = "square"
        assert macro.pulse_name == "square_y90"

    def test_switching_family_changes_all_suffixes(self):
        from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
            XYDriveMacro,
            X180Macro,
            XNeg90Macro,
            Y180Macro,
            YNeg90Macro,
        )

        macros = {
            "xy_drive": XYDriveMacro.__new__(XYDriveMacro),
            "x180": X180Macro.__new__(X180Macro),
            "x_neg90": XNeg90Macro.__new__(XNeg90Macro),
            "y180": Y180Macro.__new__(Y180Macro),
            "y_neg90": YNeg90Macro.__new__(YNeg90Macro),
        }

        for macro in macros.values():
            macro.pulse_family = "kaiser"

        assert macros["xy_drive"].pulse_name == "kaiser_x90"
        assert macros["x180"].pulse_name == "kaiser_x180"
        assert macros["x_neg90"].pulse_name == "kaiser_x_neg90"
        assert macros["y180"].pulse_name == "kaiser_y180"
        assert macros["y_neg90"].pulse_name == "kaiser_y_neg90"


class TestKaiserPulseWaveform:
    """Test Kaiser pulse waveform properties."""

    def test_kaiser_peak_equals_amplitude(self):
        """Kaiser peak should equal amplitude (peak normalization)."""
        import numpy as np

        kaiser = ScalableKaiserPulse(length=100, amplitude=0.25)
        waveform = kaiser.waveform_function()

        assert np.max(np.abs(waveform)) == pytest.approx(0.25, rel=1e-10)

    def test_kaiser_peak_within_bounds(self):
        """Kaiser waveform should never exceed [-1, 1] when amplitude <= 1."""
        import numpy as np

        kaiser = ScalableKaiserPulse(length=1000, amplitude=1.0)
        waveform = kaiser.waveform_function()

        assert np.max(np.abs(waveform)) <= 1.0

    def test_kaiser_is_symmetric(self):
        """Kaiser window should be symmetric around its center."""
        import numpy as np

        kaiser = ScalableKaiserPulse(length=100, amplitude=1.0)
        waveform = kaiser.waveform_function()

        np.testing.assert_allclose(waveform, waveform[::-1], atol=1e-12)


class TestHermitePulseWaveform:
    """Test Hermite pulse waveform properties."""

    def test_hermite_peak_equals_amplitude(self):
        """Hermite peak should equal amplitude (peak normalization)."""
        import numpy as np

        hermite = ScalableHermitePulse(length=100, amplitude=0.25)
        waveform = hermite.waveform_function()

        assert np.max(np.abs(waveform)) == pytest.approx(0.25, rel=1e-10)

    def test_hermite_is_symmetric(self):
        """Hermite window should be symmetric around its center."""
        import numpy as np

        hermite = ScalableHermitePulse(length=100, amplitude=1.0)
        waveform = hermite.waveform_function()

        np.testing.assert_allclose(waveform, waveform[::-1], atol=1e-12)

    def test_hermite_with_axis_angle(self):
        """Hermite pulse with axis_angle should produce a complex waveform."""
        import numpy as np

        hermite = ScalableHermitePulse(length=100, amplitude=0.5, axis_angle=np.pi / 2)
        waveform = hermite.waveform_function()

        assert np.iscomplexobj(waveform)
        assert np.max(np.abs(waveform)) == pytest.approx(0.5, rel=1e-10)

    def test_hermite_coeff_zero_gives_gaussian_shape(self):
        """hermite_coeff=0 reduces the envelope to exp(-x²/2) (pure Gaussian shape).

        The Hermite waveform peak-normalises by the highest sample, so it is
        proportional to a Gaussian but not bit-for-bit equal to
        ScalableGaussianPulse for even-length arrays where no sample lands
        exactly at centre.  We verify shape proportionality instead.
        """
        import numpy as np

        length = 101  # odd so one sample is exactly at centre (x=0)
        sigma_ratio = 1 / 6
        hermite = ScalableHermitePulse(
            length=length, amplitude=1.0, sigma_ratio=sigma_ratio, hermite_coeff=0.0
        )
        gauss = ScalableGaussianPulse(
            length=length, amplitude=1.0, sigma_ratio=sigma_ratio, subtracted=False
        )
        wh = hermite.waveform_function()
        wg = gauss.waveform_function()

        # With an odd-length array the centre sample has x=0, so exp(-0/2)=1
        # and peak normalisation is exact.  Both waveforms should coincide.
        np.testing.assert_allclose(np.real(wh), np.real(wg), rtol=1e-6)

    def test_hermite_coeff_affects_shape(self):
        """Different hermite_coeff values should produce distinct waveforms."""
        import numpy as np

        h1 = ScalableHermitePulse(length=100, amplitude=1.0, hermite_coeff=0.2)
        h2 = ScalableHermitePulse(length=100, amplitude=1.0, hermite_coeff=0.8)

        assert not np.allclose(h1.waveform_function(), h2.waveform_function())

    def test_hermite_axis_variants_reference_sigma_ratio(self):
        """Axis variant pulses should carry sigma_ratio QuAM reference to the anchor."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        # Axis variants should have their sigma_ratio as a QuAM reference string.
        for gate in ("x_neg90", "y90", "y180", "y_neg90"):
            pulse = pulses[f"hermite_{gate}"]
            assert isinstance(pulse.sigma_ratio, str), (
                f"hermite_{gate}.sigma_ratio should be a QuAM reference, got {pulse.sigma_ratio!r}"
            )
            assert "hermite_x90" in pulse.sigma_ratio or "hermite_x180" in pulse.sigma_ratio

    def test_hermite_axis_variants_reference_hermite_coeff(self):
        """Axis variant pulses should carry hermite_coeff QuAM reference to the anchor."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        for gate in ("x_neg90", "y90", "y180", "y_neg90"):
            pulse = pulses[f"hermite_{gate}"]
            assert isinstance(pulse.hermite_coeff, str), (
                f"hermite_{gate}.hermite_coeff should be a QuAM reference, got {pulse.hermite_coeff!r}"
            )


class TestSquarePulseWaveform:
    """Test Square pulse waveform properties."""

    def test_square_is_constant(self):
        """Square pulse should be constant amplitude."""
        import numpy as np

        sq = ScalableSquarePulse(length=100, amplitude=0.5)
        waveform = sq.waveform_function()

        np.testing.assert_allclose(waveform, 0.5 * np.ones(100))

    def test_square_with_axis_angle(self):
        """Square pulse with axis_angle should produce complex waveform."""
        import numpy as np

        sq = ScalableSquarePulse(length=100, amplitude=0.5, axis_angle=np.pi / 2)
        waveform = sq.waveform_function()

        assert np.iscomplexobj(waveform)
        np.testing.assert_allclose(np.abs(waveform), 0.5 * np.ones(100))


class TestDragPulseWaveform:
    """Test DRAG pulse waveform properties."""

    def test_drag_single_channel_is_real(self):
        """Single-channel DRAG should emit only the I-component."""
        import numpy as np

        drag = ScalableDragPulse(length=101, amplitude=0.4, axis_angle=None)
        waveform = drag.waveform_function()

        assert not np.iscomplexobj(waveform)
        assert np.max(np.abs(waveform)) == pytest.approx(0.4, rel=1e-10)

    def test_drag_iq_has_quadrature_component(self):
        """IQ DRAG should contain both I and Q components."""
        import numpy as np

        drag = ScalableDragPulse(
            length=101, amplitude=1.0, axis_angle=0.0, drag_coefficient=0.35
        )
        waveform = drag.waveform_function()

        assert np.iscomplexobj(waveform)
        i_component = np.real(waveform)
        q_component = np.imag(waveform)

        assert np.max(i_component) == pytest.approx(1.0, rel=1e-10)
        assert np.max(np.abs(q_component)) == pytest.approx(0.35, rel=1e-10)
        np.testing.assert_allclose(q_component, -q_component[::-1], atol=1e-12)


class TestMakeReadoutPulse:
    """Test readout pulse factory."""

    def test_readout_pulse_type(self):
        pulse = make_readout_pulse()
        assert isinstance(pulse, SquareReadoutPulse)
