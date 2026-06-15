"""Test-wide fixtures and helpers."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make test utilities (test_utils.py) importable from any sub-directory
sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(autouse=True)
def bypass_quam_config_version_check():
    """Bypass the QUAM global config version check.

    The QUAM 0.5.x load() path runs quam_version_validator against the user's
    ~/.quam/config.json. If that file is from an older QUAM version the check
    raises InvalidQuamConfigVersion and aborts. Patching the validator to a
    no-op lets tests call QuamBase.load() without requiring a migrated user
    config on every developer machine.
    """
    with patch("quam.config.resolvers.quam_version_validator"):
        yield
