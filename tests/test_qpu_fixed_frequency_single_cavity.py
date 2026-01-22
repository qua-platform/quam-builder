from quam_builder.architecture.superconducting.qpu.fixed_frequency_single_cavity_quam import (
    FixedFrequencyTransmonSingleCavityQuam,
)
from quam_builder.architecture.superconducting.qubit import (
    FixedFrequencyTransmon,
    BosonicMode,
)


def test_qpu_instantiation():
    """QPU can be instantiated with empty qubits and cavities."""
    qpu = FixedFrequencyTransmonSingleCavityQuam()
    assert qpu.qubits == {}
    assert qpu.cavities == {}


def test_type_classes():
    """Verify the QPU has correct type hints for qubits and cavities."""
    assert FixedFrequencyTransmonSingleCavityQuam.qubit_type == FixedFrequencyTransmon
    assert FixedFrequencyTransmonSingleCavityQuam.cavity_type == BosonicMode


def test_add_qubits_and_cavities():
    """QPU supports multiple qubits and multiple cavities."""
    qpu = FixedFrequencyTransmonSingleCavityQuam()

    # Add transmon qubits
    qpu.qubits["q0"] = FixedFrequencyTransmon(id="q0")
    qpu.qubits["q1"] = FixedFrequencyTransmon(id="q1")

    # Add bosonic cavities
    qpu.cavities["c0"] = BosonicMode(id="c0")
    qpu.cavities["c1"] = BosonicMode(id="c1")

    assert len(qpu.qubits) == 2
    assert len(qpu.cavities) == 2
    assert "q0" in qpu.qubits
    assert "q1" in qpu.qubits
    assert "c0" in qpu.cavities
    assert "c1" in qpu.cavities
