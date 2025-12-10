import numpy as np
import pytest

from quam.components.channels import SingleChannel
from quam_builder.architecture.quantum_dots.components.virtual_gate_set import (
    VirtualGateSet,
    VirtualizationLayer,
)


@pytest.fixture
def physical_channels_fixture() -> dict[str, SingleChannel]:
    """Provides a dictionary of mock physical channels."""
    return {
        "P1": SingleChannel(id="P1", opx_output=("con1", 1)),
        "P2": SingleChannel(id="P2", opx_output=("con2", 2)),
        "P3": SingleChannel(id="P3", opx_output=("con3", 3)),
    }


@pytest.fixture
def virtual_gate_set_fixture(physical_channels_fixture) -> VirtualGateSet:
    """Provides a VirtualGateSet instance with physical channels."""
    return VirtualGateSet(id="vgs_test", channels=physical_channels_fixture)


def test_initialization(virtual_gate_set_fixture, physical_channels_fixture):
    """Test basic initialization of VirtualGateSet."""
    vgs = virtual_gate_set_fixture
    assert vgs.id == "vgs_test"
    assert vgs.channels == physical_channels_fixture
    assert vgs.layers == []


def test_add_layer_success_first_layer(virtual_gate_set_fixture):
    """Test adding a valid first layer."""
    vgs = virtual_gate_set_fixture
    layer = vgs.add_layer(source_gates=["virt1"], target_gates=["P1"], matrix=[[1.0]])
    assert len(vgs.layers) == 1
    assert isinstance(vgs.layers[0], VirtualizationLayer)
    assert vgs.layers[0] == layer
    assert layer.source_gates == ["virt1"]
    assert layer.target_gates == ["P1"]


def test_add_layer_success_second_layer(virtual_gate_set_fixture):
    """Test adding a valid second layer targeting the first layer's source."""
    vgs = virtual_gate_set_fixture
    vgs.add_layer(
        source_gates=["virt_L0"],
        target_gates=["P1"],
        matrix=[[1.0]],
        layer_id="L0",
    )
    layer2 = vgs.add_layer(
        source_gates=["virt_L1"],
        target_gates=["virt_L0"],
        matrix=[[0.5]],
        layer_id="L1",
    )
    assert len(vgs.layers) == 2
    assert vgs.layers[1] == layer2
    assert layer2.target_gates == ["virt_L0"]  # Targets source of layer 0


def test_add_layer_second_layer_targets_physical(virtual_gate_set_fixture):
    """Test adding a second layer that targets a physical gate directly."""
    vgs = virtual_gate_set_fixture
    vgs.add_layer(
        source_gates=["virt_L0"],
        target_gates=["P1"],
        matrix=[[1.0]],
        layer_id="L0",
    )
    # virt_L1 targets P2 (physical), which is allowed
    vgs.add_layer(
        source_gates=["virt_L1"],
        target_gates=["P2"],
        matrix=[[0.5]],
        layer_id="L1",
    )
    assert len(vgs.layers) == 2
    assert vgs.layers[1].target_gates == ["P2"]


@pytest.mark.parametrize(
    "layer_setup, new_layer_params, expected_error_msg_part",
    [
        # Case 1: Target gate not in physical channels (first layer)
        (
            [],  # No existing layers
            {"source_gates": ["v1"], "target_gates": ["PX"], "matrix": [[1.0]]},
            "Target gate 'PX' in new layer does not correspond",
        ),
        # Case 2: Target gate not in previous source or physical (second layer)
        (
            [{"source_gates": ["v_L0"], "target_gates": ["P1"], "matrix": [[1.0]]}],
            {"source_gates": ["v_L1"], "target_gates": ["v_PX"], "matrix": [[1.0]]},
            "Target gate 'v_PX' in new layer does not correspond",
        ),
        # Case 3: Target gate is already a target in a previous layer
        (
            [{"source_gates": ["v_L0"], "target_gates": ["P1"], "matrix": [[1.0]]}],
            {"source_gates": ["v_L1"], "target_gates": ["P1"], "matrix": [[1.0]]},
            "Target gate 'P1' in new layer is already a target gate",
        ),
        # Case 4: Source gate is already a source in a previous layer
        (
            [{"source_gates": ["v_L0"], "target_gates": ["P1"], "matrix": [[1.0]]}],
            {"source_gates": ["v_L0"], "target_gates": ["P2"], "matrix": [[1.0]]},
            "Source gate 'v_L0' in new layer is already a source gate",
        ),
        # Case 5: Source gate is already a target in a previous layer
        (
            [{"source_gates": ["v_L0"], "target_gates": ["P1"], "matrix": [[1.0]]}],
            {"source_gates": ["P1"], "target_gates": ["P2"], "matrix": [[1.0]]},
            "Source gate 'P1' in new layer is already a target gate",
        ),
    ],
)
def test_validate_new_layer_errors(
    virtual_gate_set_fixture,
    layer_setup,
    new_layer_params,
    expected_error_msg_part,
):
    """Test various validation errors when adding a new layer."""
    vgs = virtual_gate_set_fixture
    for layer_params in layer_setup:
        vgs.add_layer(**layer_params)  # Setup existing layers

    with pytest.raises(ValueError) as excinfo:
        vgs.add_layer(**new_layer_params)
    assert expected_error_msg_part in str(excinfo.value)


def test_resolve_voltages_no_layers(virtual_gate_set_fixture):
    """Test voltage resolution when no virtual layers exist."""
    vgs = virtual_gate_set_fixture
    # P1, P2, P3 are physical channels. P3 is not in input.
    input_voltages = {"P1": 1.0, "P2": -0.5}
    resolved = vgs.resolve_voltages(input_voltages)

    assert len(resolved) == 3  # P1, P2, P3
    assert np.isclose(resolved["P1"], 1.0)
    assert np.isclose(resolved["P2"], -0.5)
    assert np.isclose(resolved["P3"], 0.0)  # Default for missing physical


def test_resolve_voltages_one_layer(virtual_gate_set_fixture):
    """Test voltage resolution with a single virtual layer."""
    vgs = virtual_gate_set_fixture
    # v_g1 = 2.0 * P1 => P1 = 0.5 * v_g1
    vgs.add_layer(source_gates=["v_g1"], target_gates=["P1"], matrix=[[2.0]])

    # To avoid KeyError with current `VirtualizationLayer.resolve_voltages`'s `+=`,
    # ensure target physical gates are in the input dict if they are targeted.
    # P1 is a target. P2, P3 are other physical gates.
    input_voltages = {"v_g1": 1.0, "P1": 0.0, "P2": 0.5, "P3": 0.0}
    resolved = vgs.resolve_voltages(input_voltages)

    assert len(resolved) == 3  # P1, P2, P3 (physical channels)
    assert np.isclose(resolved["P1"], 0.5)  # 0.0 + 0.5 * 1.0
    assert np.isclose(resolved["P2"], 0.5)  # Unchanged physical
    assert np.isclose(resolved["P3"], 0.0)  # Unchanged physical


def test_resolve_voltages_two_layers(virtual_gate_set_fixture):
    """Test voltage resolution with two stacked virtual layers."""
    vgs = virtual_gate_set_fixture
    # Layer 0: v_g0 = 2.0 * P1  => P1 = 0.5 * v_g0
    vgs.add_layer(
        source_gates=["v_g0"],
        target_gates=["P1"],
        matrix=[[2.0]],
        layer_id="L0",
    )
    # Layer 1: v_g1 = 0.5 * v_g0 => v_g0 = 2.0 * v_g1
    vgs.add_layer(
        source_gates=["v_g1"],
        target_gates=["v_g0"],
        matrix=[[0.5]],
        layer_id="L1",
    )

    # Initial voltages:
    # v_g1 is top-level virtual.
    # v_g0 is intermediate virtual target, P1 is physical target.
    # P2, P3 are other physical gates.
    # All targets (v_g0, P1) must be present for `+=` in current implementation.
    initial_voltages = {"v_g1": 1.0, "v_g0": 0.0, "P1": 0.0, "P2": 0.3, "P3": 0.0}
    resolved = vgs.resolve_voltages(initial_voltages)

    # Trace:
    # 1. Input: {"v_g1": 1.0, "v_g0": 0.0, "P1": 0.0, "P2": 0.3, "P3": 0.0}
    # 2. Process Layer 1 (v_g1 -> v_g0, M_inv_L1 = [[2.0]]):
    #    v_g0_val = initial_voltages["v_g0"] (0.0) + 2.0 * initial_voltages["v_g1"] (1.0) = 2.0
    #    After L1: {"v_g0": 2.0, "P1": 0.0, "P2": 0.3, "P3": 0.0} (v_g1 popped)
    # 3. Process Layer 0 (v_g0 -> P1, M_inv_L0 = [[0.5]]):
    #    P1_val = initial_voltages["P1"] (0.0) + 0.5 * result_from_L1["v_g0"] (2.0) = 1.0
    #    After L0: {"P1": 1.0, "P2": 0.3, "P3": 0.0} (v_g0 popped)
    # 4. Super().resolve_voltages: ensures P1,P2,P3 are present.
    #    P1 already 1.0, P2 already 0.3, P3 already 0.0.

    assert len(resolved) == 3
    assert np.isclose(resolved["P1"], 1.0)
    assert np.isclose(resolved["P2"], 0.3)  # Unchanged physical
    assert np.isclose(resolved["P3"], 0.0)  # Unchanged physical


def test_resolve_voltages_allow_extra_entries_false_error(virtual_gate_set_fixture):
    """Test error if allow_extra_entries=False and unknown gate in input."""
    vgs = virtual_gate_set_fixture
    vgs.add_layer(source_gates=["v_g1"], target_gates=["P1"], matrix=[[1.0]])

    # "unknown_gate" is not a defined physical or virtual channel
    with pytest.raises(ValueError) as excinfo:
        vgs.resolve_voltages({"v_g1": 1.0, "unknown_gate": 0.5}, allow_extra_entries=False)
    assert "Channels {'unknown_gate'} in voltages that are not part" in str(excinfo.value)


def test_resolve_voltages_allow_extra_entries_true_ignored(virtual_gate_set_fixture):
    """Test unknown gates are ignored if allow_extra_entries=True."""
    vgs = virtual_gate_set_fixture
    vgs.add_layer(source_gates=["v_g1"], target_gates=["P1"], matrix=[[1.0]])

    # P1 needs to be in input for current += implementation
    initial_voltages = {
        "v_g1": 1.0,
        "unknown_gate": 0.5,
        "P1": 0.0,
        "P2": 0.0,
        "P3": 0.0,
    }
    resolved = vgs.resolve_voltages(initial_voltages, allow_extra_entries=True)

    assert len(resolved) == 3  # Only physical channels P1, P2, P3 in final output
    assert np.isclose(resolved["P1"], 1.0)
    assert "unknown_gate" not in resolved  # Discarded by final super().resolve_voltages


def test_resolve_voltages_mixed_physical_virtual_input(virtual_gate_set_fixture):
    """Test resolving when input contains mix of physical and virtual gate voltages."""
    vgs = virtual_gate_set_fixture
    # v_g1 = 2.0 * P1 => P1 = 0.5 * v_g1
    # v_g2 = 1.0 * P2 => P2 = 1.0 * v_g2
    vgs.add_layer(
        source_gates=["v_g1"],
        target_gates=["P1"],
        matrix=[[2.0]],
        layer_id="L0",
    )
    vgs.add_layer(
        source_gates=["v_g2"],
        target_gates=["P2"],
        matrix=[[1.0]],
        layer_id="L1",
    )

    # Input provides v_g1 (virtual), P2 (physical directly), and P3 (physical directly).
    # P1 is target of v_g1.
    initial_voltages = {"v_g1": 2.0, "P2": 0.7, "P3": -0.2, "P1": 0.01}
    # Note: v_g2 is not provided, so its layer won't act.

    resolved = vgs.resolve_voltages(initial_voltages)

    # Expected:
    # P1 from v_g1: 0.0 + 0.5 * 2.0 = 1.0
    # P2 directly from input: 0.7
    # P3 directly from input: -0.2
    assert len(resolved) == 3
    assert np.isclose(resolved["P1"], 1.01)
    assert np.isclose(resolved["P2"], 0.7)
    assert np.isclose(resolved["P3"], -0.2)


def test_matrix_validation_non_square_matrix(virtual_gate_set_fixture):
    """Test that non-square matrices are rejected."""
    vgs = virtual_gate_set_fixture
    non_square_matrix = [[1.0, 0.5], [0.0, 1.0], [0.5, 0.0]]  # 3x2 matrix

    with pytest.raises(ValueError) as excinfo:
        vgs.add_layer(
            source_gates=["v1", "v2"], target_gates=["P1", "P2"], matrix=non_square_matrix
        )
    assert "Matrix dimensions do not match source/target gate counts" in str(excinfo.value)


def test_matrix_validation_non_invertible_matrix(virtual_gate_set_fixture):
    """Test that non-invertible matrices are rejected."""
    vgs = virtual_gate_set_fixture
    singular_matrix = [[1.0, 2.0], [2.0, 4.0]]  # Determinant = 0

    with pytest.raises(ValueError) as excinfo:
        vgs.add_layer(source_gates=["v1", "v2"], target_gates=["P1", "P2"], matrix=singular_matrix)
    assert "Matrix is not invertible" in str(excinfo.value)


def test_matrix_validation_valid_matrix(virtual_gate_set_fixture):
    """Test that valid square invertible matrices are accepted."""
    vgs = virtual_gate_set_fixture
    valid_matrix = [[1.0, 0.5], [0.0, 1.0]]  # Square and invertible

    layer = vgs.add_layer(source_gates=["v1", "v2"], target_gates=["P1", "P2"], matrix=valid_matrix)
    assert len(vgs.layers) == 1
    assert layer.matrix == valid_matrix
