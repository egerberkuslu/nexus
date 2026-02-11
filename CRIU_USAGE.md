# CRIU Integration for Caduceus-Flux

## Overview

Caduceus-Flux now supports CRIU (Checkpoint/Restore In Userspace) for creating live snapshots of running network emulations. CRIU allows you to:

- **Capture running process state** including memory, open files, and network connections
- **Live migrate** network topologies between systems
- **Fast restore** from exact execution points
- **Time-travel debugging** by capturing state at specific moments

## Architecture

### Snapshot Types

Caduceus-Flux offers four snapshot strategies:

| Type | Description | Use Case | Portability | Speed |
|------|-------------|----------|-------------|-------|
| **topology_only** | Topology structure only | Quick saves, sharing configs | High | Fastest |
| **docker_commit** | Filesystem snapshots | Static backups | High | Fast |
| **criu_live** | Live process checkpoints | Live migration, debugging | Medium | Medium |
| **hybrid_full** | Docker + CRIU combined | Complete system state | Medium | Comprehensive |

### Components

```
caduceus-flux/
├── scripts/
│   ├── install-criu.sh          # CRIU installation script
│   └── test-criu.sh             # CRIU testing suite
├── emulation-container/
│   └── grpc_agent/
│       ├── criu_handler.py      # CRIU checkpoint/restore operations
│       ├── snapshot_manager.py  # Hybrid snapshot manager
│       └── emulation_manager.py # Integrated snapshot methods
└── CRIU_USAGE.md               # This file
```

## Installation

### Prerequisites

- Linux kernel 5.0+ (with `CONFIG_CHECKPOINT_RESTORE=y`)
- Docker with experimental features
- Root access for installation

### Installation Steps

1. **Run the installation script:**
   ```bash
   sudo ./scripts/install-criu.sh
   ```

   This script will:
   - Check kernel compatibility
   - Install CRIU and dependencies
   - Enable Docker experimental features
   - Configure checkpoint directories
   - Run verification tests

2. **Verify installation:**
   ```bash
   sudo ./scripts/test-criu.sh
   ```

3. **Check CRIU availability:**
   ```bash
   criu --version
   criu check
   ```

### Manual Installation

If the automated script fails:

```bash
# Install CRIU
sudo apt-get update
sudo apt-get install -y criu

# Enable Docker experimental features
sudo mkdir -p /etc/docker
sudo cat > /etc/docker/daemon.json <<EOF
{
  "experimental": true,
  "live-restore": true
}
EOF

sudo systemctl restart docker

# Create checkpoint directories
sudo mkdir -p /var/lib/caduceus/criu
sudo mkdir -p /var/lib/caduceus/snapshots
```

## Usage

### Creating Snapshots

#### 1. Topology-Only Snapshot (Fastest)

Captures just the network structure - perfect for sharing configurations:

```python
# Via emulation manager
result = emulation_manager.create_snapshot(
    snapshot_name="my_topology",
    snapshot_type="topology_only",
    description="Network configuration for testing"
)
```

**Output:**
- JSON file with topology definition
- No container state
- ~10 KB file size

#### 2. Docker Commit Snapshot

Captures filesystem state of all containers:

```python
result = emulation_manager.create_snapshot(
    snapshot_name="docker_backup",
    snapshot_type="docker_commit",
    description="Filesystem backup"
)
```

**Output:**
- Docker images for each container
- Filesystem changes preserved
- ~100-500 MB per container

#### 3. CRIU Live Snapshot

Captures complete running state (requires CRIU):

```python
result = emulation_manager.create_snapshot(
    snapshot_name="live_checkpoint",
    snapshot_type="criu_live",
    description="Live system checkpoint"
)
```

**Output:**
- Process memory dumps
- Open file descriptors
- Network connection state
- Running process tree
- ~50-200 MB per container

#### 4. Hybrid Full Snapshot (Recommended)

Combines Docker + CRIU for complete fidelity:

```python
result = emulation_manager.create_snapshot(
    snapshot_name="full_backup",
    snapshot_type="hybrid_full",
    description="Complete system state"
)
```

**Output:**
- Docker filesystem images
- CRIU process checkpoints
- Network state
- Topology metadata
- ~200-700 MB total

### Managing Snapshots

#### List All Snapshots

```python
result = emulation_manager.list_snapshots()

for snapshot in result['snapshots']:
    print(f"Name: {snapshot['name']}")
    print(f"Type: {snapshot['type']}")
    print(f"Size: {snapshot['size_mb']:.2f} MB")
    print(f"Created: {snapshot['timestamp']}")
```

#### Delete Snapshot

```python
result = emulation_manager.delete_snapshot("snapshot_name")
```

### Direct CRIU Operations

For advanced use cases, use the CRIU handler directly:

```python
from criu_handler import CRIUHandler, MininetCRIUManager

# Initialize
criu = CRIUHandler()

# Checkpoint a container
result = criu.checkpoint_container(
    container_id="abc123",
    checkpoint_name="my_checkpoint",
    leave_running=True  # Keep container running
)

# Restore from checkpoint
result = criu.restore_container(
    container_id="abc123",
    checkpoint_name="my_checkpoint"
)

# List checkpoints
checkpoints = criu.list_checkpoints("abc123")
```

## JSON Snapshot Format

### Topology-Only Format

```json
{
  "caduceus_version": "1.0",
  "export_type": "topology_snapshot",
  "snapshot_type": "topology_only",
  "timestamp": "2025-11-18T10:30:00Z",
  "metadata": {
    "name": "my_topology",
    "description": "Network configuration",
    "topology_id": "topo-123"
  },
  "topology": {
    "devices": [...],
    "links": [...],
    "controllers": [...]
  }
}
```

### CRIU Live Format

```json
{
  "caduceus_version": "1.0",
  "export_type": "criu_snapshot",
  "snapshot_type": "criu_live",
  "snapshot_method": "criu",
  "timestamp": "2025-11-18T10:30:00Z",
  "criu_checkpoints": [
    {
      "device_name": "h1",
      "container_id": "abc123",
      "checkpoint_name": "snap_h1",
      "checkpoint_path": "/var/lib/caduceus/criu/abc123/snap_h1",
      "checkpoint_size_bytes": 45000000,
      "checkpoint_files": [
        "core-1.img",
        "mm-1.img",
        "pages-1.img",
        ...
      ]
    }
  ],
  "network_state": {
    "h1": {
      "interfaces": [...],
      "routes": [...],
      "arp_table": [...]
    }
  }
}
```

### Hybrid Full Format

```json
{
  "caduceus_version": "1.0",
  "export_type": "hybrid_snapshot",
  "snapshot_type": "hybrid_full",
  "metadata": {
    "name": "full_backup",
    "has_docker": true,
    "has_criu": true
  },
  "components": {
    "docker": {
      "docker_snapshots": {...}
    },
    "criu": {
      "criu_checkpoints": [...]
    }
  }
}
```

## Best Practices

### When to Use Each Snapshot Type

1. **topology_only**
   - Sharing network configurations
   - Version control
   - Quick saves during development
   - Documenting network designs

2. **docker_commit**
   - Backing up configured systems
   - Preserving installed software
   - Portable snapshots across systems
   - Long-term archival

3. **criu_live**
   - Live migration to another host
   - Debugging running processes
   - Capturing exact runtime state
   - Performance analysis

4. **hybrid_full**
   - Critical system backups
   - Migration + portability
   - Maximum state preservation
   - Disaster recovery

### Performance Tips

1. **Use `leave_running` for production:**
   ```python
   # Keep emulation running while checkpointing
   criu.checkpoint_container(
       container_id="abc123",
       checkpoint_name="checkpoint",
       leave_running=True
   )
   ```

2. **Compress snapshots:**
   ```python
   result = snapshot_manager.create_snapshot(
       snapshot_name="backup",
       compression=True  # Enable gzip compression
   )
   ```

3. **Clean old checkpoints:**
   ```python
   # Delete old snapshots to free space
   emulation_manager.delete_snapshot("old_snapshot")
   ```

4. **Schedule periodic snapshots:**
   ```python
   import schedule

   def create_periodic_snapshot():
       timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
       emulation_manager.create_snapshot(
           snapshot_name=f"auto_{timestamp}",
           snapshot_type="criu_live"
       )

   schedule.every(1).hours.do(create_periodic_snapshot)
   ```

## Troubleshooting

### CRIU Check Fails

**Symptom:** `criu check` reports errors

**Solutions:**
```bash
# Check kernel config
grep CONFIG_CHECKPOINT_RESTORE /boot/config-$(uname -r)

# If not enabled, rebuild kernel with CONFIG_CHECKPOINT_RESTORE=y
# Or use a distribution with it enabled (Ubuntu 20.04+, RHEL 8+)
```

### Docker Checkpoint Fails

**Symptom:** `docker checkpoint create` fails

**Solutions:**
```bash
# 1. Enable experimental features
sudo cat /etc/docker/daemon.json
# Should show: "experimental": true

# 2. Restart Docker
sudo systemctl restart docker

# 3. Check Docker version (19.03+ required)
docker --version

# 4. Test with simple container
docker run -d --name test --security-opt seccomp=unconfined alpine sleep 3600
docker checkpoint create test checkpoint1
```

### "Operation not permitted"

**Symptom:** Permission errors during checkpoint

**Solutions:**
```bash
# 1. Run with --security-opt
docker run --security-opt seccomp=unconfined ...

# 2. Add capabilities
docker run --cap-add=SYS_ADMIN --cap-add=SYS_PTRACE ...

# 3. Run as privileged (less secure)
docker run --privileged ...
```

### Network Connections Lost

**Symptom:** Connections fail after restore

**Explanation:** CRIU cannot restore all network connections (external services, etc.)

**Solutions:**
- Close external connections before checkpoint
- Implement reconnection logic in applications
- Use internal-only networking for critical connections

### Large Checkpoint Sizes

**Symptom:** Checkpoints consume too much space

**Solutions:**
```bash
# 1. Enable compression in snapshots
compression=True

# 2. Use topology_only for configs
snapshot_type="topology_only"

# 3. Clean old checkpoints
find /var/lib/caduceus/criu -mtime +7 -delete

# 4. Use docker commit instead for filesystem-only
snapshot_type="docker_commit"
```

## API Reference

### EmulationManager Methods

#### `create_snapshot(snapshot_name, snapshot_type, description)`

Creates a snapshot of the running emulation.

**Parameters:**
- `snapshot_name` (str): Unique name for snapshot
- `snapshot_type` (str): One of: `topology_only`, `docker_commit`, `criu_live`, `hybrid_full`
- `description` (str): Optional description

**Returns:**
- Dict with `success`, `message`, and `snapshot` details

#### `list_snapshots()`

Lists all available snapshots.

**Returns:**
- Dict with `success`, `count`, and `snapshots` list

#### `delete_snapshot(snapshot_name)`

Deletes a snapshot and its artifacts.

**Parameters:**
- `snapshot_name` (str): Name of snapshot to delete

**Returns:**
- Dict with `success` and `message`

### CRIUHandler Methods

#### `checkpoint_container(container_id, checkpoint_name, leave_running)`

Checkpoints a Docker container using CRIU.

**Parameters:**
- `container_id` (str): Container ID or name
- `checkpoint_name` (str): Checkpoint name
- `leave_running` (bool): Keep container running after checkpoint

**Returns:**
- Dict with checkpoint metadata

#### `restore_container(container_id, checkpoint_name)`

Restores container from CRIU checkpoint.

**Parameters:**
- `container_id` (str): Container ID
- `checkpoint_name` (str): Checkpoint to restore from

**Returns:**
- Dict with restore status

## Examples

### Example 1: Development Workflow

```python
# Start emulation
topology = load_topology("network_design.json")
emulation_manager.start_emulation("topo-1", topology, {})

# Make changes, test...

# Create quick snapshot before risky change
emulation_manager.create_snapshot(
    snapshot_name="before_change",
    snapshot_type="criu_live"
)

# Make risky changes...

# If things go wrong, restore from snapshot
# (Restore functionality coming soon)
```

### Example 2: CI/CD Pipeline

```python
# In test pipeline
def test_network_configuration():
    # Start emulation
    start_emulation(topology)

    # Create baseline snapshot
    create_snapshot("baseline", "docker_commit")

    # Run tests
    run_tests()

    # Create post-test snapshot for analysis
    create_snapshot("post_test", "hybrid_full")

    # Compare states
    compare_snapshots("baseline", "post_test")
```

### Example 3: Production Migration

```python
# On source system
emulation_manager.create_snapshot(
    snapshot_name="production_migration",
    snapshot_type="hybrid_full",
    description="Migrating to new datacenter"
)

# Export snapshot
export_snapshot("production_migration", "/mnt/transfer/")

# On destination system
import_snapshot("/mnt/transfer/production_migration.tar.gz")
restore_snapshot("production_migration")
```

## Limitations

1. **External Dependencies:** Connections to external services may not restore correctly
2. **Kernel Compatibility:** CRIU requires specific kernel features
3. **Docker Version:** Requires Docker 19.03+ with experimental features
4. **GPU State:** GPU memory and CUDA contexts are not checkpointed
5. **Time-based Logic:** Applications expecting specific timestamps may behave unexpectedly

## Future Enhancements

- [ ] Automatic snapshot rotation
- [ ] Incremental checkpoints
- [ ] Cross-system migration tool
- [ ] Snapshot comparison and diff
- [ ] Web UI for snapshot management
- [ ] Snapshot encryption
- [ ] Cloud storage integration (S3, etc.)

## References

- [CRIU Official Documentation](https://criu.org/)
- [Docker Checkpoint/Restore](https://docs.docker.com/engine/reference/commandline/checkpoint/)
- [Linux Checkpoint/Restore](https://www.kernel.org/doc/html/latest/admin-guide/criu.html)

## Support

For issues or questions:
- Check logs: `/var/log/caduceus-criu-install.log`
- Run tests: `./scripts/test-criu.sh`
- Review installation report: `/var/lib/caduceus/criu-installation-report.txt`
- Open issue on GitHub

---

**Last Updated:** 2025-11-18
**Version:** 1.0
**Caduceus-Flux Version:** 1.0
