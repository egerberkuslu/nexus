# CRIU Snapshot Support Setup Guide

This guide will help you enable CRIU (Checkpoint/Restore In Userspace) support for live container snapshots.

## Problem Summary

CRIU-based snapshot types (CRIU Live and Hybrid Full) were showing as "Not available" because:
1. CRIU was not installed in the emulation container
2. Docker experimental features were not enabled
3. The snapshot service had CRIU support hardcoded to disabled

## Solution Applied

The following fixes have been implemented:

### 1. Updated Emulation Container Dockerfile
- Added CRIU and its dependencies to `emulation-container/Dockerfile.simple`
- CRIU will be installed in the next container rebuild

### 2. Fixed Snapshot Service
- Updated `/backend/services/snapshot/main.py` to properly detect CRIU availability
- Implemented `_capture_criu_live()` and `_capture_hybrid_full()` functions
- Removed hardcoded CRIU disabled status

### 3. Created Setup Script
- Created `enable-docker-experimental.sh` to configure Docker daemon

## Installation Steps

### Step 1: Enable Docker Experimental Features

Docker's checkpoint/restore functionality requires experimental features to be enabled.

**Run the setup script:**

```bash
sudo ./enable-docker-experimental.sh
```

This script will:
- Create/update `/etc/docker/daemon.json` with `"experimental": true`
- Restart Docker daemon
- Verify experimental features are enabled

**Manual alternative:**

```bash
# Create or edit /etc/docker/daemon.json
sudo nano /etc/docker/daemon.json

# Add or ensure this content:
{
  "experimental": true
}

# Restart Docker
sudo systemctl restart docker

# Verify
docker version --format '{{.Server.Experimental}}'
# Should output: true
```

### Step 2: Install CRIU on Host (Optional but Recommended)

While CRIU is being added to the container, installing it on the host can help with debugging:

```bash
sudo apt-get update
sudo apt-get install -y criu
criu --version
```

### Step 3: Rebuild Emulation Container

The emulation container needs to be rebuilt with CRIU support:

```bash
# Stop running containers
docker-compose down

# Rebuild emulation container
docker-compose build emulation-container

# Or rebuild all services
docker-compose build

# Start services
docker-compose up -d
```

### Step 4: Restart Snapshot Service

Restart the snapshot service to enable CRIU detection:

```bash
docker-compose restart snapshot-service
```

Or rebuild if needed:

```bash
docker-compose build snapshot-service
docker-compose up -d snapshot-service
```

## Verification

### 1. Check Docker Experimental Mode

```bash
docker version --format '{{.Server.Experimental}}'
```

Expected output: `true`

### 2. Check CRIU in Emulation Container

```bash
# Find the emulation container
CONTAINER_NAME=$(docker ps --filter "name=emu" --format "{{.Names}}" | head -1)

# Check CRIU installation
docker exec $CONTAINER_NAME criu --version
```

Expected output: CRIU version information

### 3. Check Snapshot Types API

```bash
curl http://localhost:8006/api/snapshots/types | jq
```

Look for:
- `"criu_available": true`
- `"docker_experimental": true`

### 4. Test CRIU Snapshot Creation

Using the frontend or API, try creating:
- **CRIU Live** snapshot
- **Hybrid Full** snapshot

Both should now be available and functional.

## Snapshot Type Descriptions

After setup, you'll have access to all snapshot types:

| Type | Description | Size | Duration | Requirements |
|------|-------------|------|----------|--------------|
| **Topology Only** | Quick topology structure export | ~1-10 KB | ~1 sec | None |
| **Docker Commit** | Filesystem snapshot using docker commit | ~100-500 MB | ~30 sec | Docker |
| **CRIU Live** | Live process checkpoint with CRIU | ~100-300 MB | ~1 min | CRIU + Docker Experimental |
| **Hybrid Full** | Combined Docker commit + CRIU checkpoint | ~200-700 MB | ~2 min | CRIU + Docker Experimental |

## Troubleshooting

### CRIU Still Shows as Unavailable

1. **Check Docker experimental mode:**
   ```bash
   docker version --format '{{.Server.Experimental}}'
   ```
   If `false`, Docker daemon wasn't configured properly.

2. **Check Docker daemon logs:**
   ```bash
   sudo journalctl -u docker -n 50
   ```

3. **Verify CRIU in container:**
   ```bash
   docker exec <emulation-container> which criu
   docker exec <emulation-container> criu --version
   ```

4. **Restart all services:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Docker Checkpoint Command Fails

If you see errors like "unknown flag: --checkpoint":
- Docker experimental features are not enabled
- Run the setup script again
- Verify `/etc/docker/daemon.json` has `"experimental": true`

### Permission Errors

CRIU checkpoint requires privileged access:
- Ensure emulation container runs with appropriate privileges
- Check docker-compose.yml for `privileged: true` or required capabilities

### Checkpoint Size Too Large

CRIU checkpoints can be large for containers with significant memory usage:
- Use **CRIU Live** for process state only (~100-300 MB)
- Use **Hybrid Full** for complete snapshot (~200-700 MB)
- Use **Docker Commit** for filesystem only (~100-500 MB)
- Use **Topology Only** for minimal metadata (~1-10 KB)

## Architecture Details

### CRIU Integration Flow

1. **Snapshot Service** checks for CRIU availability on startup
2. **Frontend** displays available snapshot types based on capabilities
3. **User** selects CRIU Live or Hybrid Full snapshot
4. **Snapshot Service** calls `docker checkpoint create` for each container
5. **Docker** uses CRIU to checkpoint the container processes
6. **Metadata** is stored in PostgreSQL, checkpoint data in filesystem
7. **MongoDB** stores detailed state information

### File Locations

- **CRIU Handler**: `emulation-container/grpc_agent/criu_handler.py`
- **Snapshot Service**: `backend/services/snapshot/main.py`
- **Docker Config**: `/etc/docker/daemon.json`
- **Checkpoint Storage**: `/var/lib/docker/containers/<id>/checkpoints/`
- **Snapshot Storage**: `/var/lib/caduceus-flux/snapshots/`

## References

- CRIU Documentation: https://criu.org/
- Docker Checkpoint: https://docs.docker.com/engine/reference/commandline/checkpoint/
- Experimental Features: https://docs.docker.com/engine/reference/commandline/dockerd/#daemon-configuration-file

## Support

If you encounter issues:
1. Check logs: `docker-compose logs snapshot-service`
2. Verify configuration following this guide
3. Ensure all services are rebuilt after changes
4. Check Docker daemon logs if checkpoint commands fail
