# Snapshot Quick Start Guide

## Installation (5 minutes)

```bash
# 1. Install CRIU and configure Docker
sudo ./scripts/install-criu.sh

# 2. Verify installation
sudo ./scripts/test-criu.sh

# 3. Done! You're ready to create snapshots
```

## Creating Your First Snapshot

### Option 1: Quick Topology Save (Fastest - 1 second)

```python
from emulation_manager import EmulationManager

em = EmulationManager()
# ... start your emulation ...

result = em.create_snapshot(
    snapshot_name="my_first_snapshot",
    snapshot_type="topology_only",
    description="Quick save of network structure"
)

print(f"Snapshot saved: {result['snapshot']['snapshot_path']}")
```

**Result:** JSON file (~10 KB) with topology structure

### Option 2: Docker Filesystem Backup (Fast - 30 seconds)

```python
result = em.create_snapshot(
    snapshot_name="docker_backup",
    snapshot_type="docker_commit",
    description="Backup with all installed software"
)

print(f"Containers snapshotted: {result['snapshot']['devices_snapshotted']}")
print(f"Total size: {result['snapshot']['total_size_mb']:.2f} MB")
```

**Result:** Docker images with filesystem state (~100-500 MB per container)

### Option 3: Live CRIU Checkpoint (Medium - 1 minute)

```python
result = em.create_snapshot(
    snapshot_name="live_checkpoint",
    snapshot_type="criu_live",
    description="Live snapshot with running processes"
)

print(f"Devices checkpointed: {result['snapshot']['devices_checkpointed']}")
print(f"Total size: {result['snapshot']['total_size_mb']:.2f} MB")
```

**Result:** CRIU checkpoint with process memory and state (~50-200 MB per container)

### Option 4: Complete Hybrid Backup (Comprehensive - 2 minutes)

```python
result = em.create_snapshot(
    snapshot_name="complete_backup",
    snapshot_type="hybrid_full",
    description="Complete system state"
)

print(f"Package size: {result.get('package_size_mb', 0):.2f} MB")
print(f"Package location: {result.get('package_path')}")
```

**Result:** Combined Docker + CRIU snapshot (~200-700 MB total)

## Managing Snapshots

### List All Snapshots

```python
result = em.list_snapshots()

for snapshot in result['snapshots']:
    print(f"{snapshot['name']}: {snapshot['size_mb']:.1f} MB ({snapshot['type']})")
```

### Delete Snapshot

```python
result = em.delete_snapshot("my_first_snapshot")
print(result['message'])
```

## Snapshot Comparison

| Type | Speed | Size | Portability | Live State | Use Case |
|------|-------|------|-------------|-----------|----------|
| **topology_only** | ⚡ 1s | 📦 10KB | ✅ High | ❌ No | Configs, sharing |
| **docker_commit** | 🚀 30s | 📦 500MB | ✅ High | ❌ No | Backups, archival |
| **criu_live** | 🏃 60s | 📦 200MB | ⚠️ Medium | ✅ Yes | Live migration |
| **hybrid_full** | 🐢 2min | 📦 700MB | ⚠️ Medium | ✅ Yes | Complete backup |

## Common Use Cases

### 1. Quick Save Before Risky Change

```python
# Before making changes
em.create_snapshot("before_experiment", "criu_live")

# Make changes...
# If something breaks, restore from snapshot
```

### 2. Daily Backup

```python
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M")
em.create_snapshot(f"daily_backup_{timestamp}", "hybrid_full")
```

### 3. Share Configuration with Team

```python
# Create portable topology
em.create_snapshot("team_config", "topology_only")

# Share the JSON file
# Location: /var/lib/caduceus/snapshots/team_config/team_config.json
```

### 4. CI/CD Testing

```python
# In test pipeline
def test_network():
    # Create baseline
    em.create_snapshot("test_baseline", "docker_commit")

    # Run tests
    run_integration_tests()

    # Create post-test snapshot
    em.create_snapshot("test_result", "docker_commit")
```

## Troubleshooting

### "CRIU not available"

```bash
# Install CRIU
sudo ./scripts/install-criu.sh

# Verify
criu --version
```

### "Docker experimental features not enabled"

```bash
# Check if enabled
docker version --format '{{.Server.Experimental}}'

# Should output: true
# If not, run install script again:
sudo ./scripts/install-criu.sh
```

### "Permission denied"

```bash
# Ensure directories exist
sudo mkdir -p /var/lib/caduceus/criu
sudo mkdir -p /var/lib/caduceus/snapshots

# Fix permissions
sudo chown -R $(whoami):$(whoami) /var/lib/caduceus
```

## Where Are Snapshots Stored?

```bash
# All snapshots
/var/lib/caduceus/snapshots/

# Specific snapshot
/var/lib/caduceus/snapshots/<snapshot_name>/

# CRIU checkpoints
/var/lib/caduceus/criu/
```

## Next Steps

- Read full documentation: `CRIU_USAGE.md`
- Run comprehensive tests: `sudo ./scripts/test-criu.sh`
- Explore snapshot JSON format
- Implement automated backup schedule
- Set up snapshot rotation policy

## Quick Commands Reference

```python
# Create
em.create_snapshot(name, type, description)

# List
em.list_snapshots()

# Delete
em.delete_snapshot(name)

# Types: "topology_only", "docker_commit", "criu_live", "hybrid_full"
```

---

**Need Help?** Check `CRIU_USAGE.md` for detailed documentation
