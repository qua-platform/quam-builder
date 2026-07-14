"""Rabi chevron analysis: fastest rotation (peak fringe frequency) and amplitude estimate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure


def _import_fringe_tools():
    """Import fringe fitting from misc.fitting_tools (riken-sqert-qualibration on PYTHONPATH)."""
    try:
        from misc.fitting_tools import fit_fringe_signed_minimum, plot_fringe_minimum_fit

        return fit_fringe_signed_minimum, plot_fringe_minimum_fit
    except ImportError as exc:
        raise ImportError(
            "Rabi chevron analysis requires misc.fitting_tools from riken-sqert-qualibration on PYTHONPATH."
        ) from exc


def rabi_chevron_signal_from_iq(
    i: np.ndarray,
    q: np.ndarray,
) -> np.ndarray:
    """Magnitude signal for fringe fitting from demodulated I/Q."""
    return np.hypot(np.asarray(i, dtype=float), np.asarray(q, dtype=float))


@dataclass
class RabiChevronFitResult:
    """Fitted Rabi chevron parameters."""

    opt_drive_frequency: float
    omega_peak: float
    fringe_frequency_peak: float
    pi_pulse_duration: float
    amp_scale_for_pi: float
    signed_model: Dict[str, float]
    fringe_metric_measured: np.ndarray
    success: bool
    raw: Dict[str, Any]


def analyze_rabi_chevron(
    signal: np.ndarray,
    durations: np.ndarray,
    frequencies: np.ndarray,
    *,
    reference_pulse_duration: float,
    reference_drive_amplitude: float = 1.0,
    duration_unit_ns: Optional[float] = 4.0,
    min_fringe_points: int = 3,
    verbose: bool = False,
) -> RabiChevronFitResult:
    """Fit a Rabi chevron map and extract resonance + amplitude scaling.

    The data layout matches error-amplification calibrations:
    ``signal[i, j]`` at ``(durations[i], frequencies[j])``.

    Fringe frequency is extracted per drive-frequency column (Rabi oscillation along
    duration). The optimum drive frequency is where the fringe frequency is **maximum**
    (fastest rotation). A rough π-pulse amplitude scale is

    ``amp_scale_for_pi ≈ A_ref × π / (ω_peak × T_ref)``.

    Parameters
    ----------
    signal
        2-D array (n_duration, n_frequency).
    durations
        Pulse-duration axis (same units as in the QUA program, e.g. clock cycles).
    frequencies
        Drive-frequency axis (Hz).
    reference_pulse_duration
        Drive duration used with ``reference_drive_amplitude`` (same units as ``durations``).
    reference_drive_amplitude
        Drive amplitude used during the sweep (QUA ``amplitude_scale`` or pulse amp).
    duration_unit_ns
        Optional ns per duration step for reporting ``pi_pulse_duration`` in ns.
    """
    fit_fringe_signed_minimum, _ = _import_fringe_tools()

    signal = np.asarray(signal, dtype=float)
    durations = np.asarray(durations, dtype=float)
    frequencies = np.asarray(frequencies, dtype=float)

    if signal.ndim != 2:
        raise ValueError("signal must be 2-D (n_duration, n_frequency)")
    if signal.shape != (len(durations), len(frequencies)):
        raise ValueError(
            f"signal shape {signal.shape} must match (len(durations), len(frequencies)) "
            f"= ({len(durations)}, {len(frequencies)})"
        )

    result = fit_fringe_signed_minimum(
        signal,
        durations,
        frequencies,
        fringe_metric="frequency",
        frequency_extremum="max",
        cosine_start="max",
        min_fringe_points=min_fringe_points,
        verbose=verbose,
        reference_pulse_duration=reference_pulse_duration,
        reference_drive_amplitude=reference_drive_amplitude,
    )

    omega_peak = float(result.get("omega_peak", result["signed_model"].get("epsilon_0", np.nan)))
    pi_dur = float(result["pi_pulse_duration"])
    if duration_unit_ns is not None and np.isfinite(pi_dur):
        pi_dur_ns = pi_dur * duration_unit_ns
    else:
        pi_dur_ns = pi_dur

    return RabiChevronFitResult(
        opt_drive_frequency=float(result["opt_sweep"]),
        omega_peak=omega_peak,
        fringe_frequency_peak=float(result["opt_fringe_metric"]),
        pi_pulse_duration=pi_dur_ns,
        amp_scale_for_pi=float(result["amp_scale_for_pi"]),
        signed_model=dict(result["signed_model"]),
        fringe_metric_measured=np.asarray(result["fringe_metrics_measured"], dtype=float),
        success=bool(result["success"]),
        raw=result,
    )


def plot_rabi_chevron_fit(
    fit: RabiChevronFitResult,
    frequencies: np.ndarray,
    *,
    ax: Optional[Axes] = None,
    xlabel: str = "Drive frequency [Hz]",
    ylabel: str = "Rabi frequency [cycles / duration step]",
) -> Axes:
    """Plot per-column Rabi frequencies and the fitted peak profile."""
    _, plot_fringe_minimum_fit = _import_fringe_tools()
    frequencies = np.asarray(frequencies, dtype=float)
    opt_x = fit.opt_drive_frequency if fit.success else None
    return plot_fringe_minimum_fit(
        frequencies,
        fit.signed_model,
        ax=ax,
        y_measured=fit.fringe_metric_measured,
        opt_x_sweep=opt_x,
        xlabel=xlabel,
        ylabel=ylabel,
    )


def plot_rabi_chevron_summary(
    signal: np.ndarray,
    durations: np.ndarray,
    frequencies: np.ndarray,
    fit: RabiChevronFitResult,
) -> Tuple[Figure, np.ndarray]:
    """Heatmap of chevron data plus fringe-frequency fit panel."""
    import matplotlib.pyplot as plt

    signal = np.asarray(signal, dtype=float)
    durations = np.asarray(durations, dtype=float)
    frequencies = np.asarray(frequencies, dtype=float)

    fig, axs = plt.subplots(1, 2, figsize=(12, 4))

    extent = [frequencies[0], frequencies[-1], durations[-1], durations[0]]
    axs[0].imshow(signal, aspect="auto", extent=extent, origin="upper")
    axs[0].set_xlabel("Drive frequency [Hz]")
    axs[0].set_ylabel("Duration [clock cycles]")
    axs[0].set_title("Rabi chevron")
    if fit.success:
        axs[0].axvline(fit.opt_drive_frequency, color="w", ls="--", lw=1.5)

    plot_rabi_chevron_fit(fit, frequencies, ax=axs[1])
    axs[1].set_title("Fastest rotation (max fringe frequency)")

    fig.tight_layout()
    return fig, axs


def synthetic_rabi_chevron(
    durations: np.ndarray,
    frequencies: np.ndarray,
    *,
    resonance_hz: float = 15e6,
    omega_peak: float = 0.5,
    alpha: float = 0.2e-6,
    amplitude: float = 0.4,
    offset: float = 0.5,
) -> np.ndarray:
    """Generate a synthetic chevron for tests and demos (peak Rabi rate at ``resonance_hz``)."""
    durations = np.asarray(durations, dtype=float)
    frequencies = np.asarray(frequencies, dtype=float)
    data = np.zeros((len(durations), len(frequencies)))
    for j, freq in enumerate(frequencies):
        dr = freq - resonance_hz
        omega_col = np.sqrt(max(omega_peak**2 - (alpha * dr) ** 2, 0.0))
        data[:, j] = offset + amplitude * np.cos(omega_col * durations)
    return data
