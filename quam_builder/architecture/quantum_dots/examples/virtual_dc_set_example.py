"""
VirtualDCSet example (updated)

This example shows how to build and use a :class:`~quam_builder.architecture.quantum_dots.components.virtual_dc_set.VirtualDCSet`
to control DC offsets via a virtualization stack **independent of the OPX**, using external DAC drivers.

Key ideas:
- Physical channels are :class:`~quam_builder.architecture.quantum_dots.components.voltage_gate.VoltageGate` objects.
- Each physical gate should have:
  - ``offset_parameter``: a callable like a QCoDeS parameter (``param() -> float`` and ``param(v)`` sets)
  - ``dac_spec``: a :class:`~quam_builder.architecture.quantum_dots.components.dac_spec.DacSpec` (or ``QdacSpec``)
    with ``abs_dac_voltage_limit`` set, so VirtualDCSet can enforce per-channel limits.

By default this file runs without QCoDeS (it uses a small in-memory fake parameter).
Set ``QUAM_QDAC=1`` to use a real QDAC-II via QCoDeS if available.
"""

from __future__ import annotations

import os
from typing import Callable

from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components.dac_spec import DacSpec, QdacSpec
from quam_builder.architecture.quantum_dots.components.virtual_dc_set import VirtualDCSet
from quam_builder.architecture.quantum_dots.components.voltage_gate import VoltageGate


class FakeOffsetParameter:
    """Minimal QCoDeS-like parameter: param() -> value, param(v) sets value."""

    def __init__(self, initial: float = 0.0) -> None:
        self._value = float(initial)

    def __call__(self, value: float | None = None) -> float:
        if value is not None:
            self._value = float(value)
        return self._value


def create_voltage_gate(
    *,
    gate_id: str,
    opx_port_id: int,
    dac_output_port: int,
    lf_fem: int = 5,
    dac_voltage_limit: float = 2.5,
    offset_parameter: Callable[[float | None], float],
    use_qdac_spec: bool = False,
) -> VoltageGate:
    """Create a VoltageGate wired to an external DAC via offset_parameter + dac_spec."""
    gate = VoltageGate(
        id=gate_id,
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=opx_port_id),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    gate.offset_parameter = offset_parameter
    gate.dac_spec = (
        QdacSpec(
            output_port=dac_output_port,
            dac_name="main",
            abs_dac_voltage_limit=dac_voltage_limit,
        )
        if use_qdac_spec
        else DacSpec(
            output_port=dac_output_port,
            dac_name="main",
            abs_dac_voltage_limit=dac_voltage_limit,
        )
    )
    return gate


###########################################
###### Instantiate Physical Channels ######
###########################################
use_qdac = os.environ.get("QUAM_QDAC") == "1"

if use_qdac:
    from qcodes import Instrument
    from qcodes_contrib_drivers.drivers.QDevil.QDAC2 import QDac2

    qdac_ip = os.environ.get("QDAC_IP", "172.16.33.111")
    qdac_name = os.environ.get("QDAC_NAME", "QDAC")

    try:
        qdac = Instrument.find_instrument(qdac_name)
    except KeyError:
        qdac = QDac2(
            qdac_name, visalib="@py", address=f"TCPIP::{qdac_ip}::5025::SOCKET"
        )

    def make_param(port: int) -> Callable[[float | None], float]:
        return qdac.channel(port).dc_constant_V

    use_qdac_spec = True
else:
    def make_param(_port: int) -> FakeOffsetParameter:
        return FakeOffsetParameter(0.0)

    use_qdac_spec = False


p1 = create_voltage_gate(
    gate_id="plunger_1",
    opx_port_id=1,
    dac_output_port=1,
    dac_voltage_limit=0.5,  # unique limit for this gate
    offset_parameter=make_param(1),
    use_qdac_spec=use_qdac_spec,
)
p2 = create_voltage_gate(
    gate_id="plunger_2",
    opx_port_id=2,
    dac_output_port=2,
    offset_parameter=make_param(2),
    use_qdac_spec=use_qdac_spec,
)
p3 = create_voltage_gate(
    gate_id="plunger_3",
    opx_port_id=3,
    dac_output_port=3,
    offset_parameter=make_param(3),
    use_qdac_spec=use_qdac_spec,
)
p4 = create_voltage_gate(
    gate_id="plunger_4",
    opx_port_id=4,
    dac_output_port=4,
    offset_parameter=make_param(4),
    use_qdac_spec=use_qdac_spec,
)
b1 = create_voltage_gate(
    gate_id="barrier_1",
    opx_port_id=5,
    dac_output_port=5,
    offset_parameter=make_param(5),
    use_qdac_spec=use_qdac_spec,
)
b2 = create_voltage_gate(
    gate_id="barrier_2",
    opx_port_id=6,
    dac_output_port=6,
    dac_voltage_limit=0.05,  # unique limit for this gate
    offset_parameter=make_param(6),
    use_qdac_spec=use_qdac_spec,
)
b3 = create_voltage_gate(
    gate_id="barrier_3",
    opx_port_id=7,
    dac_output_port=7,
    offset_parameter=make_param(7),
    use_qdac_spec=use_qdac_spec,
)
s1 = create_voltage_gate(
    gate_id="sensor_DC",
    opx_port_id=8,
    dac_output_port=8,
    offset_parameter=make_param(8),
    use_qdac_spec=use_qdac_spec,
)


###########################################
###### Instantiate VirtualDCSet Layer #####
###########################################
virtual_dc_set = VirtualDCSet(
    id="Dots DC",
    channels={
        "plunger_1": p1,
        "plunger_2": p2,
        "plunger_3": p3,
        "plunger_4": p4,
        "barrier_1": b1,
        "barrier_2": b2,
        "barrier_3": b3,
        "sensor_DC": s1,
    },
    check_max_voltage=True,
)

# Matrix shape is [source_gates x target_gates]
virtual_dc_set.add_layer(
    layer_id="cross_compensation",
    source_gates=["VP1", "VP2", "VP3", "VP4"],
    target_gates=["plunger_1", "plunger_2", "plunger_3", "plunger_4"],
    matrix=[
        [1, 0.2, 0, 0.3],
        [0.5, 1, 0.7, 0],
        [0.3, 0, 1, 0.6],
        [0, 0.1, 0.3, 1],
    ],
)

virtual_dc_set.add_layer(
    layer_id="detuning_1",
    source_gates=["det_1", "det_2"],
    target_gates=["VP1", "VP2"],
    matrix=[
        [0.8, 0.5],
        [0.3, 0.7],
    ],
)

virtual_dc_set.add_layer(
    layer_id="detuning_2",
    source_gates=["det_3", "det_4"],
    target_gates=["VP3", "VP4"],
    matrix=[
        [0.7, 0.4],
        [0.6, 0.9],
    ],
)


###########################################
###### Apply a virtual voltage change #####
###########################################
# Set absolute targets (virtual or physical names are allowed).
# VirtualDCSet will:
# - optionally requery current physical voltages (requery=True),
# - compute deltas in the mixed virtual/physical space,
# - resolve those deltas back to physical DAC outputs,
# - enforce per-channel ``abs_dac_voltage_limit``,
# - write final values via ``offset_parameter``.
virtual_dc_set.set_voltages(
    {"det_1": 0.10, "det_2": -0.05, "barrier_2": 0.02},
    requery=True,
    resync=True,
)

print("Applied physical voltages:")
for ch_name, ch in virtual_dc_set.channels.items():
    print(
        f"  {ch_name}: {ch.offset_parameter(): .4f} V "
        f"(limit={getattr(ch.dac_spec, 'abs_dac_voltage_limit', None)} V)"
    )

print("\nAll current virtual+physical levels (computed):")
print(virtual_dc_set.all_current_voltages)

print("\nChecking that DAC limits raise as expected...")
try:
    # Both of these exceed the per-gate abs_dac_voltage_limit set above.
    virtual_dc_set.set_voltages(
        {"plunger_1": 0.8, "barrier_2": 0.2},
        requery=True,
        resync=False,
    )
except ValueError as exc:
    msg = str(exc)
    assert "exceeds limit" in msg or "exceed" in msg, msg
    print(f"OK: caught expected ValueError: {exc}")
else:
    raise AssertionError("Expected a ValueError due to DAC voltage limits, but none was raised.")
