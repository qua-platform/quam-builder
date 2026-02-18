"""Helpers for voltage-gate sequence validation against a server."""

# from configuration import *

import pytest

from qm import SimulationConfig, QuantumMachinesManager, generate_qua_script
pytest.importorskip("qm_saas")
from qm_saas import QOPVersion, QmSaas
import matplotlib.pyplot as plt
import numpy as np


def simulate_program(qmm, machine, prog, simulation_duration=10000):
    # Simulates the QUA program for the specified duration
    simulation_config = SimulationConfig(duration=simulation_duration // 4)  # In clock cycles = 4ns
    # Simulate blocks python until the simulation is done
    config = machine.generate_config()
    print(generate_qua_script(prog, config))
    job = qmm.simulate(config, prog, simulation_config)
    # Get the simulated samples
    samples = job.get_simulated_samples()

    return qmm, samples


def validate_program(samples, requested_wf_p, requested_wf_m):
    t0 = np.where(samples["con1"].analog[f"{5}-{6}"] != 0)[0][0]
    import matplotlib.pyplot as plt

    wf_p = samples["con1"].analog[f"{5}-{6}"][t0:]
    wf_m = samples["con1"].analog[f"{5}-{3}"][t0:]
    plt.plot(wf_p)
    plt.show()
    t1 = np.where(np.isclose(wf_p, 0.0, atol=1e-6))[0][0]

    # Plot the simulated samples
    plt.figure()
    plt.plot(requested_wf_p, "bx", label="requested wf (+)")
    plt.plot(wf_p[: t1 + 1], "b", label="simulated wf (+)")
    plt.plot(requested_wf_m, "rx", label="requested wf (-)")
    plt.plot(wf_m[: t1 + 1], "r", label="simulated wf (-)")
    plt.legend()
    plt.show()
    print(
        f"Difference between requested and simulated (+): {np.mean((wf_p[:len(requested_wf_p)] - requested_wf_p) / requested_wf_p) * 100:.2e} %"
    )
    print(
        f"Difference between requested and simulated (-): {np.mean((wf_m[:len(requested_wf_m)] - requested_wf_m) / requested_wf_m) * 100:.2e} %"
    )
    print(
        f"Relative sum after compensation (+): {np.sum(wf_p[:t1+1]) / np.sum(wf_p[:len(requested_wf_p)]) * 100:.2f} %"
    )
    print(
        f"Relative sum after compensation (-): {np.sum(wf_m[:t1+1]) / np.sum(wf_p[:len(requested_wf_m)]) * 100:.2f} %"
    )
    print(f"Max gradient during compensation (+): {max(np.diff(wf_p[:t1+1])) * 1000:.2f} mV")
    print(f"Max gradient during compensation (-): {max(np.diff(wf_m[:t1+1])) * 1000:.2f} mV")
    # Success criteria
    assert (np.mean((wf_p[: len(requested_wf_p)] - requested_wf_p) / requested_wf_p) < 0.1) & (
        np.mean((wf_m[: len(requested_wf_m)] - requested_wf_m) / requested_wf_m) < 0.1
    ), "Simulated wf doesn't match requested wf."
    # assert (np.sum(wf_p[: t1 + 1]) / np.sum(wf_p[: len(requested_wf_p)]) * 100 < 1) & (
    #     np.sum(wf_m[: t1 + 1]) / np.sum(wf_p[: len(requested_wf_m)]) * 100 < 1
    # ), "The compensation pulse leads to more than 1% error."
    assert (max(np.abs(np.diff(wf_p[: t1 + 1]))) < 0.5) & (
        max(np.abs(np.diff(wf_m[: t1 + 1]))) < 0.5
    ), "The maximum voltage gradient is above 0.5 V."


def get_linear_ramp(start_value, end_value, duration, sampling_rate=1):
    """
    Generates a list of points describing a linear ramp between two points.

    Args:
        start_value (float): The starting value of the ramp.
        end_value (float): The ending value of the ramp.
        duration (int): The duration of the ramp (in time units).
        sampling_rate (int, optional): Number of samples per time unit. Defaults to 1.

    Returns:
        list: List of float values representing the ramp.
    """
    num_points = duration
    if num_points <= 1:
        return [start_value] * num_points
    ramp = [
        start_value + (end_value - start_value) * (i + 1) / num_points for i in range(num_points)
    ]
    return [point for point in ramp for _ in range(sampling_rate)]


def validate_compensation(samples, allowed=1.0):
    plt.figure()
    for name, sample in samples.con1.analog.items():
        plt.plot(sample, label=name)
    plt.legend()
    plt.show()
    for name, sample in samples.con1.analog.items():
        integrated = np.abs(np.trapz(sample))
        assert (
            integrated < allowed
        ), f"non sufficient compensation for analog output:{name} with abs integrated voltage:{integrated}"


def validate_durations(sample, expected_durations, steps):
    durations = np.diff(np.where(np.abs(np.diff(sample)))[0])[:steps]
    try:
        assert all(
            durations == expected_durations
        ), f"durations: {durations}, expected: {expected_durations}"
    except:
        raise Exception(f"durations: {durations}, expected: {expected_durations}")


def validate_keep_levels(sample, expected):
    correlate_expected = np.dot(expected, expected)
    correlated = np.correlate(sample, expected, mode="valid")
    assert np.isclose(
        np.max(correlated), correlate_expected
    ), f"failed with {correlate_expected=} and {np.max(correlated)=}"
