"""Root conftest — applies to all test directories."""

import pathlib

import pytest

_SERVER_DIR = pathlib.Path(__file__).parent / "tests_against_server"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-mark every test under tests_against_server/ with ``@pytest.mark.server``."""
    marker = pytest.mark.server
    for item in items:
        if pathlib.Path(item.fspath).is_relative_to(_SERVER_DIR):
            item.add_marker(marker)
