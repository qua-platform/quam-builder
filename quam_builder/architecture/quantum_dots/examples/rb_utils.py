"""Single-qubit randomized benchmarking utilities for spin qubits.

This module provides helper functions and analysis routines for single-qubit RB,
including PPU-friendly lookup tables for Clifford composition, inversion, and
decomposition into native spin-qubit gates.

Native gate set used for decompositions:
- X90, X180: Physical X rotations (Gaussian pulses)
- Y90, Y180: Physical Y rotations (Gaussian pulses with 90° phase)
- Z90, Z180, Z270: Virtual Z rotations (frame rotations, zero duration)
- Idle: Identity gate (removed in decomposition)
"""

from dataclasses import dataclass, field

from matplotlib import pyplot as plt
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Clifford
from scipy.optimize import curve_fit
import xarray as xr


# =============================================================================
# Constants
# =============================================================================

# Single-qubit gate mapping for QUA switch/case implementation
# Maps gate names to integers for efficient execution
SINGLE_QUBIT_GATE_MAP = {
    "x90": 0,  # X90 (pi/2 rotation about X)
    "x180": 1,  # X180 (pi rotation about X)
    "y90": 2,  # Y90 (pi/2 rotation about Y)
    "y180": 3,  # Y180 (pi rotation about Y)
    "z90": 4,  # Virtual Z (pi/2) - zero duration
    "z180": 5,  # Virtual Z (pi) - zero duration
    "z270": 6,  # Virtual Z (3pi/2) - zero duration
    "idle": 7,  # Identity / idle
}

EPS = 1e-8


def get_gate_name(gate) -> str:
    """Extract standardized gate name from a Qiskit gate.

    Maps Qiskit gate names to our native spin qubit gate set:
    - sx -> x90
    - x -> x180
    - rz(pi/2) -> z90
    - rz(pi) -> z180
    - rz(3pi/2) -> z270
    - id -> idle
    """
    name = gate.name.lower()

    if name == "rz":
        angle = gate.params[0]
        # Normalize angle to [0, 2pi)
        angle = angle % (2 * np.pi)
        if np.isclose(angle, np.pi / 2, atol=EPS):
            return "z90"
        if np.isclose(angle, np.pi, atol=EPS):
            return "z180"
        if np.isclose(angle, 3 * np.pi / 2, atol=EPS) or np.isclose(
            angle, -np.pi / 2 % (2 * np.pi), atol=EPS
        ):
            return "z270"
        if np.isclose(angle, 0, atol=EPS) or np.isclose(angle, 2 * np.pi, atol=EPS):
            return "idle"
        raise ValueError(f"Unsupported RZ angle: {angle} ({angle * 180 / np.pi:.1f} deg)")

    if name == "sx":
        return "x90"
    if name == "x":
        return "x180"
    if name == "id":
        return "idle"

    return name


def process_circuit_to_integers(circuit: QuantumCircuit) -> list[int]:
    """Convert a quantum circuit to a list of gate integers.

    Each gate is converted to an integer for efficient QUA switch/case execution.
    Identity/idle gates are skipped.
    """
    result = []

    for instruction in circuit:
        gate_name = get_gate_name(instruction.operation)
        if gate_name == "idle":
            continue
        if gate_name not in SINGLE_QUBIT_GATE_MAP:
            raise ValueError(f"Unsupported gate: {gate_name}")
        result.append(SINGLE_QUBIT_GATE_MAP[gate_name])

    return result


# =============================================================================
# Clifford Lookup Tables (PPU RB)
# =============================================================================


def _generate_single_qubit_clifford_group() -> list[Clifford]:
    """Generate the 24 single-qubit Cliffords using H and S generators."""
    identity = Clifford.from_label("I")
    generators = [Clifford.from_label("H"), Clifford.from_label("S")]

    cliffords = [identity]
    queue = [identity]

    while queue:
        current = queue.pop(0)
        for generator in generators:
            candidate = generator @ current
            if not any(candidate == existing for existing in cliffords):
                cliffords.append(candidate)
                queue.append(candidate)

    if len(cliffords) != 24:
        raise ValueError(f"Expected 24 single-qubit Cliffords, got {len(cliffords)}")

    return cliffords


def _find_clifford_index(target: Clifford, cliffords: list[Clifford]) -> int:
    for idx, clifford in enumerate(cliffords):
        if target == clifford:
            return idx
    raise ValueError("Clifford not found in group list")


def build_single_qubit_clifford_tables(
    basis_gates: list[str] | None = None,
) -> dict[str, list[int] | int]:
    """Build lookup tables for PPU-side single-qubit RB.

    Returns:
        Dictionary with:
            - num_cliffords: Number of single-qubit Cliffords (24).
            - compose: Flattened composition table (left * right).
            - inverse: Inverse Clifford index for each Clifford.
            - decomp_flat: Concatenated native gate sequences.
            - decomp_offsets: Offsets into decomp_flat per Clifford.
            - decomp_lengths: Lengths of each Clifford decomposition.
            - max_decomp_length: Max decomposition length across Cliffords.
    """
    basis_gates = basis_gates or ["rz", "sx", "x"]
    cliffords = _generate_single_qubit_clifford_group()
    num_cliffords = len(cliffords)

    compose_flat = []
    inverse = []

    for clifford in cliffords:
        inv = clifford.adjoint()
        inverse.append(_find_clifford_index(inv, cliffords))

    for clifford_left in cliffords:
        for clifford_right in cliffords:
            composed = clifford_left @ clifford_right
            compose_flat.append(_find_clifford_index(composed, cliffords))

    decomp_flat = []
    decomp_offsets = []
    decomp_lengths = []

    for clifford in cliffords:
        qc = QuantumCircuit(1)
        qc.append(clifford, [0])
        transpiled = transpile(qc, basis_gates=basis_gates, optimization_level=1)
        gate_sequence = process_circuit_to_integers(transpiled)

        decomp_offsets.append(len(decomp_flat))
        decomp_lengths.append(len(gate_sequence))
        decomp_flat.extend(gate_sequence)

    return {
        "num_cliffords": num_cliffords,
        "compose": compose_flat,
        "inverse": inverse,
        "decomp_flat": decomp_flat,
        "decomp_offsets": decomp_offsets,
        "decomp_lengths": decomp_lengths,
        "max_decomp_length": max(decomp_lengths) if decomp_lengths else 0,
    }


# =============================================================================
# Data Analysis
# =============================================================================


def rb_decay_curve(x, A, alpha, B):
    """Exponential decay model: F(m) = A * alpha^m + B"""
    return A * alpha**x + B


@dataclass
class SingleQubitRBResult:
    """Analyze single-qubit RB experiment results.

    Attributes:
        circuit_depths: List of circuit depths used.
        num_circuits_per_length: Number of circuits per depth.
        num_averages: Number of shots per circuit.
        state: Measured states (0 or 1).
    """

    circuit_depths: list[int]
    num_circuits_per_length: int
    num_averages: int
    state: np.ndarray
    fit_success: bool = True
    alpha: float = field(default=None, init=False)
    fidelity: float = field(default=None, init=False)
    error_per_clifford: float = field(default=None, init=False)

    def __post_init__(self):
        self.data = xr.Dataset(
            data_vars={"state": (["circuit_depth", "sequence", "shot"], self.state)},
            coords={
                "circuit_depth": self.circuit_depths,
                "sequence": range(self.num_circuits_per_length),
                "shot": range(self.num_averages),
            },
        )

    def get_survival_probability(self) -> np.ndarray:
        """Calculate survival probability (P(|0>)) at each circuit depth."""
        return (
            (self.data.state == 0).sum(("sequence", "shot"))
            / (self.num_circuits_per_length * self.num_averages)
        ).values

    def fit_exponential(self) -> tuple:
        """Fit survival probability to exponential decay. Returns (A, alpha, B)."""
        survival_prob = self.get_survival_probability()

        try:
            popt, _ = curve_fit(
                rb_decay_curve,
                self.circuit_depths,
                survival_prob,
                p0=[0.5, 0.99, 0.5],
                bounds=([0, 0, 0], [1, 1, 1]),
                maxfev=10000,
            )
            A, alpha, B = popt
            self.alpha = alpha
            self.fit_success = True
        except RuntimeError:
            A, alpha, B = 0.5, 0.5, 0.5
            self.alpha = alpha
            self.fit_success = False

        return A, alpha, B

    def get_fidelity(self, alpha: float) -> float:
        """Calculate average Clifford fidelity from decay constant."""
        d = 2  # Single qubit dimension
        error_per_clifford = (1 - alpha) * (d - 1) / d
        fidelity = 1 - error_per_clifford
        self.fidelity = fidelity
        self.error_per_clifford = error_per_clifford
        return fidelity

    def plot_with_fidelity(self, ax=None) -> plt.Figure:
        """Plot RB results with fitted curve and fidelity metrics."""
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        else:
            fig = ax.get_figure()

        survival_prob = self.get_survival_probability()
        std_err = np.sqrt(
            survival_prob * (1 - survival_prob) / (self.num_circuits_per_length * self.num_averages)
        )

        ax.errorbar(
            self.circuit_depths,
            survival_prob,
            yerr=std_err,
            fmt="o",
            capsize=3,
            color="blue",
            label="Data",
        )

        A, alpha, B = self.fit_exponential()
        fidelity = self.get_fidelity(alpha)

        x_smooth = np.linspace(min(self.circuit_depths), max(self.circuit_depths), 100)
        ax.plot(
            x_smooth,
            rb_decay_curve(x_smooth, A, alpha, B),
            "-",
            color="red",
            linewidth=2,
            label="Fit",
        )

        ax.text(
            0.95,
            0.95,
            f"Clifford Fidelity: {fidelity * 100:.2f}%\n"
            f"Error/Clifford: {self.error_per_clifford * 100:.3f}%",
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            horizontalalignment="right",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
        )

        ax.set_xlabel("Number of Cliffords")
        ax.set_ylabel("Survival Probability")
        ax.set_title("Single-Qubit Randomized Benchmarking")
        ax.legend(loc="lower left")
        ax.set_ylim([0, 1.05])
        ax.grid(True, alpha=0.3)

        return fig


# =============================================================================
# Time Estimation
# =============================================================================


def estimate_total_experiment_time(
    circuit_lengths: list[int],
    num_circuits_per_length: int,
    num_shots: int,
    gate_duration_ns: int = 500,
    init_duration_us: float = 400,
    measure_duration_us: float = 400,
    compensation_duration_us: float = 1000,
    average_gates_per_clifford: float = 1.875,
) -> dict:
    """Estimate total experiment time for an RB experiment.

    Returns:
        Dictionary with total_sequences, avg_sequence_time_us,
        total_time_seconds, total_time_minutes, total_time_hours.
    """
    total_sequences = len(circuit_lengths) * num_circuits_per_length * num_shots
    avg_cliffords = np.mean(circuit_lengths)

    # Gate time (physical gates only, virtual Z is free)
    gate_time_us = avg_cliffords * average_gates_per_clifford * gate_duration_ns / 1000
    avg_sequence_time_us = (
        init_duration_us + gate_time_us + measure_duration_us + compensation_duration_us
    )

    total_time_s = total_sequences * avg_sequence_time_us / 1e6

    return {
        "total_sequences": total_sequences,
        "avg_sequence_time_us": avg_sequence_time_us,
        "total_time_seconds": total_time_s,
        "total_time_minutes": total_time_s / 60,
        "total_time_hours": total_time_s / 3600,
    }
