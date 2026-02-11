#!/usr/bin/env python3
"""
Example: Using CRIU Snapshots in Caduceus-Flux
Demonstrates different snapshot types and operations
"""

import requests
import time
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost/api"
TOPOLOGY_ID = "your-topology-id"
EMULATION_ID = "your-emulation-id"


class SnapshotExample:
    """Example usage of snapshot API"""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def create_topology_snapshot(self, name: str) -> dict:
        """Example 1: Create quick topology snapshot"""
        print(f"\n=== Creating Topology-Only Snapshot: {name} ===")

        response = requests.post(
            f"{self.base_url}/snapshots",
            json={
                "name": name,
                "topology_id": TOPOLOGY_ID,
                "snapshot_type": "topology_only",
                "description": "Quick topology structure save",
                "compression": True
            }
        )

        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Result: {json.dumps(result, indent=2)}")

        return result

    def create_docker_snapshot(self, name: str) -> dict:
        """Example 2: Create Docker commit snapshot"""
        print(f"\n=== Creating Docker Commit Snapshot: {name} ===")

        response = requests.post(
            f"{self.base_url}/snapshots",
            json={
                "name": name,
                "topology_id": TOPOLOGY_ID,
                "emulation_id": EMULATION_ID,
                "snapshot_type": "docker_commit",
                "description": "Filesystem backup via Docker commit",
                "compression": True
            }
        )

        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Result: {json.dumps(result, indent=2)}")

        return result

    def create_criu_snapshot(self, name: str) -> dict:
        """Example 3: Create CRIU live snapshot"""
        print(f"\n=== Creating CRIU Live Snapshot: {name} ===")

        response = requests.post(
            f"{self.base_url}/snapshots",
            json={
                "name": name,
                "topology_id": TOPOLOGY_ID,
                "emulation_id": EMULATION_ID,
                "snapshot_type": "criu_live",
                "description": "Live process checkpoint with CRIU",
                "compression": True
            }
        )

        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Result: {json.dumps(result, indent=2)}")

        return result

    def create_hybrid_snapshot(self, name: str) -> dict:
        """Example 4: Create hybrid full snapshot"""
        print(f"\n=== Creating Hybrid Full Snapshot: {name} ===")

        response = requests.post(
            f"{self.base_url}/snapshots",
            json={
                "name": name,
                "topology_id": TOPOLOGY_ID,
                "emulation_id": EMULATION_ID,
                "snapshot_type": "hybrid_full",
                "description": "Complete Docker + CRIU snapshot",
                "compression": True
            }
        )

        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Result: {json.dumps(result, indent=2)}")

        return result

    def list_snapshots(self, topology_id: str = None) -> list:
        """Example 5: List all snapshots"""
        print("\n=== Listing All Snapshots ===")

        params = {}
        if topology_id:
            params["topology_id"] = topology_id

        response = requests.get(f"{self.base_url}/snapshots", params=params)

        snapshots = response.json()
        print(f"Found {len(snapshots)} snapshots:")

        for snap in snapshots:
            print(f"  - {snap['name']}")
            print(f"    Type: {snap['snapshot_type']}")
            print(f"    Status: {snap['status']}")
            print(f"    Size: {snap.get('size_mb', 0):.2f} MB")
            print(f"    Created: {snap['timestamp']}")
            print()

        return snapshots

    def get_snapshot_details(self, snapshot_id: str) -> dict:
        """Example 6: Get snapshot details"""
        print(f"\n=== Getting Snapshot Details: {snapshot_id} ===")

        response = requests.get(f"{self.base_url}/snapshots/{snapshot_id}")

        snapshot = response.json()
        print(f"Snapshot: {json.dumps(snapshot, indent=2)}")

        return snapshot

    def download_snapshot(self, snapshot_id: str, output_file: str):
        """Example 7: Download snapshot"""
        print(f"\n=== Downloading Snapshot: {snapshot_id} ===")

        response = requests.get(f"{self.base_url}/snapshots/{snapshot_id}/download")

        if response.status_code == 200:
            with open(output_file, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded to: {output_file}")
            print(f"Size: {len(response.content)} bytes")
        else:
            print(f"Error: {response.text}")

    def import_snapshot(self, file_path: str, name: str = None) -> dict:
        """Example 8: Import snapshot"""
        print(f"\n=== Importing Snapshot from: {file_path} ===")

        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {}
            if name:
                data['name'] = name

            response = requests.post(
                f"{self.base_url}/snapshots/import",
                files=files,
                data=data
            )

        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Result: {json.dumps(result, indent=2)}")

        return result

    def restore_snapshot(self, snapshot_id: str) -> dict:
        """Example 9: Restore snapshot"""
        print(f"\n=== Restoring Snapshot: {snapshot_id} ===")

        response = requests.post(
            f"{self.base_url}/snapshots/{snapshot_id}/restore",
            json={
                "snapshot_id": snapshot_id,
                "restore_network_state": True
            }
        )

        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Result: {json.dumps(result, indent=2)}")

        return result

    def delete_snapshot(self, snapshot_id: str):
        """Example 10: Delete snapshot"""
        print(f"\n=== Deleting Snapshot: {snapshot_id} ===")

        response = requests.delete(f"{self.base_url}/snapshots/{snapshot_id}")

        print(f"Status: {response.status_code}")
        if response.status_code == 204:
            print("Snapshot deleted successfully")
        else:
            print(f"Error: {response.text}")

    def get_snapshot_types(self) -> dict:
        """Example 11: Get available snapshot types"""
        print("\n=== Available Snapshot Types ===")

        response = requests.get(f"{self.base_url}/snapshots/types")

        types_info = response.json()
        print(json.dumps(types_info, indent=2))

        return types_info

    def get_snapshot_stats(self) -> dict:
        """Example 12: Get snapshot statistics"""
        print("\n=== Snapshot Statistics ===")

        response = requests.get(f"{self.base_url}/snapshots/stats")

        stats = response.json()
        print(f"Total Snapshots: {stats['total_snapshots']}")
        print(f"By Type: {stats['by_type']}")
        print(f"By Status: {stats['by_status']}")
        print(f"Total Size: {stats['total_size_mb']:.2f} MB")

        return stats


def wait_for_snapshot(api: SnapshotExample, snapshot_id: str, timeout: int = 300):
    """Wait for snapshot to complete"""
    print(f"\nWaiting for snapshot {snapshot_id} to complete...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        snapshot = api.get_snapshot_details(snapshot_id)

        status = snapshot.get('status')
        print(f"  Status: {status}")

        if status == 'captured':
            print("✓ Snapshot captured successfully!")
            return True
        elif status == 'failed':
            print("✗ Snapshot failed!")
            print(f"  Error: {snapshot.get('error')}")
            return False

        time.sleep(5)

    print("✗ Timeout waiting for snapshot")
    return False


def main():
    """Run all examples"""
    print("=" * 70)
    print("Caduceus-Flux Snapshot Examples")
    print("=" * 70)

    api = SnapshotExample(API_BASE_URL)

    # Example 1: List snapshot types
    api.get_snapshot_types()

    # Example 2: Create topology-only snapshot (fast)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    topology_snap = api.create_topology_snapshot(f"topology_{timestamp}")

    # Example 3: List all snapshots
    time.sleep(2)
    api.list_snapshots(TOPOLOGY_ID)

    # Example 4: Get snapshot details
    if 'id' in topology_snap:
        api.get_snapshot_details(topology_snap['id'])

        # Example 5: Download snapshot
        api.download_snapshot(topology_snap['id'], f"snapshot_{timestamp}.json.gz")

    # Example 6: Get stats
    api.get_snapshot_stats()

    # Uncomment these for full snapshot examples (require running emulation)

    # # Example 7: Docker commit snapshot
    # docker_snap = api.create_docker_snapshot(f"docker_{timestamp}")
    # if 'id' in docker_snap:
    #     wait_for_snapshot(api, docker_snap['id'])

    # # Example 8: CRIU live snapshot
    # criu_snap = api.create_criu_snapshot(f"criu_{timestamp}")
    # if 'id' in criu_snap:
    #     wait_for_snapshot(api, criu_snap['id'])

    # # Example 9: Hybrid full snapshot
    # hybrid_snap = api.create_hybrid_snapshot(f"hybrid_{timestamp}")
    # if 'id' in hybrid_snap:
    #     wait_for_snapshot(api, hybrid_snap['id'])

    # # Example 10: Restore snapshot
    # api.restore_snapshot(topology_snap['id'])

    # # Example 11: Delete snapshot
    # api.delete_snapshot(topology_snap['id'])

    print("\n" + "=" * 70)
    print("Examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
