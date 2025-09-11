# Mininet Web Framework - API Documentation

## Overview

The Mininet Web Framework provides a comprehensive RESTful API for managing software-defined networks. The API is organized into multiple endpoints covering network lifecycle management, topology control, performance monitoring, diagnostics, and AI-powered features.

**Base URL**: `http://localhost:5000/api`

**Content-Type**: All requests and responses use `application/json`

## Authentication

Currently, the API operates without authentication in development mode. For production deployments, implement JWT-based authentication:

```bash
# Future authentication header format
Authorization: Bearer <jwt_token>
```

## Network Management

### Network Operations

#### Get Network Status
```http
GET /api/network/status
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "running": true,
    "network_exists": true,
    "topology": {
      "hosts": 4,
      "switches": 2,
      "controllers": 1,
      "links": 5
    },
    "connectivity": {
      "reachable_pairs": 12,
      "total_pairs": 12,
      "success_rate": 100.0
    },
    "devices": {
      "hosts": ["h1", "h2", "h3", "h4"],
      "switches": ["s1", "s2"],
      "controllers": ["c0"]
    }
  }
}
```

#### Start Network
```http
POST /api/network/start
```

**Response:**
```json
{
  "status": "success",
  "message": "Network started successfully",
  "data": {
    "hosts_started": 4,
    "switches_started": 2,
    "controllers_connected": 1,
    "startup_time": 2.3
  }
}
```

#### Stop Network
```http
POST /api/network/stop
```

**Response:**
```json
{
  "status": "success",
  "message": "Network stopped successfully",
  "data": {
    "cleanup_time": 1.2,
    "processes_terminated": 15
  }
}
```

#### Restart Network
```http
POST /api/network/restart
```

#### Delete Network
```http
DELETE /api/network
```

#### Create Network
```http
POST /api/network/create
```

**Request Body:**
```json
{
  "topology": {
    "type": "custom",
    "hosts": [
      {"name": "h1", "ip": "10.0.1.1", "mac": "00:00:00:00:00:01"},
      {"name": "h2", "ip": "10.0.1.2", "mac": "00:00:00:00:00:02"}
    ],
    "switches": [
      {"name": "s1", "dpid": "0000000000000001"},
      {"name": "s2", "dpid": "0000000000000002"}
    ],
    "links": [
      {"source": "h1", "target": "s1", "bandwidth": "1Gbps"},
      {"source": "h2", "target": "s2", "bandwidth": "1Gbps"},
      {"source": "s1", "target": "s2", "bandwidth": "10Gbps"}
    ],
    "controllers": [
      {"name": "c0", "type": "ryu", "port": 6633}
    ]
  }
}
```

### Connectivity Testing

#### Test Host-to-Host Connectivity
```http
POST /api/network/test-connectivity
```

**Request Body:**
```json
{
  "src_host": "h1",
  "dst_host": "h2",
  "test_type": "ping",
  "packet_count": 4,
  "timeout": 5
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "src": "h1",
    "dst": "h2",
    "test_type": "ping",
    "results": {
      "packets_sent": 4,
      "packets_received": 4,
      "packet_loss": 0.0,
      "min_rtt": 0.123,
      "avg_rtt": 0.145,
      "max_rtt": 0.167,
      "std_rtt": 0.018
    },
    "success": true
  }
}
```

#### Ping All Hosts
```http
POST /api/network/ping-all
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_tests": 12,
    "successful_tests": 12,
    "failed_tests": 0,
    "success_rate": 100.0,
    "results": [
      {"src": "h1", "dst": "h2", "success": true, "rtt": 0.145},
      {"src": "h1", "dst": "h3", "success": true, "rtt": 0.167},
      {"src": "h2", "dst": "h3", "success": true, "rtt": 0.134}
    ]
  }
}
```

### Link Management

#### Modify Link Properties
```http
POST /api/network/links/modify
```

**Request Body:**
```json
{
  "src": "s1",
  "dst": "s2",
  "bandwidth": "5Gbps",
  "delay": "10ms",
  "loss": "0.1%"
}
```

#### Disable Link
```http
POST /api/network/links/disable
```

**Request Body:**
```json
{
  "src": "s1",
  "dst": "s2"
}
```

#### Enable Link
```http
POST /api/network/links/enable
```

**Request Body:**
```json
{
  "src": "s1",
  "dst": "s2"
}
```

## Controller Management

### Controller Operations

#### Get Controller Status
```http
GET /api/controller/status
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "running": true,
    "type": "ryu",
    "app": "simple_switch_13",
    "port": 6633,
    "connected_switches": 2,
    "uptime": 1847,
    "stats": {
      "packets_in": 1024,
      "packets_out": 1018,
      "flow_entries": 12,
      "table_misses": 6
    }
  }
}
```

#### Start Controller
```http
POST /api/controller/start
```

**Request Body:**
```json
{
  "controller_type": "ryu",
  "port": 6633,
  "options": {
    "app": "simple_switch_13",
    "verbose": true,
    "observe_links": true
  }
}
```

#### Stop Controller
```http
POST /api/controller/stop
```

#### Connect Switches
```http
POST /api/controller/connect-switches
```

**Request Body:**
```json
{
  "switches": ["s1", "s2", "s3"]
}
```

### Flow Management

#### Get Flow Entries
```http
GET /api/controller/flows?switch_id=s1
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "switch_id": "s1",
    "flow_count": 5,
    "flows": [
      {
        "flow_id": "1",
        "priority": 32768,
        "match": {
          "in_port": 1,
          "eth_dst": "00:00:00:00:00:01"
        },
        "actions": [
          {"type": "output", "port": 2}
        ],
        "byte_count": 1024,
        "packet_count": 16,
        "duration": 120
      }
    ]
  }
}
```

#### Install Flow Rule
```http
POST /api/controller/flows
```

**Request Body:**
```json
{
  "switch_id": "s1",
  "priority": 1000,
  "match": {
    "in_port": 1,
    "eth_type": 2048,
    "ipv4_dst": "10.0.1.2"
  },
  "actions": [
    {"type": "output", "port": 2}
  ],
  "idle_timeout": 60,
  "hard_timeout": 300
}
```

#### Delete Flow Rule
```http
DELETE /api/controller/flows
```

**Request Body:**
```json
{
  "switch_id": "s1",
  "flow_id": "5"
}
```

## Topology Management

### Topology Information

#### Get Complete Topology
```http
GET /api/topology/info
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "hosts": [
      {
        "name": "h1",
        "ip": "10.0.1.1",
        "mac": "00:00:00:00:00:01",
        "connected_to": ["s1"],
        "status": "active"
      }
    ],
    "switches": [
      {
        "name": "s1",
        "dpid": "0000000000000001",
        "connected_to": ["h1", "h2", "s2"],
        "ports": 3,
        "flows": 5,
        "status": "connected"
      }
    ],
    "controllers": [
      {
        "name": "c0",
        "type": "ryu",
        "ip": "127.0.0.1",
        "port": 6633,
        "status": "active"
      }
    ],
    "links": [
      {
        "source": "h1",
        "target": "s1",
        "bandwidth": "1Gbps",
        "delay": "1ms",
        "status": "up"
      }
    ]
  }
}
```

#### Get Topology Devices
```http
GET /api/topology/devices
```

#### Get Topology Links
```http
GET /api/topology/links
```

### Topology Templates

#### Get Available Templates
```http
GET /api/topology/templates
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "templates": [
      {
        "name": "linear",
        "description": "Linear topology with N hosts",
        "parameters": ["hosts"],
        "preview": "h1---s1---h2---s2---h3"
      },
      {
        "name": "tree",
        "description": "Tree topology with specified depth and fanout",
        "parameters": ["depth", "fanout"],
        "preview": "Tree structure"
      }
    ]
  }
}
```

#### Create from Template
```http
POST /api/topology/create-from-template
```

**Request Body:**
```json
{
  "template_name": "linear",
  "parameters": {
    "hosts": 4
  }
}
```

#### Save Current Topology as Template
```http
POST /api/topology/save-template
```

**Request Body:**
```json
{
  "name": "custom-datacenter",
  "description": "Custom datacenter topology",
  "topology_config": {
    "hosts": [...],
    "switches": [...],
    "links": [...]
  }
}
```

## Statistics and Monitoring

### Network Statistics

#### Get Network Statistics
```http
GET /api/stats/network
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "overview": {
      "total_hosts": 4,
      "total_switches": 2,
      "total_links": 5,
      "active_flows": 12
    },
    "traffic": {
      "total_bytes": 1048576,
      "total_packets": 8192,
      "bytes_per_second": 1024,
      "packets_per_second": 64
    },
    "health": {
      "link_utilization": 15.5,
      "average_latency": 0.145,
      "packet_loss": 0.0,
      "jitter": 0.012
    }
  }
}
```

#### Get Device Statistics
```http
GET /api/stats/devices?device_id=s1
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "device_id": "s1",
    "type": "switch",
    "interfaces": [
      {
        "port": 1,
        "name": "s1-eth1",
        "rx_bytes": 524288,
        "tx_bytes": 524288,
        "rx_packets": 4096,
        "tx_packets": 4096,
        "rx_dropped": 0,
        "tx_dropped": 0,
        "rx_errors": 0,
        "tx_errors": 0
      }
    ],
    "flows": {
      "total": 5,
      "active": 5,
      "expired": 0
    }
  }
}
```

### Real-time Monitoring

#### Start Monitoring
```http
POST /api/stats/monitoring/start
```

**Request Body:**
```json
{
  "interval": 5,
  "devices": ["s1", "s2", "h1", "h2"]
}
```

#### Stop Monitoring
```http
POST /api/stats/monitoring/stop
```

#### Get Monitoring Data
```http
GET /api/stats/monitoring/data?timerange=300&device_filter=s1
```

## Storage and Snapshots

### Configuration Storage

#### List Saved Configurations
```http
GET /api/storage/configurations
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "configurations": [
      {
        "id": "config_123",
        "name": "production-setup",
        "description": "Production network configuration",
        "created_at": "2024-01-15T10:30:00Z",
        "size": "2.5MB",
        "hosts": 20,
        "switches": 8
      }
    ]
  }
}
```

#### Save Current Configuration
```http
POST /api/storage/save-configuration
```

**Request Body:**
```json
{
  "name": "backup-config",
  "description": "Backup before major changes"
}
```

#### Load Configuration
```http
POST /api/storage/load-configuration
```

**Request Body:**
```json
{
  "config_id": "config_123"
}
```

#### Delete Configuration
```http
DELETE /api/storage/configurations/<config_id>
```

### Network Snapshots

#### List Snapshots
```http
GET /api/snapshots/list
```

#### Create Snapshot
```http
POST /api/snapshots/create
```

**Request Body:**
```json
{
  "name": "pre-maintenance",
  "description": "Snapshot before maintenance window"
}
```

#### Restore Snapshot
```http
POST /api/snapshots/restore
```

**Request Body:**
```json
{
  "snapshot_id": "snap_456"
}
```

#### Delete Snapshot
```http
DELETE /api/snapshots/delete/<snapshot_id>
```

## Device Management

### Host Management

#### Get Host Status
```http
GET /api/devices/<device_id>/host/status
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "device_id": "h1",
    "hostname": "host-1",
    "ip_addresses": ["10.0.1.1"],
    "mac_addresses": ["00:00:00:00:00:01"],
    "interfaces": [
      {
        "name": "h1-eth0",
        "ip": "10.0.1.1/24",
        "mac": "00:00:00:00:00:01",
        "status": "up",
        "mtu": 1500
      }
    ],
    "services": {
      "ssh": {"running": true, "port": 22},
      "http": {"running": false, "port": 80}
    },
    "routing_table": [
      {
        "destination": "0.0.0.0/0",
        "gateway": "10.0.1.254",
        "interface": "h1-eth0"
      }
    ]
  }
}
```

#### Configure Host Interface
```http
POST /api/devices/<device_id>/host/interfaces
```

**Request Body:**
```json
{
  "interface": "h1-eth0",
  "ip": "10.0.1.10",
  "netmask": "255.255.255.0",
  "gateway": "10.0.1.1"
}
```

#### Manage Host Services
```http
POST /api/devices/<device_id>/host/services/<service_name>
```

**Request Body:**
```json
{
  "action": "start",
  "config": {
    "port": 8080,
    "enable_ssl": false
  }
}
```

### Switch Management

#### Get Switch Status
```http
GET /api/devices/<device_id>/switch/status
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "device_id": "s1",
    "dpid": "0000000000000001",
    "connected_controller": "127.0.0.1:6633",
    "openflow_version": "1.3",
    "ports": [
      {
        "port_no": 1,
        "name": "s1-eth1",
        "hw_addr": "aa:bb:cc:dd:ee:01",
        "state": "up",
        "curr_speed": "1000000"
      }
    ],
    "flow_tables": [
      {
        "table_id": 0,
        "name": "classifier",
        "match_fields": ["in_port", "eth_dst"],
        "flow_count": 5,
        "lookup_count": 1024,
        "matched_count": 1018
      }
    ]
  }
}
```

#### Configure Switch Ports
```http
POST /api/devices/<device_id>/switch/ports
```

**Request Body:**
```json
{
  "port_config": [
    {
      "port": 1,
      "admin_state": "up",
      "config": {
        "no_flood": false,
        "no_packet_in": false
      }
    }
  ]
}
```

## Performance Management

### Performance Testing

#### Get Performance Status
```http
GET /api/performance/status
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "system_ready": true,
    "available_hosts": 4,
    "test_tools": ["iperf3", "ping", "netperf"],
    "active_tests": 0,
    "monitoring_active": false,
    "last_test": "2024-01-15T10:25:00Z"
  }
}
```

#### Run Comprehensive Performance Test
```http
POST /api/performance/test/comprehensive
```

**Request Body:**
```json
{
  "src_host": "h1",
  "dst_host": "h2",
  "duration": 30,
  "test_types": ["bandwidth", "latency", "jitter", "packet_loss"]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "session_id": "perf_789",
    "results": {
      "bandwidth": {
        "tcp_throughput": 954.2,
        "udp_throughput": 899.7,
        "unit": "Mbps"
      },
      "latency": {
        "min": 0.123,
        "avg": 0.145,
        "max": 0.167,
        "std": 0.018,
        "unit": "ms"
      },
      "jitter": {
        "avg": 0.012,
        "max": 0.045,
        "unit": "ms"
      },
      "packet_loss": {
        "percentage": 0.0,
        "packets_sent": 1000,
        "packets_received": 1000
      }
    }
  }
}
```

#### Run Stress Test
```http
POST /api/performance/test/stress
```

**Request Body:**
```json
{
  "duration": 60,
  "concurrent_flows": 10,
  "flow_size": "100MB"
}
```

### Performance Monitoring

#### Start Real-time Monitoring
```http
POST /api/performance/monitoring/start
```

**Request Body:**
```json
{
  "interval": 5,
  "hosts": ["h1", "h2", "h3"]
}
```

#### Get Monitoring Status
```http
GET /api/performance/monitoring/status
```

#### Get Historical Data
```http
GET /api/performance/monitoring/history?pair_key=h1-h2&limit=100
```

### Performance Reports

#### Generate Performance Report
```http
POST /api/performance/reports/generate
```

**Request Body:**
```json
{
  "session_id": "perf_789",
  "format": "json",
  "include_analysis": true
}
```

## Diagnostic Tools

### Network Diagnostics

#### Run Ping Test
```http
POST /api/diagnostic/ping
```

**Request Body:**
```json
{
  "src": "h1",
  "dst": "h2",
  "count": 10,
  "interval": 1,
  "timeout": 5
}
```

#### Run Traceroute
```http
POST /api/diagnostic/traceroute
```

**Request Body:**
```json
{
  "src": "h1",
  "dst": "h2",
  "max_hops": 30
}
```

#### Bandwidth Test
```http
POST /api/diagnostic/bandwidth
```

**Request Body:**
```json
{
  "src": "h1",
  "dst": "h2",
  "duration": 10,
  "protocol": "tcp"
}
```

#### Port Scan
```http
POST /api/diagnostic/port-scan
```

**Request Body:**
```json
{
  "target": "h2",
  "ports": [22, 80, 443, 8080],
  "scan_type": "tcp"
}
```

#### Network Health Check
```http
GET /api/diagnostic/network-health
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "overall_status": "healthy",
    "score": 95,
    "issues": [],
    "recommendations": [],
    "checks": {
      "connectivity": {"status": "pass", "score": 100},
      "performance": {"status": "pass", "score": 90},
      "configuration": {"status": "pass", "score": 95}
    }
  }
}
```

## LLM Integration

### LLM Service Management

#### Get LLM Status
```http
GET /api/llm/status
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "service_active": true,
    "current_service": "ollama",
    "model": "llama3.1:8b",
    "available_services": ["ollama", "openai", "gemini", "claude"],
    "templates_available": 15,
    "last_generation": "2024-01-15T10:20:00Z"
  }
}
```

#### Switch LLM Service
```http
POST /api/llm/switch-service
```

**Request Body:**
```json
{
  "service_type": "openai",
  "service_kwargs": {
    "model": "gpt-4",
    "api_key": "sk-..."
  }
}
```

### Topology Generation

#### Generate Topology from Description
```http
POST /api/llm/generate-topology
```

**Request Body:**
```json
{
  "description": "Create a data center network with 3 tiers: 4 edge switches, 2 aggregation switches, 1 core switch, and 16 servers",
  "parameters": {
    "complexity": "complex",
    "controller_type": "ryu",
    "addressing": "auto"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "topology": {
      "hosts": [...],
      "switches": [...],
      "links": [...],
      "controllers": [...]
    },
    "description": "Generated 3-tier data center topology",
    "creation_successful": true,
    "validation": {
      "valid": true,
      "issues": [],
      "warnings": []
    }
  }
}
```

#### Generate from Template
```http
POST /api/llm/generate-from-template
```

**Request Body:**
```json
{
  "template_name": "campus-network",
  "parameters": {
    "departments": 4,
    "hosts_per_department": 10,
    "redundancy": true
  }
}
```

#### Chat with LLM
```http
POST /api/llm/chat
```

**Request Body:**
```json
{
  "message": "How can I optimize my network for low latency?",
  "use_history": true
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "response": "To optimize your network for low latency, consider the following strategies:\n1. Reduce the number of hops...",
    "context_used": true,
    "suggestions": [
      "Implement QoS policies",
      "Use high-speed links",
      "Optimize routing protocols"
    ]
  }
}
```

### LLM Configuration Management

#### List LLM Configurations
```http
GET /api/llm-config/configurations
```

#### Create LLM Configuration
```http
POST /api/llm-config/configurations
```

**Request Body:**
```json
{
  "name": "production-openai",
  "service_type": "openai",
  "model_name": "gpt-4",
  "api_key": "sk-...",
  "config": {
    "temperature": 0.7,
    "max_tokens": 2000
  }
}
```

#### Test LLM Configuration
```http
POST /api/llm-config/configurations/<config_id>/test
```

#### Set Active Configuration
```http
POST /api/llm-config/active
```

**Request Body:**
```json
{
  "config_id": "llm_config_123"
}
```

## Error Handling

### Standard Error Response Format

```json
{
  "status": "error",
  "message": "Brief error description",
  "error": {
    "code": "ERROR_CODE",
    "details": "Detailed error information",
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_12345"
  }
}
```

### Common Error Codes

- `NETWORK_NOT_FOUND` - Network does not exist
- `NETWORK_ALREADY_RUNNING` - Network is already started
- `CONTROLLER_NOT_CONNECTED` - SDN controller not available
- `INVALID_TOPOLOGY` - Topology configuration is invalid
- `DEVICE_NOT_FOUND` - Specified device does not exist
- `INSUFFICIENT_PERMISSIONS` - Operation requires higher privileges
- `RESOURCE_CONFLICT` - Resource is already in use
- `TIMEOUT_ERROR` - Operation timed out
- `VALIDATION_ERROR` - Input validation failed

### HTTP Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

## Rate Limiting

The API implements rate limiting to prevent abuse:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1642251600
```

- **Standard endpoints**: 1000 requests per hour
- **Performance tests**: 10 concurrent tests maximum
- **LLM generation**: 50 requests per hour per API key

## WebSocket API

For real-time updates, the framework provides WebSocket endpoints:

### Connection
```javascript
const ws = new WebSocket('ws://localhost:5000/ws');
```

### Message Format
```json
{
  "type": "network_status",
  "data": {
    "running": true,
    "hosts": 4,
    "switches": 2
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Available Channels
- `network_status` - Network state changes
- `topology_updates` - Topology modifications
- `performance_metrics` - Real-time performance data
- `controller_events` - SDN controller events
- `diagnostic_alerts` - Network health alerts

## SDK and Client Libraries

### Python SDK
```python
from mininet_web_client import MininetWebClient

client = MininetWebClient('http://localhost:5000')
result = await client.network.create_topology({
    'type': 'linear',
    'hosts': 4
})
```

### JavaScript/Node.js SDK
```javascript
const MininetClient = require('mininet-web-client');

const client = new MininetClient('http://localhost:5000');
const result = await client.network.getStatus();
```

### cURL Examples

```bash
# Create a linear topology
curl -X POST http://localhost:5000/api/network/create \
  -H "Content-Type: application/json" \
  -d '{
    "topology": {
      "type": "linear",
      "hosts": 4
    }
  }'

# Start the network
curl -X POST http://localhost:5000/api/network/start

# Get network status
curl -X GET http://localhost:5000/api/network/status

# Run performance test
curl -X POST http://localhost:5000/api/performance/test/comprehensive \
  -H "Content-Type: application/json" \
  -d '{
    "src_host": "h1",
    "dst_host": "h4",
    "duration": 30
  }'
```

This comprehensive API documentation provides complete coverage of all available endpoints, request/response formats, and usage examples for the Mininet Web Framework.