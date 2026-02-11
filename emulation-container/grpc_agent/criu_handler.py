"""
CRIU Handler for Container Checkpointing
Integrates CRIU with Containernet/Mininet-WiFi for live snapshots
"""

from __future__ import annotations

import os
import json
import subprocess
import logging
import shutil
import tarfile
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# CRIU checkpoint directory
CRIU_BASE_DIR = "/var/lib/caduceus/criu"
SNAPSHOT_BASE_DIR = "/var/lib/caduceus/snapshots"


class CRIUException(Exception):
    """Exception raised for CRIU-specific errors"""
    pass


class CRIUHandler:
    """Manages CRIU checkpoint/restore operations for Docker containers"""

    def __init__(self, checkpoint_dir: str = CRIU_BASE_DIR):
        self.checkpoint_dir = checkpoint_dir
        self.snapshot_dir = SNAPSHOT_BASE_DIR

        # Create directories
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs(self.snapshot_dir, exist_ok=True)

        # Verify CRIU availability
        self.criu_available = self._verify_criu_available()
        self.docker_experimental = self._check_docker_experimental()

        if not self.criu_available:
            logger.warning("CRIU is not available - checkpoint/restore will be disabled")

        if not self.docker_experimental:
            logger.warning("Docker experimental features not enabled - CRIU may not work")

    def _verify_criu_available(self) -> bool:
        """Check if CRIU is installed and functional"""
        try:
            result = subprocess.run(
                ['criu', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"CRIU is available: {version}")
                return True
            else:
                logger.warning("CRIU command failed")
                return False
        except FileNotFoundError:
            logger.warning("CRIU not installed")
            return False
        except Exception as e:
            logger.error(f"CRIU verification failed: {e}")
            return False

    def _check_docker_experimental(self) -> bool:
        """Check if Docker experimental features are enabled"""
        try:
            result = subprocess.run(
                ['docker', 'version', '--format', '{{.Server.Experimental}}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                experimental = result.stdout.strip().lower() == 'true'
                logger.info(f"Docker experimental features: {experimental}")
                return experimental
            return False
        except Exception as e:
            logger.warning(f"Could not check Docker experimental status: {e}")
            return False

    def checkpoint_container(
        self,
        container_id: str,
        checkpoint_name: str,
        leave_running: bool = True
    ) -> Dict:
        """
        Create CRIU checkpoint of Docker container

        Args:
            container_id: Docker container ID or name
            checkpoint_name: Unique name for this checkpoint
            leave_running: Keep container running after checkpoint (default: True)

        Returns:
            Dict with checkpoint metadata
        """
        if not self.criu_available:
            raise CRIUException("CRIU is not available")

        if not self.docker_experimental:
            raise CRIUException("Docker experimental features not enabled")

        try:
            logger.info(f"Creating CRIU checkpoint for container {container_id}")

            # Create checkpoint directory for this container
            container_checkpoint_dir = os.path.join(
                self.checkpoint_dir,
                container_id
            )
            os.makedirs(container_checkpoint_dir, exist_ok=True)

            # Build docker checkpoint command
            cmd = [
                'docker', 'checkpoint', 'create',
                '--checkpoint-dir', container_checkpoint_dir
            ]

            if leave_running:
                cmd.append('--leave-running')

            cmd.extend([container_id, checkpoint_name])

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Execute checkpoint
            start_time = datetime.now()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            checkpoint_duration = (datetime.now() - start_time).total_seconds()

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"Checkpoint failed: {error_msg}")
                raise CRIUException(f"Docker checkpoint failed: {error_msg}")

            # Collect checkpoint metadata
            checkpoint_path = os.path.join(container_checkpoint_dir, checkpoint_name)
            metadata = self._collect_checkpoint_metadata(
                container_id,
                checkpoint_name,
                checkpoint_path,
                checkpoint_duration
            )

            # Save metadata to JSON
            metadata_file = os.path.join(checkpoint_path, 'metadata.json')
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(
                f"Checkpoint created successfully: {checkpoint_name} "
                f"({metadata['size_mb']:.2f} MB in {checkpoint_duration:.2f}s)"
            )

            return {
                'success': True,
                'checkpoint_name': checkpoint_name,
                'checkpoint_path': checkpoint_path,
                'container_id': container_id,
                'duration_seconds': checkpoint_duration,
                'metadata': metadata
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Checkpoint timeout for container {container_id}")
            raise CRIUException("Checkpoint operation timed out")
        except Exception as e:
            logger.error(f"Checkpoint failed: {e}", exc_info=True)
            raise CRIUException(f"Checkpoint failed: {str(e)}")

    def restore_container(
        self,
        container_id: str,
        checkpoint_name: str
    ) -> Dict:
        """
        Restore container from CRIU checkpoint

        Args:
            container_id: Docker container ID to restore
            checkpoint_name: Name of checkpoint to restore from

        Returns:
            Dict with restore status
        """
        if not self.criu_available:
            raise CRIUException("CRIU is not available")

        try:
            logger.info(f"Restoring container {container_id} from checkpoint {checkpoint_name}")

            checkpoint_path = os.path.join(
                self.checkpoint_dir,
                container_id,
                checkpoint_name
            )

            if not os.path.exists(checkpoint_path):
                raise CRIUException(f"Checkpoint not found: {checkpoint_path}")

            # Build restore command
            cmd = [
                'docker', 'start',
                '--checkpoint', checkpoint_name,
                '--checkpoint-dir', os.path.dirname(checkpoint_path),
                container_id
            ]

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Execute restore
            start_time = datetime.now()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            restore_duration = (datetime.now() - start_time).total_seconds()

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"Restore failed: {error_msg}")
                raise CRIUException(f"Docker restore failed: {error_msg}")

            logger.info(
                f"Container restored successfully in {restore_duration:.2f}s"
            )

            return {
                'success': True,
                'container_id': container_id,
                'checkpoint_name': checkpoint_name,
                'duration_seconds': restore_duration
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Restore timeout for container {container_id}")
            raise CRIUException("Restore operation timed out")
        except Exception as e:
            logger.error(f"Restore failed: {e}", exc_info=True)
            raise CRIUException(f"Restore failed: {str(e)}")

    def _collect_checkpoint_metadata(
        self,
        container_id: str,
        checkpoint_name: str,
        checkpoint_path: str,
        duration_seconds: float
    ) -> Dict:
        """Collect detailed metadata about checkpoint"""

        metadata = {
            'container_id': container_id,
            'checkpoint_name': checkpoint_name,
            'checkpoint_path': checkpoint_path,
            'created_at': datetime.utcnow().isoformat(),
            'duration_seconds': duration_seconds,
            'criu_version': self._get_criu_version(),
            'files': [],
            'size_bytes': 0,
            'size_mb': 0.0
        }

        # List checkpoint files
        if os.path.exists(checkpoint_path):
            try:
                files = []
                total_size = 0

                for entry in os.scandir(checkpoint_path):
                    if entry.is_file(follow_symlinks=False):
                        size = entry.stat().st_size
                        files.append({
                            'name': entry.name,
                            'size': size
                        })
                        total_size += size

                metadata['files'] = sorted(files, key=lambda x: x['size'], reverse=True)
                metadata['size_bytes'] = total_size
                metadata['size_mb'] = total_size / (1024 * 1024)

            except Exception as e:
                logger.warning(f"Error collecting file metadata: {e}")

        # Get container info
        try:
            container_info = self._get_container_info(container_id)
            if container_info:
                metadata['container_info'] = container_info
        except Exception as e:
            logger.warning(f"Error getting container info: {e}")

        return metadata

    def _get_container_info(self, container_id: str) -> Optional[Dict]:
        """Get container information from Docker"""
        try:
            result = subprocess.run(
                ['docker', 'inspect', container_id],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                info = json.loads(result.stdout)[0]
                return {
                    'name': info.get('Name', '').lstrip('/'),
                    'image': info.get('Config', {}).get('Image'),
                    'created': info.get('Created'),
                    'state': info.get('State', {})
                }
        except Exception as e:
            logger.debug(f"Could not get container info: {e}")

        return None

    def _get_criu_version(self) -> str:
        """Get CRIU version string"""
        try:
            result = subprocess.run(
                ['criu', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def list_checkpoints(self, container_id: str) -> List[Dict]:
        """List all checkpoints for a container"""
        container_checkpoint_dir = os.path.join(
            self.checkpoint_dir,
            container_id
        )

        if not os.path.exists(container_checkpoint_dir):
            return []

        checkpoints = []

        try:
            for checkpoint_name in os.listdir(container_checkpoint_dir):
                checkpoint_path = os.path.join(
                    container_checkpoint_dir,
                    checkpoint_name
                )

                if not os.path.isdir(checkpoint_path):
                    continue

                metadata_file = os.path.join(checkpoint_path, 'metadata.json')

                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            checkpoints.append(metadata)
                    except Exception as e:
                        logger.warning(f"Could not read metadata for {checkpoint_name}: {e}")
                else:
                    # Create basic metadata if file doesn't exist
                    size = self._get_directory_size(checkpoint_path)
                    checkpoints.append({
                        'checkpoint_name': checkpoint_name,
                        'checkpoint_path': checkpoint_path,
                        'size_mb': size / (1024 * 1024),
                        'created_at': datetime.fromtimestamp(
                            os.path.getctime(checkpoint_path)
                        ).isoformat()
                    })
        except Exception as e:
            logger.error(f"Error listing checkpoints: {e}")

        return sorted(checkpoints, key=lambda x: x.get('created_at', ''), reverse=True)

    def delete_checkpoint(
        self,
        container_id: str,
        checkpoint_name: str
    ) -> bool:
        """Delete a checkpoint"""
        try:
            # Try Docker command first
            result = subprocess.run(
                ['docker', 'checkpoint', 'rm', container_id, checkpoint_name],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Checkpoint deleted via Docker: {checkpoint_name}")

            # Also remove from filesystem
            checkpoint_path = os.path.join(
                self.checkpoint_dir,
                container_id,
                checkpoint_name
            )

            if os.path.exists(checkpoint_path):
                shutil.rmtree(checkpoint_path)
                logger.info(f"Checkpoint directory removed: {checkpoint_path}")

            return True

        except Exception as e:
            logger.error(f"Delete checkpoint failed: {e}")
            return False

    def _get_directory_size(self, path: str) -> int:
        """Calculate total size of directory recursively"""
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._get_directory_size(entry.path)
        except Exception as e:
            logger.warning(f"Error calculating directory size: {e}")
        return total

    def export_checkpoint(
        self,
        container_id: str,
        checkpoint_name: str,
        output_path: str
    ) -> str:
        """
        Export checkpoint to a portable archive

        Args:
            container_id: Container ID
            checkpoint_name: Checkpoint name
            output_path: Path for output tar.gz file

        Returns:
            Path to created archive
        """
        try:
            checkpoint_path = os.path.join(
                self.checkpoint_dir,
                container_id,
                checkpoint_name
            )

            if not os.path.exists(checkpoint_path):
                raise CRIUException(f"Checkpoint not found: {checkpoint_path}")

            logger.info(f"Exporting checkpoint to {output_path}")

            # Create tar.gz archive
            with tarfile.open(output_path, 'w:gz') as tar:
                tar.add(checkpoint_path, arcname=checkpoint_name)

            archive_size = os.path.getsize(output_path)
            logger.info(
                f"Checkpoint exported: {output_path} "
                f"({archive_size / (1024 * 1024):.2f} MB)"
            )

            return output_path

        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise CRIUException(f"Export failed: {str(e)}")

    def import_checkpoint(
        self,
        archive_path: str,
        container_id: str,
        checkpoint_name: str
    ) -> bool:
        """
        Import checkpoint from archive

        Args:
            archive_path: Path to checkpoint archive
            container_id: Target container ID
            checkpoint_name: Name for imported checkpoint

        Returns:
            True if successful
        """
        try:
            if not os.path.exists(archive_path):
                raise CRIUException(f"Archive not found: {archive_path}")

            logger.info(f"Importing checkpoint from {archive_path}")

            # Extract to checkpoint directory
            extract_path = os.path.join(
                self.checkpoint_dir,
                container_id
            )
            os.makedirs(extract_path, exist_ok=True)

            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(path=extract_path)

            logger.info(f"Checkpoint imported successfully")
            return True

        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise CRIUException(f"Import failed: {str(e)}")


class MininetCRIUManager:
    """
    CRIU Manager specialized for Mininet/Containernet
    Handles network namespace checkpointing and topology preservation
    """

    def __init__(self, emulation_manager):
        self.em = emulation_manager
        self.criu = CRIUHandler()

    def is_available(self) -> bool:
        """Check if CRIU is available for use"""
        return self.criu.criu_available and self.criu.docker_experimental

    def checkpoint_topology(
        self,
        checkpoint_name: str,
        include_network_state: bool = True
    ) -> Dict:
        """
        Checkpoint entire Mininet topology using CRIU

        Args:
            checkpoint_name: Name for this topology checkpoint
            include_network_state: Save network configuration state

        Returns:
            Dict with checkpoint results for all devices
        """
        if not self.em.is_running():
            return {
                'success': False,
                'error': 'No emulation running'
            }

        if not self.is_available():
            return {
                'success': False,
                'error': 'CRIU not available'
            }

        logger.info(f"Starting topology checkpoint: {checkpoint_name}")

        results = {
            'success': True,
            'checkpoint_name': checkpoint_name,
            'emulation_id': self.em.emulation_id,
            'topology_id': self.em.topology_id,
            'timestamp': datetime.utcnow().isoformat(),
            'devices': {},
            'failed_devices': [],
            'total_size_mb': 0.0
        }

        # Checkpoint each dockerized device
        for device_name, device_info in self.em.devices.items():
            node = device_info.get('node')
            properties = device_info.get('properties', {})

            # Only checkpoint Docker containers
            if not properties.get('dockerized'):
                logger.debug(f"Skipping non-dockerized device: {device_name}")
                continue

            # Get container ID
            container_id = self._get_container_id(node, device_name)

            if not container_id:
                logger.warning(f"Could not get container ID for {device_name}")
                results['failed_devices'].append({
                    'device': device_name,
                    'error': 'Container ID not found'
                })
                continue

            try:
                # Create checkpoint for this device
                device_checkpoint_name = f"{checkpoint_name}_{device_name}"

                checkpoint_result = self.criu.checkpoint_container(
                    container_id=container_id,
                    checkpoint_name=device_checkpoint_name,
                    leave_running=True  # Keep emulation running
                )

                results['devices'][device_name] = {
                    'container_id': container_id,
                    'checkpoint_name': device_checkpoint_name,
                    'size_mb': checkpoint_result['metadata']['size_mb'],
                    'duration_seconds': checkpoint_result['duration_seconds']
                }

                results['total_size_mb'] += checkpoint_result['metadata']['size_mb']

                logger.info(
                    f"Checkpointed {device_name}: "
                    f"{checkpoint_result['metadata']['size_mb']:.2f} MB"
                )

            except Exception as e:
                logger.error(f"Failed to checkpoint {device_name}: {e}")
                results['failed_devices'].append({
                    'device': device_name,
                    'error': str(e)
                })
                results['success'] = False

        # Capture network state if requested
        if include_network_state:
            try:
                results['network_state'] = self._capture_network_state()
            except Exception as e:
                logger.warning(f"Failed to capture network state: {e}")

        # Save topology metadata
        results['topology_state'] = {
            'links': {k: {'node1': v['node1'], 'node2': v['node2']}
                     for k, v in self.em.links.items()},
            'status': self.em.status,
            'wifi_enabled': self.em.is_wifi_enabled
        }

        # Save checkpoint metadata
        self._save_topology_checkpoint_metadata(checkpoint_name, results)

        logger.info(
            f"Topology checkpoint complete: {len(results['devices'])} devices, "
            f"{results['total_size_mb']:.2f} MB total"
        )

        return results

    def _get_container_id(self, node, device_name: str) -> Optional[str]:
        """Extract container ID from Mininet node"""
        try:
            # For Docker/DockerSta nodes
            if hasattr(node, 'dimage'):
                if hasattr(node, 'dcli') and hasattr(node, 'dc'):
                    container_info = node.dcli.inspect_container(node.dc)
                    return container_info['Id']
                elif hasattr(node, 'dc'):
                    # Try to get ID directly
                    return node.dc

            # Try to find by name
            result = subprocess.run(
                ['docker', 'ps', '-aqf', f'name=mn.{device_name}'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]

        except Exception as e:
            logger.debug(f"Error getting container ID for {device_name}: {e}")

        return None

    def _capture_network_state(self) -> Dict:
        """Capture current network configuration for all devices"""
        network_state = {}

        for device_name, device_info in self.em.devices.items():
            node = device_info.get('node')
            if not node:
                continue

            try:
                device_state = {
                    'interfaces': [],
                    'routes': [],
                    'arp_table': []
                }

                # Get interfaces
                for intf in node.intfList():
                    intf_data = {
                        'name': intf.name,
                        'ip': intf.IP() if hasattr(intf, 'IP') else None,
                        'mac': intf.MAC() if hasattr(intf, 'MAC') else None,
                        'status': 'up' if intf.isUp() else 'down'
                    }
                    device_state['interfaces'].append(intf_data)

                # Get routes
                routes_output = node.cmd('ip route show').strip()
                if routes_output:
                    device_state['routes'] = routes_output.split('\n')

                # Get ARP table
                arp_output = node.cmd('ip neigh show').strip()
                if arp_output:
                    device_state['arp_table'] = arp_output.split('\n')

                network_state[device_name] = device_state

            except Exception as e:
                logger.warning(f"Could not capture network state for {device_name}: {e}")

        return network_state

    def _save_topology_checkpoint_metadata(
        self,
        checkpoint_name: str,
        results: Dict
    ):
        """Save topology checkpoint metadata to file"""
        try:
            metadata_dir = os.path.join(
                self.criu.snapshot_dir,
                'topology_checkpoints'
            )
            os.makedirs(metadata_dir, exist_ok=True)

            metadata_file = os.path.join(
                metadata_dir,
                f"{checkpoint_name}.json"
            )

            with open(metadata_file, 'w') as f:
                json.dump(results, f, indent=2)

            logger.info(f"Topology checkpoint metadata saved: {metadata_file}")

        except Exception as e:
            logger.warning(f"Could not save checkpoint metadata: {e}")

    def list_topology_checkpoints(self) -> List[Dict]:
        """List all topology checkpoints"""
        metadata_dir = os.path.join(
            self.criu.snapshot_dir,
            'topology_checkpoints'
        )

        if not os.path.exists(metadata_dir):
            return []

        checkpoints = []

        try:
            for filename in os.listdir(metadata_dir):
                if filename.endswith('.json'):
                    metadata_file = os.path.join(metadata_dir, filename)
                    try:
                        with open(metadata_file, 'r') as f:
                            checkpoint_data = json.load(f)
                            checkpoints.append(checkpoint_data)
                    except Exception as e:
                        logger.warning(f"Could not read {filename}: {e}")
        except Exception as e:
            logger.error(f"Error listing topology checkpoints: {e}")

        return sorted(checkpoints, key=lambda x: x.get('timestamp', ''), reverse=True)
