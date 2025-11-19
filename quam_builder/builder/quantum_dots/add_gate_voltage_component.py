from typing import Dict, Union
from quam_builder.architecture.quantum_dots.components.voltage_gate import VoltageGate
from quam_builder.architecture.quantum_dots.qubit import (
    LDQubit,
)


def add_gate_voltage_component(
    qubit: Union[LDQubit],
    wiring_path: str,
    ports: Dict[str, str],
):
    """Adds a flux component to a ldv qubit based on the provided wiring path and ports.

    Args:
        qubit (Union[LDQubit]): The qubit to which the gate voltage component will be added.
        wiring_path (str): The path to the wiring configuration.
        ports (Dict[str, str]): A dictionary mapping port names to their respective configurations.

    Raises:
        ValueError: If the port keys do not match any implemented mapping.
    """
    if "opx_output" in ports:
        qubit.z = VoltageGate(opx_output=f"{wiring_path}/opx_output")
    else:
        raise ValueError(
            f"Unimplemented mapping of port keys to channel for ports: {ports}"
        )
