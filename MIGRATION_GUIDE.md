# Migration Guide: Docker to Standalone Emulation Container

## Overview

This guide helps you migrate from the old Docker-containerized emulation setup to the new **standalone systemd service** architecture.

## Why Migrate?

### Issues with Docker Approach

- ❌ Mininet-WiFi doesn't work properly in Docker containers
- ❌ Containernet has Docker isolation conflicts
- ❌ Network namespace management is limited
- ❌ Wireless interface simulation fails
- ❌ Performance overhead from double virtualization

### Benefits of Standalone

- ✅ Full Mininet-WiFi wireless support
- ✅ Better network emulation compatibility
- ✅ Improved performance
- ✅ Simpler deployment and debugging
- ✅ Standard Linux service management
- ✅ Direct kernel access for namespaces

## Pre-Migration Checklist

Before starting the migration:

- [ ] Backup existing data and snapshots
- [ ] Stop the Docker-based emulation container
- [ ] Document any custom configurations
- [ ] Test on a non-production system first
- [ ] Ensure you have sudo/root access
- [ ] Have at least 10GB free disk space
- [ ] Linux kernel 4.15+

## Step 1: Backup Current Setup

### Backup Snapshots

```bash
# Create backup directory
mkdir -p ~/caduceus-backup
cd ~/caduceus-backup

# Backup emulation snapshots
docker cp caduceus-emulation:/var/lib/caduceus-flux/snapshots ./snapshots_backup

# Or if using volume mounts
cp -r /path/to/emulation_snapshots ./snapshots_backup
```

### Backup Configurations

```bash
# Backup any custom Dockerfiles or configs
cp emulation-container/Dockerfile Dockerfile.backup

# Document environment variables
docker inspect caduceus-emulation > container_config.json
```

## Step 2: Stop Old Docker Service

### Stop and Remove Container

```bash
# Stop the emulation container
docker-compose stop emulation-container

# Optionally remove the container
docker-compose rm emulation-container

# Verify it's stopped
docker ps | grep emulation
```

### Update docker-compose.yml

The `docker-compose.yml` has already been updated in this release:

```yaml
# OLD (REMOVED):
emulation-container:
  build: ./emulation-container/Dockerfile
  container_name: caduceus-emulation
  privileged: true
  network_mode: host
  ...

# NEW (COMMENTED):
# The emulation-container is now deployed as a standalone service
# See emulation-container/QUICK_START.md for setup instructions
```

## Step 3: Install Standalone Emulation

### Run Installation Script

```bash
cd /path/to/caduceus-flux

# Run with sudo (required for system-level changes)
sudo bash emulation-container/install.sh
```

This will:
- Install Mininet and all dependencies
- Install Mininet-WiFi
- Install FRRouting and BIRD
- Install Python gRPC requirements
- Create system directories
- Compile gRPC stubs

**Estimated time: 15-30 minutes**

### Check Installation

```bash
# Verify Mininet is installed
which mn
mn --version

# Verify Python packages
python3 -c "import grpc; print('gRPC installed')"

# Check directories
ls -la /var/lib/caduceus-flux/
ls -la /opt/grpc_agent/
```

## Step 4: Configure Service

### Copy Configuration Files

```bash
# Create config directory
sudo mkdir -p /etc/caduceus-flux

# Copy configuration template
sudo cp emulation-container/config.yaml.example /etc/caduceus-flux/emulation.yaml

# Copy environment file
sudo tee /etc/caduceus-flux/emulation.conf > /dev/null <<'EOF'
PYTHONUNBUFFERED=1
EOF

# Set permissions
sudo chown -R root:root /etc/caduceus-flux
sudo chmod 755 /etc/caduceus-flux
sudo chmod 644 /etc/caduceus-flux/*.yaml
sudo chmod 644 /etc/caduceus-flux/*.conf
```

### Optional: Customize Configuration

Edit if you have specific requirements:

```bash
sudo vi /etc/caduceus-flux/emulation.yaml
```

Key sections to check:
- `server.port`: gRPC port (default: 50051)
- `emulation.snapshot_dir`: Snapshot location
- `routing.frr.enabled`: FRRouting support
- `logging.level`: Log verbosity

### Restore Old Snapshots (if needed)

```bash
# If you backed up snapshots earlier
sudo cp -r ~/caduceus-backup/snapshots_backup/* /var/lib/caduceus-flux/snapshots/

# Set permissions
sudo chown -R $USER:$USER /var/lib/caduceus-flux/snapshots
```

## Step 5: Deploy Systemd Service

### Install Service Files

```bash
# Create helper script directory
sudo mkdir -p /opt/caduceus-emulation/scripts

# Copy helper scripts
sudo cp emulation-container/scripts/*.sh /opt/caduceus-emulation/scripts/
sudo chmod +x /opt/caduceus-emulation/scripts/*.sh

# Copy gRPC agent (if not already in /opt/grpc_agent)
if [ ! -d /opt/grpc_agent ]; then
    sudo mkdir -p /opt/grpc_agent
    sudo cp -r emulation-container/grpc_agent/* /opt/grpc_agent/
fi

# Set permissions
sudo chown -R root:root /opt/grpc_agent
sudo chown -R root:root /opt/caduceus-emulation
```

### Install Systemd Service

```bash
# Copy service file
sudo cp emulation-container/caduceus-emulation.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable caduceus-emulation

# Verify it's enabled
sudo systemctl is-enabled caduceus-emulation
```

## Step 6: Start the Service

### Start Emulation Container

```bash
# Start the service
sudo systemctl start caduceus-emulation

# Check status
sudo systemctl status caduceus-emulation

# View logs (real-time)
sudo journalctl -u caduceus-emulation -f
```

### Verify It's Working

```bash
# Check if gRPC server is listening
sudo lsof -i :50051

# Test gRPC connectivity
grpcurl -plaintext localhost:50051 list

# Check service health
systemctl is-active caduceus-emulation
```

## Step 7: Update Docker Services

### Update Environment Variables

The Docker microservices need to be updated to connect to the standalone service.

**Option A: Using .env file**

```bash
# Update your .env file
echo "EMULATION_GRPC_HOST=host.docker.internal" >> .env
echo "EMULATION_GRPC_PORT=50051" >> .env
```

**Option B: Update docker-compose.yml**

The `docker-compose.yml` has already been updated with the correct hosts. If you made custom changes, update these services:

- `orchestrator-service`
- `device-manager-service`
- `webshell-service`
- `metrics-collector-service`

Set their environment to:
```yaml
environment:
  EMULATION_GRPC_HOST: host.docker.internal
  EMULATION_GRPC_PORT: 50051
```

### Start Docker Services

```bash
# Start Docker services (emulation-container section is now commented out)
docker-compose up -d

# Verify they're connected
docker logs caduceus-orchestrator-service | grep "emulation\|gRPC\|50051"
```

## Step 8: Verification and Testing

### Check All Components

```bash
# Standalone service
sudo systemctl status caduceus-emulation

# Docker services
docker-compose ps

# gRPC connectivity
grpcurl -plaintext localhost:50051 list

# Network connectivity
docker run --rm -it --network caduceus-network ubuntu bash
apt update && apt install -y netcat
nc -zv host.docker.internal 50051
```

### Test Emulation

```bash
# Via gRPC (if you have client code)
python3 << 'EOF'
import grpc
from backend.proto import emulation_pb2_grpc, emulation_pb2

channel = grpc.insecure_channel('localhost:50051')
stub = emulation_pb2_grpc.EmulationServiceStub(channel)

# Test basic connectivity
try:
    response = stub.GetEmulationStatus(emulation_pb2.GetEmulationStatusRequest(
        emulation_id="test"
    ))
    print("✓ gRPC connection successful")
except:
    print("✗ gRPC connection failed")
EOF
```

## Step 9: Cleanup Old Setup

### Remove Old Docker Image (Optional)

```bash
# Only after confirming everything works!

# Remove stopped containers
docker-compose rm emulation-container

# Remove old image
docker rmi caduceus-flux_emulation-container

# Verify
docker image ls | grep emulation
```

### Remove Installation Artifacts

```bash
# Keep the Dockerfile for reference, but it's no longer used
mv emulation-container/Dockerfile emulation-container/Dockerfile.unused
```

## Troubleshooting Migration

### Service won't start

```bash
# Check detailed logs
journalctl -u caduceus-emulation -n 50 -p err

# Verify dependencies
which python3
python3 -c "import grpc"

# Check permissions
ls -la /opt/grpc_agent/server.py
```

### Docker containers can't reach emulation

```bash
# Test connectivity from Docker container
docker run --rm -it --network caduceus-network ubuntu bash
apt update && apt install -y netcat iputils-ping
nc -zv host.docker.internal 50051
ping host.docker.internal

# On Linux, may need to use gateway IP instead
docker inspect caduceus-network | grep Gateway
nc -zv <gateway-ip> 50051
```

### Snapshots not accessible

```bash
# Check permissions
ls -la /var/lib/caduceus-flux/snapshots/

# Verify ownership
sudo chown -R $USER:$USER /var/lib/caduceus-flux/snapshots
sudo chmod -R 755 /var/lib/caduceus-flux/snapshots
```

### gRPC port conflict

```bash
# Find what's using port 50051
sudo lsof -i :50051

# Stop conflicting service
sudo kill -9 <PID>

# Or use different port in config
sudo vi /etc/caduceus-flux/emulation.yaml
# Change: server.port: 50052
```

## Configuration Migration

### Old Docker Environment Variables

Map old Docker environment variables to new configuration:

| Old (Docker Env) | New (YAML Config) | Notes |
|------------------|-------------------|-------|
| `PYTHONUNBUFFERED=1` | Automatic in service | Set in service file |
| Custom OVS config | `networking.ovs.*` | Update in emulation.yaml |
| Custom FRR config | `routing.frr.*` | Update in emulation.yaml |
| Port mapping | `server.port` | Update in emulation.yaml |

### Custom Scripts

If you had custom startup scripts in the old Docker container:

1. Review the entrypoint.sh logic
2. Merge custom logic into `scripts/setup-networking.sh`
3. Restart service: `sudo systemctl restart caduceus-emulation`

## Performance Comparison

### Expected Improvements

| Metric | Docker | Standalone | Improvement |
|--------|--------|------------|-------------|
| Startup Time | 10-30s | 3-5s | 80% faster |
| Memory Usage | 2-3GB | 1-2GB | 50% less |
| CPU Overhead | 15-20% | 5-10% | 67% less |
| Wireless Support | Limited | Full | ✅ Working |
| Namespace Control | Limited | Full | ✅ Direct |

## Rollback Plan (if needed)

If you need to revert to Docker approach:

```bash
# Stop standalone service
sudo systemctl stop caduceus-emulation
sudo systemctl disable caduceus-emulation

# Restore Docker setup
git checkout docker-compose.yml emulation-container/Dockerfile
docker-compose up -d emulation-container

# Remove standalone files (optional)
sudo rm /etc/systemd/system/caduceus-emulation.service
sudo systemctl daemon-reload
```

## Verification Checklist

After migration, verify:

- [ ] Standalone service is running: `systemctl status caduceus-emulation`
- [ ] gRPC server is listening: `lsof -i :50051`
- [ ] Docker services are running: `docker-compose ps`
- [ ] Docker services can connect: Check logs for gRPC connection
- [ ] Snapshots are accessible: `ls -la /var/lib/caduceus-flux/snapshots/`
- [ ] Web UI works: Open browser to http://localhost:3000
- [ ] REST API works: `curl http://localhost:8012/health`

## Support and Next Steps

After successful migration:

1. Review [emulation-container/DEPLOYMENT.md](emulation-container/DEPLOYMENT.md) for advanced configuration
2. Set up monitoring and alerts for the standalone service
3. Configure backups for `/var/lib/caduceus-flux/`
4. Document any custom configurations in your team wiki
5. Update deployment procedures in your documentation

## FAQ

**Q: Can I run both Docker and Standalone versions simultaneously?**
A: Not recommended. The Docker version has been removed from docker-compose. If needed, use different ports.

**Q: What if I need Containernet?**
A: Containernet can be used with the standalone emulation by running Docker containers separately and connecting them to Mininet bridges.

**Q: How do I backup the standalone setup?**
A: Backup `/var/lib/caduceus-flux/`, `/etc/caduceus-flux/`, and `/opt/grpc_agent/` directories.

**Q: Can I move the installation to a different directory?**
A: Yes, but update the systemd service file paths accordingly. Not recommended for standard setups.

**Q: How do I monitor the standalone service?**
A: Use `journalctl -u caduceus-emulation` for logs, `systemctl status caduceus-emulation` for status, and integrate with your monitoring system via systemd metrics.

---

For detailed information, see:
- [emulation-container/QUICK_START.md](emulation-container/QUICK_START.md)
- [emulation-container/DEPLOYMENT.md](emulation-container/DEPLOYMENT.md)
- [emulation-container/README_STANDALONE.md](emulation-container/README_STANDALONE.md)
