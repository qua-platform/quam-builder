"""Smoke test for the QM SaaS cloud simulator fixture."""

from qm import qua

from validation_utils import simulate_program


def test_saas_simulate_voltage_gate_sequence(qmm_saas, machine):
    """Verify qmm_saas can simulate a minimal voltage-gate program on LF-FEM slot 5."""
    machine.gate_set.add_point(
        "init",
        voltages={"ch1": 0.5, "ch2": -0.2},
        duration=100,
    )

    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.step_to_point("init")
        seq.ramp_to_zero()

    _, samples = simulate_program(qmm_saas, machine, prog, simulation_duration=2000)

    assert "con1" in samples
    assert f"{5}-{6}" in samples["con1"].analog
    assert f"{5}-{3}" in samples["con1"].analog
