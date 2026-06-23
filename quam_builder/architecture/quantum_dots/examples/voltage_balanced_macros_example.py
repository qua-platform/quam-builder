# ruff: noqa: E402, I001
# pylint: disable=line-too-long
"""Run the voltage-balanced chained macro simulation on QM SaaS.

Example:
    python quam_builder/architecture/quantum_dots/examples/voltage_balanced_macros_example.py \
      --sim-backend cloud \
      --cloud-config .qm_saas_credentials.json \
      --chained-sequence

    Opens an interactive plot window by default. To also save a PNG, pass ``--plot-dir``.
    Use ``--no-plot`` in headless/CI runs.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_CS_INSTALLATIONS_TESTS_CONFIG = (
    _PROJECT_ROOT.parent / "tests" / ".qm_cluster_config.json"
)
_CHAINED_SIM_CLOCK_CYCLES = 4_800
_TWO_STAGE_SIM_CLOCK_CYCLES = 6_000
_LF_FEM_OUTPUT_DELAY_NS = 161

from qm import QuantumMachinesManager, SimulationConfig, qua  # noqa: E402
from quam.components.ports import LFFEMAnalogOutputPort  # noqa: E402

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (  # noqa: E402
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import (
    wire_machine_macros,
)  # noqa: E402
from quam_builder.architecture.quantum_dots.operations.macro_catalog import (  # noqa: E402
    VoltageBalancedMacroCatalog,
)
from quam_builder.architecture.quantum_dots.operations.voltage_balanced_macros.state_macros import (  # noqa: E402
    TwoStageBalancedInitializeMacro,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    VoltagePointName,
)  # noqa: E402
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam  # noqa: E402


def build_voltage_balanced_tutorial_machine() -> LossDiVincenzoQuam:
    cluster_cfg = (
        _CS_INSTALLATIONS_TESTS_CONFIG
        if _CS_INSTALLATIONS_TESTS_CONFIG.is_file()
        else None
    )
    machine = build_tutorial_machine(
        mw_fem_slots=[1],
        lf_fem_slots=[3, 5],
        cluster_config_path=cluster_cfg,
    )
    wire_machine_macros(machine, catalogs=[VoltageBalancedMacroCatalog()], save=False)
    _set_demo_voltage_points(machine)
    _apply_lf_fem_output_delay(machine)
    return machine


def _set_demo_voltage_points(machine: LossDiVincenzoQuam) -> None:
    pair = next(iter(machine.quantum_dot_pairs.values()))
    dot_ids = [dot.id for dot in pair.quantum_dots]
    pair.add_point(
        VoltagePointName.EMPTY,
        dict.fromkeys(dot_ids, 0.05),
        duration=1000,
        replace_existing_point=True,
    )
    pair.add_point(
        VoltagePointName.MEASURE,
        dict.fromkeys(dot_ids, 0.12),
        duration=1000,
        replace_existing_point=True,
    )

    qubit_pair = next(iter(machine.qubit_pairs.values()))
    exchange_dot_ids = [
        qubit_pair.quantum_dot_pair.quantum_dots[0].id,
        qubit_pair.quantum_dot_pair.quantum_dots[1].id,
    ]
    qubit_pair.add_point(
        VoltagePointName.EXCHANGE,
        dict.fromkeys(exchange_dot_ids, 0.06),
        duration=1000,
        replace_existing_point=True,
    )


def _apply_lf_fem_output_delay(machine: LossDiVincenzoQuam) -> None:
    for virtual_gate_set in machine.virtual_gate_sets.values():
        for channel in virtual_gate_set.channels.values():
            output = getattr(channel, "opx_output", None)
            if isinstance(output, LFFEMAnalogOutputPort):
                output.delay = _LF_FEM_OUTPUT_DELAY_NS

    for sensor_dot in machine.sensor_dots.values():
        resonator = getattr(sensor_dot, "readout_resonator", None)
        output = (
            getattr(resonator, "opx_output", None) if resonator is not None else None
        )
        if isinstance(output, LFFEMAnalogOutputPort):
            output.delay = _LF_FEM_OUTPUT_DELAY_NS


def build_chained_program(machine: LossDiVincenzoQuam) -> object:
    pair = next(iter(machine.quantum_dot_pairs.values()))
    qubit = next(iter(machine.qubits.values()))
    qubit_pair = next(iter(machine.qubit_pairs.values()))

    with qua.program() as program:
        pair.empty()
        qua.align()
        qubit.measure()
        qua.align()
        pair.initialize()
        qua.align()
        qubit.x90()
        qua.align()
        qubit_pair.cz()
        qua.align()
        qubit.x180()
        qua.align()
        pair.measure()

    return program


def _load_cloud_config(path: Path | None) -> tuple[str, str, str, Path]:
    config_path = path or _PROJECT_ROOT / ".qm_saas_credentials.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"Cloud config not found: {config_path}")

    with open(config_path, encoding="utf-8") as file:
        config = json.load(file)

    return (
        config["email"],
        config["password"],
        config.get("host", "qm-saas.dev.quantum-machines.co"),
        config_path,
    )


def run_cloud_chained_simulation(
    machine: LossDiVincenzoQuam,
    *,
    cloud_config: Path | None,
    plot_dir: Path | None,
    no_plot: bool = False,
) -> None:
    try:
        import qm_saas  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError("Cloud simulation requires the `qm_saas` package.") from exc

    email, password, host, config_path = _load_cloud_config(cloud_config)
    print(
        f"Using QM cloud simulator: host={host!r} (credentials: {config_path})",
        flush=True,
    )

    client = qm_saas.QmSaas(email=email, password=password, host=host)
    client.close_all()
    with client.simulator(client.latest_version()) as instance:
        qmm = QuantumMachinesManager(
            host=instance.host,
            port=instance.port,
            connection_headers=instance.default_connection_headers,
        )
        job = qmm.simulate(
            machine.generate_config(),
            build_chained_program(machine),
            SimulationConfig(duration=_CHAINED_SIM_CLOCK_CYCLES),
        )
        job.wait_until("Done", timeout=600)
        samples = job.get_simulated_samples()

    _check_lf_integrals(samples, machine)
    if not no_plot:
        save_path = plot_dir / "chained_sequence.png" if plot_dir is not None else None
        if save_path is not None:
            save_path.parent.mkdir(parents=True, exist_ok=True)
        _plot_samples(samples, machine, output_path=save_path)
    print("Simulated: chained voltage-balanced macro sequence", flush=True)


def _iter_controller_samples(samples: object) -> Iterator[tuple[str, object]]:
    if isinstance(samples, Mapping):
        for controller_id, controller_samples in samples.items():
            if controller_samples is not None:
                yield str(controller_id), controller_samples
        return

    for controller_id in ("con1", "con2", "con3", "con4", "con5"):
        if hasattr(samples, controller_id):
            yield controller_id, getattr(samples, controller_id)


def _lf_output_sample_keys(
    machine: LossDiVincenzoQuam,
    gate_set_id: str = "main_qpu",
) -> Iterator[tuple[str, str, float, str]]:
    for channel in machine.virtual_gate_sets[gate_set_id].channels.values():
        output = channel.opx_output
        if not isinstance(output, LFFEMAnalogOutputPort):
            continue
        dt = 1.0 / float(output.sampling_rate) if output.sampling_rate else 1e-9
        yield output.controller_id, f"{output.fem_id}-{output.port_id}", dt, channel.id


def _dt_for_sample(
    controller_samples: object,
    sim_key: str,
    machine: LossDiVincenzoQuam,
    controller_id: str,
) -> float:
    sampling_rates = getattr(controller_samples, "analog_sampling_rate", None)
    if isinstance(sampling_rates, Mapping) and sampling_rates.get(sim_key):
        return 1.0 / float(sampling_rates[sim_key])

    for ctrl, key, dt, _label in _lf_output_sample_keys(machine):
        if ctrl == controller_id and key == sim_key:
            return dt
    return 1e-9


def _as_waveform_array(waveform: object) -> object:
    import numpy as np

    return np.asarray(waveform).ravel()


def _check_lf_integrals(
    samples: object,
    machine: LossDiVincenzoQuam,
    *,
    atol_v_s: float = 2e-5,
) -> None:
    checked = 0
    controller_samples = dict(_iter_controller_samples(samples))
    for controller_id, sim_key, _dt, _label in _lf_output_sample_keys(machine):
        samples_for_controller = controller_samples.get(controller_id)
        if (
            samples_for_controller is None
            or sim_key not in samples_for_controller.analog
        ):
            continue

        dt = _dt_for_sample(samples_for_controller, sim_key, machine, controller_id)
        values = _as_waveform_array(samples_for_controller.analog[sim_key]).real
        integral = float(values.sum() * dt)
        checked += 1
        if abs(integral) > atol_v_s:
            raise AssertionError(
                f"DC integral check failed: controller={controller_id} key={sim_key} "
                f"integral={integral:.3e} V*s (tol {atol_v_s:.3e})"
            )

    if checked == 0:
        print(
            "No LF analog samples were returned; skipped DC integral check.", flush=True
        )
    else:
        print(f"DC integral check passed on {checked} LF line(s).", flush=True)


def _plot_samples(
    samples: object,
    machine: LossDiVincenzoQuam,
    *,
    output_path: Path | None = None,
    title: str = "Chained voltage-balanced macro sequence",
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    lf_labels = {
        (controller_id, sim_key): label
        for controller_id, sim_key, _dt, label in _lf_output_sample_keys(machine)
    }
    fig, ax = plt.subplots(figsize=(9, 3.5))
    plotted = 0
    for controller_id, controller_samples in _iter_controller_samples(samples):
        for sim_key, waveform in controller_samples.analog.items():
            values = _as_waveform_array(waveform)
            if len(values) == 0:
                continue
            dt = _dt_for_sample(controller_samples, sim_key, machine, controller_id)
            label = lf_labels.get(
                (controller_id, sim_key), f"{controller_id} {sim_key}"
            )
            time_us = np.arange(len(values)) * dt * 1e6
            ax.plot(time_us, values.real, lw=0.8, label=f"{label} real")
            plotted += 1
            if np.any(values.imag):
                ax.plot(
                    time_us,
                    values.imag,
                    lw=0.8,
                    ls="--",
                    label=f"{label} imag",
                )
                plotted += 1

    if plotted == 0:
        ax.text(0.5, 0.5, "No analog data", transform=ax.transAxes, ha="center")
    else:
        ax.legend(loc="best", fontsize=6, framealpha=0.92)

    ax.set_xlabel("Time (us)")
    ax.set_ylabel("V")
    ax.set_title(title)
    fig.tight_layout()
    if output_path is not None:
        fig.savefig(output_path, dpi=120)
    plt.show()
    plt.close(fig)


# ── Two-stage balanced initialize: swap, persist, simulate ──────────────────


def swap_pair_initialize_to_two_stage(machine: LossDiVincenzoQuam) -> None:
    """Replace the BalancedInitializeMacro on the first QuantumDotPair with
    TwoStageBalancedInitializeMacro after the initial wiring stage.

    Also registers the INITIALIZE voltage point (inner stage, V1) on the pair
    so the two-stage macro has both voltage levels it needs: the inner
    INITIALIZE point (V1, smaller excursion) and the outer EMPTY point (V2).
    """
    pair = next(iter(machine.quantum_dot_pairs.values()))
    dot_ids = [dot.id for dot in pair.quantum_dots]

    # Inner voltage point (V1): slightly smaller than EMPTY (V2 = 0.12 V).
    pair.add_point(
        'init1',
        dict.fromkeys(dot_ids, 0.16),
        duration=1000,
        replace_existing_point=True,
    )

    pair.add_point(
        'init2',
        dict.fromkeys(dot_ids, 0.08),
        duration=1000,
        replace_existing_point=True,
    )

    before_type = type(pair.macros[VoltagePointName.INITIALIZE]).__name__
    pair.macros[VoltagePointName.INITIALIZE] = TwoStageBalancedInitializeMacro(
        point_1='init1',
        point_2='init2',
        ramp_duration_1=524,
        ramp_duration_2=1048,
        ramp_duration_mid=16,
        hold_duration=1048,
    )
    after_type = type(pair.macros[VoltagePointName.INITIALIZE]).__name__

    print(
        f"Swapped pair '{pair.id}' initialize macro: {before_type} → {after_type}",
        flush=True,
    )


def demonstrate_two_stage_persistence(
    machine: LossDiVincenzoQuam,
) -> LossDiVincenzoQuam:
    """Save the machine state to disk, reload it, and verify the macro type and
    parameters survive the round-trip.

    Returns the reloaded machine so the caller can use it for simulation.
    """
    pair = next(iter(machine.quantum_dot_pairs.values()))
    macro_before: TwoStageBalancedInitializeMacro = pair.macros[VoltagePointName.INITIALIZE]

    assert isinstance(macro_before, TwoStageBalancedInitializeMacro), (
        f"Expected TwoStageBalancedInitializeMacro, got {type(macro_before).__name__}"
    )
    print(
        f"Before save  — type={type(macro_before).__name__}, "
        f"point_1={macro_before.point_1!r}, point_2={macro_before.point_2!r}, "
        f"hold_duration={macro_before.hold_duration}, "
        f"ramp_duration_1={macro_before.ramp_duration_1}",
        flush=True,
    )

    with tempfile.TemporaryDirectory() as save_dir:
        machine.save(save_dir)
        print(f"Saved QuAM state → {save_dir}", flush=True)
        loaded = LossDiVincenzoQuam.load(save_dir)

    loaded_pair = next(iter(loaded.quantum_dot_pairs.values()))
    macro_after: TwoStageBalancedInitializeMacro = loaded_pair.macros[VoltagePointName.INITIALIZE]

    assert isinstance(macro_after, TwoStageBalancedInitializeMacro), (
        f"Reload failed: expected TwoStageBalancedInitializeMacro, "
        f"got {type(macro_after).__name__}"
    )
    assert macro_after.hold_duration == macro_before.hold_duration
    assert macro_after.ramp_duration_1 == macro_before.ramp_duration_1
    assert macro_after.ramp_duration_2 == macro_before.ramp_duration_2
    assert macro_after.ramp_duration_mid == macro_before.ramp_duration_mid
    assert macro_after.point_1 == macro_before.point_1
    assert macro_after.point_2 == macro_before.point_2

    print(
        f"After reload — type={type(macro_after).__name__}, "
        f"point_1={macro_after.point_1!r}, point_2={macro_after.point_2!r}, "
        f"hold_duration={macro_after.hold_duration}, "
        f"ramp_duration_1={macro_after.ramp_duration_1}",
        flush=True,
    )
    print(
        "Persistence check passed: TwoStageBalancedInitializeMacro round-trips cleanly.",
        flush=True,
    )
    return loaded


def build_two_stage_init_program(machine: LossDiVincenzoQuam) -> object:
    """QUA program that exercises the two-stage balanced initialize macro."""
    pair = next(iter(machine.quantum_dot_pairs.values()))
    qubit = next(iter(machine.qubits.values()))

    with qua.program() as program:
        pair.initialize()


    return program


def run_cloud_two_stage_simulation(
    machine: LossDiVincenzoQuam,
    *,
    cloud_config: Path | None,
    plot_dir: Path | None,
    no_plot: bool = False,
) -> None:
    """Swap to the two-stage init macro, verify persistence, then simulate."""
    swap_pair_initialize_to_two_stage(machine)
    machine = demonstrate_two_stage_persistence(machine)
    _apply_lf_fem_output_delay(machine)

    try:
        import qm_saas  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError("Cloud simulation requires the `qm_saas` package.") from exc

    email, password, host, config_path = _load_cloud_config(cloud_config)
    print(
        f"Using QM cloud simulator: host={host!r} (credentials: {config_path})",
        flush=True,
    )

    client = qm_saas.QmSaas(email=email, password=password, host=host)
    client.close_all()
    with client.simulator(client.latest_version()) as instance:
        qmm = QuantumMachinesManager(
            host=instance.host,
            port=instance.port,
            connection_headers=instance.default_connection_headers,
        )
        job = qmm.simulate(
            machine.generate_config(),
            build_two_stage_init_program(machine),
            SimulationConfig(duration=_TWO_STAGE_SIM_CLOCK_CYCLES),
        )
        job.wait_until("Done", timeout=600)
        samples = job.get_simulated_samples()

    _check_lf_integrals(samples, machine)
    if not no_plot:
        save_path = (
            plot_dir / "two_stage_init_sequence.png" if plot_dir is not None else None
        )
        if save_path is not None:
            save_path.parent.mkdir(parents=True, exist_ok=True)
        _plot_samples(
            samples,
            machine,
            output_path=save_path,
            title="Two-stage balanced initialize sequence",
        )
    print("Simulated: two-stage balanced initialize sequence", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim-backend", choices=("cloud",), default="cloud")
    parser.add_argument("--cloud-config", type=Path, default=None)
    parser.add_argument("--plot-dir", type=Path, default=None)
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip matplotlib (use in headless/CI; no window, no file).",
    )
    parser.add_argument(
        "--two-stage-init",
        action="store_false",
        help=(
            "Swap the pair initialize macro to TwoStageBalancedInitializeMacro, "
            "verify persistence across save/reload, then simulate."
        ),
    )
    # parse_known_args: Jupyter/IPython pass e.g. --f=... for the kernel connection file.
    args, _unknown = parser.parse_known_args()

    if args.two_stage_init:
        run_cloud_two_stage_simulation(
            build_voltage_balanced_tutorial_machine(),
            cloud_config=args.cloud_config,
            plot_dir=args.plot_dir,
            no_plot=args.no_plot,
        )
    else:
        run_cloud_chained_simulation(
            build_voltage_balanced_tutorial_machine(),
            cloud_config=args.cloud_config,
            plot_dir=args.plot_dir,
            no_plot=args.no_plot,
        )


if __name__ == "__main__":
    main()
