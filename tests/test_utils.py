"""Utilities for AST comparisons in tests."""

from typing import Any

import numpy as np
import pytest

# Assuming 'quaqsim' is an installed dependency.
# These imports are for type hinting and potentially for isinstance checks if needed.
pytest.importorskip("quaqsim")
from quaqsim.program_ast.node import Node
from quaqsim.program_ast.expressions.expression import Expression
from quaqsim.program_ast.expressions.definition import Definition


class SKIP_AST_ENTRY:
    pass


def is_float_str(value: Any) -> bool:
    """Checks if a value is a string that can be converted to a float."""
    try:
        float(value)
        return True
    except Exception:
        return False


# Helper function to log mismatches with path and context
def _log_mismatch(path_list: list[str], reason: str, n1_context: Any, n2_context: Any):
    path_str = ".".join(str(p) for p in path_list) if path_list else "root"
    print(f"Mismatch at {path_str}: {reason}\n")

    if isinstance(n1_context, list):
        print("Node 1: ")
        for elem in n1_context:
            code = _format_value_as_code(elem, 1).replace("\\n", "\n")
            print(f"{code}, ")
    else:
        print(f"Node 1: {_format_value_as_code(n1_context, 0)}")
    if isinstance(n2_context, list):
        print("Node 2: ")
        for elem in n2_context:
            code = _format_value_as_code(elem, 1).replace("\\n", "\n")
            print(f"{code}, ")
    else:
        print(f"Node 2: {_format_value_as_code(n2_context, 0)}")


def compare_ast_nodes(
    node1: Any, node2: Any, current_path: list[str] | None = None
) -> bool:
    """Recursively compares two QUA AST elements for structural equality.

    Compares nodes, their attributes (which can be other nodes, expressions,
    lists, or literals) for structural equality. The top-level arguments
    are expected to be Node instances for a meaningful AST comparison.

    Args:
        node1: The first AST element (expected to be Node at top level).
        node2: The second AST element (expected to be Node at top level).
        current_path: A list representing the path to the current comparison point.

    Returns:
        True if the elements are structurally identical, False otherwise.
    """
    if current_path is None:
        current_path = []

    if node1 is SKIP_AST_ENTRY or node2 is SKIP_AST_ENTRY:
        return True
    if type(node1) is not type(node2):
        _log_mismatch(
            current_path,
            f"Types differ. Got {type(node1).__name__} and {type(node2).__name__}",
            node1,
            node2,
        )
        return False

    if isinstance(node1, (int, str, bool, float, type(None))):
        if is_float_str(node1) and is_float_str(node2):
            if np.isclose(float(node1), float(node2)):
                return True
        if node1 != node2:
            _log_mismatch(
                current_path,
                f"Literal values differ. Got '{node1}' and '{node2}'",
                node1,
                node2,
            )
            return False
        return True

    if isinstance(node1, list):
        # node2 is confirmed to be a list by the initial type check
        if len(node1) != len(node2):
            _log_mismatch(
                current_path,
                f"List lengths differ. Got {len(node1)} and {len(node2)}",
                node1,
                node2,
            )
            return False
        for i, (item1, item2) in enumerate(zip(node1, node2)):
            item_path = current_path + [f"[{i}]"]
            if not compare_ast_nodes(item1, item2, item_path):
                return False
        return True

    # Check for objects that have a __dict__
    if hasattr(node1, "__dict__") and hasattr(node2, "__dict__"):
        # Types matched and they have __dict__
        if isinstance(node1, (Node, Expression)):
            # node2 is also Node or Expression due to type check
            dict1 = node1.__dict__
            dict2 = node2.__dict__

            if set(dict1.keys()) != set(dict2.keys()):
                reason = (
                    f"Attribute keys differ. "
                    f"Keys1: {sorted(list(set(dict1.keys())))}. "
                    f'Keys2: {sorted(list(set(dict2.keys())))}"'
                )
                _log_mismatch(current_path, reason, node1, node2)
                return False

            # Sort keys for deterministic comparison
            sorted_keys = sorted(dict1.keys())
            for key in sorted_keys:
                attr_path = current_path + [key]
                if not compare_ast_nodes(dict1[key], dict2[key], attr_path):
                    return False
            return True
        elif isinstance(node1, Definition):  # node2 is also Definition
            if node1.name != node2.name:
                _log_mismatch(
                    current_path + ["name"],
                    f"Definition names differ. N1: '{node1.name}', N2: '{node2.name}'",
                    node1,
                    node2,
                )
                return False
            if node1.type != node2.type:
                _log_mismatch(
                    current_path + ["type"],
                    f"Definition types differ. T1: '{node1.type}', T2: '{node2.type}'",
                    node1,
                    node2,
                )
                return False

            # Ensure 'value' attributes are lists (if they exist)
            node1_value = getattr(node1, "value", None)
            node2_value = getattr(node2, "value", None)

            if not (isinstance(node1_value, list) and isinstance(node2_value, list)):
                _log_mismatch(
                    current_path + ["value"],
                    "Def 'value' attr is not list for one/both nodes, or missing.",
                    node1,
                    node2,
                )
                return False

            if len(node1_value) != len(node2_value):
                _log_mismatch(
                    current_path + ["value"],
                    f"Def value list lengths differ. "
                    f"L1: {len(node1_value)}, L2: {len(node2_value)}",
                    node1,
                    node2,
                )
                return False

            for i, (val_item1, val_item2) in enumerate(zip(node1_value, node2_value)):
                item_path = current_path + [f"value[{i}]"]

                d_item1 = (
                    val_item1.__dict__
                    if not isinstance(val_item1, dict)
                    and hasattr(val_item1, "__dict__")
                    else val_item1
                )
                d_item2 = (
                    val_item2.__dict__
                    if not isinstance(val_item2, dict)
                    and hasattr(val_item2, "__dict__")
                    else val_item2
                )

                if not (isinstance(d_item1, dict) and isinstance(d_item2, dict)):
                    _log_mismatch(
                        item_path,
                        "Def value item is not structured as a dictionary.",
                        val_item1,
                        val_item2,
                    )
                    return False

                item1_val = d_item1.get("value")
                item2_val = d_item2.get("value")
                if item1_val != item2_val:
                    _log_mismatch(
                        item_path + ["value"],
                        f"Item 'value' differs. V1: '{item1_val}', V2: '{item2_val}'",
                        val_item1,
                        val_item2,
                    )
                    return False

                item1_type = d_item1.get("type")
                item2_type = d_item2.get("type")
                if item1_type != item2_type:
                    _log_mismatch(
                        item_path + ["type"],
                        f"Item 'type' differs. T1: '{item1_type}', T2: '{item2_type}'",
                        val_item1,
                        val_item2,
                    )
                    return False
            return True
        else:
            # These are non-Node, non-Definition objects of the same type,
            # both having __dict__.
            if node1 != node2:
                _log_mismatch(
                    current_path,
                    "Fallback equality for other __dict__ objects failed.",
                    node1,
                    node2,
                )
                return False
            return True

    # Fallback for any other types not explicitly handled by the above checks
    if node1 != node2:
        _log_mismatch(
            current_path,
            "Fallback equality for non-__dict__ objects failed.",
            node1,
            node2,
        )
        return False
    return True


def _format_value_as_code(value: Any, indent_level: int) -> str:
    """Recursively formats a Python value as a code string.

    Args:
        value: The Python value to format (can be an AST node, list, basic type).
        indent_level: The current indentation level.

    Returns:
        A string representation of the value as Python code.
    """
    indent_str = "    " * indent_level
    next_indent_str = "    " * (indent_level + 1)

    if value is None:
        return "None"
    if isinstance(value, str):
        return repr(value)  # repr() handles quotes and escapes correctly
    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, list):
        if not value:
            return "[]"
        # Format list elements, each on a new line if the list is not empty
        elements_str = ",\\n".join(
            [
                f"{next_indent_str}{_format_value_as_code(elem, indent_level + 1)}"
                for elem in value
            ]
        )
        return f"[\\n{elements_str}\\n{indent_str}]"

    # Check if it's an AST node
    if isinstance(value, (Node, Expression, Definition)):
        module_full_name = type(value).__module__
        class_name = type(value).__name__
        class_path = f"{module_full_name}.{class_name}"

        if not hasattr(value, "__dict__") or not value.__dict__:
            return f"{class_path}()"

        args_list = []
        # Sort attributes for deterministic output
        sorted_attr_names = sorted(value.__dict__.keys())

        for attr_name in sorted_attr_names:
            attr_value = getattr(value, attr_name)
            formatted_attr_value = _format_value_as_code(attr_value, indent_level + 1)
            args_list.append(f"\\n{next_indent_str}{attr_name}={formatted_attr_value}")

        return f"{class_path}({','.join(args_list)}\\n{indent_str})"

    # Fallback for other types (e.g., custom objects not part of the AST)
    return repr(value)


def ast_to_code_string(root_node: Node) -> str:
    """Converts a QUA program AST node to a Python code string representation.

    The output string can be used to reconstruct the AST object, assuming
    `from quaqsim import program_ast` is imported in the target scope.

    Args:
        root_node: The root AST node (e.g., a Program instance).

    Returns:
        A string representing the AST node as Python code.
    """
    return _format_value_as_code(root_node, indent_level=0)


def print_ast_as_code(root_node: Node) -> None:
    """Prints the AST node as a reconstructable Python code string.

    Args:
        root_node: The root AST node to print.
    """
    print(ast_to_code_string(root_node).replace("\\n", "\n"))
