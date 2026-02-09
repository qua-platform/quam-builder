"""
Pylint plugin for QUA DSL compatibility.

QUA is a domain-specific language embedded in Python that uses Python syntax
to build quantum control programs. However, QUA expressions generate IR/AST
at "compile time" rather than executing at Python runtime. This means many
pylint rules that assume Python semantics produce false positives.

Usage:
    1. Add to your pylint configuration:
       
       # pyproject.toml
       [tool.pylint.main]
       load-plugins = ["pylint_qua_plugin"]
       
       # Or .pylintrc
       [MAIN]
       load-plugins=pylint_qua_plugin

    2. Ensure this file is in your PYTHONPATH or installed as a package.

The plugin suppresses rules in two contexts:
    1. Inside `with qua.program()` blocks
    2. Inside QUA control flow function calls (if_, for_, while_, etc.) anywhere

Suppressed rules:
    - C1805: use-implicit-booleaness-not-comparison-to-zero
    - C1803: use-implicit-booleaness-not-comparison-to-string  
    - C0121: singleton-comparison
    - R1714: consider-using-in
    - W0104: pointless-statement
    - W0106: expression-not-assigned
    - R1705: no-else-return
    - R1720: no-else-raise
    - R1709: boolean-if-simplify (consider-using-ternary-expression)
    - W0127: self-assigning-variable

Author: Quantum Machines
License: Apache 2.0
"""

from __future__ import annotations
import functools
from typing import Set, List, Tuple, Dict, Any
from astroid import nodes, MANAGER
from pylint.lint import PyLinter


# Rules that conflict with QUA DSL semantics (both codes and symbols)
QUA_SUPPRESSED_MSGIDS: Set[str] = {
    # Message codes (uppercase)
    "C1805", "C1803", "C0121", "R1714", "W0104", "W0106", "R1705", "R1720", "R1709", "W0127",
    # Symbolic names (pylint uses these internally)
    "use-implicit-booleaness-not-comparison-to-zero",
    "use-implicit-booleaness-not-comparison-to-string",
    "singleton-comparison",
    "consider-using-in",
    "pointless-statement",
    "expression-not-assigned",
    "no-else-return",
    "no-else-raise",
    "consider-using-ternary-expression",
    "self-assigning-variable",
}

# QUA control flow and statement functions that take QUA expressions as arguments
# These can appear outside of `with qua.program()` blocks in helper functions
QUA_CONTROL_FLOW_FUNCTIONS: Set[str] = {
    # Control flow
    "if_", "else_", "elif_",
    "for_", "for_each_",
    "while_",
    "switch_", "case_", "default_",
    # Variable operations
    "assign", "assign_addition_", "assign_subtraction_",
    "declare", "declare_stream",
    # Timing and synchronization
    "wait", "wait_for_trigger", "align", "reset_phase", "reset_frame", "reset_global_phase",
    "frame_rotation", "frame_rotation_2pi", "update_frequency",
    # Playback
    "play", "measure", "save", "pause",
    "ramp", "ramp_to_zero",
    # Math operations that take QUA variables
    "Math.abs", "Math.log", "Math.log2", "Math.log10", "Math.exp", "Math.sqrt",
    "Math.pow", "Math.sin", "Math.cos", "Math.tan", "Math.asin", "Math.acos", "Math.atan",
    "Math.div", "Math.msb", "Math.sum", "Math.max", "Math.min",
    "Cast.to_int", "Cast.to_fixed", "Cast.to_bool", "Cast.unsafe_cast_int", "Cast.unsafe_cast_fixed",
    "Util.cond",
    # I/O
    "set_dc_offset", "get_dc_offset",
    "IO1", "IO2",
    # Randomization
    "Random.rand_int", "Random.rand_fixed",
}

# Also match these as bare function names (without module prefix)
QUA_CONTROL_FLOW_BARE_NAMES: Set[str] = {
    name.split(".")[-1] for name in QUA_CONTROL_FLOW_FUNCTIONS
} | {
    name for name in QUA_CONTROL_FLOW_FUNCTIONS if "." not in name
}


def _is_qua_context_call(node: nodes.Call) -> bool:
    """Check if a Call node represents a QUA program context manager."""
    func = node.func
    
    if isinstance(func, nodes.Attribute):
        if func.attrname != "program":
            return False
        # Build module path and check for qua
        parts = []
        current = func.expr
        while isinstance(current, nodes.Attribute):
            parts.insert(0, current.attrname)
            current = current.expr
        if isinstance(current, nodes.Name):
            parts.insert(0, current.name)
        module_path = ".".join(parts)
        return "qua" in module_path.lower()
    
    elif isinstance(func, nodes.Name):
        return func.name == "program"
    
    return False


def _is_qua_control_flow_call(node: nodes.Call) -> bool:
    """Check if a Call node is a QUA control flow function."""
    func = node.func
    
    # Handle bare function names: if_(condition)
    if isinstance(func, nodes.Name):
        return func.name in QUA_CONTROL_FLOW_BARE_NAMES
    
    # Handle attribute access: qua.if_(condition), Math.abs(x)
    if isinstance(func, nodes.Attribute):
        # Build the full call path
        parts = [func.attrname]
        current = func.expr
        while isinstance(current, nodes.Attribute):
            parts.insert(0, current.attrname)
            current = current.expr
        if isinstance(current, nodes.Name):
            parts.insert(0, current.name)
        
        full_path = ".".join(parts)
        
        # Check if it matches any QUA function pattern
        # Match: Math.abs, Cast.to_int, qua.if_, etc.
        if full_path in QUA_CONTROL_FLOW_FUNCTIONS:
            return True
        
        # Also match if the last part is a QUA function (e.g., qm.qua.if_)
        if func.attrname in QUA_CONTROL_FLOW_BARE_NAMES:
            return True
    
    return False


def _get_call_line_range(node: nodes.Call) -> Tuple[int, int]:
    """Get the line range of a function call including all its arguments."""
    start_line = node.lineno
    end_line = node.end_lineno or node.lineno
    return (start_line, end_line)


def _collect_qua_ranges(module: nodes.Module) -> List[Tuple[int, int]]:
    """Collect all line ranges inside QUA contexts and QUA control flow calls."""
    ranges = []
    
    # Collect `with qua.program()` blocks
    for node in module.nodes_of_class(nodes.With):
        for context_item, _ in node.items:
            if isinstance(context_item, nodes.Call) and _is_qua_context_call(context_item):
                ranges.append((node.lineno, node.end_lineno or node.lineno))
    
    # Collect QUA control flow function calls (can be anywhere in the file)
    for node in module.nodes_of_class(nodes.Call):
        if _is_qua_control_flow_call(node):
            ranges.append(_get_call_line_range(node))
    
    return ranges


def _in_qua_range(line: int, ranges: List[Tuple[int, int]]) -> bool:
    """Check if a line is inside any QUA range."""
    return any(start <= line <= end for start, end in ranges)


# Global storage for QUA ranges, keyed by file path
_qua_ranges: Dict[str, List[Tuple[int, int]]] = {}
_transform_registered = False


def _module_transform(module: nodes.Module) -> nodes.Module:
    """AST transform that collects QUA ranges before any checking happens."""
    global _qua_ranges
    filepath = getattr(module, 'file', None)
    if filepath and filepath != '<?>':
        ranges = _collect_qua_ranges(module)
        if ranges:
            _qua_ranges[filepath] = ranges
    return module


def register(linter: PyLinter) -> None:
    """Register the QUA plugin with pylint."""
    global _qua_ranges, _transform_registered
    _qua_ranges = {}
    
    # Register the AST transform (only once globally)
    if not _transform_registered:
        MANAGER.register_transform(nodes.Module, _module_transform)
        _transform_registered = True
    
    # Wrap add_message to filter QUA-incompatible messages
    original_add_message = linter.add_message
    
    @functools.wraps(original_add_message)
    def filtered_add_message(
        msgid: str,
        line: int | None = None,
        node: nodes.NodeNG | None = None,
        args: Any = None,
        confidence: Any = None,
        col_offset: int | None = None,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        # Get line number
        check_line = line if line is not None else (node.lineno if node else None)
        
        # Get filepath - try multiple sources
        filepath = getattr(linter, 'current_file', None)
        if not filepath and node is not None:
            # Try to get file from the node's root
            root = node.root()
            filepath = getattr(root, 'file', None)
        
        # Check if should suppress
        if (
            check_line is not None
            and filepath
            and filepath in _qua_ranges
            and (msgid in QUA_SUPPRESSED_MSGIDS or msgid.upper() in QUA_SUPPRESSED_MSGIDS)
            and _in_qua_range(check_line, _qua_ranges[filepath])
        ):
            return  # Suppress this message
        
        return original_add_message(
            msgid, line=line, node=node, args=args,
            confidence=confidence, col_offset=col_offset,
            end_lineno=end_lineno, end_col_offset=end_col_offset,
        )
    
    linter.add_message = filtered_add_message


if __name__ == "__main__":
    print("QUA Pylint Plugin - suppresses rules in `with qua.program()` contexts")
    print(f"Suppressed codes: {sorted(r for r in QUA_SUPPRESSED_MSGIDS if r[0].isupper())}")
