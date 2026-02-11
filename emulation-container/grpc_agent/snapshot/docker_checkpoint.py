"""
Docker checkpoint handler for CRIU-based container checkpointing
Uses Docker's experimental checkpoint feature
"""

from __future__ import annotations

import os
import subprocess
import logging
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Default checkpoint directories
CHECKPOINT_BASE_DIR = "/var/lib/caduceus/checkpoints"
DOCKER_CHECKPOINT_DIR = "/var/lib/docker/containers"


class DockerCheckpointError(Exception):
    """Exception raised for Docker checkpoint errors"""
    pass


class DockerCheckpointHandler:
    """
    Handles Docker checkpoint create/restore operations using CRIU

    Docker checkpoint requirements:
    - Docker experimental features enabled
    - Container started without -t (TTY) flag
    - Container has --security-opt=seccomp:unconfined
    - CRIU installed on host (version 2.0+)
    """

    def __init__(self, checkpoint_dir: str = CHECKPOINT_BASE_DIR):
        """
        Initialize checkpoint handler

        Args:
            checkpoint_dir: Base directory for storing checkpoint metadata
        """
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        # Check availability
        self.criu_available = self._check_criu_available()
        self.docker_experimental = self._check_docker_experimental()

        if not self.criu_available:
            logger.warning("CRIU is not available - checkpoints will not work")
        if not self.docker_experimental:
            logger.warning("Docker experimental features not enabled")

    def _check_criu_available(self) -> bool:
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
                logger.info(f"CRIU available: {version}")
                return True
            return False
        except FileNotFoundError:
            logger.warning("CRIU not installed")
            return False
        except Exception as e:
            logger.error(f"CRIU check failed: {e}")
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
                logger.info(f"Docker experimental: {experimental}")
                return experimental
            return False
        except Exception as e:
            logger.warning(f"Could not check Docker experimental: {e}")
            return False

    def is_available(self) -> bool:
        """Check if checkpoint functionality is available"""
        return self.criu_available and self.docker_experimental

    def create_checkpoint(
        self,
        container_id: str,
        checkpoint_name: str,
        leave_running: bool = True,
        checkpoint_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Docker checkpoint for a container

        Args:
            container_id: Docker container ID or name
            checkpoint_name: Unique name for this checkpoint
            leave_running: Keep container running after checkpoint (default True)
            checkpoint_dir: Custom checkpoint directory (optional)

        Returns:
            Dict with checkpoint metadata including path and size

        Raises:
            DockerCheckpointError: If checkpoint creation fails
        """
        if not self.is_available():
            raise DockerCheckpointError("CRIU/Docker checkpoint not available")

        # Validate container exists and is running
        if not self._container_exists(container_id):
            raise DockerCheckpointError(f"Container {container_id} not found")

        if not self._container_running(container_id):
            raise DockerCheckpointError(f"Container {container_id} is not running")

        # Build checkpoint command
        cmd = ['docker', 'checkpoint', 'create']

        if checkpoint_dir:
            cmd.extend(['--checkpoint-dir', checkpoint_dir])

        if leave_running:
            cmd.append('--leave-running')

        cmd.extend([container_id, checkpoint_name])

        logger.info(f"Creating checkpoint: {' '.join(cmd)}")

        try:
            start_time = datetime.utcnow()

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                raise DockerCheckpointError(f"Checkpoint failed: {error_msg}")

            # Get checkpoint path
            if checkpoint_dir:
                checkpoint_path = os.path.join(checkpoint_dir, checkpoint_name)
            else:
                # Default Docker checkpoint location
                container_full_id = self._get_container_full_id(container_id)
                checkpoint_path = os.path.join(
                    DOCKER_CHECKPOINT_DIR,
                    container_full_id,
                    'checkpoints',
                    checkpoint_name
                )

            # Calculate size
            size_bytes = self._get_directory_size(checkpoint_path)

            metadata = {
                'container_id': container_id,
                'container_full_id': self._get_container_full_id(container_id),
                'checkpoint_name': checkpoint_name,
                'checkpoint_path': checkpoint_path,
                'size_bytes': size_bytes,
                'leave_running': leave_running,
                'duration_seconds': duration,
                'created_at': datetime.utcnow().isoformat()
            }

            logger.info(
                f"Checkpoint created: {checkpoint_name} "
                f"({size_bytes / 1024 / 1024:.2f} MB in {duration:.2f}s)"
            )

            return metadata

        except subprocess.TimeoutExpired:
            raise DockerCheckpointError("Checkpoint timed out after 5 minutes")
        except DockerCheckpointError:
            raise
        except Exception as e:
            raise DockerCheckpointError(f"Checkpoint failed: {e}")

    def restore_checkpoint(
        self,
        container_id: str,
        checkpoint_name: str,
        checkpoint_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Restore a container from a checkpoint

        Args:
            container_id: Docker container ID or name
            checkpoint_name: Name of checkpoint to restore
            checkpoint_dir: Custom checkpoint directory (optional)

        Returns:
            Dict with restore metadata

        Raises:
            DockerCheckpointError: If restore fails
        """
        if not self.is_available():
            raise DockerCheckpointError("CRIU/Docker checkpoint not available")

        # Container should be stopped before restore
        if self._container_running(container_id):
            logger.info(f"Stopping container {container_id} before restore")
            self._stop_container(container_id)

        # Build restore command
        cmd = ['docker', 'start', '--checkpoint', checkpoint_name]

        if checkpoint_dir:
            cmd.extend(['--checkpoint-dir', checkpoint_dir])

        cmd.append(container_id)

        logger.info(f"Restoring checkpoint: {' '.join(cmd)}")

        try:
            start_time = datetime.utcnow()

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                raise DockerCheckpointError(f"Restore failed: {error_msg}")

            metadata = {
                'container_id': container_id,
                'checkpoint_name': checkpoint_name,
                'duration_seconds': duration,
                'restored_at': datetime.utcnow().isoformat()
            }

            logger.info(f"Checkpoint restored: {checkpoint_name} in {duration:.2f}s")

            return metadata

        except subprocess.TimeoutExpired:
            raise DockerCheckpointError("Restore timed out after 5 minutes")
        except DockerCheckpointError:
            raise
        except Exception as e:
            raise DockerCheckpointError(f"Restore failed: {e}")

    def list_checkpoints(self, container_id: str) -> List[Dict[str, Any]]:
        """
        List all checkpoints for a container

        Args:
            container_id: Docker container ID or name

        Returns:
            List of checkpoint info dicts
        """
        try:
            result = subprocess.run(
                ['docker', 'checkpoint', 'ls', container_id],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return []

            checkpoints = []
            lines = result.stdout.strip().split('\n')

            # Skip header line
            for line in lines[1:]:
                if line.strip():
                    checkpoint_name = line.strip()
                    checkpoints.append({
                        'name': checkpoint_name,
                        'container_id': container_id
                    })

            return checkpoints

        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            return []

    def delete_checkpoint(
        self,
        container_id: str,
        checkpoint_name: str,
        checkpoint_dir: Optional[str] = None
    ) -> bool:
        """
        Delete a checkpoint

        Args:
            container_id: Docker container ID or name
            checkpoint_name: Name of checkpoint to delete
            checkpoint_dir: Custom checkpoint directory (optional)

        Returns:
            True if deletion successful
        """
        try:
            cmd = ['docker', 'checkpoint', 'rm']

            if checkpoint_dir:
                cmd.extend(['--checkpoint-dir', checkpoint_dir])

            cmd.extend([container_id, checkpoint_name])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info(f"Deleted checkpoint: {checkpoint_name}")
                return True

            logger.warning(f"Failed to delete checkpoint: {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
            return False

    def export_checkpoint(
        self,
        container_id: str,
        checkpoint_name: str,
        export_path: str,
        checkpoint_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        Export checkpoint to a tar.gz archive

        Args:
            container_id: Docker container ID or name
            checkpoint_name: Name of checkpoint
            export_path: Path to save the archive
            checkpoint_dir: Custom checkpoint directory (optional)

        Returns:
            Path to exported archive or None if failed
        """
        try:
            # Find checkpoint path
            if checkpoint_dir:
                checkpoint_path = os.path.join(checkpoint_dir, checkpoint_name)
            else:
                container_full_id = self._get_container_full_id(container_id)
                checkpoint_path = os.path.join(
                    DOCKER_CHECKPOINT_DIR,
                    container_full_id,
                    'checkpoints',
                    checkpoint_name
                )

            if not os.path.exists(checkpoint_path):
                logger.error(f"Checkpoint path not found: {checkpoint_path}")
                return None

            # Create tar.gz archive
            import tarfile
            archive_path = f"{export_path}.tar.gz"

            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(checkpoint_path, arcname=checkpoint_name)

            logger.info(f"Exported checkpoint to: {archive_path}")
            return archive_path

        except Exception as e:
            logger.error(f"Failed to export checkpoint: {e}")
            return None

    def import_checkpoint(
        self,
        container_id: str,
        archive_path: str,
        checkpoint_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        Import checkpoint from a tar.gz archive

        Args:
            container_id: Docker container ID or name
            archive_path: Path to the archive
            checkpoint_dir: Destination checkpoint directory (optional)

        Returns:
            Checkpoint name or None if failed
        """
        try:
            import tarfile

            # Determine destination
            if checkpoint_dir:
                dest_dir = checkpoint_dir
            else:
                container_full_id = self._get_container_full_id(container_id)
                dest_dir = os.path.join(
                    DOCKER_CHECKPOINT_DIR,
                    container_full_id,
                    'checkpoints'
                )

            os.makedirs(dest_dir, exist_ok=True)

            # Extract archive
            with tarfile.open(archive_path, "r:gz") as tar:
                # Get checkpoint name from archive
                members = tar.getnames()
                if not members:
                    return None

                checkpoint_name = members[0].split('/')[0]
                tar.extractall(dest_dir)

            logger.info(f"Imported checkpoint: {checkpoint_name}")
            return checkpoint_name

        except Exception as e:
            logger.error(f"Failed to import checkpoint: {e}")
            return None

    # ==================== Helper Methods ====================

    def _container_exists(self, container_id: str) -> bool:
        """Check if container exists"""
        try:
            result = subprocess.run(
                ['docker', 'inspect', container_id],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def _container_running(self, container_id: str) -> bool:
        """Check if container is running"""
        try:
            result = subprocess.run(
                ['docker', 'inspect', '-f', '{{.State.Running}}', container_id],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip().lower() == 'true'
        except Exception:
            return False

    def _stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a container"""
        try:
            result = subprocess.run(
                ['docker', 'stop', '-t', str(timeout), container_id],
                capture_output=True,
                timeout=timeout + 30
            )
            return result.returncode == 0
        except Exception:
            return False

    def _get_container_full_id(self, container_id: str) -> str:
        """Get full container ID from short ID or name"""
        try:
            result = subprocess.run(
                ['docker', 'inspect', '-f', '{{.Id}}', container_id],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return container_id
        except Exception:
            return container_id

    def _get_directory_size(self, path: str) -> int:
        """Get total size of a directory"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception:
            pass
        return total_size

    def get_container_id_from_mininet_node(self, node) -> Optional[str]:
        """
        Extract Docker container ID from a Mininet/Containernet node

        Args:
            node: Mininet node object

        Returns:
            Container ID or None
        """
        try:
            # Containernet Docker nodes have a 'dc' (docker container) attribute
            if hasattr(node, 'dc'):
                return node.dc.id

            # Alternative: check for container attribute
            if hasattr(node, 'container'):
                return node.container.id

            # Try to get from PID
            if hasattr(node, 'pid'):
                # Look up container by PID
                result = subprocess.run(
                    ['docker', 'ps', '-q', '--filter', f'pid={node.pid}'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()

            return None

        except Exception as e:
            logger.error(f"Failed to get container ID: {e}")
            return None


# Export
__all__ = ['DockerCheckpointHandler', 'DockerCheckpointError']
