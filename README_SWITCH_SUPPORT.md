# Multiple Switch Support Documentation

## Overview

This enhanced Mininet web framework now supports multiple types of network switches alongside the traditional OpenFlow controllers. The system provides a unified interface for managing different switch technologies including Linux Bridge, Open vSwitch, and P4-programmable switches.

## Supported Switch Types

### 1. Open vSwitch (OVS)
- **Type**: `ovs`
- **Description**: Enhanced Open vSwitch with advanced management capabilities
- **Features**:
  - OpenFlow support (1.0, 1.3, etc.)
  - Flow table management
  - QoS support
  - Port mirroring
  - NetFlow/sFlow export
  - Bridge management via `ovs-vsctl`

### 2. Linux Bridge
- **Type**: `linux_bridge`
- **Description**: Native Linux bridging using `brctl` commands
- **Features**:
  - L2 learning bridge
  - STP (Spanning Tree Protocol) support
  - VLAN configuration
  - MAC address table management
  - Standalone operation (no controller required)
  - Lightweight and fast

### 3. P4 Behavioral Model (BMv2)
- **Type**: `p4`
- **Description**: P4-programmable switch using BMv2
- **Features**:
  - Runtime P4 program compilation
  - Table entry management
  - Custom packet processing pipelines
  - P4Runtime API support
  - Multiple program templates
  - Research and education focused

## Architecture

### Switch Factory Pattern
The system uses a factory pattern similar to the controller management:

```
SwitchFactory
├── BaseSwitchManager (abstract base)
├── LinuxBridgeSwitch
├── OVSSwitchManager
└── P4SwitchManager
```

### API Endpoints

#### General Switch Management
- `GET /api/switch/available` - List available switch types
- `GET /api/switch/info` - Get information about all switches
- `GET /api/switch/capabilities/<switch_type>` - Get switch capabilities
- `POST /api/switch/create` - Create a new switch instance
- `GET /api/switch/status/<switch_type>` - Get switch status
- `GET /api/switch/stats/<switch_type>` - Get switch statistics

#### Port Management
- `POST /api/switch/port/<switch_id>/<port_name>` - Configure switch port
- `GET /api/switch/port/<switch_id>/<port_name>` - Get port configuration
- `GET /api/switch/ports/<switch_id>` - List switch ports

#### P4-Specific Operations
- `POST /api/switch/p4/compile/<program_name>` - Compile P4 program
- `POST /api/switch/p4/table/<table_name>/entry` - Add table entry
- `GET /api/switch/p4/table/<table_name>/entries` - Get table entries
- `POST /api/switch/p4/template/<program_name>` - Create from template
- `GET /api/switch/p4/templates` - List available templates

## Usage Examples

### Creating a Topology with Different Switch Types

```python
from backend.core.mininet_manager import MininetManager

# Initialize manager
mgr = MininetManager()

# Create topology with different switch types
topology_config = {
    'nodes': [
        {'id': 'h1', 'type': 'host', 'ip': '10.0.0.1'},
        {'id': 'h2', 'type': 'host', 'ip': '10.0.0.2'},
        {'id': 's1', 'type': 'switch'},  # OVS by default
        {'id': 's2', 'type': 'switch'},  # OVS by default
        {'id': 's3', 'type': 'switch'},  # OVS by default
    ],
    'links': [
        {'source': 'h1', 'target': 's1'},
        {'source': 'h2', 'target': 's2'},
        {'source': 's1', 'target': 's3'},
        {'source': 's2', 'target': 's3'},
    ]
}

# Create topology with Linux Bridge switches
success = mgr.create_custom_topology(
    topology_config,
    switch_type='linux_bridge'
)

# Or create with P4 switches
success = mgr.create_custom_topology(
    topology_config,
    switch_type='p4'
)
```

### API Usage Examples

#### Creating Switches via API

```bash
# Create a Linux Bridge switch
curl -X POST http://localhost:5000/api/switch/create \
  -H "Content-Type: application/json" \
  -d '{
    "switch_type": "linux_bridge",
    "switch_id": "br0",
    "config": {
      "stp": true
    }
  }'

# Create a P4 switch
curl -X POST http://localhost:5000/api/switch/create \
  -H "Content-Type: application/json" \
  -d '{
    "switch_type": "p4",
    "switch_id": "p4s1",
    "config": {
      "program_name": "basic_forwarding"
    }
  }'
```

#### Managing P4 Programs

```bash
# Compile a P4 program
curl -X POST http://localhost:5000/api/switch/p4/compile/my_program

# Add table entry
curl -X POST http://localhost:5000/api/switch/p4/table/dmac/entry \
  -H "Content-Type: application/json" \
  -d '{
    "match_fields": {
      "hdr.ethernet.dstAddr": "00:00:00:00:00:01"
    },
    "action_name": "forward",
    "action_params": {
      "port": 1
    }
  }'

# Create program from template
curl -X POST http://localhost:5000/api/switch/p4/template/my_firewall \
  -H "Content-Type: application/json" \
  -d '{
    "program_type": "firewall"
  }'
```

## P4 Program Templates

The system includes several pre-built P4 program templates:

### 1. Basic Forwarding (`basic_forwarding.p4`)
- Simple L2 learning switch
- MAC address learning and forwarding
- Flooding for unknown destinations

### 2. L2 Forwarding (`l2_forwarding.p4`)
- Enhanced L2 forwarding with broadcast handling
- Improved MAC learning table
- Support for multicast

### 3. L3 Forwarding (`l3_forwarding.p4`)
- IPv4 routing with TTL decrement
- Longest prefix matching (LPM)
- Next-hop resolution

### 4. Firewall (`firewall.p4`)
- Packet filtering based on rules
- Port blocking
- Access control lists

### 5. Load Balancer (`load_balancer.p4`)
- Simple load balancing
- Server pool management
- Connection distribution

## Configuration Options

### Switch-Specific Configuration

#### Linux Bridge Options
```json
{
  "stp": true,
  "priority": 32768,
  "hello_time": 2,
  "max_age": 20
}
```

#### OVS Options
```json
{
  "protocols": "OpenFlow13",
  "dpid": "0000000000000001",
  "fail_mode": "secure",
  "vlan_mode": "trunk"
}
```

#### P4 Options
```json
{
  "program_name": "basic_forwarding",
  "thrift_port": 9090,
  "grpc_port": 50051,
  "interfaces": ["eth1", "eth2"]
}
```

## Installation and Setup

### Linux Bridge Support
```bash
# Install bridge utilities
sudo apt-get install bridge-utils

# Load bridge kernel module
sudo modprobe bridge
```

### P4 Support
```bash
# Install P4 compiler and tools
sudo apt-get install p4c-bm2-ss

# Install BMv2
sudo apt-get install openvswitch-switch  # For simple_switch
```

### OVS Enhanced Support
```bash
# Install Open vSwitch (if not already installed)
sudo apt-get install openvswitch-switch

# Start OVS service
sudo systemctl start openvswitch-switch
```

## Integration with Controllers

The switch system integrates seamlessly with the existing controller framework:

- **OpenFlow switches** work with Ryu, POX, OsKen, and OpenDaylight
- **Linux Bridge switches** operate standalone or with basic controllers
- **P4 switches** can use P4Runtime alongside traditional OpenFlow

## Performance Considerations

### Switch Type Performance Comparison

1. **Linux Bridge**: Fastest for simple L2 switching, minimal overhead
2. **OVS**: Good performance with OpenFlow, additional features available
3. **P4 BMv2**: Slower due to software-based packet processing, best for research

### Resource Requirements

- **Linux Bridge**: Minimal CPU and memory usage
- **OVS**: Moderate resource usage, kernel datapath for performance
- **P4 BMv2**: Higher CPU usage due to software switching

## Troubleshooting

### Common Issues

#### Linux Bridge Issues
```bash
# Check bridge status
brctl show

# Check bridge interfaces
ip link show type bridge

# Debug STP issues
brctl showstp <bridge_name>
```

#### OVS Issues
```bash
# Check OVS status
sudo ovs-vsctl show

# Check OpenFlow flows
sudo ovs-ofctl dump-flows <bridge_name>

# Check controller connection
sudo ovs-vsctl get-controller <bridge_name>
```

#### P4 Issues
```bash
# Check BMv2 process
ps aux | grep simple_switch

# Check P4 compilation errors
# Look in /tmp/p4_programs/ and /tmp/p4_compiled/

# Check Thrift connection
netstat -tlnp | grep 9090
```

### Log Files
- Main logs: `/var/log/mininet-web-framework/`
- P4 compilation logs: `/tmp/p4_programs/`
- Switch-specific logs: Check individual switch manager logs

## Future Enhancements

### Planned Features
1. **DPDK Integration**: High-performance packet processing
2. **OVS-DPDK Support**: Hardware-accelerated OVS
3. **P4 Hardware Targets**: Support for Tofino, Netronome
4. **Advanced P4 Features**: P4Runtime shell integration
5. **Machine Learning Integration**: ML-based traffic classification

### Extensibility
The switch factory pattern makes it easy to add new switch types:

```python
class MyCustomSwitch(BaseSwitchManager):
    def __init__(self):
        super().__init__("My Custom Switch", "custom")

    def check_installation(self) -> bool:
        # Implementation here
        pass

    def create_switch(self, switch_id: str, **kwargs) -> Any:
        # Implementation here
        pass
```

## Conclusion

This enhanced switch support provides a comprehensive platform for network research and education, supporting everything from simple L2 bridging to advanced P4-programmable data planes. The unified API and factory pattern make it easy to extend and customize for specific use cases.
