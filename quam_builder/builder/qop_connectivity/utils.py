"""
Utility functions for wiring generation.

This module contains helper functions used across the wiring generation system.
"""
from functools import reduce
from typing import Dict, Any


def set_nested_value_with_path(d: Dict, path: str, value: Any) -> None:
    """Sets a value in a nested dictionary using a '/' separated path.

    This function creates any missing intermediate dictionaries as needed.

    Args:
        d: The dictionary in which the value will be set
        path: The '/' separated path to the value (e.g., "qubits/q0/drive/port")
        value: The value to set

    Example:
        >>> d = {}
        >>> set_nested_value_with_path(d, "a/b/c", "value")
        >>> # d is now {"a": {"b": {"c": "value"}}}
    """
    keys = path.split("/")  # Split the path into keys
    reduce(lambda d, key: d.setdefault(key, {}), keys[:-1], d)[keys[-1]] = value