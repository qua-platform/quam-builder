"""Legacy import wrapper for voltage sequence helpers."""

from quam_builder.tools.voltage_sequence.voltage_sequence import (
    DEFAULT_PULSE_NAME,
    VoltageSequence,
    VoltageTuningPoint,
)

__all__ = ["VoltageSequence", "VoltageTuningPoint", "DEFAULT_PULSE_NAME"]
