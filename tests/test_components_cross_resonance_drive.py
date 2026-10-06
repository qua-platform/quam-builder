from quam.components.channels import IQChannel
from quam.components.pulses import SquarePulse
from quam_builder.architecture.superconducting.components.cross_resonance_drive import (
    CrossResonanceDriveIQ,
    CrossResonanceDriveMW,
)
from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import (
    FixedFrequencyTransmon,
)
from quam_builder.architecture.superconducting.qubit_pair.fixed_frequency_transmon_pair import (
    FixedFrequencyTransmonPair,
)
from quam_builder.builder.superconducting.add_default_pulses import (
    add_default_transmon_pair_pulses,
)
from quam_builder.common.pulses import FlatTopGaussianPulse

ALL_CR = [
    CrossResonanceDriveIQ(
        opx_output_I="",
        opx_output_Q="",
        frequency_converter_up="",
    ),
    CrossResonanceDriveMW(opx_output=""),
]


def _target_qubit_with_xy(qubit_id="q1") -> FixedFrequencyTransmon:
    target = FixedFrequencyTransmon(id=qubit_id)
    target.xy = IQChannel(
        opx_output_I="",
        opx_output_Q="",
        frequency_converter_up="",
        intermediate_frequency=-200e6,
    )
    return target


def test_class_attribute():
    for cr in ALL_CR:
        assert hasattr(cr, "intermediate_frequency")
        assert cr.intermediate_frequency == "#./inferred_intermediate_frequency"
        assert hasattr(cr, "operations")
        assert cr.operations == {}


def test_upconverter_frequency_property():
    for cr in ALL_CR:
        assert hasattr(type(cr), "upconverter_frequency")


def test_pair_cross_resonance_default_none():
    pair = FixedFrequencyTransmonPair(id="q0_q1")
    assert hasattr(pair, "cross_resonance")
    assert pair.cross_resonance is None


def test_default_cross_resonance_pulses():
    for cr in ALL_CR:
        pair_id = "q0_q1"
        pair = FixedFrequencyTransmonPair(
            id=pair_id,
            cross_resonance=cr,
            qubit_target=_target_qubit_with_xy(),
        )
        add_default_transmon_pair_pulses(pair)

        assert "square" in pair.cross_resonance.operations
        assert "flattop" in pair.cross_resonance.operations

        assert f"cr_{pair_id}_square" in pair.qubit_target.xy.operations
        assert f"cr_{pair_id}_flattop" in pair.qubit_target.xy.operations


def test_default_cross_resonance_pulses_skipped_when_none():
    pair = FixedFrequencyTransmonPair(id="q0_q1", cross_resonance=None)
    add_default_transmon_pair_pulses(pair)
    assert pair.cross_resonance is None
