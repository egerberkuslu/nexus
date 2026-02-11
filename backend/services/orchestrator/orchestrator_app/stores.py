from __future__ import annotations

import json
from typing import Any, Dict, Optional


class ActiveEmulationStore:
    """Manages active emulation state in Redis."""

    def __init__(self, client, *, key: str = "active_emulations"):
        self.client = client
        self.key = key

    def get(self, topology_id: str) -> Optional[Dict[str, Any]]:
        emulation_data = self.client.hget(self.key, topology_id)
        if emulation_data:
            return json.loads(emulation_data)
        return None

    def set(self, topology_id: str, emulation_info: Dict[str, Any]) -> None:
        self.client.hset(self.key, topology_id, json.dumps(emulation_info))

    def delete(self, topology_id: str) -> None:
        self.client.hdel(self.key, topology_id)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        all_emulations = self.client.hgetall(self.key)
        return {k: json.loads(v) for k, v in all_emulations.items()}

    def find_by_emulation_id(self, emulation_id: str) -> Optional[str]:
        for topology_id, info in self.get_all().items():
            if info.get("emulation_id") == emulation_id:
                return topology_id
        return None

    def __contains__(self, topology_id: str) -> bool:
        return bool(self.client.hexists(self.key, topology_id))


class AlgorithmRunStore:
    """Stores algorithm run metadata in Redis."""

    def __init__(self, client, *, runs_key: str = "algorithm_runs", latest_key: str = "algorithm_latest_by_topology"):
        self.client = client
        self.runs_key = runs_key
        self.latest_key = latest_key

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        raw = self.client.hget(self.runs_key, run_id)
        if raw:
            return json.loads(raw)
        return None

    def set(self, run_id: str, record: Dict[str, Any]) -> None:
        self.client.hset(self.runs_key, run_id, json.dumps(record))
        topo_id = record.get("topology_id")
        if topo_id:
            self.client.hset(self.latest_key, str(topo_id), str(run_id))

    def delete(self, run_id: str) -> None:
        self.client.hdel(self.runs_key, run_id)

    def latest_for_topology(self, topology_id: str) -> Optional[str]:
        return self.client.hget(self.latest_key, topology_id)

