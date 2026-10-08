import numpy as np
from quam_builder.architecture.quantum_dots.components.virtual_gate_set import VirtualGateSet

class DummyChannel:
    pass

def to_quam_matrix(apply_matrix):
    apply_T = np.asarray(apply_matrix, dtype=float).T
    return np.linalg.inv(apply_T).tolist()

def test_shared_targets_across_layers():
    vgs = VirtualGateSet(
        id="test_vgs",
        channels={
            "P1": DummyChannel(),
            "P2": DummyChannel(),
            "B12": DummyChannel(),
        }
    )

    # Lowest virtual layer
    vgs.add_layer(
        layer_id="dummy_normalized",
        source_gates=["nP1", "nP2"],
        target_gates=["P1", "P2"],
        matrix=[
            [1.0, 0.0],
            [0.0, 1.0],
        ],
    )

    # Branch 1
    vgs.add_layer(
        layer_id="detuning",
        source_gates=["e", "u"], # e = 1.0*nP1 + (-1.0)*nP2, u = 1.0*nP1 + 1.0*nP2
        target_gates=["nP1", "nP2"], 
        matrix=
            to_quam_matrix( 
                (
                    [1.0, -1.0],
                    [1.0,  1.0]
                )
            )
    )

    # Branch 2 - reuse nP1/nP2 as targets
    vgs.add_layer(
        layer_id="barrier_compensation",
        source_gates=["J12", "y1", "y2"], # J12 = B12 + (-0.2)*nP1 + (-0.3)*nP2, y1 and y2 are dummy virtual gates to keep the matrix square
        target_gates=["B12", "nP1", "nP2"],
        matrix=
            to_quam_matrix(
                (
                    [1.0, -0.2, -0.3],
                    [0  ,  1.0,    0],
                    [0  ,    0,  1.0],
                )
            )
    )

    r_e = vgs.resolve_voltages({"e": 0.1})
    r_J12 = vgs.resolve_voltages({"J12": 0.2})
    r_both = vgs.resolve_voltages({"e": 0.1, "J12": 0.2})

    print("e only:", r_e)
    print("J12 only:", r_J12)
    print("both:", r_both)

    for gate in ["P1", "P2", "B12"]:
        assert np.isclose(
            r_both[gate],
            r_e[gate] + r_J12[gate],
        )