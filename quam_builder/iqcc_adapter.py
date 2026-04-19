"""IQCC Cloud proxies: present IQCC's synchronous API in the QOP manager / job shape."""

from __future__ import annotations

import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional

import numpy as np

# Set by lazy import on first use, or replaced by tests via patch("quam_builder.iqcc_adapter.IQCC_Cloud").
IQCC_Cloud: Any = None


class _IQCCCapabilities:
    def supports(self, cap: Any) -> bool:
        from qm import QopCaps

        return cap == QopCaps.qop3


class IQCCManagerProxy:
    """Minimal QuantumMachinesManager-shaped facade for IQCC Cloud."""

    def __init__(self, device_name: str) -> None:
        self.device_name = device_name
        self.capabilities = _IQCCCapabilities()

    def open_qm(self, config: dict, close_other_machines: bool = False) -> IQCCMachineProxy:
        _ = close_other_machines
        return IQCCMachineProxy(device_name=self.device_name, config=config)

    def close_all_qms(self) -> None:
        return None

    def simulate(self, config: Any, program: Any, simulation_config: Any) -> None:
        raise NotImplementedError(
            "IQCC Cloud does not support simulation (qmm.simulate / simulate_and_plot). "
            "Use a local QOP, unset iqcc_device, or run with simulate=False."
        )


class IQCCMachineProxy:
    """QuantumMachine-shaped facade; executes synchronously on IQCC."""

    def __init__(self, device_name: str, config: dict) -> None:
        self.device_name = device_name
        self.config = config

    def execute(self, program: Any) -> IQCCJobProxy:
        mod = sys.modules[__name__]
        cls = mod.IQCC_Cloud
        if cls is None:
            from iqcc_cloud_client import IQCC_Cloud as _IQCC_Cloud

            mod.IQCC_Cloud = _IQCC_Cloud
            cls = _IQCC_Cloud
        run_data = cls(self.device_name).execute(program, self.config, False)
        return IQCCJobProxy(run_data)

    def get_jobs(self, status: Optional[Iterable[str]] = None) -> List[Any]:
        _ = status
        return []

    def get_running_job(self) -> None:
        return None

    def close(self) -> None:
        return None


class IQCCJobProxy:
    def __init__(self, run_data: Mapping[str, Any]) -> None:
        self._run_data = dict(run_data)

    @property
    def result_handles(self) -> IQCCResultHandles:
        raw = self._run_data.get("result", {})
        if not isinstance(raw, Mapping):
            raw = {}
        return IQCCResultHandles(dict(raw))

    def execution_report(self) -> str:
        stdout = self._run_data.get("stdout", "") or ""
        stderr = self._run_data.get("stderr", "") or ""
        parts = []
        if stdout:
            parts.append(stdout.rstrip())
        if stderr:
            parts.append(stderr.rstrip())
        return "\n".join(parts) if parts else ""


class _FetchResultsView(Mapping[str, np.ndarray]):
    def __init__(self, items: Dict[str, np.ndarray]) -> None:
        self._items = items

    def __getitem__(self, key: str) -> np.ndarray:
        return self._items[key]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def get(self, key: str, default: Any = None) -> Any:
        return self._items.get(key, default)


class IQCCResultHandles:
    """ResultHandles-shaped view over IQCC run_data['result']."""

    def __init__(self, result: Mapping[str, Any]) -> None:
        self._result = dict(result)

    def keys(self) -> List[str]:
        return list(self._result.keys())

    def get(self, name: str) -> IQCCResultHandle:
        if name not in self._result:
            raise KeyError(name)
        return IQCCResultHandle(name, np.asarray(self._result[name]))

    def is_processing(self) -> bool:
        return False

    def fetch_results(
        self,
        wait_until_done: bool = False,
        stream_names: Optional[List[str]] = None,
    ) -> _FetchResultsView:
        _ = wait_until_done
        names = stream_names if stream_names is not None else self.keys()
        out: Dict[str, np.ndarray] = {n: np.asarray(self._result[n]) for n in names if n in self._result}
        return _FetchResultsView(out)

    def __getattr__(self, name: str) -> IQCCResultHandle:
        if name in self._result:
            return self.get(name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")


class IQCCResultHandle:
    def __init__(self, name: str, values: np.ndarray) -> None:
        self._name = name
        self._values = values

    def wait_for_values(self, n: int) -> None:
        _ = n
        return None

    def fetch(self) -> np.ndarray:
        return self._values
