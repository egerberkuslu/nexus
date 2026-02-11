#!/usr/bin/env python3
"""Register external MCP servers with the MCP Tool Hub."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


def _getenv(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _to_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _request_json(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {"raw": raw.decode("utf-8", errors="replace")}


def _wait_for_tool_hub(base_url: str, retries: int = 30, delay: float = 2.0) -> None:
    health_url = f"{base_url}/health"
    for _ in range(retries):
        try:
            _request_json("GET", health_url)
            return
        except Exception:
            time.sleep(delay)
    raise RuntimeError(f"MCP Tool Hub not reachable at {health_url}")


def _register_server(base_url: str, spec: dict) -> None:
    name = spec["name"]
    url = f"{base_url}/api/mcp/servers/{name}"
    payload = {
        "name": name,
        "base_url": spec["url"],
        "profile": spec.get("profile"),
        "read_only": spec.get("read_only", True),
    }

    for key in (
        "allowed_methods",
        "allowed_write_prefixes",
        "allowed_path_prefixes",
        "blocked_path_prefixes",
    ):
        values = spec.get(key)
        if values:
            payload[key] = values

    _request_json("PUT", url, payload)


def main() -> None:
    tool_hub_url = _getenv("MCP_TOOL_HUB_URL", "http://mcp-tool-hub-service:8018").rstrip("/")

    servers = [
        {
            "name": "grafana",
            "url": _getenv("MCP_GRAFANA_URL"),
            "profile": _getenv("MCP_GRAFANA_PROFILE", "grafana"),
            "read_only": _to_bool(_getenv("MCP_GRAFANA_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_GRAFANA_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_GRAFANA_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_GRAFANA_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_GRAFANA_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "influxdb",
            "url": _getenv("MCP_INFLUXDB_URL"),
            "profile": _getenv("MCP_INFLUXDB_PROFILE", "influxdb"),
            "read_only": _to_bool(_getenv("MCP_INFLUXDB_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_INFLUXDB_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_INFLUXDB_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_INFLUXDB_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_INFLUXDB_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "consul",
            "url": _getenv("MCP_CONSUL_URL"),
            "profile": _getenv("MCP_CONSUL_PROFILE", "consul"),
            "read_only": _to_bool(_getenv("MCP_CONSUL_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_CONSUL_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_CONSUL_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_CONSUL_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_CONSUL_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "kafka",
            "url": _getenv("MCP_KAFKA_URL"),
            "profile": _getenv("MCP_KAFKA_PROFILE", "kafka"),
            "read_only": _to_bool(_getenv("MCP_KAFKA_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_KAFKA_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_KAFKA_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_KAFKA_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_KAFKA_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "prometheus",
            "url": _getenv("MCP_PROMETHEUS_URL"),
            "profile": _getenv("MCP_PROMETHEUS_PROFILE", "prometheus"),
            "read_only": _to_bool(_getenv("MCP_PROMETHEUS_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_PROMETHEUS_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_PROMETHEUS_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_PROMETHEUS_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_PROMETHEUS_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "rabbitmq",
            "url": _getenv("MCP_RABBITMQ_URL"),
            "profile": _getenv("MCP_RABBITMQ_PROFILE", "rabbitmq"),
            "read_only": _to_bool(_getenv("MCP_RABBITMQ_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_RABBITMQ_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_RABBITMQ_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_RABBITMQ_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_RABBITMQ_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "flink",
            "url": _getenv("MCP_FLINK_URL"),
            "profile": _getenv("MCP_FLINK_PROFILE", "flink"),
            "read_only": _to_bool(_getenv("MCP_FLINK_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_FLINK_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_FLINK_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_FLINK_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_FLINK_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "spark-history",
            "url": _getenv("MCP_SPARK_HISTORY_URL"),
            "profile": _getenv("MCP_SPARK_HISTORY_PROFILE", "spark-history"),
            "read_only": _to_bool(_getenv("MCP_SPARK_HISTORY_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_SPARK_HISTORY_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_SPARK_HISTORY_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_SPARK_HISTORY_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_SPARK_HISTORY_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "hdfs",
            "url": _getenv("MCP_HDFS_URL"),
            "profile": _getenv("MCP_HDFS_PROFILE", "hdfs"),
            "read_only": _to_bool(_getenv("MCP_HDFS_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_HDFS_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_HDFS_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_HDFS_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_HDFS_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "hive",
            "url": _getenv("MCP_HIVE_URL"),
            "profile": _getenv("MCP_HIVE_PROFILE", "hive"),
            "read_only": _to_bool(_getenv("MCP_HIVE_READ_ONLY"), True),
            "allowed_methods": _parse_list(_getenv("MCP_HIVE_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_HIVE_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_HIVE_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_HIVE_BLOCKED_PATH_PREFIXES")),
        },
        {
            "name": "onos",
            "url": _getenv("MCP_ONOS_URL"),
            "profile": _getenv("MCP_ONOS_PROFILE", "onos"),
            "read_only": _to_bool(_getenv("MCP_ONOS_READ_ONLY"), False),
            "allowed_methods": _parse_list(_getenv("MCP_ONOS_ALLOWED_METHODS")),
            "allowed_write_prefixes": _parse_list(_getenv("MCP_ONOS_ALLOWED_WRITE_PREFIXES")),
            "allowed_path_prefixes": _parse_list(_getenv("MCP_ONOS_ALLOWED_PATH_PREFIXES")),
            "blocked_path_prefixes": _parse_list(_getenv("MCP_ONOS_BLOCKED_PATH_PREFIXES")),
        },
    ]

    _wait_for_tool_hub(tool_hub_url)

    for spec in servers:
        if not spec.get("url"):
            continue
        _register_server(tool_hub_url, spec)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"Registration failed: {exc.code} {exc.reason}")
        raise
    except Exception as exc:
        print(f"Registration failed: {exc}")
        raise
