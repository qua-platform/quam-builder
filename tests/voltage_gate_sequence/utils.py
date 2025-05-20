from typing import Any

# Assuming 'quaqsim' is an installed dependency.
# These imports are for type hinting and potentially for isinstance checks if needed.
from quaqsim.program_ast.node import Node
from quaqsim.program_ast.expressions.expression import Expression


def compare_ast_nodes(node1: Any, node2: Any) -> bool:
    """Recursively compares two QUA AST elements for structural equality.

    Compares nodes, their attributes (which can be other nodes, expressions,
    lists, or literals) for structural equality. The top-level arguments
    are expected to be Node instances for a meaningful AST comparison.

    Args:
        node1: The first AST element (expected to be Node at top level).
        node2: The second AST element (expected to be Node at top level).

    Returns:
        True if the elements are structurally identical, False otherwise.
    """
    if type(node1) is not type(node2):
        return False

    if isinstance(node1, (int, str, bool, float, type(None))):
        return node1 == node2

    if isinstance(node1, list):
        if not isinstance(node2, list):
            return False
        # Type of node2 is already confirmed to be list if we are here due to the first check.
        if len(node1) != len(node2):
            return False
        for item1, item2 in zip(node1, node2):
            # Recursively call, which can handle nested Nodes or other types
            if not compare_ast_nodes(item1, item2):
                return False
        return True

    # Check for objects that have a __dict__
    if hasattr(node1, "__dict__") and hasattr(node2, "__dict__"):
        # If types matched and they have __dict__, check if they are Node instances
        if isinstance(node1, (Node, Expression)):
            if not type(node1) is type(node2):
                return False
            dict1 = node1.__dict__
            dict2 = node2.__dict__

            if set(dict1.keys()) != set(dict2.keys()):
                return False

            # Sort keys for deterministic comparison, though __dict__ order is usually stable for same type
            sorted_keys = sorted(dict1.keys())
            for key in sorted_keys:
                if not compare_ast_nodes(dict1[key], dict2[key]):
                    return False
            return True
        else:
            # These are non-Node objects of the same type, both having __dict__
            # Fallback to direct equality if they are not AST Nodes.
            # This might be relevant for other complex attribute types.
            return node1 == node2

    # Fallback for any other types not explicitly handled by the above checks
    # (e.g., custom objects without __dict__ that are directly comparable)
    return node1 == node2


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
        elements_str = ",\n".join(
            [
                f"{next_indent_str}{_format_value_as_code(elem, indent_level + 1)}"
                for elem in value
            ]
        )
        return f"[\n{elements_str}\n{indent_str}]"

    # Check if it's an AST node
    if isinstance(value, (Node, Expression)):
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
            args_list.append(f"\n{next_indent_str}{attr_name}={formatted_attr_value}")

        return f"{class_path}({','.join(args_list)}\n{indent_str})"

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
    print(ast_to_code_string(root_node))
