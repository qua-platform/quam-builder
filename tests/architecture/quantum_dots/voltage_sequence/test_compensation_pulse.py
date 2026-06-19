import numpy as np
import pytest
from typing import List, Dict
from qm import SimulationConfig

from quam.components import (
    StickyChannelAddon,
    pulses,
)
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    LFFEMAnalogInputPort,
)

from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    VirtualGateSet,
)
from quam_builder.architecture.quantum_dots.components.voltage_gate import VoltageGate
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.components.readout_resonator import (
    ReadoutResonatorSingle,
)
from qm.qua import *

# Constants
SIM_LENGTH = 40000
HALF_MAX_HEIGHT = 0.25
CLOCK_CYCLE = 4
LFFEM = 6
MWFEM = 1
QOP = "172.16.33.115"
CLUSTER = "CS_4"

# Absolute tolerance (V·ns) for the discrepancy between the expected
# compensation area and the measured compensation area from the waveform report.
# Python path: OPX float16 rounding + duration quantisation → typically < 1 V·ns
# QUA path: additional fixed-point (4.28) rounding in the tracker → larger residual
PYTHON_ATOL = 2.0
QUA_ATOL = 10.0

example_steps = [
    {"voltages": {"virtual_dot_1": 0.1, "virtual_dot_2": -0.3}, "duration": 500},
    {
        "voltages": {"virtual_dot_1": 0.01, "virtual_dot_3": 0.3},
        "duration": 1000,
        "ramp_duration": 1000,
    },
    {"voltages": {"virtual_dot_2": 0.1}, "duration": 1000},
    {"voltages": {"virtual_dot_1": -0.2, "virtual_dot_2": 0.2}, "duration": 1000},
    {"voltages": {}, "duration": 1000},
    {"voltages": {"virtual_dot_1": 0.1}, "duration": 1000, "ramp_duration": 1000},
    {"voltages": {"virtual_dot_1": 0.2, "virtual_dot_2": 0.3}, "duration": 1000},
    {"voltages": {"virtual_dot_2": -0.1, "virtual_dot_3": -0.2}, "duration": 1000},
    {
        "voltages": {"virtual_dot_1": 0.02, "virtual_dot_2": 0.05},
        "duration": 1000,
        "ramp_duration": 1000,
    },
    {
        "voltages": {"virtual_dot_1": -0.2, "virtual_dot_2": 0.1},
        "duration": 1000,
        "ramp_duration": 1000,
    },
    {"voltages": {"virtual_dot_2": -0.1, "virtual_dot_3": 0.1}, "duration": 1000},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_total_area(waveform_list):
    compensation_pulses = waveform_list[-3:]  # go_to_zero, comp, return_to_zero
    signal_pulses = waveform_list[:-3]

    amp_index = 1 if waveform_list[0]["current_amp_elements"][0] == 0.0 else 0

    # go_to_zero brings level to 0, so: level_before + delta = 0
    go_to_zero = compensation_pulses[0]
    go_to_zero_delta = go_to_zero["current_amp_elements"][amp_index] * HALF_MAX_HEIGHT
    final_signal_level = -go_to_zero_delta

    n = len(signal_pulses)
    level_before = [None] * n
    level_after = [None] * n

    # Forward pass: the waveform report normalises the total level change
    # by the base waveform amplitude for both step and ramp pulses, so
    # delta = amplitude_element * HALF_MAX_HEIGHT in both cases.
    current = 0.0
    for i, wf in enumerate(signal_pulses):
        level_before[i] = current
        delta = wf["current_amp_elements"][amp_index] * HALF_MAX_HEIGHT
        current = current + delta
        level_after[i] = current

    # Compute areas
    total_area = 0.0
    schedule = signal_pulses[0]["timestamp"]

    for i, wf in enumerate(signal_pulses):
        start = wf["timestamp"]

        # Sticky hold during gap (ramp hold durations appear here)
        if start > schedule:
            gap = start - schedule
            hold_level = level_after[i - 1] if i > 0 else 0.0
            total_area += hold_level * gap

        duration = wf["length"]
        if wf["pulse_name"] == "ramp":
            # Trapezoid
            total_area += 0.5 * (level_before[i] + level_after[i]) * duration
        else:
            # Step: tracker uses target * duration (no sticky-edge correction)
            total_area += level_after[i] * duration

        schedule = start + duration

    # Sticky hold between last signal pulse and go_to_zero
    comp_start = go_to_zero["timestamp"]
    if comp_start > schedule:
        total_area += level_after[-1] * (comp_start - schedule)

    # Compensation pulse (after go_to_zero, level is 0, so delta IS the level)
    comp = compensation_pulses[1]
    comp_level = comp["current_amp_elements"][amp_index] * HALF_MAX_HEIGHT
    comp_area = comp_level * comp["length"]

    return total_area, comp_area


def random_matrix(rows: int, cols: int, seed: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    m = rng.random((rows, cols)) * 0.01  # values in [0, 1)
    np.fill_diagonal(m, 1.0)  # sets the main diagonal to 1
    return m


def create_voltage_gate(
    name: str,
    opx_output_port: int,
    lf_fem: int = LFFEM,
    controller: str = "con1",
) -> VoltageGate:
    channel = VoltageGate(
        id=name,
        opx_output=LFFEMAnalogOutputPort(
            controller, lf_fem, port_id=opx_output_port, upsampling_mode="pulse"
        ),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    return channel


def create_resonator_channel(
    name: str,
    frequency: int,
    opx_output_port: int,
    opx_input_port: int,
    lf_fem: int = LFFEM,
    controller: str = "con1",
    readout_pulse_len=200,
    readout_pulse_amp=0.01,
) -> ReadoutResonatorSingle:

    readout_pulse = pulses.SquareReadoutPulse(
        length=readout_pulse_len, id="readout", amplitude=readout_pulse_amp
    )
    resonator = ReadoutResonatorSingle(
        id=name,
        frequency_bare=0,
        intermediate_frequency=frequency,
        operations={"readout": readout_pulse},
        opx_output=LFFEMAnalogOutputPort(
            controller, lf_fem, port_id=opx_output_port, upsampling_mode="mw"
        ),
        opx_input=LFFEMAnalogInputPort(controller, lf_fem, port_id=opx_input_port),
    )
    return resonator


def create_example_quam(
    num_plungers: int = 4,
    num_barriers: int = 3,
    num_sensors: int = 1,
    matrix: np.ndarray = None,
) -> BaseQuamQD:

    machine = BaseQuamQD()

    machine.network = {"host": QOP, "cluster_name": CLUSTER}
    plungers = {
        f"virtual_dot_{i+1}": create_voltage_gate(f"plunger_{i+1}", i + 1)
        for i in range(num_plungers)
    }
    barriers = {
        f"virtual_barrier_{i+1}": create_voltage_gate(
            f"barrier_{i+1}", i + 1 + num_plungers
        )
        for i in range(num_barriers)
    }
    sensors = {
        f"virtual_sensor_{i+1}": create_voltage_gate(
            f"sensor_{i+1}", i + 1 + num_plungers + num_barriers
        )
        for i in range(num_sensors)
    }
    resonator = create_resonator_channel(
        "readout_resonator", frequency=int(500e6), opx_output_port=6, opx_input_port=1
    )
    channels = {**plungers, **barriers, **sensors}

    machine.create_virtual_gate_set(
        virtual_channel_mapping=channels,
        gate_set_id="main_qpu",
        compensation_matrix=matrix,
    )

    machine.register_channel_elements(
        plunger_channels=list(plungers.values()),
        barrier_channels=list(barriers.values()),
        sensor_resonator_mappings={list(sensors.values())[0]: resonator},
    )
    return machine


def expected_pulse_sequence(
    virtual_gate_set: VirtualGateSet,
    steps: List[Dict[str, List]],
    max_voltage_compensation=0.01,
    zero_padding_start: int = 318,
    num_samples_total: int = 10000,
):
    """
    Feed steps into the function in the form:
        [
            {
                "voltages" : {"virtual_dot_1": 0.1, "virtual_dot_2": 0.05},
                "duration" : 1000,
            },
            {
                "voltages" : {"virtual_dot_1": -0.01, "virtual_dot_2": 0.02},
                "duration" : 1000,
                "ramp_duration" : 1000,
            },
        ]

    This function will output the expected waveform.
    """
    channels = list(virtual_gate_set.channels.keys())
    valid_names = list(virtual_gate_set.valid_channel_names)
    samples = {ch: np.zeros(zero_padding_start).tolist() for ch in channels}
    areas = {ch: 0 for ch in channels}
    level_tracker = {ch: 0 for ch in channels}

    voltage_state = {name: 0.0 for name in valid_names}
    for gate in steps:
        voltage_state.update(gate["voltages"])
        physical_voltages = virtual_gate_set.resolve_voltages(voltage_state)
        is_ramp = "ramp_duration" in gate

        for ch in channels:
            target = physical_voltages[ch]
            if is_ramp:
                num_ramp_samples = gate["ramp_duration"] // 4
                sample = np.linspace(
                    level_tracker[ch], target, num_ramp_samples, endpoint=False
                )
                samples[ch].extend(sample)
                area = sum(sample)
                areas[ch] = areas[ch] + area

            num_step_samples = gate["duration"] // 4
            sample = np.ones(num_step_samples) * target
            area = sum(sample)
            areas[ch] = areas[ch] + area

            samples[ch].extend(sample)
            level_tracker[ch] = target

    schedule_len = len(list(samples.values())[0])
    if schedule_len > num_samples_total:
        for g, s in samples.items():
            samples[g] = s[:num_samples_total]
    else:
        for g, s in samples.items():
            diff = num_samples_total - schedule_len
            s.extend(np.zeros(diff).tolist())

    areas = {n: -s * CLOCK_CYCLE for n, s in areas.items()}
    return samples, areas


def add_pulse_sequence(
    sequence,
    steps: List[Dict[str, List]],
):
    for s in steps:
        if "ramp_duration" in s:
            sequence.ramp_to_voltages(**s)
        else:
            sequence.step_to_voltages(**s)


def add_pulse_sequence_qua(
    sequence,
    steps: List[Dict[str, List]],
    qua_vars: Dict[str, any],
):
    """Replay the same step list but through QUA variables, so the sequence
    takes the QUA code paths for delta computation, integrated-voltage
    tracking, and compensation calculation."""
    for s in steps:
        voltages_qua = {}
        for name, val in s["voltages"].items():
            assign(qua_vars[name], val)
            voltages_qua[name] = qua_vars[name]

        if "ramp_duration" in s:
            sequence.ramp_to_voltages(
                voltages=voltages_qua,
                duration=s["duration"],
                ramp_duration=s["ramp_duration"],
            )
        else:
            sequence.step_to_voltages(
                voltages=voltages_qua,
                duration=s["duration"],
            )


def _create_program_python(steps):
    machine = create_example_quam(matrix=random_matrix(8, 8, seed=42))
    with program() as prog:
        seq = machine.voltage_sequences["main_qpu"]
        add_pulse_sequence(seq, steps)
        seq.apply_compensation_pulse(max_voltage=0.5)
    return prog, machine


def _create_program_qua(steps):
    machine = create_example_quam(matrix=random_matrix(8, 8, seed=42))
    with program() as prog:
        seq = machine.voltage_sequences["main_qpu"]
        qua_vars = {
            name: declare(fixed, value=0.0) for name in seq.gate_set.valid_channel_names
        }
        add_pulse_sequence_qua(seq, steps, qua_vars)
        seq.apply_compensation_pulse(max_voltage=0.5)
    return prog, machine


def _simulate(machine, prog, simulation_duration: int):
    qmm = machine.connect()
    simulation_config = SimulationConfig(duration=simulation_duration // 4)
    job = qmm.simulate(machine.generate_config(), prog, simulation_config)
    job.wait_until("Done")
    waveform_report = job.get_simulated_waveform_report()
    return waveform_report.to_dict()


def _measure_compensation_areas(machine, waveform_dict):
    """Return {channel_name: measured_comp_area} from the waveform report."""
    element_names = list(machine.virtual_gate_sets["main_qpu"].channels.keys())
    element_waveforms = {
        name: [k for k in waveform_dict["analog_waveforms"] if k["element"] == name]
        for name in element_names
    }
    return {name: find_total_area(wf)[1] for name, wf in element_waveforms.items()}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_compensation_pulse_python_voltages():
    """Compensation area from Python-valued voltages matches expected within PYTHON_ATOL."""
    prog, machine = _create_program_python(example_steps)
    _, expected_areas = expected_pulse_sequence(
        machine.virtual_gate_sets["main_qpu"],
        example_steps,
        num_samples_total=SIM_LENGTH,
    )
    waveform_dict = _simulate(machine, prog, SIM_LENGTH)
    measured_areas = _measure_compensation_areas(machine, waveform_dict)

    for ch_name, measured in measured_areas.items():
        expected = expected_areas[ch_name]
        diff = abs(measured - expected)
        assert diff < PYTHON_ATOL, (
            f"{ch_name}: compensation area discrepancy {diff:.4f} V·ns "
            f"exceeds tolerance {PYTHON_ATOL} V·ns "
            f"(expected={expected:.4f}, measured={measured:.4f})"
        )


def test_compensation_pulse_qua_voltages():
    """Compensation area from QUA-variable voltages matches expected within QUA_ATOL."""
    prog, machine = _create_program_qua(example_steps)
    _, expected_areas = expected_pulse_sequence(
        machine.virtual_gate_sets["main_qpu"],
        example_steps,
        num_samples_total=SIM_LENGTH,
    )
    waveform_dict = _simulate(machine, prog, SIM_LENGTH)
    measured_areas = _measure_compensation_areas(machine, waveform_dict)

    for ch_name, measured in measured_areas.items():
        expected = expected_areas[ch_name]
        diff = abs(measured - expected)
        assert diff < QUA_ATOL, (
            f"{ch_name}: compensation area discrepancy {diff:.4f} V·ns "
            f"exceeds tolerance {QUA_ATOL} V·ns "
            f"(expected={expected:.4f}, measured={measured:.4f})"
        )
