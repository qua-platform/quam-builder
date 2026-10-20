"""Shared fixtures for tests that run against a QM simulator (on-prem or cloud).

Tests request the ``qmm`` fixture. By default that is the QM SaaS cloud simulator.

Switch backend without editing tests:

- CLI: ``pytest -m server --qm-backend=on_prem tests_against_server/``
- Env: ``QM_TEST_BACKEND=on_prem pytest -m server tests_against_server/``

Allowed values: ``saas`` (default), ``on_prem``.
Connection settings live next to this file (copy the ``.example`` files and fill in):

- SaaS: ``.qm_saas_credentials.json``, plus outbound ports 443 + 9510.
- On-prem: ``.qm_cluster_config.json``, plus LAN/VPN access to the cluster.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from qm import QuantumMachinesManager

_SERVER_DIR = Path(__file__).resolve().parent
_SAAS_CREDENTIALS_PATH = _SERVER_DIR / ".qm_saas_credentials.json"
_CLUSTER_CONFIG_PATH = _SERVER_DIR / ".qm_cluster_config.json"
_VALID_BACKENDS = frozenset({"saas", "on_prem"})


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-mark every test under tests_against_server/ with ``@pytest.mark.server``."""
    for item in items:
        if Path(item.fspath).resolve().is_relative_to(_SERVER_DIR):
            item.add_marker(pytest.mark.server)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--qm-backend",
        choices=sorted(_VALID_BACKENDS),
        default=None,
        help="QM simulator backend for server tests: saas (default) or on_prem. "
        "Overrides QM_TEST_BACKEND env var when set.",
    )


def _selected_backend(config: pytest.Config) -> str:
    cli = config.getoption("--qm-backend")
    if cli is not None:
        return cli
    env = os.environ.get("QM_TEST_BACKEND", "saas").lower()
    if env not in _VALID_BACKENDS:
        pytest.fail(f"Unknown QM_TEST_BACKEND={env!r}; use one of {sorted(_VALID_BACKENDS)}")
    return env


def _load_json_config(path: Path) -> dict[str, str]:
    if not path.exists():
        pytest.skip(f"{path} not found. Copy {path.name}.example to {path.name} and fill it in.")
    with open(path) as f:
        return json.load(f)


def _saas_cluster_config():
    """OPX1000 layout matching voltage_gate_sequence LF-FEM ports on slot 5."""
    from qm_saas import ClusterConfig

    cluster_config = ClusterConfig()
    cluster_config.controller().lf_fems(5)
    return cluster_config


@pytest.fixture(scope="session")
def qmm_saas():
    """Session-scoped QuantumMachinesManager connected to QM SaaS."""
    qm_saas = pytest.importorskip("qm_saas")
    creds = _load_json_config(_SAAS_CREDENTIALS_PATH)
    client = qm_saas.QmSaas(
        email=creds["email"],
        password=creds["password"],
        host=creds.get("host", "qm-saas.dev.quantum-machines.co"),
    )
    client.close_all()
    instance = client.simulator(client.latest_version(), _saas_cluster_config())
    instance.spawn()
    if not instance.is_alive:
        pytest.fail(
            f"QM SaaS simulator instance failed to start (expires_at={instance.expires_at})"
        )
    try:
        yield QuantumMachinesManager(
            host=instance.host,
            port=instance.port,
            connection_headers=instance.default_connection_headers,
        )
    finally:
        instance.close()
        client.close_all()


@pytest.fixture(scope="session")
def qmm_on_prem():
    """Session-scoped QuantumMachinesManager for the on-prem cluster."""
    cluster = _load_json_config(_CLUSTER_CONFIG_PATH)
    return QuantumMachinesManager(host=cluster["host"], cluster_name=cluster["cluster_name"])


@pytest.fixture(scope="session")
def qmm(request: pytest.FixtureRequest):
    """Default QMM for server tests; backend selected via --qm-backend / QM_TEST_BACKEND."""
    backend = _selected_backend(request.config)
    if backend == "on_prem":
        return request.getfixturevalue("qmm_on_prem")
    return request.getfixturevalue("qmm_saas")
