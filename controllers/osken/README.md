# OS-Ken SDN Controller

OS-Ken is a component-based SDN framework, the successor to the Ryu controller. It provides a well-defined API for network management and control applications.

## Features

- **OpenFlow 1.0 - 1.5** support
- **REST API** for topology discovery and flow management
- **Event-driven** architecture
- **Simple Learning Switch** application
- **Topology Discovery** with LLDP
- **Integration** with Mininet/Containernet

## Quick Start

### Build the Container

```bash
cd controllers/osken
docker build -t caduceus-flux/osken:latest .
```

### Run the Controller

```bash
# Standalone mode
docker run -d \
  --name osken-controller \
  -p 6653:6653 \
  -p 8080:8080 \
  caduceus-flux/osken:latest

# With custom applications
docker run -d \
  --name osken-controller \
  -p 6653:6653 \
  -p 8080:8080 \
  -v $(pwd)/apps:/opt/osken/apps \
  caduceus-flux/osken:latest
```

### Using with Caduceus-Flux

The controller is automatically integrated in the docker-compose setup:

```bash
# Start all services including OS-Ken
docker-compose up -d

# Check controller logs
docker-compose logs -f osken
```

## REST API Endpoints

### Topology API

```bash
# Get all switches
curl http://localhost:8080/v1.0/topology/switches

# Get all links
curl http://localhost:8080/v1.0/topology/links

# Get topology summary
curl http://localhost:8080/v1.0/topology/summary
```

### Example Response

```json
{
  "switch_count": 3,
  "link_count": 2,
  "switches": ["0x1", "0x2", "0x3"]
}
```

## Custom Applications

Place custom OS-Ken applications in the `apps/` directory:

```python
# apps/my_app.py
from ryu.base import app_manager
from ryu.controller import ofp_event

class MyApp(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(MyApp, self).__init__(*args, **kwargs)
        # Your code here
```

Run with custom app:

```bash
ryu-manager /opt/osken/apps/my_app.py
```

## Integration with Mininet

```python
# In Mininet topology
from mininet.node import RemoteController

net.addController('c0', 
                  controller=RemoteController,
                  ip='osken',  # Container name
                  port=6653)
```

## Configuration

Edit `config/osken.conf` to customize:

- OpenFlow listen port
- REST API port
- Logging level
- Default applications

## Logging

Logs are stored in `/var/log/osken/`:

```bash
# View logs
docker exec osken-controller tail -f /var/log/osken/osken.log

# Or using docker logs
docker logs -f osken-controller
```

## Troubleshooting

### Controller not connecting

1. Check if port 6653 is accessible:
   ```bash
   docker exec osken-controller netstat -tuln | grep 6653
   ```

2. Verify switches are configured to connect:
   ```bash
   # In Mininet
   ovs-vsctl show
   ```

### REST API not responding

1. Check if port 8080 is bound:
   ```bash
   curl http://localhost:8080/v1.0/topology/summary
   ```

2. Check controller logs for errors

## Performance Tuning

For high-performance deployments:

```bash
docker run -d \
  --name osken-controller \
  --cpus=2 \
  --memory=2g \
  -p 6653:6653 \
  -p 8080:8080 \
  caduceus-flux/osken:latest
```

## Security

For production use:

1. **Enable TLS** for OpenFlow connections
2. **Add authentication** to REST API
3. **Use network policies** to restrict access
4. **Regular updates** of OS-Ken and dependencies

## References

- [OS-Ken Documentation](https://osrg.github.io/ryu-book/en/)
- [OpenFlow Specification](https://www.opennetworking.org/sdn-resources/openflow/)
- [Caduceus-Flux Documentation](../../README.md)

