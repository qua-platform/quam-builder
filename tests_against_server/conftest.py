"""Shared fixtures for tests that run against a QM simulator (on-prem or cloud)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("qm_saas")
from qm import QuantumMachinesManager
from qm_saas import ClusterConfig, QmSaas

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SAAS_CREDENTIALS_PATH = _REPO_ROOT / ".qm_saas_credentials.json"


def _saas_cluster_config() -> ClusterConfig:
    """OPX1000 layout matching voltage_gate_sequence LF-FEM ports on slot 5."""
    cluster_config = ClusterConfig()
    cluster_config.controller().lf_fems(5)
    return cluster_config


@pytest.fixture(scope="session")
def qm_saas_credentials() -> dict[str, str]:
    if not _SAAS_CREDENTIALS_PATH.exists():
        pytest.skip(
            f"QM SaaS credentials not found at {_SAAS_CREDENTIALS_PATH}. "
            "Copy .qm_saas_credentials.json.example to .qm_saas_credentials.json "
            "and fill in your credentials."
        )
    with open(_SAAS_CREDENTIALS_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def qm_saas_client(qm_saas_credentials: dict[str, str]):
    client = QmSaas(
        email=qm_saas_credentials["email"],
        password=qm_saas_credentials["password"],
        host=qm_saas_credentials.get("host", "qm-saas.dev.quantum-machines.co"),
    )
    client.close_all()
    yield client
    client.close_all()


@pytest.fixture(scope="session")
def qm_saas_instance(qm_saas_client: QmSaas):
    cluster_config = _saas_cluster_config()
    instance = qm_saas_client.simulator(qm_saas_client.latest_version(), cluster_config)
    instance.spawn()
    if not instance.is_alive:
        pytest.fail(
            f"QM SaaS simulator instance failed to start (expires_at={instance.expires_at})"
        )
    yield instance
    instance.close()


@pytest.fixture(scope="session")
def qmm_saas(qm_saas_instance):
    if not qm_saas_instance.is_alive:
        pytest.fail(
            f"QM SaaS simulator instance is no longer alive (expires_at={qm_saas_instance.expires_at})"
        )
    return QuantumMachinesManager(
        host=qm_saas_instance.host,
        port=qm_saas_instance.port,
        connection_headers=qm_saas_instance.default_connection_headers,
    )
