"""
Sample QUA file for testing the pylint QUA plugin.

This file contains patterns that would trigger false positive pylint warnings in QUA code.
The plugin should suppress warnings inside QUA contexts while still flagging regular Python code.

Test cases:
1. Regular Python code OUTSIDE QUA context -> warnings SHOULD appear
2. Code INSIDE `with qua.program()` blocks -> warnings SHOULD be suppressed
3. QUA control flow functions OUTSIDE program context -> warnings SHOULD be suppressed
"""

from qm.qua import (
    program,
    declare,
    declare_stream,
    for_,
    while_,
    if_,
    elif_,
    else_,
    assign,
    play,
    measure,
    wait,
    save,
    Math,
)


# =============================================================================
# TEST CASE 1: Regular Python code - pylint SHOULD flag these
# =============================================================================


def regular_python_function():
    """Regular Python code that should trigger pylint warnings."""
    n = 5
    # C1805: use-implicit-booleaness-not-comparison-to-zero
    # This SHOULD be flagged by pylint
    if n & 1 == 0:
        print("even")

    flag = True
    # C0121: singleton-comparison
    # This SHOULD be flagged by pylint
    if flag == True:  # noqa: E712 - intentionally testing this pattern
        print("true")


# =============================================================================
# TEST CASE 2: Code INSIDE QUA program context - pylint should NOT flag these
# =============================================================================

with program() as test_program:
    # Declare QUA variables
    n_op = declare(int)
    state = declare(bool)
    x = declare(int)

    # C1805: use-implicit-booleaness-not-comparison-to-zero
    # This is VALID QUA - if_() needs a QUA boolean expression
    # Should be SUPPRESSED by the plugin
    if_(n_op & 1 == 0)

    # C1805 again - comparison to zero is intentional in QUA
    # Should be SUPPRESSED
    while_(x == 0)

    # C0121: singleton-comparison
    # QUA needs explicit comparison, not Python truthiness
    # Should be SUPPRESSED
    if_(state == True)

    # R1714: consider-using-in
    # QUA doesn't support Python's `in` operator
    # Should be SUPPRESSED
    if_((x == 1) | (x == 2) | (x == 3))

    # W0104/W0106: pointless-statement / expression-not-assigned
    # QUA statements build IR, they're not pointless
    # Should be SUPPRESSED
    play("pulse", "resonator")
    measure("readout", "qubit")

    # W0127: self-assigning-variable pattern
    # QUA uses assign() for variable updates
    # Should be SUPPRESSED
    assign(x, x + 1)


# =============================================================================
# TEST CASE 3: QUA control flow OUTSIDE program context (helper functions)
# =============================================================================


def qua_helper_function():
    """Helper function that uses QUA control flow - called from within a program."""
    n = declare(int)

    # These are QUA function calls, even outside `with qua.program()`
    # The plugin should suppress warnings inside these calls

    # C1805 inside if_() - should be SUPPRESSED
    if_(n & 1 == 0)

    # C1805 inside while_() - should be SUPPRESSED
    while_(n == 0)

    # C0121 inside if_() - should be SUPPRESSED
    if_(n == True)

    # Multi-line QUA call - should be SUPPRESSED
    for_(n, 0, n == 0, 1)  # C1805 here should be suppressed

    # Nested in assign - should be SUPPRESSED
    assign(n, n + 1)

    # Inside wait() - should be SUPPRESSED
    wait(n == 0)


def another_qua_helper():
    """Another helper with QUA calls."""
    x = declare(int)
    result = declare_stream()

    # Using Math functions with QUA variables - should be SUPPRESSED
    assign(x, Math.abs(x == 0))

    # elif_ and else_
    if_(x == 0)
    elif_(x == 1)
    else_()

    # save with comparison - should be SUPPRESSED
    save(x == 0, result)


# =============================================================================
# TEST CASE 4: Mixed context - some should warn, some should not
# =============================================================================


def mixed_function():
    """Mix of QUA and regular Python."""

    # Regular Python - SHOULD warn
    py_var = 5
    if py_var == 0:  # C1805 - should warn
        print("zero")

    # QUA call - should NOT warn
    qua_var = declare(int)
    if_(qua_var == 0)  # Should be suppressed

    # Regular Python again - SHOULD warn
    if py_var == True:  # C0121 - should warn  # noqa: E712
        print("true")


if __name__ == "__main__":
    print("Sample QUA file for testing pylint plugin")
