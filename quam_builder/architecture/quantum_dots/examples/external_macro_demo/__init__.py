"""Demo package for external macro catalog workflow.

Provides build_macro_overrides for use with wire_machine_macros.
"""

from .catalog import LabInitializeMacro, build_macro_overrides

__all__ = ["LabInitializeMacro", "build_macro_overrides"]
