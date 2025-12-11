from enum import Enum

from qualang_tools.wirer.connectivity import wiring_spec


# Extend WiringLineType with quantum-dot specific entries when missing in the installed
# qualang_tools version. This keeps the tests compatible with older releases.
_existing_members = {member.name: member.value for member in wiring_spec.WiringLineType}
_extra_members = {
    "PLUNGER_GATE": "plunger_gate",
    "PLUNGER": "plunger_gate",
    "BARRIER_GATE": "barrier_gate",
    "BARRIER": "barrier_gate",
    "GLOBAL_GATE": "global_gate",
    "SENSOR_GATE": "sensor_gate",
    "RF_RESONATOR": "rf_resonator",
}

if any(name not in _existing_members for name in _extra_members):
    merged = {**_existing_members, **{k: v for k, v in _extra_members.items() if k not in _existing_members}}
    ExtendedWiringLineType = Enum("WiringLineType", merged)

    wiring_spec.WiringLineType = ExtendedWiringLineType
    # Ensure any future imports see the extended enum
    import sys

    sys.modules["qualang_tools.wirer.connectivity.wiring_spec"].WiringLineType = ExtendedWiringLineType
