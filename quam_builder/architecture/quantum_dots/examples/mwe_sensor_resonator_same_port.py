from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from qualang_tools.wirer.wirer.channel_specs import lf_fem_spec


SENSOR_DOTS = [1, 2, 3]
QUANTUM_DOTS = [1, 2, 3]
QUANTUM_DOT_PAIRS = list(zip(QUANTUM_DOTS, QUANTUM_DOTS[1:]))

SENSOR_GATE_CONSTRAINTS = lf_fem_spec(con=1, out_slot=3)
S1_RESONATOR_CONSTRAINTS = lf_fem_spec(con=1, in_slot=2, out_slot=2, in_port=1, out_port=1)
S2TO3_RESONATOR_CONSTRAINTS = lf_fem_spec(con=1, in_slot=3, out_slot=3, in_port=2, out_port=8)
BAR_PAIR_1_CONSTRAINTS = lf_fem_spec(con=1, out_slot=2, out_port=2)
BAR_PAIR_2_CONSTRAINTS = lf_fem_spec(con=1, out_slot=2, out_port=3)


def _make_instruments() -> Instruments:
    instruments = Instruments()
    instruments.add_lf_fem(controller=1, slots=[2, 3])
    return instruments


def _channels_to_port_dicts(channels) -> list[dict]:
    port_dicts = []
    for channel in channels:
        port_dicts.append(
            {
                "con": getattr(channel, "con", None),
                "slot": getattr(channel, "slot", None),
                "port": getattr(channel, "port", None),
            }
        )
    return port_dicts


def _run_allocation(connectivity: Connectivity, label: str) -> None:
    print(f"Allocating wiring: {label}")
    try:
        instruments = _make_instruments()
        allocate_wiring(connectivity, instruments)
        print("✓ Allocation succeeded")
        available_channels = getattr(instruments, "available_channels", None)
        if available_channels is None:
            print("  No available_channels attribute found on instruments.")
        else:
            print("  Available channels after allocation:")
            for channel_type, channels in available_channels.items():
                channel_ports = _channels_to_port_dicts(channels)
                print(f"    {channel_type}: {len(channels)}")
                print(f"      {channel_ports}")
    except Exception as exc:
        print(f"✗ Allocation failed: {exc}")
        print(f"  type: {type(exc)}")
        print(f"  repr: {exc!r}")


def case_1_single_resonator() -> None:
    connectivity = Connectivity()
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[0],
        shared_line=False,
        constraints=S1_RESONATOR_CONSTRAINTS,
    )
    _run_allocation(connectivity, "single sensor resonator line (same in/out port)")


def case_2_resonator_plus_sensor_gate() -> None:
    connectivity = Connectivity()
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[0],
        shared_line=False,
        constraints=S1_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_voltage_gate_lines([SENSOR_DOTS[0]], constraints=SENSOR_GATE_CONSTRAINTS)
    _run_allocation(connectivity, "resonator + sensor gate voltage line")


def case_3_resonators_and_sensor_gates() -> None:
    connectivity = Connectivity()
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[0],
        shared_line=False,
        constraints=S1_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[1:],
        shared_line=True,
        constraints=S2TO3_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_voltage_gate_lines(SENSOR_DOTS, constraints=SENSOR_GATE_CONSTRAINTS)
    _run_allocation(connectivity, "3 sensors: resonators + sensor gate voltages")


def case_4_add_quantum_dot_plungers() -> None:
    connectivity = Connectivity()
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[0],
        shared_line=False,
        constraints=S1_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[1:],
        shared_line=True,
        constraints=S2TO3_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_voltage_gate_lines(SENSOR_DOTS, constraints=SENSOR_GATE_CONSTRAINTS)
    connectivity.add_quantum_dot_voltage_gate_lines(QUANTUM_DOTS, constraints=SENSOR_GATE_CONSTRAINTS)
    _run_allocation(connectivity, "add quantum dot plunger gates")


def case_5_add_barriers_unconstrained() -> None:
    connectivity = Connectivity()
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[0],
        shared_line=False,
        constraints=S1_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[1:],
        shared_line=True,
        constraints=S2TO3_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_voltage_gate_lines(SENSOR_DOTS, constraints=SENSOR_GATE_CONSTRAINTS)
    connectivity.add_quantum_dot_voltage_gate_lines(QUANTUM_DOTS, constraints=SENSOR_GATE_CONSTRAINTS)
    connectivity.add_quantum_dot_pairs(QUANTUM_DOT_PAIRS)
    _run_allocation(connectivity, "add barrier gates (unconstrained)")


def case_6_add_barriers_constrained_unused_slot() -> None:
    connectivity = Connectivity()
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[0],
        shared_line=False,
        constraints=S1_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_resonator_line(
        SENSOR_DOTS[1:],
        shared_line=True,
        constraints=S2TO3_RESONATOR_CONSTRAINTS,
    )
    connectivity.add_sensor_dot_voltage_gate_lines(SENSOR_DOTS, constraints=SENSOR_GATE_CONSTRAINTS)
    connectivity.add_quantum_dot_voltage_gate_lines(QUANTUM_DOTS, constraints=SENSOR_GATE_CONSTRAINTS)
    connectivity.add_quantum_dot_pairs([QUANTUM_DOT_PAIRS[0]], constraints=BAR_PAIR_1_CONSTRAINTS)
    connectivity.add_quantum_dot_pairs([QUANTUM_DOT_PAIRS[1]], constraints=BAR_PAIR_2_CONSTRAINTS)
    _run_allocation(connectivity, "add barrier gates (constrained to free slot)")


def main() -> None:
    case_1_single_resonator()
    case_2_resonator_plus_sensor_gate()
    case_3_resonators_and_sensor_gates()
    case_4_add_quantum_dot_plungers()
    case_5_add_barriers_unconstrained()
    case_6_add_barriers_constrained_unused_slot()


if __name__ == "__main__":
    main()
