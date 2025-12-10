import io

import numpy as np
import pytest

from quam.components.channels import SingleChannel
from quam_builder.architecture.quantum_dots.components.virtual_gate_set import (
    VirtualGateSet,
)


def _channels(names):
    return {
        name: SingleChannel(id=name, opx_output=("con", idx + 1)) for idx, name in enumerate(names)
    }


def test_tall_virtual_matrix_uses_pseudoinverse():
    gate_set = VirtualGateSet(
        id="rectangular_vgs_tall",
        channels=_channels(["P1", "P2"]),
    )
    gate_set.allow_rectangular_matrices = True

    matrix = [
        [1.0, 0.2],
        [0.0, 1.0],
        [0.4, -0.6],
    ]
    source_gates = ["V_a", "V_b", "V_c"]
    target_gates = ["P1", "P2"]

    gate_set.add_layer(
        source_gates=source_gates,
        target_gates=target_gates,
        matrix=matrix,
    )

    source_vector = np.array([0.2, -0.1, 0.3])
    expected_physical = np.linalg.pinv(np.asarray(matrix)) @ source_vector

    resolved = gate_set.resolve_voltages(dict(zip(source_gates, source_vector, strict=False)))

    assert np.allclose(
        np.array([resolved["P1"], resolved["P2"]]),
        expected_physical,
    )


def test_wide_virtual_matrix_returns_min_norm_solution():
    gate_set = VirtualGateSet(
        id="rectangular_vgs_wide",
        channels=_channels(["P1", "P2", "P3"]),
    )
    gate_set.allow_rectangular_matrices = True

    matrix = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 1.0],
    ]
    source_gates = ["V_bias", "V_sym"]
    target_gates = ["P1", "P2", "P3"]

    gate_set.add_layer(
        source_gates=source_gates,
        target_gates=target_gates,
        matrix=matrix,
    )

    source_vector = np.array([0.3, -0.2])
    expected_physical = np.linalg.pinv(np.asarray(matrix)) @ source_vector

    resolved = gate_set.resolve_voltages(dict(zip(source_gates, source_vector, strict=False)))

    resolved_vector = np.array(
        [resolved["P1"], resolved["P2"], resolved["P3"]],
    )

    # Expect the minimum-norm physical solution, which pseudo-inverse provides.
    assert np.allclose(resolved_vector, expected_physical)


def test_rectangular_roundtrip_visualisation():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    plt = pytest.importorskip("matplotlib.pyplot")

    gate_set = VirtualGateSet(
        id="rectangular_roundtrip",
        channels=_channels(["P1", "P2", "P3"]),
    )
    gate_set.allow_rectangular_matrices = True

    matrix = [
        [1.0, 0.2, -0.1],
        [0.0, 1.0, 0.5],
    ]
    source_gates = ["V_bias", "V_sym"]
    target_gates = ["P1", "P2", "P3"]
    matrix_array = np.asarray(matrix)

    gate_set.add_layer(
        source_gates=source_gates,
        target_gates=target_gates,
        matrix=matrix,
    )

    pinv_matrix = np.linalg.pinv(matrix_array)
    source_samples = np.array(
        [
            [0.12, -0.05],
            [-0.08, 0.03],
            [0.05, 0.1],
            [-0.02, -0.08],
        ]
    )
    physical_samples = np.array([pinv_matrix @ source for source in source_samples])

    resolved_samples = []
    for source_vector in source_samples:
        resolved = gate_set.resolve_voltages(dict(zip(source_gates, source_vector, strict=False)))
        resolved_samples.append(np.array([resolved["P1"], resolved["P2"], resolved["P3"]]))
    resolved_samples = np.array(resolved_samples)

    np.testing.assert_allclose(resolved_samples, physical_samples, rtol=1e-9, atol=1e-9)

    fig, axes = plt.subplots(1, 3, figsize=(9, 3), sharex=False, sharey=False)
    for idx, channel in enumerate(target_gates):
        axes[idx].plot(
            physical_samples[:, idx],
            resolved_samples[:, idx],
            "o",
            label=f"{channel}",
        )
        axes[idx].plot(
            physical_samples[:, idx],
            physical_samples[:, idx],
            "--",
            color="gray",
            linewidth=0.8,
        )
        axes[idx].set_title(channel)
        axes[idx].set_xlabel("Original physical (V)")
        axes[idx].set_ylabel("Resolved physical (V)")
        axes[idx].legend()

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
