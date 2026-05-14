"""Demo package for external macro catalog workflow.

Provides build_component_overrides for use with wire_machine_macros.
"""

from .catalog import LabInitializeMacro, build_component_overrides

__all__ = ["LabInitializeMacro", "build_component_overrides"]
