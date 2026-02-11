from __future__ import annotations

import importlib
import io
import json
import os
import tarfile
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass
from typing import Any, Optional, Callable


def new_run_id() -> str:
    return uuid.uuid4().hex


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _now_ts() -> float:
    return time.time()


@dataclass(frozen=True)
class AlgoBundle:
    manifest: dict[str, Any]
    bundle_dir: str


def load_bundle_to_tempdir(
    *,
    bundle_zip_bytes: Optional[bytes],
    manifest_json: Optional[str],
    source_code: Optional[str],
    source_filename: str = "algorithm.py",
) -> tuple[AlgoBundle, str]:
    """
    Creates a temp directory that contains:
      - bundle/ (python files)
      - manifest.json
    Returns (bundle, tmp_root) where tmp_root must be cleaned up by caller.
    """
    tmp_root = tempfile.mkdtemp(prefix="caduceus-algo-bundle-")
    bundle_dir = os.path.join(tmp_root, "bundle")
    os.makedirs(bundle_dir, exist_ok=True)

    manifest: dict[str, Any] = {}

    if bundle_zip_bytes:
        names: list[str] = []
        with zipfile.ZipFile(io.BytesIO(bundle_zip_bytes)) as zf:
            names = zf.namelist()
            zf.extractall(bundle_dir)
        # Allow manifest.json either at bundle root or inside archive root folder.
        candidates = [
            os.path.join(bundle_dir, "manifest.json"),
        ]
        # If zip has a single top-level dir, check that too.
        try:
            top_level = {p.split("/", 1)[0] for p in names if p and not p.endswith("/")}
            if len(top_level) == 1:
                only = next(iter(top_level))
                candidates.append(os.path.join(bundle_dir, only, "manifest.json"))
        except Exception:
            pass

        manifest_path = next((p for p in candidates if os.path.exists(p)), None)
        if not manifest_path:
            raise ValueError("Bundle zip must contain manifest.json at the root")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        if not manifest_json or not str(manifest_json).strip():
            raise ValueError("manifest_json is required when no bundle zip is provided")
        try:
            manifest = json.loads(manifest_json)
        except Exception as exc:
            raise ValueError(f"Invalid manifest_json: {exc}") from exc

        if source_code is None:
            raise ValueError("source_code is required when no bundle zip is provided")

        with open(os.path.join(bundle_dir, source_filename), "w", encoding="utf-8") as f:
            f.write(source_code)

        with open(os.path.join(bundle_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must be an object")

    return AlgoBundle(manifest=manifest, bundle_dir=bundle_dir), tmp_root


def run_selector_if_present(
    *,
    bundle: AlgoBundle,
    topo_context: dict[str, Any],
    extra_sys_paths: Optional[list[str]] = None,
) -> Optional[list[Any]]:
    selector_spec = bundle.manifest.get("selector")
    if not selector_spec:
        return None
    if not isinstance(selector_spec, str) or ":" not in selector_spec:
        raise ValueError("manifest.selector must be 'module:function'")

    mod_name, fn_name = selector_spec.split(":", 1)
    bundle_root = bundle.bundle_dir

    # Temporarily add bundle root to sys.path for imports.
    import sys

    added_paths: list[str] = []
    sys.path.insert(0, bundle_root)
    added_paths.append(bundle_root)
    for p in (extra_sys_paths or []):
        path = str(p or "").strip()
        if not path:
            continue
        sys.path.insert(0, path)
        added_paths.append(path)
    try:
        mod = importlib.import_module(mod_name)
        fn: Any = getattr(mod, fn_name)
        if not callable(fn):
            raise ValueError("selector symbol is not callable")
        return fn(topo_context)
    finally:
        for p in added_paths:
            try:
                sys.path.remove(p)
            except Exception:
                pass


def build_topo_context(
    *,
    topology: dict[str, Any],
    node_id_to_algo_id: dict[str, int],
    algo_id_to_node_id: dict[int, str],
    params: dict[str, Any],
) -> dict[str, Any]:
    nodes_payload: list[dict[str, Any]] = []
    for node in (topology.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        nodes_payload.append(
            {
                "id": node_id,
                "name": node.get("name"),
                "device_type": node.get("device_type") or node.get("type"),
                "properties": node.get("properties") or {},
                "algo_id": node_id_to_algo_id.get(node_id),
            }
        )

    links_payload: list[dict[str, Any]] = []
    for link in (topology.get("links") or []):
        if not isinstance(link, dict):
            continue
        a = str(link.get("source_node_id") or link.get("source") or link.get("node1") or "")
        b = str(link.get("target_node_id") or link.get("target") or link.get("node2") or "")
        if not a or not b:
            continue
        links_payload.append(
            {
                "id": link.get("id"),
                "a": a,
                "b": b,
                "a_algo_id": node_id_to_algo_id.get(a),
                "b_algo_id": node_id_to_algo_id.get(b),
                "properties": link.get("properties") or {},
            }
        )

    return {
        "topology": {"id": topology.get("id"), "name": topology.get("name")},
        "params": params,
        "nodes": nodes_payload,
        "links": links_payload,
        "mapping": {"node_id_to_algo_id": node_id_to_algo_id, "algo_id_to_node_id": algo_id_to_node_id},
    }


def create_run_tar_bytes(
    *,
    run_id: str,
    bundle: AlgoBundle,
    sdk_dir: str,
    per_node_configs: dict[int, dict[str, Any]],
) -> bytes:
    """
    Creates a tarball that will be extracted at container root `/`.
    It contains `/tmp/caduceus_algo/<run_id>/...`
    """
    run_root = os.path.join("tmp", "caduceus_algo", run_id)

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        # Create directories
        for d in ("", "bundle", "caduceus_sdk", "configs", "events", "states", "pids", "logs"):
            p = os.path.join(run_root, d) if d else run_root
            ti = tarfile.TarInfo(name=p)
            ti.type = tarfile.DIRTYPE
            ti.mode = 0o755
            ti.mtime = int(_now_ts())
            tf.addfile(ti)

        # Manifest
        manifest_bytes = json.dumps(bundle.manifest, ensure_ascii=False, indent=2).encode("utf-8")
        ti = tarfile.TarInfo(name=os.path.join(run_root, "manifest.json"))
        ti.size = len(manifest_bytes)
        ti.mode = 0o644
        ti.mtime = int(_now_ts())
        tf.addfile(ti, io.BytesIO(manifest_bytes))

        # SDK package
        tf.add(sdk_dir, arcname=os.path.join(run_root, "caduceus_sdk"))

        # Bundle code (exclude manifest.json duplicates)
        for root, _dirs, files in os.walk(bundle.bundle_dir):
            for filename in files:
                if filename == "manifest.json":
                    continue
                full = os.path.join(root, filename)
                rel = os.path.relpath(full, bundle.bundle_dir)
                tf.add(full, arcname=os.path.join(run_root, "bundle", rel))

        # Per-node configs
        for algo_id, cfg in per_node_configs.items():
            content = json.dumps(cfg, ensure_ascii=False, indent=2).encode("utf-8")
            ti = tarfile.TarInfo(name=os.path.join(run_root, "configs", f"{int(algo_id)}.json"))
            ti.size = len(content)
            ti.mode = 0o644
            ti.mtime = int(_now_ts())
            tf.addfile(ti, io.BytesIO(content))

    return buf.getvalue()


def normalize_selected_nodes(
    selected_raw: Optional[list[Any]],
    *,
    node_id_to_algo_id: dict[str, int],
    algo_id_to_node_id: dict[int, str],
) -> Optional[list[int]]:
    if selected_raw is None:
        return None

    selected: set[int] = set()
    for item in selected_raw:
        if item is None:
            continue
        # algo id direct
        if isinstance(item, int):
            if item in algo_id_to_node_id:
                selected.add(item)
            continue
        s = str(item).strip()
        if not s:
            continue
        # maybe numeric
        if s.isdigit():
            i = int(s)
            if i in algo_id_to_node_id:
                selected.add(i)
                continue
        # node id
        if s in node_id_to_algo_id:
            selected.add(int(node_id_to_algo_id[s]))
            continue
        # fallback: allow passing the stringified algo_id_to_node_id values
        for aid, nid in algo_id_to_node_id.items():
            if nid == s:
                selected.add(int(aid))
                break

    return sorted(selected) if selected else []
