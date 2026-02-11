# Caduceus-Flux Emulation Container - Standalone Deployment Guide

## Overview

The Caduceus-Flux emulation container is now deployed as a **standalone systemd service** on the host system rather than as a Docker container. This approach is necessary due to incompatibilities between Docker and Mininet-WiFi/Containernet for network emulation.

## Why Standalone?

**Docker Limitations:**
- Mininet-WiFi requires direct access to kernel network namespaces
- Containernet needs direct control over container networking
- Docker's isolation prevents proper namespace manipulation required for network emulation
- MAC address spoofing and wireless interface simulation don't work in Docker

**Solution:**
- Deploy gRPC server directly on host
- Full access to kernel features
- Direct Mininet-WiFi and wireless simulation support
- Better performance for network emulation

## Installation

### Prerequisites

- Linux system (Ubuntu 20.04, 22.04, or similar)
- Root or sudo access
- 4GB+ RAM
- 10GB+ disk space

### Step 1: Install Dependencies

Run the automated installation script:

```bash
cd /path/to/caduceus-flux
sudo bash emulation-container/install.sh
```

This script will:
- Update system packages
- Install Mininet and dependencies
- Install Mininet-WiFi
- Install FRRouting and BIRD routing daemons
- Install gRPC Python libraries
- Create necessary system directories
- Compile gRPC protocol stubs

**Installation Time:** 15-30 minutes depending on system speed

### Step 2: Configure the Service

1. Copy the configuration template:
```bash
sudo cp emulation-container/config.yaml.example /etc/caduceus-flux/emulation.yaml
```

2. Edit the configuration (optional - defaults are suitable for most setups):
```bash
sudo vi /etc/caduceus-flux/emulation.yaml
```

3. Create environment file for systemd (optional):
```bash
sudo tee /etc/caduceus-flux/emulation.conf > /dev/null <<'EOF'
# Caduceus-Flux Emulation Container Environment Configuration
PYTHONUNBUFFERED=1
EOF
```

### Step 3: Install Systemd Service

1. Copy the systemd service file:
```bash
sudo cp emulation-container/caduceus-emulation.service /etc/systemd/system/
```

2. Copy the helper scripts:
```bash
sudo mkdir -p /opt/caduceus-emulation/scripts
sudo cp emulation-container/scripts/*.sh /opt/caduceus-emulation/scripts/
sudo chmod +x /opt/caduceus-emulation/scripts/*.sh
```

3. Create symlink to gRPC agent (if not installed in /opt/grpc_agent):
```bash
sudo mkdir -p /opt/grpc_agent
sudo cp -r emulation-container/grpc_agent/* /opt/grpc_agent/
```

4. Reload systemd configuration:
```bash
sudo systemctl daemon-reload
```

### Step 4: Enable and Start the Service

```bash
# Enable service to start on boot
sudo systemctl enable caduceus-emulation

# Start the service
sudo systemctl start caduceus-emulation

# Check status
sudo systemctl status caduceus-emulation

# View logs
sudo journalctl -u caduceus-emulation -f
```

## Configuration

### Environment File: `/etc/caduceus-flux/emulation.conf`

```bash
# Python
PYTHONUNBUFFERED=1

# Optional: Emulation server binding address (default: 0.0.0.0)
EMULATION_SERVER_HOST=0.0.0.0

# Optional: Emulation server port (default: 50051)
EMULATION_SERVER_PORT=50051

# Optional: Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

### Configuration File: `/etc/caduceus-flux/emulation.yaml`

Key settings:

```yaml
server:
  host: "0.0.0.0"          # gRPC server address
  port: 50051              # gRPC server port

emulation:
  wireless_enabled: true   # Enable Mininet-WiFi support
  container_enabled: false # Containernet (keep disabled with Docker)
  snapshot_dir: "/var/lib/caduceus-flux/snapshots"
  config_dir: "/var/lib/caduceus-flux/configs"
  logs_dir: "/var/lib/caduceus-flux/logs"

networking:
  ip_forward: true         # Enable IP forwarding
  ipv6_enabled: true       # Enable IPv6 support
  ovs:
    enabled: true          # Open vSwitch support

routing:
  frr:
    enabled: true          # FRRouting daemon
    bgp: true              # BGP routing
    ospf: true             # OSPF routing
```

## Microservices Integration

The Docker-based microservices connect to the standalone emulation container using `host.docker.internal` (Linux/Docker Desktop) or `localhost` when run on the host.

### Docker Compose Configuration

Update `.env` or environment variables:

```bash
# Connect to standalone emulation container
EMULATION_GRPC_HOST=host.docker.internal
EMULATION_GRPC_PORT=50051
```

### Updated Services

The following services have been updated to support standalone emulation:
- `orchestrator-service`
- `device-manager-service`
- `webshell-service`
- `metrics-collector-service`

## Network Connectivity

### gRPC Communication

The emulation container exposes:
- **Port 50051**: gRPC server
- **Port 6633**: OpenFlow 1.0
- **Port 6653**: OpenFlow 1.3+

From Docker containers, access via:
```
host.docker.internal:50051
```

From host system, access via:
```
localhost:50051
127.0.0.1:50051
```

### Host Network Access

For services running on the host system, add to `/etc/hosts` or use IP directly:

```bash
# Direct localhost access
grpcurl -plaintext localhost:50051 list
```

## Management

### Check Service Status

```bash
# Service status
sudo systemctl status caduceus-emulation

# Check if gRPC server is responding
grpcurl -plaintext localhost:50051 list

# View recent logs
sudo journalctl -u caduceus-emulation -n 50

# Follow logs in real-time
sudo journalctl -u caduceus-emulation -f
```

### Start/Stop/Restart

```bash
# Start the service
sudo systemctl start caduceus-emulation

# Stop the service
sudo systemctl stop caduceus-emulation

# Restart the service
sudo systemctl restart caduceus-emulation

# Reload configuration (without restart)
sudo systemctl reload caduceus-emulation
```

### View System Resources

```bash
# Check CPU and memory usage
systemctl status caduceus-emulation | grep Memory

# Monitor resource usage
watch -n 1 'systemctl status caduceus-emulation | grep -E "Memory|CPU"'
```

## Troubleshooting

### Service Won't Start

1. Check logs:
```bash
sudo journalctl -u caduceus-emulation -n 100
```

2. Verify permissions:
```bash
ls -la /opt/grpc_agent/
ls -la /var/lib/caduceus-flux/
```

3. Check for port conflicts:
```bash
sudo lsof -i :50051
```

### gRPC Connection Issues

1. Verify service is running:
```bash
sudo systemctl status caduceus-emulation
```

2. Test connectivity:
```bash
# From Docker container
docker exec <container> curl -v telnet://host.docker.internal:50051

# From host
nc -zv localhost 50051
```

3. Check firewall:
```bash
sudo ufw status
sudo ufw allow 50051/tcp
```

### Mininet Compatibility Issues

1. Check kernel modules:
```bash
lsmod | grep mac80211
lsmod | grep openvswitch
```

2. Verify wireless simulation:
```bash
iwconfig  # Should show virtual wireless devices if running
```

3. Check network namespaces:
```bash
ip netns list
```

### Out of Memory / Resource Exhaustion

If experiencing resource limits:

1. Check current limits:
```bash
systemctl show -p MemoryMax caduceus-emulation
```

2. Increase limits in systemd service:
```bash
# Edit service file
sudo systemctl edit caduceus-emulation

# Add or modify:
MemoryMax=16G
CPUQuota=100%
```

3. Reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart caduceus-emulation
```

## Performance Tuning

### Kernel Parameters

For better network emulation performance, consider:

```bash
# Increase connection tracking table size
sudo sysctl -w net.netfilter.nf_conntrack_max=262144

# Increase socket buffers
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728

# Persist changes in /etc/sysctl.conf
```

### OVS Tuning

For better OpenFlow switch performance:

```bash
# Check OVS status
sudo ovs-vsctl show

# Set pmd thread type for performance
sudo ovs-vsctl set Open_vSwitch . other_config:pmd-cpu-mask=0x1
```

## Monitoring Integration

The emulation container provides metrics via:

1. **Direct gRPC calls**: `GetMetrics()`, `StreamMetrics()`
2. **Integration with Prometheus**: Metrics exported via metrics-collector-service
3. **InfluxDB**: Historical metrics stored via Kafka pipeline

Configure in metrics-collector-service environment:
```yaml
EMULATION_GRPC_HOST: host.docker.internal
EMULATION_GRPC_PORT: 50051
```

## Backup and Recovery

### Snapshot Management

Snapshots are stored in `/var/lib/caduceus-flux/snapshots/`:

```bash
# List snapshots
ls -la /var/lib/caduceus-flux/snapshots/

# Backup snapshots
sudo tar -czf caduceus-snapshots-backup.tar.gz /var/lib/caduceus-flux/snapshots/

# Restore snapshots
sudo tar -xzf caduceus-snapshots-backup.tar.gz -C /
```

## Uninstallation

To remove the standalone emulation container:

```bash
# Stop the service
sudo systemctl stop caduceus-emulation

# Disable from startup
sudo systemctl disable caduceus-emulation

# Remove systemd service
sudo rm /etc/systemd/system/caduceus-emulation.service
sudo systemctl daemon-reload

# Remove installation directories
sudo rm -rf /opt/grpc_agent
sudo rm -rf /opt/caduceus-emulation

# Keep data directories (optional to remove):
sudo rm -rf /var/lib/caduceus-flux
sudo rm -rf /etc/caduceus-flux
```

## Advanced: Custom Deployment

### Running Outside Systemd

For development or debugging:

```bash
# Manual startup with environment
export PYTHONUNBUFFERED=1
cd /opt/grpc_agent
python3 server.py
```

### Docker Integration (Advanced)

If you need Containernet containers alongside the emulation:

1. Keep emulation container standalone
2. Run application containers via Docker independently
3. Connect application containers to Mininet-managed networks via OVS bridges

### Multi-Instance Deployment

To run multiple emulation instances:

1. Create separate systemd service files for each instance
2. Configure different gRPC ports (50051, 50052, etc.)
3. Update microservices to connect to appropriate instance

```bash
# Create second instance
sudo cp /etc/systemd/system/caduceus-emulation.service \
        /etc/systemd/system/caduceus-emulation-2.service

# Edit the second instance configuration
sudo vi /etc/systemd/system/caduceus-emulation-2.service
# Change port to 50052 and rename service identifiers
```

## Support and Debugging

For detailed debugging:

1. Enable debug logging:
```bash
# Edit config
sudo vi /etc/caduceus-flux/emulation.yaml

# Set logging level
logging:
  level: "DEBUG"
```

2. Increase verbosity in systemd:
```bash
sudo systemctl edit caduceus-emulation
# Add: Environment="PYTHONDONTWRITEBYTECODE=1"
```

3. Capture full logs:
```bash
sudo journalctl -u caduceus-emulation --since "1 hour ago" > emulation-debug.log
```

## References

- [Mininet Documentation](http://mininet.org/)
- [Mininet-WiFi](https://github.com/intrig-unicamp/mininet-wifi)
- [FRRouting Documentation](https://docs.frrouting.org/)
- [gRPC Documentation](https://grpc.io/docs/)
- [systemd Service Documentation](https://www.freedesktop.org/wiki/Software/systemd/)
