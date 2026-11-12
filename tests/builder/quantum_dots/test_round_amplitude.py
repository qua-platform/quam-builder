
import pytest

from quam_builder.architecture.quantum_dots.voltage_sequence.voltage_sequence import (
    round_amplitude,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        (0.0, 0.0),
        (0.5, 0.5),
        (0.4, 0.399993896484375),
        (-0.4, -0.399993896484375),
        (0.1, 0.100006103515625),
        (-0.1, -0.100006103515625),
    ],
)
def test_round_amplitude_python(value, expected):
    assert round_amplitude(value) == expected


def test_round_amplitude_idempotent():
    """Rounding an already rounded value should not change it."""
    value = 0.4
    rounded = round_amplitude(value)

    assert round_amplitude(rounded) == rounded
