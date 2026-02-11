# Ryu SDN Controller

Ryu is a component-based software defined networking framework. It provides software components with well-defined API for developers to create new network management and control applications.

## Features

- **OpenFlow** 1.0, 1.2, 1.3, 1.4, 1.5 support
- **REST API** for flow management  
- **Topology discovery**
- **Event-driven** programming model
- **Python-based** applications

## Quick Start

### Build

```bash
cd controllers/ryu
docker build -t caduceus-flux/ryu:latest .
```

### Run

```bash
docker run -d \
  --name ryu-controller \
  -p 6653:6653 \
  -p 8080:8080 \
  caduceus-flux/ryu:latest
```

## REST API

Ryu includes `ofctl_rest.py` for REST-based flow control:

```bash
# Get all switches
curl http://localhost:8080/stats/switches

# Get flows
curl http://localhost:8080/stats/flow/1

# Add flow
curl -X POST -d '{
  "dpid": 1,
  "match": {"in_port": 1},
  "actions": [{"type": "OUTPUT", "port": 2}]
}' http://localhost:8080/stats/flowentry/add
```

## Integration

Used automatically in Caduceus-Flux docker-compose setup:

```yaml
ryu:
  image: caduceus-flux/ryu:latest
  ports:
    - "6653:6653"
    - "8080:8080"
```

## References

- [Ryu Documentation](https://ryu.readthedocs.io/)
- [Ryu Book](https://osrg.github.io/ryu-book/en/)

