import os
from pathlib import Path

from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from qualang_tools.wirer.wirer.channel_specs import lf_fem_spec


EXAMPLES_DIR = Path(__file__).resolve().parent
os.environ.setdefault("QUAM_STATE_PATH", str(EXAMPLES_DIR / "quam_state"))

########################################################################################################################
# %%                                              Define static parameters
########################################################################################################################
sensor_dots = [1, 2, 3]
quantum_dots = [1, 2, 3]
quantum_dot_pairs = list(zip(quantum_dots, quantum_dots[1:]))

########################################################################################################################
# %%                                 Define custom/hardcoded channel addresses
########################################################################################################################
# Multiplexed readout for sensor 1 to 2 and 3 to 4 on two feed-lines
s_ch = lf_fem_spec(con=1, out_slot=3)
s1_res_ch = lf_fem_spec(con=1, in_slot=2, out_slot=2, in_port=1, out_port=1)
s1_res_ch_port2 = lf_fem_spec(con=1, in_slot=2, out_slot=2, in_port=1, out_port=2)
s2to3_res_ch = lf_fem_spec(con=1, in_slot=3, out_slot=3, in_port=2, out_port=8)
barrier_pair_1_ch = lf_fem_spec(con=1, out_slot=2, out_port=2)
barrier_pair_2_ch = lf_fem_spec(con=1, out_slot=2, out_port=3)
barrier_pair_1_alt_ch = lf_fem_spec(con=1, out_slot=2, out_port=3)
barrier_pair_2_alt_ch = lf_fem_spec(con=1, out_slot=2, out_port=4)


def _make_instruments() -> Instruments:
    instruments = Instruments()
    instruments.add_lf_fem(controller=1, slots=[2, 3])
    return instruments


def _make_connectivity(
    include_barrier_gates: bool,
    barrier_constraints=None,
    s1_res_constraints=None,
) -> Connectivity:
    connectivity = Connectivity()

    # Option 2: explicit resonator and voltage-gate wiring with constraints
    connectivity.add_sensor_dot_resonator_line(
        sensor_dots[0],
        shared_line=False,
        constraints=s1_res_constraints or s1_res_ch,
    )
    connectivity.add_sensor_dot_resonator_line(
        sensor_dots[1:],
        shared_line=True,
        constraints=s2to3_res_ch,
    )
    connectivity.add_sensor_dot_voltage_gate_lines(sensor_dots, constraints=s_ch)

    # Plunger gates for quantum dots (constrained to the same LF-FEM)
    connectivity.add_quantum_dot_voltage_gate_lines(quantum_dots, constraints=s_ch)

    if include_barrier_gates:
        connectivity.add_quantum_dot_pairs(
            quantum_dot_pairs=quantum_dot_pairs,
            constraints=barrier_constraints,
        )

    return connectivity


def _dump_instruments(instruments: Instruments, label: str) -> None:
    print(f"\n--- Instruments snapshot ({label}) ---")
    available_channels = getattr(instruments, "available_channels", None)
    if available_channels is None:
        print("No available_channels attribute found on instruments.")
        return
    for channel_type, channels in available_channels.items():
        print(f"{channel_type}: {len(channels)} available")
        print(channels)


def _dump_connectivity(connectivity: Connectivity, label: str) -> None:
    print(f"\n--- Connectivity snapshot ({label}) ---")
    elements = getattr(connectivity, "elements", None)
    if not elements:
        print("No elements found on connectivity.")
    else:
        element_items = elements.items() if isinstance(elements, dict) else enumerate(elements)
        print(f"Total elements: {len(elements)}")
        for key, element in element_items:
            name = getattr(element, "name", None) or getattr(element, "id", None) or str(key)
            element_type = type(element)
            print(f"- {name} ({element_type})")
            try:
                element_vars = vars(element)
            except TypeError:
                element_vars = None
            if element_vars:
                print(f"  fields: {element_vars}")
            else:
                print(f"  repr: {element!r}")

    specs = getattr(connectivity, "specs", None)
    if not specs:
        print("No wiring specs found on connectivity.")
        return
    print(f"\nWiring specs: {len(specs)}")
    for idx, spec in enumerate(specs, start=1):
        print(f"- spec[{idx}]")
        try:
            spec_vars = vars(spec)
        except TypeError:
            spec_vars = None
        if spec_vars:
            print(f"  fields: {spec_vars}")
        else:
            print(f"  repr: {spec!r}")


def _print_exception_details(exc: Exception) -> None:
    print(f"  type: {type(exc)}")
    print(f"  message: {exc}")
    print(f"  repr: {exc!r}")


def example_port_constraints_ok_without_barriers() -> None:
    """Port constraints are respected; allocation succeeds without barrier gates."""
    print("=" * 80)
    print("EXAMPLE: Port constraints WITHOUT barrier gates (expected to succeed)")
    print("=" * 80)

    instruments = _make_instruments()
    connectivity = _make_connectivity(include_barrier_gates=False)

    print("Allocating wiring (no barrier gates)...")
    try:
        allocate_wiring(connectivity, instruments)
        print("✓ Allocation succeeded without barrier gates")
    except Exception as exc:
        print(f"✗ Allocation failed without barrier gates: {exc}")
        _print_exception_details(exc)
        _dump_connectivity(connectivity, label="no barriers")
        _dump_instruments(instruments, label="no barriers")
        raise


def example_port_constraints_fail_with_barriers() -> bool:
    """Port constraints are respected; allocation fails once barrier gates are added."""
    print("=" * 80)
    print("EXAMPLE: Port constraints WITH barrier gates (expected to fail)")
    print("=" * 80)

    instruments = _make_instruments()
    connectivity = _make_connectivity(include_barrier_gates=True)

    print("Allocating wiring (with barrier gates)...")
    try:
        allocate_wiring(connectivity, instruments)
        print("✓ Allocation succeeded with barrier gates (unexpected)")
        return True
    except Exception as exc:
        print(f"✗ Allocation failed with barrier gates: {exc}")
        _print_exception_details(exc)
        wiring_spec = getattr(exc, "wiring_spec", None) or getattr(exc, "spec", None)
        if wiring_spec is not None:
            print(f"\n--- Exception wiring spec ---\n{wiring_spec}")
        _dump_connectivity(connectivity, label="with barriers")
        _dump_instruments(instruments, label="with barriers")
        return False


def example_barrier_constraints_avoid_rf() -> None:
    """Constrain each barrier to a non-conflicting port (expected to succeed)."""
    print("=" * 80)
    print("EXAMPLE: Constrain barrier gates per-pair (expected to succeed)")
    print("=" * 80)

    instruments = _make_instruments()
    connectivity = _make_connectivity(include_barrier_gates=False)
    connectivity.add_quantum_dot_pairs(
        quantum_dot_pairs=[quantum_dot_pairs[0]],
        constraints=barrier_pair_1_ch,
    )
    connectivity.add_quantum_dot_pairs(
        quantum_dot_pairs=[quantum_dot_pairs[1]],
        constraints=barrier_pair_2_ch,
    )

    print("Allocating wiring (barrier gates constrained per pair)...")
    try:
        allocate_wiring(connectivity, instruments)
        print("✓ Allocation succeeded with barrier constraints")
    except Exception as exc:
        print(f"✗ Allocation failed with barrier constraints: {exc}")
        _print_exception_details(exc)
        _dump_connectivity(connectivity, label="barriers constrained")
        _dump_instruments(instruments, label="barriers constrained")
        raise


def example_move_rf_port() -> None:
    """Move the s1 resonator RF output to port 2 (expected to succeed)."""
    print("=" * 80)
    print("EXAMPLE: Move s1 RF output to port 2 (expected to succeed)")
    print("=" * 80)

    instruments = _make_instruments()
    connectivity = _make_connectivity(
        include_barrier_gates=False,
        s1_res_constraints=s1_res_ch_port2,
    )
    connectivity.add_quantum_dot_pairs(
        quantum_dot_pairs=[quantum_dot_pairs[0]],
        constraints=barrier_pair_1_alt_ch,
    )
    connectivity.add_quantum_dot_pairs(
        quantum_dot_pairs=[quantum_dot_pairs[1]],
        constraints=barrier_pair_2_alt_ch,
    )

    print("Allocating wiring (s1 RF output moved to port 2)...")
    try:
        allocate_wiring(connectivity, instruments)
        print("✓ Allocation succeeded with moved RF port")
    except Exception as exc:
        print(f"✗ Allocation failed with moved RF port: {exc}")
        _print_exception_details(exc)
        _dump_connectivity(connectivity, label="s1 RF moved")
        _dump_instruments(instruments, label="s1 RF moved")
        raise


if __name__ == "__main__":
    example_port_constraints_ok_without_barriers()
    example_port_constraints_fail_with_barriers()
    example_barrier_constraints_avoid_rf()
    example_move_rf_port()
