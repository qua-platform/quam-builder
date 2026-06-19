"""Compatibility layer for virtual gate modules."""

from . import virtual_gate_set, virtualisation_layer
from .virtual_gate_set import *  # noqa: F401,F403
from .virtualisation_layer import *  # noqa: F401,F403

__all__ = [
    *virtual_gate_set.__all__,
    *virtualisation_layer.__all__,
]
