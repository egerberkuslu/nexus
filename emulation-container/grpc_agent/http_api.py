"""
HTTP API wrapper for Emulation Manager
Provides REST endpoints for snapshot operations
Includes v2 API with Docker checkpoint support
"""

from __future__ import annotations

from flask import Flask, request, jsonify
import logging
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from emulation_manager import EmulationManager

# Import new snapshot package
from snapshot import (
    TopologySnapshotEngine,
    DockerSnapshotEngine,
    CRIUSnapshotEngine,
    HybridSnapshotEngine,
    RestoreEngine,
    DockerCheckpointHandler,
    NetworkStateCapture
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize emulation manager
em = EmulationManager()

# Initialize snapshot engines
checkpoint_handler = DockerCheckpointHandler()
topology_engine = TopologySnapshotEngine(em)
docker_engine = DockerSnapshotEngine(em)
criu_engine = CRIUSnapshotEngine(em)
hybrid_engine = HybridSnapshotEngine(em)
restore_engine = RestoreEngine(em)
network_capture = NetworkStateCapture(em)


# ==================== Legacy API (v1) ====================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'emulation-container-http',
        'snapshot_available': em.snapshot_manager is not None,
        'criu_available': checkpoint_handler.criu_available,
        'docker_experimental': checkpoint_handler.docker_experimental
    })


@app.route('/api/snapshot/create', methods=['POST'])
def create_snapshot():
    """Create snapshot via HTTP (legacy v1)"""
    try:
        data = request.json

        snapshot_name = data.get('snapshot_name')
        snapshot_type = data.get('snapshot_type', 'hybrid_full')
        description = data.get('description', '')
        compression = data.get('compression', True)

        if not snapshot_name:
            return jsonify({
                'success': False,
                'message': 'snapshot_name required'
            }), 400

        result = em.create_snapshot(
            snapshot_name=snapshot_name,
            snapshot_type=snapshot_type,
            description=description
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Snapshot creation failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/snapshot/list', methods=['GET'])
def list_snapshots():
    """List snapshots (legacy v1)"""
    try:
        result = em.list_snapshots()
        return jsonify(result)
    except Exception as e:
        logger.error(f"List snapshots failed: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/snapshot/delete/<snapshot_name>', methods=['DELETE'])
def delete_snapshot(snapshot_name):
    """Delete snapshot (legacy v1)"""
    try:
        result = em.delete_snapshot(snapshot_name)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Delete snapshot failed: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/snapshot/restore', methods=['POST'])
def restore_snapshot_v1():
    """Restore snapshot (legacy v1 - placeholder)"""
    return jsonify({
        'success': False,
        'message': 'Use /api/v2/snapshot/restore for full restore support'
    }), 501


# ==================== New API (v2) ====================

@app.route('/api/v2/snapshot/create', methods=['POST'])
def create_snapshot_v2():
    """
    Create snapshot using new snapshot engines

    Request body:
    {
        "snapshot_name": "my_snapshot",
        "snapshot_type": "hybrid_full",  // topology_only, docker_commit, criu_live, hybrid_full
        "topology_id": "...",
        "emulation_id": "...",
        "compression": true,
        "target_containers": ["h1", "h2"],  // null = all
        "include_routing": true,
        "include_flows": true,
        "include_arp": true
    }
    """
    try:
        data = request.json or {}

        snapshot_name = data.get('snapshot_name')
        snapshot_type = data.get('snapshot_type', 'hybrid_full')
        compression = data.get('compression', True)
        target_containers = data.get('target_containers')
        include_routing = data.get('include_routing', True)
        include_flows = data.get('include_flows', True)
        include_arp = data.get('include_arp', True)

        if not snapshot_name:
            return jsonify({
                'success': False,
                'error_message': 'snapshot_name is required'
            }), 400

        # Select appropriate engine
        engine = _get_snapshot_engine(snapshot_type)

        # Create snapshot
        result = engine.create_snapshot(
            snapshot_name=snapshot_name,
            description=data.get('description', ''),
            target_devices=target_containers,
            compression=compression,
            include_routing=include_routing,
            include_flows=include_flows,
            include_arp=include_arp
        )

        # Convert dataclass to dict
        response = {
            'success': result.success,
            'snapshot_name': result.snapshot_name,
            'snapshot_type': result.snapshot_type,
            'snapshot_path': result.snapshot_path,
            'size_bytes': result.size_bytes,
            'devices_captured': result.devices_captured,
            'containers_captured': result.containers_captured,
            'duration_seconds': result.duration_seconds,
            'error_message': result.error_message,
            'topology_data': result.topology_data,
            'network_state': result.network_state,
            'docker_images': result.docker_images,
            'criu_checkpoints': result.criu_checkpoints,
            'criu_available': result.criu_available,
            'timestamp': result.timestamp
        }

        if result.success:
            return jsonify(response), 200
        else:
            return jsonify(response), 500

    except Exception as e:
        logger.error(f"Snapshot creation failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/snapshot/restore', methods=['POST'])
def restore_snapshot_v2():
    """
    Restore from snapshot data

    Request body:
    {
        "snapshot_data": {...},  // Full snapshot data from MongoDB
        "target_devices": ["h1", "h2"],  // null = all
        "restore_network_state": true,
        "restore_docker_images": true,
        "restore_criu_checkpoints": true
    }
    """
    try:
        data = request.json or {}

        snapshot_data = data.get('snapshot_data')
        if not snapshot_data:
            return jsonify({
                'success': False,
                'error_message': 'snapshot_data is required'
            }), 400

        target_devices = data.get('target_devices')
        restore_network_state = data.get('restore_network_state', True)
        restore_docker_images = data.get('restore_docker_images', True)
        restore_criu_checkpoints = data.get('restore_criu_checkpoints', True)

        # Validate snapshot data
        valid, error = restore_engine.validate_snapshot(snapshot_data)
        if not valid:
            return jsonify({
                'success': False,
                'error_message': f'Invalid snapshot data: {error}'
            }), 400

        # Perform restore
        result = restore_engine.restore_snapshot(
            snapshot_data=snapshot_data,
            target_devices=target_devices,
            restore_network_state=restore_network_state,
            restore_docker_images=restore_docker_images,
            restore_criu_checkpoints=restore_criu_checkpoints
        )

        response = {
            'success': result.success,
            'snapshot_name': result.snapshot_name,
            'devices_restored': result.devices_restored,
            'containers_restored': result.containers_restored,
            'network_state_restored': result.network_state_restored,
            'duration_seconds': result.duration_seconds,
            'error_message': result.error_message,
            'warnings': result.warnings,
            'rollback_performed': result.rollback_performed,
            'restored_devices': result.restored_devices,
            'failed_devices': result.failed_devices
        }

        if result.success:
            return jsonify(response), 200
        else:
            return jsonify(response), 500

    except Exception as e:
        logger.error(f"Snapshot restore failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/snapshot/list', methods=['GET'])
def list_snapshots_v2():
    """List all snapshots with detailed info"""
    try:
        # This would list from local storage
        # The actual list is managed by the backend service
        snapshots = []

        # List from each engine
        if hasattr(em, 'snapshot_manager') and em.snapshot_manager:
            snapshots = em.snapshot_manager.list_snapshots()

        return jsonify({
            'success': True,
            'snapshots': snapshots,
            'count': len(snapshots)
        }), 200

    except Exception as e:
        logger.error(f"List snapshots failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/snapshot/<snapshot_name>', methods=['DELETE'])
def delete_snapshot_v2(snapshot_name: str):
    """Delete a snapshot by name"""
    try:
        # Delete from local storage
        if hasattr(em, 'snapshot_manager') and em.snapshot_manager:
            result = em.snapshot_manager.delete_snapshot(snapshot_name)
            return jsonify({
                'success': result,
                'snapshot_name': snapshot_name
            }), 200 if result else 404

        return jsonify({
            'success': False,
            'error_message': 'Snapshot manager not available'
        }), 500

    except Exception as e:
        logger.error(f"Delete snapshot failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/checkpoint/status', methods=['GET'])
def checkpoint_status():
    """Get Docker checkpoint/CRIU status"""
    try:
        return jsonify({
            'success': True,
            'criu_available': checkpoint_handler.criu_available,
            'docker_experimental': checkpoint_handler.docker_experimental,
            'checkpoint_supported': checkpoint_handler.is_available()
        }), 200

    except Exception as e:
        logger.error(f"Checkpoint status check failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/checkpoint/create', methods=['POST'])
def create_checkpoint():
    """
    Create Docker checkpoint for a specific container

    Request body:
    {
        "container_id": "abc123",
        "checkpoint_name": "my_checkpoint",
        "leave_running": true
    }
    """
    try:
        data = request.json or {}

        container_id = data.get('container_id')
        checkpoint_name = data.get('checkpoint_name')
        leave_running = data.get('leave_running', True)

        if not container_id or not checkpoint_name:
            return jsonify({
                'success': False,
                'error_message': 'container_id and checkpoint_name are required'
            }), 400

        if not checkpoint_handler.is_available():
            return jsonify({
                'success': False,
                'error_message': 'Docker checkpoint not available (CRIU required)'
            }), 400

        result = checkpoint_handler.create_checkpoint(
            container_id=container_id,
            checkpoint_name=checkpoint_name,
            leave_running=leave_running
        )

        return jsonify({
            'success': True,
            **result
        }), 200

    except Exception as e:
        logger.error(f"Checkpoint creation failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/checkpoint/restore', methods=['POST'])
def restore_checkpoint():
    """
    Restore a container from checkpoint

    Request body:
    {
        "container_id": "abc123",
        "checkpoint_name": "my_checkpoint"
    }
    """
    try:
        data = request.json or {}

        container_id = data.get('container_id')
        checkpoint_name = data.get('checkpoint_name')

        if not container_id or not checkpoint_name:
            return jsonify({
                'success': False,
                'error_message': 'container_id and checkpoint_name are required'
            }), 400

        if not checkpoint_handler.is_available():
            return jsonify({
                'success': False,
                'error_message': 'Docker checkpoint not available (CRIU required)'
            }), 400

        result = checkpoint_handler.restore_checkpoint(
            container_id=container_id,
            checkpoint_name=checkpoint_name
        )

        return jsonify({
            'success': True,
            **result
        }), 200

    except Exception as e:
        logger.error(f"Checkpoint restore failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/checkpoint/list/<container_id>', methods=['GET'])
def list_checkpoints(container_id: str):
    """List checkpoints for a container"""
    try:
        checkpoints = checkpoint_handler.list_checkpoints(container_id)
        return jsonify({
            'success': True,
            'container_id': container_id,
            'checkpoints': checkpoints
        }), 200

    except Exception as e:
        logger.error(f"List checkpoints failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/checkpoint/<container_id>/<checkpoint_name>', methods=['DELETE'])
def delete_checkpoint(container_id: str, checkpoint_name: str):
    """Delete a checkpoint"""
    try:
        result = checkpoint_handler.delete_checkpoint(container_id, checkpoint_name)
        return jsonify({
            'success': result,
            'container_id': container_id,
            'checkpoint_name': checkpoint_name
        }), 200 if result else 404

    except Exception as e:
        logger.error(f"Delete checkpoint failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/network/state', methods=['GET'])
def capture_network_state():
    """Capture current network state"""
    try:
        devices = request.args.getlist('devices')
        include_routing = request.args.get('include_routing', 'true').lower() == 'true'
        include_arp = request.args.get('include_arp', 'true').lower() == 'true'
        include_flows = request.args.get('include_flows', 'true').lower() == 'true'

        state = network_capture.capture_all(
            devices=devices if devices else None,
            include_routing=include_routing,
            include_arp=include_arp,
            include_flows=include_flows
        )

        return jsonify({
            'success': True,
            'state': state
        }), 200

    except Exception as e:
        logger.error(f"Network state capture failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/network/state/restore', methods=['POST'])
def restore_network_state():
    """Restore network state"""
    try:
        data = request.json or {}

        state = data.get('state')
        if not state:
            return jsonify({
                'success': False,
                'error_message': 'state is required'
            }), 400

        devices = data.get('devices')
        restore_routing = data.get('restore_routing', True)
        restore_arp = data.get('restore_arp', True)
        restore_flows = data.get('restore_flows', True)

        errors = network_capture.restore_all(
            state=state,
            devices=devices,
            restore_routing=restore_routing,
            restore_arp=restore_arp,
            restore_flows=restore_flows
        )

        return jsonify({
            'success': len(errors) == 0,
            'errors': errors
        }), 200 if len(errors) == 0 else 500

    except Exception as e:
        logger.error(f"Network state restore failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


@app.route('/api/v2/containers', methods=['GET'])
def list_containers():
    """List all containers in the current emulation"""
    try:
        containers = []

        if hasattr(em, 'devices'):
            for name, info in em.devices.items():
                is_docker = info.get('is_docker', False)
                device_type = info.get('type', 'unknown')

                container_info = {
                    'name': name,
                    'type': device_type,
                    'is_docker': is_docker,
                    'status': 'running' if em.status == 'running' else 'stopped'
                }

                # Get container ID if available
                if is_docker:
                    node = info.get('node')
                    if node:
                        container_id = checkpoint_handler.get_container_id_from_mininet_node(node)
                        if container_id:
                            container_info['container_id'] = container_id

                containers.append(container_info)

        return jsonify({
            'success': True,
            'containers': containers,
            'count': len(containers)
        }), 200

    except Exception as e:
        logger.error(f"List containers failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error_message': str(e)
        }), 500


# ==================== Helper Functions ====================

def _get_snapshot_engine(snapshot_type: str):
    """Get the appropriate snapshot engine for the given type"""
    engines = {
        'topology_only': topology_engine,
        'docker_commit': docker_engine,
        'criu_live': criu_engine,
        'hybrid_full': hybrid_engine
    }

    engine = engines.get(snapshot_type)
    if not engine:
        raise ValueError(f"Unknown snapshot type: {snapshot_type}")

    return engine


# ==================== Main ====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
