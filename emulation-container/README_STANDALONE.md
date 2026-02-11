# Caduceus-Flux Emulation Container - Standalone Architecture

## Overview

The Caduceus-Flux emulation container has been refactored from a Docker containerized service to a **standalone systemd service** running directly on the host system.

## Why This Change?

### Problems with Docker Containerization

1. **Namespace Isolation**: Docker's network isolation prevents Mininet from directly managing network namespaces
2. **Wireless Simulation**: Mininet-WiFi requires kernel module access that Docker containers can't properly provide
3. **Containernet Limitations**: Container management tools don't work properly inside Docker
4. **Performance**: Double-layered virtualization causes unnecessary overhead
5. **Interface Management**: Difficulty managing virtual wireless interfaces inside containers

### Solution Benefits

✅ Direct kernel access for namespace management
✅ Full Mininet-WiFi wireless simulation support
✅ Better performance without Docker overhead
✅ Easier debugging and log access
✅ Simpler resource management via systemd
✅ Standard Linux service management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Host System                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │    Emulation Container (Standalone Service)         │  │
│  │                                                     │  │
│  │  - Mininet + Mininet-WiFi                         │  │
│  │  - Containernet (optional)                        │  │
│  │  - FRRouting + BIRD                               │  │
│  │  - Open vSwitch                                   │  │
│  │  - gRPC Server (port 50051)                       │  │
│  │                                                     │  │
│  │  Systemd Service: caduceus-emulation              │  │
│  │  Logs: journalctl / /var/log/                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                         ▲                                  │
│                         │ localhost:50051                  │
│                         │ /var/lib/caduceus-flux/         │
└─────────────────────────┼──────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────────┐
│  Docker Network │  │ Host System  │  │  Monitoring      │
│  (Microservices)│  │  Processes   │  │  & Logging       │
│                 │  │              │  │                  │
│ - orchestrator  │  │ via gRPC:    │  │ - Prometheus     │
│ - device-mgr    │  │ 50051        │  │ - InfluxDB       │
│ - metrics-coll  │  │              │  │ - Grafana        │
│ - webshell      │  │              │  │                  │
└─────────────────┘  └──────────────┘  └──────────────────┘
```

## File Structure

```
emulation-container/
├── README_STANDALONE.md          # This file
├── QUICK_START.md                # Quick start guide
├── DEPLOYMENT.md                 # Comprehensive deployment guide
├── install.sh                    # Automated installation script
├── caduceus-emulation.service    # Systemd service file
├── config.yaml.example           # Configuration template
├── .env.example                  # Environment variables template
│
├── grpc_agent/                   # gRPC server implementation
│   ├── server.py                 # Main gRPC server
│   ├── emulation_manager.py      # Emulation logic
│   ├── device_handler.py         # Device management
│   ├── link_handler.py           # Link management
│   ├── protocol_handler.py       # Protocol management
│   ├── state_handler.py          # State snapshots
│   └── monitoring_handler.py     # Metrics collection
│
├── scripts/                      # Helper scripts
│   ├── setup-networking.sh       # Network environment setup
│   └── cleanup.sh                # Cleanup on shutdown
│
├── protocols/                    # Protocol definitions
└── (other supporting files)
```

## Deployment Overview

### Installation Steps

1. **Install Dependencies** (root privileges required)
   ```bash
   sudo bash install.sh
   ```
   - Updates system packages
   - Installs Mininet, Mininet-WiFi, FRRouting, BIRD
   - Installs Python gRPC dependencies
   - Compiles gRPC protocol stubs

2. **Configure Service**
   ```bash
   sudo cp config.yaml.example /etc/caduceus-flux/emulation.yaml
   sudo vi /etc/caduceus-flux/emulation.yaml  # Optional: customize
   ```

3. **Deploy Systemd Service**
   ```bash
   sudo cp caduceus-emulation.service /etc/systemd/system/
   sudo mkdir -p /opt/caduceus-emulation/scripts
   sudo cp scripts/*.sh /opt/caduceus-emulation/scripts/
   sudo chmod +x /opt/caduceus-emulation/scripts/*.sh
   sudo cp -r grpc_agent /opt/
   ```

4. **Enable and Start**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable caduceus-emulation
   sudo systemctl start caduceus-emulation
   ```

### Verification

```bash
# Check service status
sudo systemctl status caduceus-emulation

# View logs
sudo journalctl -u caduceus-emulation -f

# Test gRPC
grpcurl -plaintext localhost:50051 list
```

## Configuration

### System Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| Service File | Systemd service definition | `/etc/systemd/system/caduceus-emulation.service` |
| Config YAML | Application configuration | `/etc/caduceus-flux/emulation.yaml` |
| Environment | Systemd environment variables | `/etc/caduceus-flux/emulation.conf` |
| gRPC Agent | Python server implementation | `/opt/grpc_agent/` |

### Key Configuration Options

**Server Binding:**
```yaml
server:
  host: "0.0.0.0"    # Listen on all interfaces
  port: 50051        # gRPC port
```

**Emulation Features:**
```yaml
emulation:
  wireless_enabled: true    # Enable Mininet-WiFi
  container_enabled: false  # Containernet (keep false)
```

**Networking:**
```yaml
networking:
  ip_forward: true          # Enable routing
  ovs:
    enabled: true           # Open vSwitch
```

## Integration with Docker Microservices

The Docker-based microservices are automatically configured to connect to the standalone emulation container:

### Environment Variables in docker-compose.yml

```yaml
environment:
  EMULATION_GRPC_HOST: host.docker.internal  # Docker host gateway
  EMULATION_GRPC_PORT: 50051                 # gRPC server port
```

### Services That Connect to Emulation

- **orchestrator-service**: Manages emulation lifecycle
- **device-manager-service**: Manages virtual devices
- **webshell-service**: Web shell access to devices
- **metrics-collector-service**: Collects emulation metrics

### Docker Network Access

From Docker containers, the emulation container is accessible via:
```
host.docker.internal:50051
```

On Linux (non-Docker Desktop):
```
172.20.0.1:50051  # Docker gateway IP (check docker-compose network)
```

## Systemd Service Management

### Common Operations

```bash
# Start service
sudo systemctl start caduceus-emulation

# Stop service
sudo systemctl stop caduceus-emulation

# Restart service
sudo systemctl restart caduceus-emulation

# Check status
sudo systemctl status caduceus-emulation

# View logs
sudo journalctl -u caduceus-emulation -f

# View last 100 lines
sudo journalctl -u caduceus-emulation -n 100

# Filter by severity
sudo journalctl -u caduceus-emulation -p err

# Search in logs
sudo journalctl -u caduceus-emulation | grep "error message"
```

### Service Lifecycle

The systemd service file defines:

- **ExecStartPre**: Setup networking and OVS
- **ExecStart**: Start Python gRPC server
- **ExecStop**: Cleanup emulation resources
- **Restart**: Automatic restart on failure
- **Resource Limits**: Memory and CPU restrictions

## Monitoring and Observability

### System Logs

Access via systemd journal:
```bash
sudo journalctl -u caduceus-emulation -f
```

Log files:
- Application logs: `/var/lib/caduceus-flux/logs/emulation.log`
- OVS logs: `/var/log/openvswitch/`
- FRR logs: `/var/log/frr/`

### Metrics

The emulation container provides metrics via gRPC:

```protobuf
GetMetrics(): Returns current metrics
StreamMetrics(): Streams metrics in real-time
```

Metrics are collected by `metrics-collector-service` and stored in:
- InfluxDB (time-series)
- Kafka topics (event stream)

### Health Checks

Monitor via systemd:
```bash
systemctl is-active caduceus-emulation
systemctl is-enabled caduceus-emulation
```

Test gRPC connectivity:
```bash
grpcurl -plaintext localhost:50051 list
```

## Performance Tuning

### Systemd Resource Limits

Configure in service file:
```ini
MemoryMax=16G        # Maximum memory usage
CPUQuota=80%         # Maximum CPU usage
```

### Kernel Parameters

For better network emulation:
```bash
# Increase connection tracking
sudo sysctl -w net.netfilter.nf_conntrack_max=262144

# Increase socket buffers
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728
```

### OVS Performance

```bash
# Check OVS status
sudo ovs-vsctl show

# Optimize for performance
sudo ovs-vsctl set Open_vSwitch . other_config:pmd-cpu-mask=0x1
```

## Data Persistence

### Snapshot Storage

Emulation snapshots stored at:
```
/var/lib/caduceus-flux/snapshots/
```

Backup snapshots:
```bash
sudo tar -czf backup.tar.gz /var/lib/caduceus-flux/snapshots/
```

### Configuration Backup

Backup configuration:
```bash
sudo tar -czf config-backup.tar.gz /etc/caduceus-flux/
```

## Troubleshooting

### Service won't start

1. Check detailed logs:
```bash
journalctl -u caduceus-emulation -n 50 -p err
```

2. Verify file permissions:
```bash
ls -la /opt/grpc_agent/
```

3. Check Python availability:
```bash
which python3
python3 --version
```

### Port already in use

```bash
# Find process using port 50051
sudo lsof -i :50051

# Stop conflicting service
sudo systemctl stop <service>
```

### Docker container can't reach emulation

```bash
# Test from Docker container
docker run --rm -it --network caduceus-network ubuntu bash
apt update && apt install -y netcat
nc -zv host.docker.internal 50051
```

### Memory/Resource issues

Check current limits:
```bash
systemctl show -p MemoryMax caduceus-emulation
```

Increase limits:
```bash
sudo systemctl edit caduceus-emulation
# Add: MemoryMax=16G
sudo systemctl daemon-reload
sudo systemctl restart caduceus-emulation
```

## Advanced Topics

### Running Multiple Instances

Create additional service instances:
```bash
sudo cp /etc/systemd/system/caduceus-emulation.service \
        /etc/systemd/system/caduceus-emulation-2.service

# Edit and change port to 50052, update service name
sudo vi /etc/systemd/system/caduceus-emulation-2.service

# Enable and start
sudo systemctl enable caduceus-emulation-2
sudo systemctl start caduceus-emulation-2
```

### Container Host Integration

For running Docker containers as part of Mininet topology:

1. Keep emulation standalone (no Docker)
2. Start application containers separately with Docker
3. Connect containers to Mininet networks via OVS bridges

### Custom Protocol Implementation

Add custom protocols in `grpc_agent/protocol_handler.py` and rebuild.

## Related Documentation

- [QUICK_START.md](QUICK_START.md) - Fast setup guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - Comprehensive deployment
- [Mininet Wiki](http://mininet.org/)
- [gRPC Documentation](https://grpc.io/)
- [systemd Documentation](https://www.freedesktop.org/wiki/Software/systemd/)

## Support

For issues, check:
1. Service logs: `journalctl -u caduceus-emulation -f`
2. Deployment guide: See DEPLOYMENT.md
3. System resources: `systemctl status caduceus-emulation`
4. Network connectivity: `grpcurl -plaintext localhost:50051 list`
