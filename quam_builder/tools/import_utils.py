"""Utilities for dynamic class loading and imports."""

import importlib
from typing import Type, TypeVar

__all__ = ["load_class_from_string"]

T = TypeVar("T")


def load_class_from_string(class_path: str) -> Type[T]:
    """Load a class dynamically from a string path.

    Args:
        class_path: Full path to the class in the format 'module.ClassName'.

    Returns:
        The class type.

    Raises:
        ValueError: If the class_path format is invalid.
        ImportError: If the module or class cannot be imported.

    Example:
        >>> MyClass = load_class_from_string("my_module.MyClass")
        >>> instance = MyClass()
    """
    if "." not in class_path:
        raise ValueError(
            "class_path should be a full path in the format 'module.ClassName'"
        )
    module_path, class_name = class_path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ModuleNotFoundError, AttributeError) as e:
        raise ImportError(f"Could not import class '{class_path}': {e}")
