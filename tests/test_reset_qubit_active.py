import pytest

from quam.components.channels import IQChannel
from quam.components.pulses import SquarePulse, SquareReadoutPulse

from quam_builder.architecture.superconducting.components.readout_resonator import (
    ReadoutResonatorIQ,
)
from quam_builder.architecture.superconducting.custom_gates.single_qubit_gates import (
    ResetMacro,
)
from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import (
    FixedFrequencyTransmon,
)


def _transmon_with_reset_pulses() -> FixedFrequencyTransmon:
    transmon = FixedFrequencyTransmon(id=1)
    transmon.xy = IQChannel(
        opx_output_I="{wiring_path}/opx_output_I",
        opx_output_Q="{wiring_path}/opx_output_Q",
        frequency_converter_up="{wiring_path}/frequency_converter_up",
        intermediate_frequency=-200e6,
    )
    transmon.resonator = ReadoutResonatorIQ(
        opx_input_I="",
        opx_input_Q="",
        opx_output_I="",
        opx_output_Q="",
        frequency_converter_up="",
    )
    transmon.xy.operations["x180"] = SquarePulse(amplitude=0.1, length=40)
    transmon.resonator.operations["readout"] = SquareReadoutPulse(
        length=2000, amplitude=0.01, threshold=0.0
    )
    return transmon


def test_reset_macro_inferred_duration_max_attempts_one():
    """max_attempts=1 is single-shot; duration matches one measure+pulse cycle."""
    transmon = _transmon_with_reset_pulses()
    one_cycle_s = (40 + 2000) * 1e-9

    reset_one = ResetMacro(
        reset_type="active",
        pi_pulse="x180",
        readout_pulse="readout",
        max_attempts=1,
    )
    transmon.macros["reset_one"] = reset_one

    assert reset_one.inferred_duration == one_cycle_s


@pytest.mark.parametrize("max_attempts", [0, -1, 1.0, "1", True])
def test_reset_qubit_active_rejects_non_positive_or_non_integer_max_attempts(max_attempts):
    with pytest.raises(ValueError, match="strictly positive integer"):
        ResetMacro(max_attempts=max_attempts)
