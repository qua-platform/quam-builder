"""Single-qubit randomized benchmarking utilities for spin qubits.

This module provides classes and functions for generating single-qubit RB circuits
and analyzing their results, specifically designed for spin qubit architectures.

The circuits are generated using Qiskit's Clifford library and transpiled to a
basis gate set compatible with spin qubit hardware (Gaussian pulses for physical
rotations, virtual Z gates for frame rotations).
"""

import copy
from dataclasses import dataclass, field
from typing import List, Optional, Literal

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
# Maps gate combinations to integers for efficient execution
SINGLE_QUBIT_GATE_MAP = {
    "x90": 0,  # X90 (pi/2 rotation about X)
    "x180": 1,  # X180 (pi rotation about X)
    "y90": 2,  # Y90 (pi/2 rotation about Y)
    "y180": 3,  # Y180 (pi rotation about Y)
    "rz_pi2": 4,  # Virtual Z (pi/2)
    "rz_pi": 5,  # Virtual Z (pi)
    "rz_3pi2": 6,  # Virtual Z (3pi/2)
    "idle": 7,  # Identity / idle
}

# Reverse mapping for debugging/visualization
GATE_INT_TO_NAME = {v: k for k, v in SINGLE_QUBIT_GATE_MAP.items()}

EPS = 1e-8


# =============================================================================
# Circuit Generation Classes
# =============================================================================


class SingleQubitRBBase:
    """Base class for single-qubit randomized benchmarking circuit generation.

    This class generates random Clifford circuits and transpiles them to a
    basis gate set suitable for spin qubit hardware. The basis gates are:
    - sx (X90): pi/2 rotation about X axis
    - x (X180): pi rotation about X axis
    - rz: Virtual Z rotation (frame rotation)

    The transpiled circuits can then be converted to integer sequences for
    efficient execution on the OPX.
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

        # Will be populated by generate_circuits_and_transpile
        self.circuits = {}
        self.transpiled_circuits = {}

    def generate_circuits_and_transpile(self):
        """Generate circuits and transpile them to the basis gate set."""
        self.circuits = self.generate_circuits()
        self.transpiled_circuits = {
            length: self._transpile_circuits(circuits) for length, circuits in self.circuits.items()
        }

    def generate_circuits(self) -> dict:
        """Generate random Clifford circuits for all specified lengths.

        Returns:
            Dictionary mapping circuit lengths to lists of circuits.
        """
        circuits = {}
        for length in self.circuit_lengths:
            circuits[length] = self._generate_circuits_per_length(length)
        return circuits

    def _generate_circuits_per_length(self, length: int) -> List[QuantumCircuit]:
        """Generate random single-qubit Clifford circuits for a given length.

        Args:
            length: Number of Cliffords in the circuit.

        Returns:
            List of generated quantum circuits.
        """
        circuits = []

        for _ in range(self.num_circuits_per_length):
            qc = QuantumCircuit(1)
            clifford_product = Clifford(qc)  # Identity Clifford

            # Apply random Clifford gates
            for _ in range(length):
                cliff = random_clifford(1, self.rolling_seed)
                self.rolling_seed += 1
                qc.append(cliff, [0])
                clifford_product = cliff @ clifford_product

            # Append the inverse Clifford to return to |0>
            inverse_clifford = clifford_product.adjoint()
            qc.append(inverse_clifford, [0])

            circuits.append(qc)

        return circuits

    def _transpile_circuits(self, circuits: List[QuantumCircuit]) -> List[QuantumCircuit]:
        """Transpile circuits to the basis gate set.

        Args:
            circuits: List of circuits to transpile.

        Returns:
            List of transpiled circuits.
        """
        transpiled = []
        for qc in circuits:
            # Transpile each Clifford separately to maintain structure
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
    """Class for generating single-qubit standard randomized benchmarking circuits.

    This class automatically generates and transpiles circuits upon initialization.
    """

    def __init__(
        self,
        circuit_lengths: List[int],
        num_circuits_per_length: int,
        basis_gates: List[str] = None,
        seed: Optional[int] = None,
    ):
        """Initialize single-qubit standard RB circuit generator.

        Args:
            circuit_lengths: List of circuit depths to generate.
            num_circuits_per_length: Number of random circuits per depth.
            basis_gates: List of basis gates for transpilation.
            seed: Random seed for circuit generation.
        """
        super().__init__(
            circuit_lengths,
            num_circuits_per_length,
            basis_gates,
            seed,
        )
        self.generate_circuits_and_transpile()


# =============================================================================
# Circuit Processing Utilities
# =============================================================================


def get_gate_name(gate) -> str:
    """Extract the gate name and parameters in a standardized format.

    Args:
        gate: A Qiskit gate instruction.

    Returns:
        Standardized gate name string.
    """
    name = gate.name.lower()
    if name == "rz":
        angle = gate.params[0]
        # Normalize angle to [0, 2pi)
        angle = angle % (2 * np.pi)
        if np.isclose(angle, np.pi / 2, atol=EPS):
            return "rz_pi2"
        if np.isclose(angle, np.pi, atol=EPS):
            return "rz_pi"
        if np.isclose(angle, 3 * np.pi / 2, atol=EPS) or np.isclose(
            angle, -np.pi / 2 % (2 * np.pi), atol=EPS
        ):
            return "rz_3pi2"
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
    """Process a quantum circuit and return a list of integers representing gates.

    Each gate in the transpiled circuit is converted to an integer for efficient
    execution using QUA switch/case blocks.

    Args:
        circuit: A transpiled Qiskit QuantumCircuit with 1 qubit.

    Returns:
        List of integers representing the gate sequence.
    """
    result = []

    for instruction in circuit:
        gate_name = get_gate_name(instruction.operation)
        if gate_name == "idle":
            continue  # Skip identity gates
        if gate_name not in SINGLE_QUBIT_GATE_MAP:
            raise ValueError(f"Unsupported gate: {gate_name}")
        result.append(SINGLE_QUBIT_GATE_MAP[gate_name])

    return result


def prepare_circuits_for_qua(
    rb_generator: SingleQubitRBBase,
) -> tuple:
    """Prepare RB circuits for QUA execution.

    Converts all transpiled circuits to integer sequences and calculates
    metadata needed for the QUA program.

    Args:
        rb_generator: An initialized RB generator with transpiled circuits.

    Returns:
        Tuple of (circuits_as_ints, max_circuit_length, total_circuits)
        - circuits_as_ints: Dict mapping lengths to lists of integer sequences
        - max_circuit_length: Maximum number of gates in any circuit
        - total_circuits: Total number of circuits across all lengths
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
# Data Analysis Classes
# =============================================================================


def rb_decay_curve(x, A, alpha, B):
    """Exponential decay model for RB fidelity.

    F(m) = A * alpha^m + B

    Args:
        x: Circuit depths (number of Cliffords).
        A: Amplitude of the decay.
        alpha: Decay constant (depolarizing parameter).
        B: Offset of the curve.

    Returns:
        Calculated decay curve values.
    """
    return A * alpha**x + B


@dataclass
class SingleQubitRBResult:
    """Class for analyzing single-qubit RB experiment results.

    Attributes:
        circuit_depths: List of circuit depths used in the RB experiment.
        num_circuits_per_length: Number of repeated sequences at each depth.
        num_averages: Number of averages (shots) for each sequence.
        state: Measured states from the RB experiment (0 or 1).
        fit_success: Whether the fit converged successfully.
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
        """Initialize the xarray Dataset to store the RB experiment data."""
        self.data = xr.Dataset(
            data_vars={"state": (["circuit_depth", "sequence", "shot"], self.state)},
            coords={
                "circuit_depth": self.circuit_depths,
                "sequence": range(self.num_circuits_per_length),
                "shot": range(self.num_averages),
            },
        )

    def get_survival_probability(self) -> np.ndarray:
        """Calculate the survival probability at each circuit depth.

        For single-qubit RB, survival probability is the probability of
        measuring |0> (ground state) after the sequence.

        Returns:
            Array of survival probabilities for each circuit depth.
        """
        # State == 0 means measured in ground state (survived)
        return (
            (self.data.state == 0).sum(("sequence", "shot"))
            / (self.num_circuits_per_length * self.num_averages)
        ).values

    def fit_exponential(self) -> tuple:
        """Fit the survival probability to an exponential decay model.

        Returns:
            Tuple of fitted parameters (A, alpha, B).
        """
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
        """Calculate the average Clifford fidelity from the decay constant.

        For single-qubit Cliffords:
        r = (1 - alpha) * (d - 1) / d = (1 - alpha) / 2
        F = 1 - r = (1 + alpha) / 2

        Args:
            alpha: Decay constant from the exponential fit.

        Returns:
            Average fidelity per Clifford gate.
        """
        d = 2  # Dimension for single qubit
        error_per_clifford = (1 - alpha) * (d - 1) / d
        fidelity = 1 - error_per_clifford
        self.fidelity = fidelity
        self.error_per_clifford = error_per_clifford
        return fidelity

    def plot_survival_probability(self, ax=None) -> plt.Figure:
        """Plot the survival probability as a function of circuit depth.

        Args:
            ax: Optional matplotlib axes to plot on.

        Returns:
            The matplotlib figure object.
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        else:
            fig = ax.get_figure()

        # Get survival probability and error bars
        survival_prob = self.get_survival_probability()

        # Calculate standard error
        std_err = np.sqrt(
            survival_prob * (1 - survival_prob) / (self.num_circuits_per_length * self.num_averages)
        )

        # Plot experimental data
        ax.errorbar(
            self.circuit_depths,
            survival_prob,
            yerr=std_err,
            fmt="o",
            capsize=3,
            color="blue",
            label="Experimental Data",
        )

        # Fit and plot
        A, alpha, B = self.fit_exponential()
        fidelity = self.get_fidelity(alpha)

        # Plot fitted curve
        x_smooth = np.linspace(min(self.circuit_depths), max(self.circuit_depths), 100)
        ax.plot(
            x_smooth,
            rb_decay_curve(x_smooth, A, alpha, B),
            "-",
            color="red",
            linewidth=2,
            label="Exponential Fit",
        )

        # Add fidelity annotation
        fidelity_text = (
            f"Clifford Fidelity: {fidelity * 100:.2f}%\n"
            f"Error per Clifford: {self.error_per_clifford * 100:.3f}%\n"
            f"Alpha: {alpha:.4f}"
        )
        ax.text(
            0.95,
            0.95,
            fidelity_text,
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

    def plot_with_fidelity(self) -> plt.Figure:
        """Plot RB results with fidelity calculation.

        This is the main plotting method that shows experimental data,
        fitted curve, and calculated fidelity metrics.

        Returns:
            The matplotlib figure object.
        """
        return self.plot_survival_probability()


# =============================================================================
# Utility Functions
# =============================================================================


def estimate_sequence_time(
    num_cliffords: int,
    gate_duration_ns: int = 500,
    init_duration_us: float = 400,
    measure_duration_us: float = 400,
    compensation_duration_us: float = 1000,
    average_gates_per_clifford: float = 1.875,
) -> float:
    """Estimate the total time for a single RB sequence.

    Args:
        num_cliffords: Number of Cliffords in the sequence.
        gate_duration_ns: Duration of each physical gate in nanoseconds.
        init_duration_us: Initialization time in microseconds.
        measure_duration_us: Measurement time in microseconds.
        compensation_duration_us: Compensation pulse time in microseconds.
        average_gates_per_clifford: Average number of physical gates per Clifford.
            For single-qubit Cliffords with {sx, x, rz}: ~1.875 gates/Clifford.

    Returns:
        Total sequence time in microseconds.
    """
    # Gate time (only count physical gates, not virtual Z)
    gate_time_us = num_cliffords * average_gates_per_clifford * gate_duration_ns / 1000

    # Total time
    total_us = init_duration_us + gate_time_us + measure_duration_us + compensation_duration_us

    return total_us


def estimate_total_experiment_time(
    circuit_lengths: List[int],
    num_circuits_per_length: int,
    num_shots: int,
    gate_duration_ns: int = 500,
    init_duration_us: float = 400,
    measure_duration_us: float = 400,
    compensation_duration_us: float = 1000,
) -> dict:
    """Estimate the total experiment time for an RB experiment.

    Args:
        circuit_lengths: List of circuit depths.
        num_circuits_per_length: Number of circuits per depth.
        num_shots: Number of repetitions per circuit.
        gate_duration_ns: Duration of each physical gate in nanoseconds.
        init_duration_us: Initialization time in microseconds.
        measure_duration_us: Measurement time in microseconds.
        compensation_duration_us: Compensation pulse time in microseconds.

    Returns:
        Dictionary with timing estimates.
    """
    total_sequences = len(circuit_lengths) * num_circuits_per_length * num_shots

    # Average sequence time
    avg_cliffords = np.mean(circuit_lengths)
    avg_sequence_time_us = estimate_sequence_time(
        avg_cliffords,
        gate_duration_ns,
        init_duration_us,
        measure_duration_us,
        compensation_duration_us,
    )

    total_time_s = total_sequences * avg_sequence_time_us / 1e6

    return {
        "total_sequences": total_sequences,
        "avg_sequence_time_us": avg_sequence_time_us,
        "total_time_seconds": total_time_s,
        "total_time_minutes": total_time_s / 60,
        "total_time_hours": total_time_s / 3600,
    }


# =============================================================================
# Timing Analysis
# =============================================================================


@dataclass
class RBTimingResult:
    """Class for analyzing timing data from RB experiments.

    All times are stored in nanoseconds.

    Attributes:
        circuit_depths: List of circuit depths.
        num_circuits_per_length: Number of circuits per depth.
        num_shots: Number of shots per circuit.
        t_init: Initialization times (depths x circuits x shots) in ns.
        t_gates: Gate sequence times (depths x circuits x shots) in ns.
        t_measure: Measurement times (depths x circuits x shots) in ns.
        t_compensation: Compensation times (depths x circuits x shots) in ns.
        t_total: Total sequence times (depths x circuits x shots) in ns.
    """

    circuit_depths: List[int]
    num_circuits_per_length: int
    num_shots: int
    t_init: np.ndarray
    t_gates: np.ndarray
    t_measure: np.ndarray
    t_compensation: np.ndarray
    t_total: np.ndarray

    def __post_init__(self):
        """Initialize the xarray Dataset for timing data."""
        self.data = xr.Dataset(
            data_vars={
                "t_init": (["circuit_depth", "sequence", "shot"], self.t_init),
                "t_gates": (["circuit_depth", "sequence", "shot"], self.t_gates),
                "t_measure": (["circuit_depth", "sequence", "shot"], self.t_measure),
                "t_compensation": (
                    ["circuit_depth", "sequence", "shot"],
                    self.t_compensation,
                ),
                "t_total": (["circuit_depth", "sequence", "shot"], self.t_total),
            },
            coords={
                "circuit_depth": self.circuit_depths,
                "sequence": range(self.num_circuits_per_length),
                "shot": range(self.num_shots),
            },
        )

    def get_mean_times(self) -> dict:
        """Get mean timing for each phase averaged over all sequences and shots.

        Returns:
            Dictionary with mean times in microseconds for each phase.
        """
        return {
            "init_us": float(self.data.t_init.mean().values) / 1000,
            "gates_us": float(self.data.t_gates.mean().values) / 1000,
            "measure_us": float(self.data.t_measure.mean().values) / 1000,
            "compensation_us": float(self.data.t_compensation.mean().values) / 1000,
            "total_us": float(self.data.t_total.mean().values) / 1000,
        }

    def get_times_by_depth(self) -> xr.Dataset:
        """Get mean timing for each phase as a function of circuit depth.

        Returns:
            xarray Dataset with mean times (in us) indexed by circuit depth.
        """
        return self.data.mean(dim=["sequence", "shot"]) / 1000  # Convert to microseconds

    def get_gate_time_per_clifford(self) -> np.ndarray:
        """Calculate the average gate time per Clifford at each depth.

        Returns:
            Array of gate time per Clifford in nanoseconds.
        """
        mean_gate_times = self.data.t_gates.mean(dim=["sequence", "shot"]).values
        return mean_gate_times / np.array(self.circuit_depths)

    def plot_timing_breakdown(self, ax=None) -> plt.Figure:
        """Plot timing breakdown as stacked bar chart.

        Args:
            ax: Optional matplotlib axes.

        Returns:
            Matplotlib figure.
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        else:
            fig = ax.get_figure()

        times_by_depth = self.get_times_by_depth()
        depths = self.circuit_depths

        # Stack the timing components
        t_init = times_by_depth.t_init.values
        t_gates = times_by_depth.t_gates.values
        t_measure = times_by_depth.t_measure.values
        t_comp = times_by_depth.t_compensation.values

        width = 0.6
        x = np.arange(len(depths))

        ax.bar(x, t_init, width, label="Initialization", color="steelblue")
        ax.bar(x, t_gates, width, bottom=t_init, label="Gates", color="coral")
        ax.bar(
            x,
            t_measure,
            width,
            bottom=t_init + t_gates,
            label="Measurement",
            color="forestgreen",
        )
        ax.bar(
            x,
            t_comp,
            width,
            bottom=t_init + t_gates + t_measure,
            label="Compensation",
            color="mediumpurple",
        )

        ax.set_xlabel("Number of Cliffords")
        ax.set_ylabel("Time (μs)")
        ax.set_title("RB Sequence Timing Breakdown")
        ax.set_xticks(x)
        ax.set_xticklabels(depths)
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3, axis="y")

        return fig

    def plot_gate_time_scaling(self, ax=None) -> plt.Figure:
        """Plot how gate sequence time scales with circuit depth.

        Args:
            ax: Optional matplotlib axes.

        Returns:
            Matplotlib figure.
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        else:
            fig = ax.get_figure()

        times_by_depth = self.get_times_by_depth()
        t_gates = times_by_depth.t_gates.values

        # Fit linear scaling
        coeffs = np.polyfit(self.circuit_depths, t_gates, 1)
        fit_line = np.poly1d(coeffs)

        ax.scatter(self.circuit_depths, t_gates, s=50, color="coral", label="Measured")
        ax.plot(
            self.circuit_depths,
            fit_line(self.circuit_depths),
            "--",
            color="gray",
            label=f"Linear fit: {coeffs[0]:.2f} μs/Clifford",
        )

        ax.set_xlabel("Number of Cliffords")
        ax.set_ylabel("Gate Sequence Time (μs)")
        ax.set_title("Gate Time Scaling with Circuit Depth")
        ax.legend()
        ax.grid(True, alpha=0.3)

        return fig

    def summary(self) -> str:
        """Generate a text summary of timing results.

        Returns:
            Formatted string with timing summary.
        """
        mean_times = self.get_mean_times()
        gate_per_clifford = self.get_gate_time_per_clifford()

        lines = [
            "=" * 50,
            "RB Timing Summary",
            "=" * 50,
            f"Mean Initialization Time: {mean_times['init_us']:.1f} μs",
            f"Mean Gate Sequence Time:  {mean_times['gates_us']:.1f} μs",
            f"Mean Measurement Time:    {mean_times['measure_us']:.1f} μs",
            f"Mean Compensation Time:   {mean_times['compensation_us']:.1f} μs",
            "-" * 50,
            f"Mean Total Sequence Time: {mean_times['total_us']:.1f} μs",
            "",
            f"Gate time per Clifford (avg): {np.mean(gate_per_clifford):.1f} ns",
            "=" * 50,
        ]
        return "\n".join(lines)


def analyze_timing_results(
    results: dict,
    circuit_depths: List[int],
    num_circuits_per_length: int,
    num_shots: int,
    clock_cycle_ns: int = 4,
) -> RBTimingResult:
    """Analyze timing data from RB experiment results.

    Args:
        results: Dictionary of results from the QUA job containing timing streams.
        circuit_depths: List of circuit depths.
        num_circuits_per_length: Number of circuits per depth.
        num_shots: Number of shots per circuit.
        clock_cycle_ns: OPX clock cycle duration in nanoseconds (default 4 ns).

    Returns:
        RBTimingResult with analyzed timing data.
    """

    # Convert from clock cycles to nanoseconds
    def to_ns(data):
        arr = np.array(data) * clock_cycle_ns
        return arr.reshape(len(circuit_depths), num_circuits_per_length, num_shots)

    return RBTimingResult(
        circuit_depths=circuit_depths,
        num_circuits_per_length=num_circuits_per_length,
        num_shots=num_shots,
        t_init=to_ns(results.get("timing_init_cycles", [])),
        t_gates=to_ns(results.get("timing_gates_cycles", [])),
        t_measure=to_ns(results.get("timing_measure_cycles", [])),
        t_compensation=to_ns(results.get("timing_compensation_cycles", [])),
        t_total=to_ns(results.get("timing_total_cycles", [])),
    )
