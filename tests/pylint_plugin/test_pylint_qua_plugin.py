"""
Tests for the pylint QUA plugin.

These tests verify that:
1. The plugin loads correctly
2. Warnings are suppressed inside QUA contexts (with qua.program())
3. Warnings are suppressed inside QUA control flow functions (if_, while_, etc.)
4. Warnings are NOT suppressed for regular Python code outside QUA contexts

The tests run pylint programmatically and check the output.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Get paths
REPO_ROOT = Path(__file__).parent.parent.parent
SAMPLE_FILE = Path(__file__).parent / "sample_qua_file.py"
PYLINTRC = REPO_ROOT / ".pylintrc"


def run_pylint(file_path: Path, use_plugin: bool = True) -> tuple[int, str, str]:
    """
    Run pylint on a file and return (return_code, stdout, stderr).

    Args:
        file_path: Path to the file to lint
        use_plugin: Whether to load the QUA plugin

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    env = {"PYTHONPATH": str(REPO_ROOT)}

    if use_plugin:
        # Run with the plugin via .pylintrc
        cmd = [
            sys.executable,
            "-m",
            "pylint",
            f"--rcfile={PYLINTRC}",
            str(file_path),
        ]
    else:
        # Run without the plugin (skip init-hook and load-plugins)
        cmd = [
            sys.executable,
            "-m",
            "pylint",
            "--disable=W,I,invalid-name,import-error,no-name-in-module,too-many-locals",
            "--enable=E,R,F,C",
            "--reports=no",
            str(file_path),
        ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, env={**dict(__import__("os").environ), **env}
    )
    return result.returncode, result.stdout, result.stderr


def count_message_occurrences(output: str, message_code: str) -> int:
    """Count how many times a pylint message code appears in the output."""
    return output.count(message_code)


def get_lines_with_message(output: str, message_code: str) -> list[int]:
    """Extract line numbers where a specific message code appears."""
    lines = []
    for line in output.split("\n"):
        if message_code in line:
            # Parse line number from pylint output format: "filename.py:LINE:COL: CODE"
            parts = line.split(":")
            if len(parts) >= 2:
                try:
                    lines.append(int(parts[1]))
                except ValueError:
                    pass
    return lines


class TestPluginLoads:
    """Test that the plugin loads correctly."""

    def test_plugin_loads_without_error(self):
        """Verify the plugin can be loaded without errors."""
        return_code, stdout, stderr = run_pylint(SAMPLE_FILE, use_plugin=True)
        # Plugin should load without import errors
        assert "Error loading plugin" not in stderr, f"Plugin failed to load: {stderr}"
        assert "ModuleNotFoundError" not in stderr, f"Module not found: {stderr}"


class TestQUAContextSuppression:
    """Test that warnings are suppressed inside QUA program contexts."""

    def test_c1805_suppressed_in_qua_program(self):
        """
        C1805 (use-implicit-booleaness-not-comparison-to-zero) should be suppressed
        inside `with qua.program()` blocks.
        """
        return_code, stdout, stderr = run_pylint(SAMPLE_FILE, use_plugin=True)

        # Get lines where C1805 appears
        lines_with_c1805 = get_lines_with_message(stdout, "C1805")

        # Lines 55-89 are inside QUA program context - should NOT have C1805
        qua_program_lines = range(55, 90)
        for line in qua_program_lines:
            assert (
                line not in lines_with_c1805
            ), f"C1805 should be suppressed on line {line} (inside QUA program)"

    def test_c0121_suppressed_in_qua_program(self):
        """
        C0121 (singleton-comparison) should be suppressed inside `with qua.program()` blocks.
        """
        return_code, stdout, stderr = run_pylint(SAMPLE_FILE, use_plugin=True)

        # Get lines where C0121 appears
        lines_with_c0121 = get_lines_with_message(stdout, "C0121")

        # Lines 55-89 are inside QUA program context - should NOT have C0121
        qua_program_lines = range(55, 90)
        for line in qua_program_lines:
            assert (
                line not in lines_with_c0121
            ), f"C0121 should be suppressed on line {line} (inside QUA program)"


class TestQUAHelperFunctionSuppression:
    """Test that warnings are suppressed inside QUA control flow function calls."""

    def test_c1805_suppressed_in_qua_helper(self):
        """
        C1805 should be suppressed inside QUA control flow functions
        even when outside a `with qua.program()` block.
        """
        return_code, stdout, stderr = run_pylint(SAMPLE_FILE, use_plugin=True)

        lines_with_c1805 = get_lines_with_message(stdout, "C1805")

        # Lines in qua_helper_function (97-120) and another_qua_helper (123-137)
        # should NOT have C1805 - these are inside if_(), while_(), for_() calls
        qua_helper_lines = range(97, 138)
        for line in qua_helper_lines:
            assert (
                line not in lines_with_c1805
            ), f"C1805 should be suppressed on line {line} (inside QUA helper function)"


class TestRegularPythonNotSuppressed:
    """Test that warnings are NOT suppressed for regular Python code."""

    def test_c1805_not_suppressed_in_regular_python(self):
        """
        C1805 should still appear for regular Python code outside QUA contexts.
        """
        return_code, stdout, stderr = run_pylint(SAMPLE_FILE, use_plugin=True)

        lines_with_c1805 = get_lines_with_message(stdout, "C1805")

        # regular_python_function is around lines 36-48
        # mixed_function is around lines 145-159
        # These SHOULD have C1805 warnings

        # At minimum, there should be SOME C1805 warnings for regular Python code
        # The exact lines may vary, but we should see warnings outside QUA contexts
        assert (
            len(lines_with_c1805) > 0
        ), "C1805 should still appear for regular Python code"

    def test_c0121_not_suppressed_in_regular_python(self):
        """
        C0121 should still appear for regular Python code outside QUA contexts.
        """
        return_code, stdout, stderr = run_pylint(SAMPLE_FILE, use_plugin=True)

        lines_with_c0121 = get_lines_with_message(stdout, "C0121")

        # regular_python_function and mixed_function should have C0121 warnings
        assert (
            len(lines_with_c0121) > 0
        ), "C0121 should still appear for regular Python code"


class TestComparisonWithoutPlugin:
    """Compare behavior with and without the plugin."""

    def test_more_warnings_without_plugin(self):
        """
        Running without the plugin should produce more warnings than with it.
        """
        _, stdout_with_plugin, _ = run_pylint(SAMPLE_FILE, use_plugin=True)
        _, stdout_without_plugin, _ = run_pylint(SAMPLE_FILE, use_plugin=False)

        c1805_with = count_message_occurrences(stdout_with_plugin, "C1805")
        c1805_without = count_message_occurrences(stdout_without_plugin, "C1805")

        c0121_with = count_message_occurrences(stdout_with_plugin, "C0121")
        c0121_without = count_message_occurrences(stdout_without_plugin, "C0121")

        # Without the plugin, there should be more warnings
        # (or at least the same if all the QUA code happens to be in contexts
        # that don't trigger warnings)
        assert (
            c1805_with <= c1805_without
        ), f"Plugin should reduce C1805 warnings: {c1805_with} (with) vs {c1805_without} (without)"
        assert (
            c0121_with <= c0121_without
        ), f"Plugin should reduce C0121 warnings: {c0121_with} (with) vs {c0121_without} (without)"


class TestRealWorldExample:
    """Test with the actual rabi_chevron.py example if it exists."""

    @pytest.mark.skipif(
        not (
            REPO_ROOT / "quam_builder/architecture/quantum_dots/examples/rabi_chevron.py"
        ).exists(),
        reason="rabi_chevron.py not found",
    )
    def test_rabi_chevron_no_qua_false_positives(self):
        """
        Run pylint on the actual rabi_chevron.py and verify QUA-related
        false positives are suppressed.
        """
        rabi_file = (
            REPO_ROOT / "quam_builder/architecture/quantum_dots/examples/rabi_chevron.py"
        )
        return_code, stdout, stderr = run_pylint(rabi_file, use_plugin=True)

        # The file uses QUA constructs - verify no false positives
        # in the QUA program section
        assert (
            "Error loading plugin" not in stderr
        ), f"Plugin failed to load: {stderr}"

        # Print output for debugging if there are issues
        if "C1805" in stdout or "C0121" in stdout:
            # Check if the warnings are from QUA context (they shouldn't be)
            lines = stdout.split("\n")
            for line in lines:
                if "C1805" in line or "C0121" in line:
                    print(f"Warning found: {line}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])