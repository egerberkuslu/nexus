# Quick Start: Standalone Emulation Container

## TL;DR - 5 Minute Setup

### 1. Install (15-30 minutes, run once)

```bash
cd /path/to/caduceus-flux
sudo bash emulation-container/install.sh
```

### 2. Configure

```bash
sudo cp emulation-container/config.yaml.example /etc/caduceus-flux/emulation.yaml
```

### 3. Deploy

```bash
# Copy systemd service
sudo cp emulation-container/caduceus-emulation.service /etc/systemd/system/

# Copy helper scripts
sudo mkdir -p /opt/caduceus-emulation/scripts
sudo cp emulation-container/scripts/*.sh /opt/caduceus-emulation/scripts/
sudo chmod +x /opt/caduceus-emulation/scripts/*.sh

# Ensure gRPC agent files are in /opt/grpc_agent
sudo mkdir -p /opt/grpc_agent
sudo cp -r emulation-container/grpc_agent/* /opt/grpc_agent/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable caduceus-emulation
sudo systemctl start caduceus-emulation
```

### 4. Verify

```bash
# Check service status
sudo systemctl status caduceus-emulation

# Check logs
sudo journalctl -u caduceus-emulation -n 20

# Test gRPC connectivity
grpcurl -plaintext localhost:50051 list
```

## Integration with Docker Services

No additional setup needed! The Docker microservices are already configured to connect to `host.docker.internal:50051`.

```bash
# Start Docker services normally
docker-compose up -d
```

## Common Operations

### View Real-Time Logs
```bash
sudo journalctl -u caduceus-emulation -f
```

### Restart Service
```bash
sudo systemctl restart caduceus-emulation
```

### Stop Service
```bash
sudo systemctl stop caduceus-emulation
```

### Check Resource Usage
```bash
systemctl status caduceus-emulation | grep Memory
```

## Troubleshooting

### Service won't start
```bash
# Check detailed error
journalctl -u caduceus-emulation -n 50 -p err

# Verify files exist
ls -la /opt/grpc_agent/server.py
```

### gRPC port already in use
```bash
# Find what's using port 50051
sudo lsof -i :50051

# Stop conflicting service
sudo kill -9 <PID>
```

### Docker containers can't reach emulation
```bash
# Test connectivity from Docker container
docker run --rm -it --network caduceus-network ubuntu bash
apt update && apt install -y netcat
nc -zv host.docker.internal 50051
```

## Next Steps

1. Read [DEPLOYMENT.md](DEPLOYMENT.md) for complete configuration options
2. Configure microservices in Docker Compose as needed
3. Deploy topologies via the REST API or web UI

## Key Endpoints

| Component | Address |
|-----------|---------|
| gRPC Server | `localhost:50051` |
| From Docker | `host.docker.internal:50051` |
| OpenFlow 1.0 | `localhost:6633` |
| OpenFlow 1.3+ | `localhost:6653` |

## Configuration Files

- **Service**: `/etc/systemd/system/caduceus-emulation.service`
- **Environment**: `/etc/caduceus-flux/emulation.conf`
- **YAML Config**: `/etc/caduceus-flux/emulation.yaml`
- **Agent Code**: `/opt/grpc_agent/`
- **Data**: `/var/lib/caduceus-flux/`

---

For more information, see [DEPLOYMENT.md](DEPLOYMENT.md)
