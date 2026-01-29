"""Single-qubit randomized benchmarking utilities for spin qubits.

This module provides classes and functions for generating single-qubit RB circuits
and analyzing their results, specifically designed for spin qubit architectures.

The circuits are generated using Qiskit's Clifford library and transpiled to a
basis gate set compatible with spin qubit hardware:
- X90, X180: Physical X rotations (Gaussian pulses)
- Y90, Y180: Physical Y rotations (Gaussian pulses with 90° phase)
- Z90, Z180, Z270: Virtual Z rotations (frame rotations, zero duration)
- Idle: Identity gate
"""

import copy
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import xarray as xr
from matplotlib import pyplot as plt
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Clifford, random_clifford
from scipy.optimize import curve_fit


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


# =============================================================================
# Circuit Generation
# =============================================================================


class SingleQubitRBBase:
    """Base class for single-qubit randomized benchmarking circuit generation.

    Generates random Clifford circuits and transpiles them to a basis gate set
    suitable for spin qubit hardware. The transpiled gates are:
    - sx (X90): pi/2 rotation about X axis
    - x (X180): pi rotation about X axis
    - rz: Virtual Z rotation (frame rotation)

    Note: Y gates are decomposed into rz + sx sequences by Qiskit, which is
    equivalent since virtual Z gates have zero duration.
    """

    def __init__(
        self,
        circuit_lengths: List[int],
        num_circuits_per_length: int,
        basis_gates: List[str] = None,
        seed: Optional[int] = None,
    ):
        """Initialize the single-qubit RB base class.

        Args:
            circuit_lengths: List of circuit depths (number of Cliffords) to generate.
            num_circuits_per_length: Number of random circuits to generate per depth.
            basis_gates: List of basis gates for transpilation.
                        Defaults to ['rz', 'sx', 'x'] for spin qubits.
            seed: Random seed for circuit generation reproducibility.
        """
        self.circuit_lengths = circuit_lengths
        self.num_circuits_per_length = num_circuits_per_length
        self.basis_gates = basis_gates or ["rz", "sx", "x"]
        self.seed = seed if seed is not None else np.random.randint(0, 1000000)
        self.rolling_seed = copy.deepcopy(self.seed)

        self.circuits = {}
        self.transpiled_circuits = {}

    def generate_circuits_and_transpile(self):
        """Generate circuits and transpile them to the basis gate set."""
        self.circuits = self.generate_circuits()
        self.transpiled_circuits = {
            length: self._transpile_circuits(circuits) for length, circuits in self.circuits.items()
        }

    def generate_circuits(self) -> dict:
        """Generate random Clifford circuits for all specified lengths."""
        circuits = {}
        for length in self.circuit_lengths:
            circuits[length] = self._generate_circuits_per_length(length)
        return circuits

    def _generate_circuits_per_length(self, length: int) -> List[QuantumCircuit]:
        """Generate random single-qubit Clifford circuits for a given length."""
        circuits = []

        for _ in range(self.num_circuits_per_length):
            qc = QuantumCircuit(1)
            clifford_product = Clifford(qc)

            for _ in range(length):
                cliff = random_clifford(1, self.rolling_seed)
                self.rolling_seed += 1
                qc.append(cliff, [0])
                clifford_product = cliff @ clifford_product

            # Append inverse to return to |0>
            inverse_clifford = clifford_product.adjoint()
            qc.append(inverse_clifford, [0])

            circuits.append(qc)

        return circuits

    def _transpile_circuits(self, circuits: List[QuantumCircuit]) -> List[QuantumCircuit]:
        """Transpile circuits to the basis gate set."""
        transpiled = []
        for qc in circuits:
            transp_circ = QuantumCircuit(1)
            for instruction in qc:
                qc_per_inst = QuantumCircuit(1)
                qc_per_inst.append(instruction)

                if isinstance(instruction.operation, Clifford):
                    transpiled_gate = transpile(
                        qc_per_inst,
                        basis_gates=self.basis_gates,
                        optimization_level=1,
                    )
                else:
                    transpiled_gate = qc_per_inst.copy()

                transp_circ = transp_circ.compose(transpiled_gate)

            transpiled.append(transp_circ)

        return transpiled


class SingleQubitStandardRB(SingleQubitRBBase):
    """Single-qubit standard randomized benchmarking circuit generator.

    Automatically generates and transpiles circuits upon initialization.
    """

    def __init__(
        self,
        circuit_lengths: List[int],
        num_circuits_per_length: int,
        basis_gates: List[str] = None,
        seed: Optional[int] = None,
    ):
        super().__init__(circuit_lengths, num_circuits_per_length, basis_gates, seed)
        self.generate_circuits_and_transpile()


# =============================================================================
# Circuit Processing
# =============================================================================


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


def process_circuit_to_integers(circuit: QuantumCircuit) -> List[int]:
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


def prepare_circuits_for_qua(rb_generator: SingleQubitRBBase) -> tuple:
    """Prepare RB circuits for QUA execution.

    Returns:
        Tuple of (circuits_as_ints, max_circuit_length, total_circuits)
    """
    circuits_as_ints = {}
    max_circuit_length = 0

    for length, circuits in rb_generator.transpiled_circuits.items():
        circuits_as_ints[length] = []
        for circuit in circuits:
            int_sequence = process_circuit_to_integers(circuit)
            circuits_as_ints[length].append(int_sequence)
            max_circuit_length = max(max_circuit_length, len(int_sequence))

    total_circuits = sum(len(c) for c in circuits_as_ints.values())

    return circuits_as_ints, max_circuit_length, total_circuits


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

    circuit_depths: List[int]
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
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
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
    circuit_lengths: List[int],
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
