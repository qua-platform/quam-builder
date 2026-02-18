"""
pylint-qua-plugin: A Pylint plugin for QUA DSL compatibility.

This plugin suppresses false positive warnings in QUA code contexts.
"""

from .pylint_qua_plugin import register

__version__ = "0.1.0"
__all__ = ["register"]