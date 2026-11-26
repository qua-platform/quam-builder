
import pytest

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)


@pytest.mark.parametrize(
    "host, cluster_name",
    [
        ("127.0.0.1", "tutorial"),
        ("192.168.1.100", "test_cluster"),
    ],
)
def test_tutorial_machine_network(host, cluster_name):
    machine = build_tutorial_machine(
        host=host,
        cluster_name=cluster_name,
    )

    assert type(machine).__name__ == "LossDiVincenzoQuam"
    assert machine.network["host"] == host
    assert machine.network["cluster_name"] == cluster_name
    assert set(machine.qubits.keys()) == {"q1", "q2"}
