import numpy as np
import pytest

from quam.components.channels import SingleChannel

from quam_builder.architecture.quantum_dots.components.virtual_gate_set import (
    VirtualGateSet,
    VirtualizationLayer,
)


@pytest.fixture
def physical_channels():
    return {
        "P1": SingleChannel(id="P1", opx_output=("con1", 1)),
        "P2": SingleChannel(id="P2", opx_output=("con2", 1)),
    }


@pytest.fixture
def gate_set(physical_channels):
    return VirtualGateSet(id="test_virtual_gate_set", channels=physical_channels)


def test_virtualization_layer_inverse_matches_numpy():
    matrix = [[2.0, 0.0], [0.0, 0.5]]
    layer = VirtualizationLayer(
        source_gates=["v1", "v2"],
        target_gates=["P1", "P2"],
        matrix=matrix,
    )

    expected_inverse = np.linalg.inv(np.asarray(matrix))
    np.testing.assert_allclose(layer.calculate_inverse_matrix(), expected_inverse)


def test_virtualization_layer_resolve_square_matrix():
    matrix = [[1.0, 0.2], [0.3, 1.0]]
    layer = VirtualizationLayer(
        source_gates=["v_comp", "v_tilt"],
        target_gates=["P1", "P2"],
        matrix=matrix,
    )

    source_vector = np.array([0.7, -0.4])
    expected_physical = np.linalg.inv(np.asarray(matrix)) @ source_vector

    resolved = layer.resolve_voltages(
        {"v_comp": source_vector[0], "v_tilt": source_vector[1]}
    )

    assert np.isclose(resolved["P1"], expected_physical[0])
    assert np.isclose(resolved["P2"], expected_physical[1])


def test_virtual_gate_set_resolve_single_layer_square(gate_set):
    matrix = [[1.0, 0.1], [0.0, 0.8]]
    gate_set.add_layer(
        source_gates=["Vx", "Vy"], target_gates=["P1", "P2"], matrix=matrix
    )

    source_vector = np.array([0.5, 0.2])
    expected = np.linalg.inv(np.asarray(matrix)) @ source_vector

    resolved = gate_set.resolve_voltages({"Vx": source_vector[0], "Vy": source_vector[1]})

    assert np.isclose(resolved["P1"], expected[0])
    assert np.isclose(resolved["P2"], expected[1])


def test_virtual_gate_set_resolve_stacked_layers_square(gate_set):
    gate_set.add_layer(
        source_gates=["V_mid"], target_gates=["P1"], matrix=[[2.0]]
    )
    gate_set.add_layer(
        source_gates=["V_top"], target_gates=["V_mid"], matrix=[[0.5]]
    )

    resolved = gate_set.resolve_voltages({"V_top": 1.2})

    assert np.isclose(resolved["P1"], 1.2)
    assert np.isclose(resolved["P2"], 0.0)


def test_virtual_gate_set_unknown_channel_rejected(gate_set):
    gate_set.add_layer(
        source_gates=["Vx"], target_gates=["P1"], matrix=[[1.0]]
    )

    with pytest.raises(ValueError):
        gate_set.resolve_voltages({"Vx": 0.2, "unknown": 0.1})


def _make_channels(names):
    return {
        name: SingleChannel(id=name, opx_output=("con1", idx + 1))
        for idx, name in enumerate(names)
    }


def test_add_to_layer_matches_direct_matrix_sources_only():
    channels_direct = _make_channels(["P1", "P2"])
    channels_incremental = _make_channels(["P1", "P2"])
    source_all = ["V1", "V2", "V3"]
    target_all = ["P1", "P2"]
    matrix_full = [
        [1.0, 0.2],
        [0.0, 1.1],
        [0.3, -0.4],
    ]

    vgs_direct = VirtualGateSet(id="direct_sources", channels=channels_direct)
    vgs_direct.allow_rectangular_matrices = True
    vgs_direct.add_layer(source_all, target_all, matrix_full)

    vgs_incremental = VirtualGateSet(id="incremental_sources", channels=channels_incremental)
    vgs_incremental.allow_rectangular_matrices = True
    vgs_incremental.add_layer(source_all[:2], target_all, matrix_full[:2])
    vgs_incremental.add_to_layer(
        source_gates=["V3"],
        target_gates=target_all,
        matrix=[matrix_full[2]],
    )

    layer_direct = vgs_direct.layers[0]
    layer_incremental = vgs_incremental.layers[0]
    assert layer_incremental.source_gates == layer_direct.source_gates == source_all
    assert layer_incremental.target_gates == target_all
    np.testing.assert_allclose(layer_incremental.matrix, matrix_full)

    sample_voltages = {"V1": 0.4, "V2": -0.15, "V3": 0.08}
    resolved_direct = vgs_direct.resolve_voltages(sample_voltages)
    resolved_incremental = vgs_incremental.resolve_voltages(sample_voltages)
    np.testing.assert_allclose(
        [resolved_direct["P1"], resolved_direct["P2"]],
        [resolved_incremental["P1"], resolved_incremental["P2"]],
    )


def test_add_to_layer_adds_targets_and_sources():
    channels_direct = _make_channels(["P1", "P2", "P3"])
    channels_incremental = _make_channels(["P1", "P2", "P3"])
    source_all = ["V1", "V2", "V3"]
    target_all = ["P1", "P2", "P3"]
    matrix_full = [
        [1.0, 0.2, 0.0],
        [0.0, 1.1, 0.0],
        [0.3, -0.4, 0.5],
    ]

    vgs_direct = VirtualGateSet(id="direct_targets", channels=channels_direct)
    vgs_direct.allow_rectangular_matrices = True
    vgs_direct.add_layer(source_all, target_all, matrix_full)

    vgs_incremental = VirtualGateSet(id="incremental_targets", channels=channels_incremental)
    vgs_incremental.allow_rectangular_matrices = True
    vgs_incremental.add_layer(
        source_all[:2],
        target_all[:2],
        [row[:2] for row in matrix_full[:2]],
    )
    vgs_incremental.add_to_layer(
        source_gates=["V3"],
        target_gates=target_all,
        matrix=[matrix_full[2]],
    )

    layer_direct = vgs_direct.layers[0]
    layer_incremental = vgs_incremental.layers[0]
    assert layer_incremental.source_gates == source_all
    assert layer_incremental.target_gates == target_all
    np.testing.assert_allclose(layer_incremental.matrix, matrix_full)

    sample_voltages = {"V1": 0.25, "V2": -0.05, "V3": 0.12}
    resolved_direct = vgs_direct.resolve_voltages(sample_voltages)
    resolved_incremental = vgs_incremental.resolve_voltages(sample_voltages)
    np.testing.assert_allclose(
        [resolved_direct["P1"], resolved_direct["P2"], resolved_direct["P3"]],
        [resolved_incremental["P1"], resolved_incremental["P2"], resolved_incremental["P3"]],
    )


def test_add_to_layer_overwrites_existing_element_with_warning():
    channels = _make_channels(["P1"])
    vgs = VirtualGateSet(id="overwrite_test", channels=channels)
    vgs.allow_rectangular_matrices = True
    vgs.add_layer(source_gates=["V1"], target_gates=["P1"], matrix=[[1.0]])

    with pytest.warns(UserWarning, match="Overwriting virtualization matrix element"):
        vgs.add_to_layer(
            source_gates=["V1"],
            target_gates=["P1"],
            matrix=[[2.0]],
        )

    resolved = vgs.resolve_voltages({"V1": 1.0})
    assert np.isclose(resolved["P1"], 0.5)  # 2 * P1 = V1 => P1 = 0.5 * V1
