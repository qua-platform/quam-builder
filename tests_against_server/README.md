# Server tests

Tests under this directory are marked `server` and are excluded from CI (`pytest -m "not server"`).

They request the shared `qmm` fixture from [`conftest.py`](conftest.py). **Default backend is QM SaaS** (cloud simulator).

## Switch backend

```bash
# SaaS (default) — needs .qm_saas_credentials.json and ports 443 + 9510
cp .qm_saas_credentials.json.example .qm_saas_credentials.json  # fill in
uv run pytest -m server tests_against_server/voltage_gate_sequence/

# On-prem lab cluster — needs VPN/LAN
uv run pytest -m server --qm-backend=on_prem tests_against_server/voltage_gate_sequence/
# or
QM_TEST_BACKEND=on_prem uv run pytest -m server tests_against_server/voltage_gate_sequence/
```

`--qm-backend` overrides `QM_TEST_BACKEND` when both are set. Allowed values: `saas`, `on_prem`.
