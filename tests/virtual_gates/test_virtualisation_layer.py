import pytest
import numpy as np

from quam_builder.architecture.quantum_dots.virtual_gates.virtual_gate_set import (
    VirtualizationLayer,
)


def test_initialization():
    """Test basic initialization of VirtualizationLayer."""
    vl = VirtualizationLayer(
        source_gates=["v_g1"],
        target_gates=["P1"],
        matrix=[[2.0]],
    )
    assert vl.source_gates == ["v_g1"]
    assert vl.target_gates == ["P1"]
    assert vl.matrix == [[2.0]]


def test_calculate_inverse_matrix():
    """Test matrix inversion."""
    vl = VirtualizationLayer(
        source_gates=["v_s1", "v_s2"],
        target_gates=["P1", "P2"],
        matrix=[[2.0, 0.0], [0.0, 0.5]],
    )
    # M = [[2, 0], [0, 0.5]] => M_inv = [[0.5, 0], [0, 2.0]]
    expected_inverse = np.array([[0.5, 0.0], [0.0, 2.0]])
    np.testing.assert_array_almost_equal(
        vl.calculate_inverse_matrix(), expected_inverse
    )


def test_resolve_voltages_simple_1_to_1():
    """Test voltage resolution for a simple 1-to-1 mapping."""
    # V_phys = M_inv * V_virt. Here, M is V_virt = M * V_phys.
    # So matrix in VL is M. M_inv is calculated.
    # V_p1 = 0.5 * v_g1
    vl = VirtualizationLayer(
        source_gates=["v_g1"], target_gates=["P1"], matrix=[[2.0]]
    )  # M = [[2.0]] => M_inv = [[0.5]]

    # Input voltages must contain target gates if they are to be accumulated.
    # For this layer, P1 is a target.
    input_voltages = {"v_g1": 1.0, "P1": 0.01}  # P1 needs to be in input for +=
    resolved = vl.resolve_voltages(input_voltages, allow_extra_entries=True)
    assert len(resolved) == 1  # v_g1 is popped
    assert "v_g1" not in resolved
    assert np.isclose(resolved["P1"], 0.51)  # 0.0 + 0.5 * 1.0


def test_resolve_voltages_2_to_2():
    """Test voltage resolution for a 2x2 mapping."""
    vl = VirtualizationLayer(
        source_gates=["v_s1", "v_s2"],
        target_gates=["P1", "P2"],
        # M: v_s1 = 2*P1 + 1*P2; v_s2 = 0*P1 + 1*P2
        matrix=[[2.0, 1.0], [0.0, 1.0]],
    )
    # M_inv: P1 = 0.5*v_s1 - 0.5*v_s2; P2 = 0*v_s1 + 1*v_s2
    # M_inv = [[0.5, -0.5], [0.0, 1.0]]

    # P1, P2 need to be in input for current += implementation
    input_voltages = {"v_s1": 2.0, "v_s2": 1.0, "P1": 0.01, "P2": 0.0}
    resolved = vl.resolve_voltages(input_voltages, allow_extra_entries=True)

    assert "v_s1" not in resolved
    assert "v_s2" not in resolved
    # P1 = 0.0 + (0.5 * 2.0) + (-0.5 * 1.0) = 1.0 - 0.5 = 0.5
    # P2 = 0.0 + (0.0 * 2.0) + (1.0 * 1.0)  = 1.0
    assert np.isclose(resolved["P1"], 0.51)
    assert np.isclose(resolved["P2"], 1.0)


def test_resolve_voltages_allow_extra_false_error():
    """Test error if allow_extra_entries=False and extra gates exist."""
    vl = VirtualizationLayer(source_gates=["v_s1"], target_gates=["P1"], matrix=[[1.0]])
    with pytest.raises(AssertionError):
        vl.resolve_voltages({"v_s1": 1.0, "extra_gate": 0.5}, allow_extra_entries=False)


def test_resolve_voltages_allow_extra_true_ignored():
    """Test extra gates are preserved if allow_extra_entries=True."""
    vl = VirtualizationLayer(source_gates=["v_s1"], target_gates=["P1"], matrix=[[1.0]])
    # P1 needs to be in input for current += implementation
    input_voltages = {"v_s1": 1.0, "extra_gate": 0.5, "P1": 0.0}
    resolved = vl.resolve_voltages(input_voltages, allow_extra_entries=True)
    assert np.isclose(resolved["P1"], 1.0)
    assert resolved["extra_gate"] == 0.5
    assert "v_s1" not in resolved


def test_resolve_voltages_partial_source_gates_input():
    """Test when input voltages don't contain all source_gates of the layer."""
    vl = VirtualizationLayer(
        source_gates=["v_s1", "v_s2"],
        target_gates=["P1", "P2"],
        matrix=[[1.0, 0.0], [0.0, 1.0]],  # Identity
    )
    # P1, P2 need to be in input for current += implementation
    input_voltages = {"v_s1": 1.0, "P1": 0.0, "P2": 0.0}  # v_s2 is missing
    resolved = vl.resolve_voltages(input_voltages, allow_extra_entries=True)

    # P1 = 0.0 + 1.0 * 1.0 (from v_s1)
    assert np.isclose(resolved["P1"], 1.0)
    # P2 = 0.0 + 0.0 * 1.0 (from v_s1), no v_s2 contribution
    assert np.isclose(resolved["P2"], 0.0)
    assert "v_s1" not in resolved
    assert "v_s2" not in resolved  # Even if not in input, it's a source_gate


def test_to_dict_conversion():
    """Test that matrix is converted to list in to_dict()."""
    vl = VirtualizationLayer(
        source_gates=["v_g1"],
        target_gates=["P1"],
        matrix=np.array([[2.0]]),  # Input as numpy array
    )
    vl_dict = vl.to_dict()
    assert vl_dict == {
        "__class__": "quam_builder.architecture.quantum_dots.components.virtual_gate_set.VirtualizationLayer",
        "source_gates": ["v_g1"],
        "target_gates": ["P1"],
        "matrix": [[2.0]],
    }
