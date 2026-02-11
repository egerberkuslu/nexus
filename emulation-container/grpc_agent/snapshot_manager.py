"""
Hybrid Snapshot Manager
Combines Docker commit + CRIU for comprehensive snapshots
Provides multiple snapshot strategies based on requirements
"""

from __future__ import annotations

import os
import json
import subprocess
import logging
import tarfile
import gzip
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from enum import Enum

try:
    from criu_handler import CRIUHandler, MininetCRIUManager, CRIUException
    CRIU_AVAILABLE = True
except ImportError:
    CRIU_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("CRIU handler not available - CRIU snapshots disabled")

logger = logging.getLogger(__name__)


class SnapshotType(Enum):
    """Types of snapshots available"""
    TOPOLOGY_ONLY = "topology_only"  # Just topology definition (fast, portable)
    DOCKER_COMMIT = "docker_commit"  # Docker commit (filesystem only)
    CRIU_LIVE = "criu_live"         # CRIU checkpoint (live state)
    HYBRID_FULL = "hybrid_full"      # Docker + CRIU (complete)


class SnapshotFormat(Enum):
    """Output formats for snapshots"""
    JSON = "json"
    JSON_GZ = "json.gz"
    TAR_GZ = "tar.gz"
    FULL_PACKAGE = "full_package"  # Includes all artifacts


class HybridSnapshotManager:
    """
    Manages multiple snapshot strategies:
    1. Topology-only: Quick structure save
    2. Docker commit: Filesystem snapshots
    3. CRIU: Live process snapshots
    4. Hybrid: Combines Docker + CRIU
    """

    def __init__(self, emulation_manager):
        self.em = emulation_manager
        self.snapshot_dir = "/var/lib/caduceus/snapshots"

        # Initialize CRIU if available
        if CRIU_AVAILABLE:
            try:
                self.criu_manager = MininetCRIUManager(emulation_manager)
                self.criu_available = self.criu_manager.is_available()
            except Exception as e:
                logger.warning(f"CRIU initialization failed: {e}")
                self.criu_manager = None
                self.criu_available = False
        else:
            self.criu_manager = None
            self.criu_available = False

        os.makedirs(self.snapshot_dir, exist_ok=True)

    def create_snapshot(
        self,
        snapshot_name: str,
        snapshot_type: SnapshotType = SnapshotType.HYBRID_FULL,
        description: str = "",
        compression: bool = True
    ) -> Dict:
        """
        Create a snapshot using specified strategy

        Args:
            snapshot_name: Unique name for snapshot
            snapshot_type: Type of snapshot to create
            description: Optional description
            compression: Whether to compress output

        Returns:
            Dict with snapshot details
        """
        logger.info(
            f"Creating {snapshot_type.value} snapshot: {snapshot_name}"
        )

        try:
            # Route to appropriate snapshot method
            if snapshot_type == SnapshotType.TOPOLOGY_ONLY:
                return self._create_topology_snapshot(
                    snapshot_name, description, compression
                )

            elif snapshot_type == SnapshotType.DOCKER_COMMIT:
                return self._create_docker_snapshot(
                    snapshot_name, description, compression
                )

            elif snapshot_type == SnapshotType.CRIU_LIVE:
                if not self.criu_available:
                    raise Exception("CRIU not available")
                return self._create_criu_snapshot(
                    snapshot_name, description, compression
                )

            elif snapshot_type == SnapshotType.HYBRID_FULL:
                return self._create_hybrid_snapshot(
                    snapshot_name, description, compression
                )

            else:
                raise ValueError(f"Unknown snapshot type: {snapshot_type}")

        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'snapshot_name': snapshot_name
            }

    def _create_topology_snapshot(
        self,
        snapshot_name: str,
        description: str,
        compression: bool
    ) -> Dict:
        """Create lightweight topology-only snapshot"""

        snapshot_data = {
            'caduceus_version': '1.0',
            'export_type': 'topology_snapshot',
            'snapshot_type': SnapshotType.TOPOLOGY_ONLY.value,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': {
                'name': snapshot_name,
                'description': description,
                'emulation_id': self.em.emulation_id,
                'topology_id': self.em.topology_id,
                'created_at': datetime.utcnow().isoformat()
            },
            'topology': self._collect_topology_data(),
            'runtime_config': self._collect_runtime_config()
        }

        # Save to file
        snapshot_path = self._save_snapshot_file(
            snapshot_name,
            snapshot_data,
            compression
        )

        return {
            'success': True,
            'snapshot_name': snapshot_name,
            'snapshot_type': SnapshotType.TOPOLOGY_ONLY.value,
            'snapshot_path': snapshot_path,
            'size_bytes': os.path.getsize(snapshot_path),
            'compressed': compression
        }

    def _create_docker_snapshot(
        self,
        snapshot_name: str,
        description: str,
        compression: bool
    ) -> Dict:
        """Create Docker commit snapshot (filesystem only)"""

        if not self.em.is_running():
            raise Exception("No emulation running")

        docker_snapshots = {}
        total_size = 0

        # Commit each Docker container
        for device_name, device_info in self.em.devices.items():
            node = device_info.get('node')
            properties = device_info.get('properties', {})

            if not properties.get('dockerized'):
                continue

            container_id = self._get_container_id(node, device_name)
            if not container_id:
                logger.warning(f"No container ID for {device_name}")
                continue

            try:
                # Docker commit
                image_tag = f"caduceus-snapshot:{snapshot_name}-{device_name}"

                result = subprocess.run(
                    ['docker', 'commit', container_id, image_tag],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    raise Exception(f"Docker commit failed: {result.stderr}")

                # Get image size
                inspect_result = subprocess.run(
                    ['docker', 'inspect', '--format={{.Size}}', image_tag],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                image_size = int(inspect_result.stdout.strip())
                total_size += image_size

                docker_snapshots[device_name] = {
                    'container_id': container_id,
                    'image_tag': image_tag,
                    'size_bytes': image_size
                }

                logger.info(
                    f"Docker committed {device_name}: "
                    f"{image_size / (1024*1024):.2f} MB"
                )

            except Exception as e:
                logger.error(f"Docker commit failed for {device_name}: {e}")

        # Create snapshot metadata
        snapshot_data = {
            'caduceus_version': '1.0',
            'export_type': 'docker_snapshot',
            'snapshot_type': SnapshotType.DOCKER_COMMIT.value,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': {
                'name': snapshot_name,
                'description': description,
                'emulation_id': self.em.emulation_id,
                'topology_id': self.em.topology_id
            },
            'topology': self._collect_topology_data(),
            'docker_snapshots': docker_snapshots,
            'total_size_bytes': total_size
        }

        snapshot_path = self._save_snapshot_file(
            snapshot_name,
            snapshot_data,
            compression
        )

        return {
            'success': True,
            'snapshot_name': snapshot_name,
            'snapshot_type': SnapshotType.DOCKER_COMMIT.value,
            'snapshot_path': snapshot_path,
            'devices_snapshotted': len(docker_snapshots),
            'total_size_mb': total_size / (1024 * 1024)
        }

    def _create_criu_snapshot(
        self,
        snapshot_name: str,
        description: str,
        compression: bool
    ) -> Dict:
        """Create CRIU live checkpoint snapshot"""

        if not self.criu_available:
            raise Exception("CRIU not available")

        if not self.em.is_running():
            raise Exception("No emulation running")

        # Create CRIU checkpoint
        criu_result = self.criu_manager.checkpoint_topology(
            checkpoint_name=snapshot_name,
            include_network_state=True
        )

        if not criu_result.get('success', True):
            raise Exception(f"CRIU checkpoint failed: {criu_result.get('error')}")

        # Create snapshot metadata
        snapshot_data = {
            'caduceus_version': '1.0',
            'export_type': 'criu_snapshot',
            'snapshot_type': SnapshotType.CRIU_LIVE.value,
            'snapshot_method': 'criu',
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': {
                'name': snapshot_name,
                'description': description,
                'emulation_id': self.em.emulation_id,
                'topology_id': self.em.topology_id,
                'was_running': True
            },
            'topology': self._collect_topology_data(),
            'criu_checkpoints': criu_result.get('devices', {}),
            'network_state': criu_result.get('network_state', {}),
            'topology_state': criu_result.get('topology_state', {}),
            'total_size_mb': criu_result.get('total_size_mb', 0)
        }

        snapshot_path = self._save_snapshot_file(
            snapshot_name,
            snapshot_data,
            compression
        )

        return {
            'success': True,
            'snapshot_name': snapshot_name,
            'snapshot_type': SnapshotType.CRIU_LIVE.value,
            'snapshot_path': snapshot_path,
            'devices_checkpointed': len(criu_result.get('devices', {})),
            'total_size_mb': criu_result.get('total_size_mb', 0),
            'criu_details': criu_result
        }

    def _create_hybrid_snapshot(
        self,
        snapshot_name: str,
        description: str,
        compression: bool
    ) -> Dict:
        """Create comprehensive snapshot with Docker + CRIU"""

        logger.info("Creating hybrid snapshot (Docker commit + CRIU)")

        results = {
            'success': True,
            'snapshot_name': snapshot_name,
            'snapshot_type': SnapshotType.HYBRID_FULL.value,
            'timestamp': datetime.utcnow().isoformat(),
            'components': {}
        }

        # 1. Create Docker commit snapshot
        try:
            docker_result = self._create_docker_snapshot(
                f"{snapshot_name}_docker",
                f"{description} (Docker component)",
                compression=False
            )
            results['components']['docker'] = docker_result
            logger.info("Docker commit snapshot created")
        except Exception as e:
            logger.warning(f"Docker commit failed (continuing): {e}")
            results['components']['docker'] = {'success': False, 'error': str(e)}

        # 2. Create CRIU checkpoint if available
        if self.criu_available:
            try:
                criu_result = self._create_criu_snapshot(
                    f"{snapshot_name}_criu",
                    f"{description} (CRIU component)",
                    compression=False
                )
                results['components']['criu'] = criu_result
                logger.info("CRIU checkpoint created")
            except Exception as e:
                logger.warning(f"CRIU checkpoint failed (continuing): {e}")
                results['components']['criu'] = {'success': False, 'error': str(e)}
        else:
            logger.info("CRIU not available, skipping live checkpoint")
            results['components']['criu'] = {
                'success': False,
                'error': 'CRIU not available'
            }

        # 3. Create comprehensive metadata
        snapshot_data = {
            'caduceus_version': '1.0',
            'export_type': 'hybrid_snapshot',
            'snapshot_type': SnapshotType.HYBRID_FULL.value,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': {
                'name': snapshot_name,
                'description': description,
                'emulation_id': self.em.emulation_id,
                'topology_id': self.em.topology_id,
                'has_docker': results['components']['docker'].get('success', False),
                'has_criu': results['components']['criu'].get('success', False)
            },
            'topology': self._collect_topology_data(),
            'components': results['components']
        }

        # Save comprehensive metadata
        snapshot_path = self._save_snapshot_file(
            snapshot_name,
            snapshot_data,
            compression
        )

        results['snapshot_path'] = snapshot_path
        results['size_bytes'] = os.path.getsize(snapshot_path)

        # Create full package with all artifacts
        package_path = self._create_snapshot_package(
            snapshot_name,
            snapshot_data
        )

        results['package_path'] = package_path
        if package_path:
            results['package_size_mb'] = os.path.getsize(package_path) / (1024 * 1024)

        logger.info(
            f"Hybrid snapshot complete: {results.get('package_size_mb', 0):.2f} MB"
        )

        return results

    def _collect_topology_data(self) -> Dict:
        """Collect current topology structure"""
        return {
            'devices': [
                {
                    'name': name,
                    'type': info.get('type'),
                    'properties': info.get('properties', {})
                }
                for name, info in self.em.devices.items()
            ],
            'links': [
                {
                    'id': link_id,
                    'node1': link_data.get('node1'),
                    'node2': link_data.get('node2')
                }
                for link_id, link_data in self.em.links.items()
            ]
        }

    def _collect_runtime_config(self) -> Dict:
        """Collect runtime configuration"""
        return {
            'status': self.em.status,
            'wifi_enabled': self.em.is_wifi_enabled,
            'start_time': self.em.start_time,
            'emulation_id': self.em.emulation_id,
            'topology_id': self.em.topology_id
        }

    def _get_container_id(self, node, device_name: str) -> Optional[str]:
        """Get container ID from node"""
        try:
            if hasattr(node, 'dimage') and hasattr(node, 'dcli') and hasattr(node, 'dc'):
                container_info = node.dcli.inspect_container(node.dc)
                return container_info['Id']
        except Exception as e:
            logger.debug(f"Error getting container ID for {device_name}: {e}")
        return None

    def _save_snapshot_file(
        self,
        snapshot_name: str,
        snapshot_data: Dict,
        compression: bool
    ) -> str:
        """Save snapshot data to file with optional compression"""

        snapshot_dir = os.path.join(self.snapshot_dir, snapshot_name)
        os.makedirs(snapshot_dir, exist_ok=True)

        if compression:
            filename = f"{snapshot_name}.json.gz"
            filepath = os.path.join(snapshot_dir, filename)

            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                json.dump(snapshot_data, f, indent=2)
        else:
            filename = f"{snapshot_name}.json"
            filepath = os.path.join(snapshot_dir, filename)

            with open(filepath, 'w') as f:
                json.dump(snapshot_data, f, indent=2)

        logger.info(f"Snapshot saved: {filepath}")
        return filepath

    def _create_snapshot_package(
        self,
        snapshot_name: str,
        snapshot_data: Dict
    ) -> Optional[str]:
        """Create tar.gz package with all snapshot artifacts"""
        try:
            package_path = os.path.join(
                self.snapshot_dir,
                f"{snapshot_name}_full_package.tar.gz"
            )

            snapshot_dir = os.path.join(self.snapshot_dir, snapshot_name)

            with tarfile.open(package_path, 'w:gz') as tar:
                tar.add(snapshot_dir, arcname=snapshot_name)

            logger.info(f"Snapshot package created: {package_path}")
            return package_path

        except Exception as e:
            logger.error(f"Failed to create snapshot package: {e}")
            return None

    def list_snapshots(self) -> List[Dict]:
        """List all available snapshots"""
        snapshots = []

        try:
            for item in os.listdir(self.snapshot_dir):
                item_path = os.path.join(self.snapshot_dir, item)

                if os.path.isdir(item_path):
                    # Look for snapshot metadata
                    json_files = [
                        f for f in os.listdir(item_path)
                        if f.endswith('.json') or f.endswith('.json.gz')
                    ]

                    if json_files:
                        metadata_file = os.path.join(item_path, json_files[0])

                        try:
                            if metadata_file.endswith('.gz'):
                                with gzip.open(metadata_file, 'rt') as f:
                                    metadata = json.load(f)
                            else:
                                with open(metadata_file, 'r') as f:
                                    metadata = json.load(f)

                            snapshots.append({
                                'name': item,
                                'path': item_path,
                                'metadata': metadata.get('metadata', {}),
                                'type': metadata.get('snapshot_type'),
                                'timestamp': metadata.get('timestamp'),
                                'size_mb': self._get_directory_size(item_path) / (1024 * 1024)
                            })
                        except Exception as e:
                            logger.warning(f"Could not read metadata for {item}: {e}")

        except Exception as e:
            logger.error(f"Error listing snapshots: {e}")

        return sorted(snapshots, key=lambda x: x.get('timestamp', ''), reverse=True)

    def _get_directory_size(self, path: str) -> int:
        """Calculate directory size recursively"""
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._get_directory_size(entry.path)
        except Exception as e:
            logger.warning(f"Error calculating size: {e}")
        return total

    def delete_snapshot(self, snapshot_name: str) -> bool:
        """Delete a snapshot and all its artifacts"""
        try:
            import shutil

            snapshot_dir = os.path.join(self.snapshot_dir, snapshot_name)

            if os.path.exists(snapshot_dir):
                shutil.rmtree(snapshot_dir)
                logger.info(f"Deleted snapshot: {snapshot_name}")

            # Also remove any standalone packages
            package_path = os.path.join(
                self.snapshot_dir,
                f"{snapshot_name}_full_package.tar.gz"
            )
            if os.path.exists(package_path):
                os.remove(package_path)

            return True

        except Exception as e:
            logger.error(f"Failed to delete snapshot {snapshot_name}: {e}")
            return False

    def export_snapshot(
        self,
        snapshot_name: str,
        output_path: str,
        include_docker_images: bool = True
    ) -> str:
        """
        Export snapshot to portable archive

        Args:
            snapshot_name: Name of snapshot to export
            output_path: Destination path
            include_docker_images: Whether to export Docker images

        Returns:
            Path to exported file
        """
        # Implementation for exporting snapshots to external storage
        pass

    def import_snapshot(
        self,
        archive_path: str,
        snapshot_name: Optional[str] = None
    ) -> Dict:
        """
        Import snapshot from archive

        Args:
            archive_path: Path to snapshot archive
            snapshot_name: Optional new name for imported snapshot

        Returns:
            Dict with import results
        """
        # Implementation for importing snapshots
        pass
