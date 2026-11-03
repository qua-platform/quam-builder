from quam_builder.architecture.superconducting.components.tunable_coupler import (
    TunableCoupler,
)
from quam_builder.architecture.superconducting.qubit_pair import (
    FixedFrequencyTransmonPair,
)
from quam_builder.builder.superconducting.add_default_pulses import (
    add_default_transmon_pair_pulses,
)


def test_coupler_defaults_to_none():
    pair = FixedFrequencyTransmonPair(id="q1-2")
    assert pair.coupler is None


def test_coupler_is_serialized():
    pair = FixedFrequencyTransmonPair(
        id="q1-2",
        coupler=TunableCoupler(id="coupler_q1_q2", opx_output="#/wiring/opx_output"),
    )

    pair_dict = pair.to_dict()

    assert "coupler" in pair_dict
    assert pair_dict["coupler"]["id"] == "coupler_q1_q2"
    assert pair_dict["coupler"]["opx_output"] == "#/wiring/opx_output"


def test_default_pulses_added_to_coupler():
    pair = FixedFrequencyTransmonPair(id="q1-2")
    pair.coupler = TunableCoupler(id="coupler_q1_q2", opx_output="#/wiring/opx_output")

    add_default_transmon_pair_pulses(pair)

    assert "const" in pair.coupler.operations
    assert "coupler" in pair.to_dict()
