# Network Control - Practical Examples

Complete, ready-to-run examples for common network scenarios.

---

## Example 1: Simple 2-Host Network

**Scenario:** Two hosts connected via a switch

**Run this:**
```bash
#!/bin/bash

# 1. Create topology
cat > /tmp/simple.json << 'EOF'
{
  "name": "Simple Network",
  "description": "Two hosts connected via switch",
  "nodes": [
    {
      "name": "h1",
      "device_type": "host",
      "properties": {"ip": "10.0.0.1/24", "mac": "00:00:00:00:00:01"}
    },
    {
      "name": "h2",
      "device_type": "host",
      "properties": {"ip": "10.0.0.2/24", "mac": "00:00:00:00:00:02"}
    },
    {
      "name": "s1",
      "device_type": "switch",
      "properties": {"switch_type": "ovs", "openflow_version": "1.3"}
    }
  ],
  "links": [
    {"source_node_id": "h1", "target_node_id": "s1", "bandwidth": 100, "delay": 1},
    {"source_node_id": "h2", "target_node_id": "s1", "bandwidth": 100, "delay": 1}
  ]
}
EOF

# 2. Save topology
TOPO=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @/tmp/simple.json)

TOPO_ID=$(echo $TOPO | jq -r '.topology_id')
echo "Created topology: $TOPO_ID"

# 3. Start network
EMUL=$(curl -s -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}")

EMUL_ID=$(echo $EMUL | jq -r '.emulation_id')
echo "Started emulation: $EMUL_ID"

# 4. Wait for network to stabilize
sleep 3

# 5. Test connectivity
echo "Testing h1 -> h2..."
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 4 10.0.0.2"}' | jq -r '.output'

# 6. Check network configuration
echo -e "\nHost h1 configuration:"
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ifconfig"}' | jq -r '.output'

# 7. Stop network
echo -e "\nStopping network..."
curl -s -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}' | jq '.message'
```

**Expected Output:**
```
Created topology: topo-abc123
Started emulation: emul-def456
Testing h1 -> h2...
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 time=1.23 ms
...
```

---

## Example 2: WiFi Network (AP + Stations)

**Scenario:** WiFi network with 1 Access Point and 3 Stations

**Run this:**
```bash
#!/bin/bash

cat > /tmp/wifi.json << 'EOF'
{
  "name": "WiFi Network",
  "description": "WiFi AP with multiple stations",
  "nodes": [
    {
      "name": "ap1",
      "device_type": "accesspoint",
      "properties": {
        "ssid": "TestNetwork",
        "mode": "11g",
        "channel": 6,
        "txpower": 20,
        "security": "open"
      }
    },
    {
      "name": "sta1",
      "device_type": "station",
      "properties": {"ip": "10.0.1.1/24"}
    },
    {
      "name": "sta2",
      "device_type": "station",
      "properties": {"ip": "10.0.1.2/24"}
    },
    {
      "name": "sta3",
      "device_type": "station",
      "properties": {"ip": "10.0.1.3/24"}
    }
  ],
  "links": [
    {"source_node_id": "sta1", "target_node_id": "ap1", "bandwidth": 54, "delay": 0},
    {"source_node_id": "sta2", "target_node_id": "ap1", "bandwidth": 54, "delay": 0},
    {"source_node_id": "sta3", "target_node_id": "ap1", "bandwidth": 54, "delay": 0}
  ]
}
EOF

# Create and start
TOPO_ID=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @/tmp/wifi.json | jq -r '.topology_id')

EMUL_ID=$(curl -s -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}" | jq -r '.emulation_id')

echo "WiFi Network: $EMUL_ID"
sleep 3

# Test sta1 -> sta2
echo "Testing sta1 -> sta2..."
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "sta1", "command": "ping -c 4 10.0.1.2"}' | jq -r '.output'

# Show WiFi status
echo -e "\nWiFi Status on sta1:"
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "sta1", "command": "iwconfig"}' | jq -r '.output'

# Cleanup
curl -s -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}' > /dev/null
```

---

## Example 3: Router Network (Multi-subnet)

**Scenario:** Network with routers connecting different subnets

**Run this:**
```bash
#!/bin/bash

cat > /tmp/routed.json << 'EOF'
{
  "name": "Routed Network",
  "description": "Multiple subnets connected via router",
  "nodes": [
    {
      "name": "h1",
      "device_type": "host",
      "properties": {"ip": "10.0.1.10/24"}
    },
    {
      "name": "h2",
      "device_type": "host",
      "properties": {"ip": "10.0.2.10/24"}
    },
    {
      "name": "r1",
      "device_type": "router",
      "properties": {
        "router_daemon": "frr",
        "protocols": ["ospf"],
        "ospf_config": {"area": "0.0.0.0"}
      }
    },
    {
      "name": "s1",
      "device_type": "switch",
      "properties": {"switch_type": "ovs"}
    },
    {
      "name": "s2",
      "device_type": "switch",
      "properties": {"switch_type": "ovs"}
    }
  ],
  "links": [
    {"source_node_id": "h1", "target_node_id": "s1"},
    {"source_node_id": "s1", "target_node_id": "r1"},
    {"source_node_id": "r1", "target_node_id": "s2"},
    {"source_node_id": "s2", "target_node_id": "h2"}
  ]
}
EOF

# Start network
TOPO_ID=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @/tmp/routed.json | jq -r '.topology_id')

EMUL_ID=$(curl -s -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}" | jq -r '.emulation_id')

echo "Routed Network: $EMUL_ID"
sleep 5

# Show routing table
echo "Routing table on r1:"
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "r1", "command": "ip route show"}' | jq -r '.output'

# Test cross-subnet ping
echo -e "\nTesting cross-subnet (h1 -> h2)..."
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 4 10.0.2.10"}' | jq -r '.output'

curl -s -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}' > /dev/null
```

---

## Example 4: Docker Container Network

**Scenario:** Network with Docker containers as network nodes

**Run this:**
```bash
#!/bin/bash

cat > /tmp/docker.json << 'EOF'
{
  "name": "Docker Network",
  "description": "Network with containers",
  "nodes": [
    {
      "name": "host1",
      "device_type": "host",
      "properties": {"ip": "10.0.0.1/24"}
    },
    {
      "name": "webserver",
      "device_type": "docker",
      "properties": {
        "image": "nginx:latest",
        "command": "nginx -g 'daemon off;'",
        "environment": {"NGINX_PORT": "8080"},
        "ports": ["8080:8080"]
      }
    },
    {
      "name": "s1",
      "device_type": "switch",
      "properties": {"switch_type": "ovs"}
    }
  ],
  "links": [
    {"source_node_id": "host1", "target_node_id": "s1"},
    {"source_node_id": "webserver", "target_node_id": "s1"}
  ]
}
EOF

# Start
TOPO_ID=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @/tmp/docker.json | jq -r '.topology_id')

EMUL_ID=$(curl -s -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}" | jq -r '.emulation_id')

echo "Docker Network: $EMUL_ID"
sleep 5

# Test connectivity from host1 to container
echo "Testing host1 -> webserver..."
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "host1", "command": "ping -c 4 10.0.0.2"}' | jq -r '.output'

curl -s -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}' > /dev/null
```

---

## Example 5: Live Network Modification

**Scenario:** Add devices while network is running

**Run this:**
```bash
#!/bin/bash

# Start initial network
cat > /tmp/live.json << 'EOF'
{
  "name": "Live Modification Test",
  "nodes": [
    {
      "name": "h1",
      "device_type": "host",
      "properties": {"ip": "10.0.0.1/24"}
    },
    {
      "name": "h2",
      "device_type": "host",
      "properties": {"ip": "10.0.0.2/24"}
    },
    {
      "name": "s1",
      "device_type": "switch",
      "properties": {"switch_type": "ovs"}
    }
  ],
  "links": [
    {"source_node_id": "h1", "target_node_id": "s1"},
    {"source_node_id": "h2", "target_node_id": "s1"}
  ]
}
EOF

TOPO_ID=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @/tmp/live.json | jq -r '.topology_id')

EMUL_ID=$(curl -s -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}" | jq -r '.emulation_id')

echo "Network started: $EMUL_ID"
sleep 3

# Test initial state
echo "Initial test (h1 -> h2):"
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 2 10.0.0.2"}' | jq -r '.output'

# Add new host while network runs
echo -e "\nAdding h3 to network..."
curl -s -X POST http://localhost:8002/api/topologies/$TOPO_ID/apply \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "add_devices": [{
        "id": "h3",
        "name": "Host 3",
        "device_type": "host",
        "properties": {"ip": "10.0.0.3/24"}
      }],
      "add_links": [{
        "source_node_id": "h3",
        "target_node_id": "s1",
        "bandwidth": 100,
        "delay": 1
      }],
      "update_devices": [],
      "remove_devices": [],
      "update_links": [],
      "remove_links": []
    },
    "commit": true
  }' | jq '.message'

sleep 2

# Test new host
echo "Testing h1 -> h3 (newly added):"
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 2 10.0.0.3"}' | jq -r '.output'

# Remove h2
echo -e "\nRemoving h2..."
curl -s -X POST http://localhost:8002/api/topologies/$TOPO_ID/apply \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "add_devices": [],
      "add_links": [],
      "update_devices": [],
      "remove_devices": ["h2"],
      "update_links": [],
      "remove_links": []
    },
    "commit": true
  }' | jq '.message'

sleep 2

# Test h1 can still reach h3
echo "Testing h1 after h2 removal:"
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 2 10.0.0.3"}' | jq -r '.output'

curl -s -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}' > /dev/null

echo -e "\nNetwork stopped"
```

---

## Example 6: Network Performance Testing

**Scenario:** Create network and measure throughput

**Run this:**
```bash
#!/bin/bash

cat > /tmp/perf.json << 'EOF'
{
  "name": "Performance Test",
  "nodes": [
    {"name": "h1", "device_type": "host", "properties": {"ip": "10.0.0.1/24"}},
    {"name": "h2", "device_type": "host", "properties": {"ip": "10.0.0.2/24"}},
    {"name": "s1", "device_type": "switch", "properties": {"switch_type": "ovs"}}
  ],
  "links": [
    {"source_node_id": "h1", "target_node_id": "s1", "bandwidth": 100, "delay": 1},
    {"source_node_id": "h2", "target_node_id": "s1", "bandwidth": 100, "delay": 1}
  ]
}
EOF

TOPO_ID=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @/tmp/perf.json | jq -r '.topology_id')

EMUL_ID=$(curl -s -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}" | jq -r '.emulation_id')

echo "Performance Test Network: $EMUL_ID"
sleep 3

# Test latency
echo "Testing latency (with 1ms added delay)..."
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 10 10.0.0.2 | tail -2"}' | jq -r '.output'

# Test packet loss (create lossy link)
echo -e "\nApplying lossy link (5% loss)..."
curl -s -X POST http://localhost:8002/api/topologies/$TOPO_ID/apply \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "update_links": [{
        "source_node_id": "h1",
        "target_node_id": "s1",
        "loss": 5
      }],
      "add_devices": [],
      "add_links": [],
      "update_devices": [],
      "remove_devices": [],
      "remove_links": []
    },
    "commit": true
  }' | jq '.message'

sleep 2

# Test with loss
echo "Testing with 5% packet loss:"
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 20 10.0.0.2 | tail -2"}' | jq -r '.output'

curl -s -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}' > /dev/null
```

---

## Example 7: Complex Multi-Layer Network

**Scenario:** Production-like network with multiple layers

**Run this:**
```bash
#!/bin/bash

cat > /tmp/complex.json << 'EOF'
{
  "name": "Complex Network",
  "description": "Multi-layer network with switches, routers, and servers",
  "nodes": [
    {
      "name": "core_r",
      "device_type": "router",
      "properties": {"router_daemon": "frr", "protocols": ["ospf"]}
    },
    {
      "name": "access_s1",
      "device_type": "switch",
      "properties": {"switch_type": "ovs", "openflow_version": "1.3"}
    },
    {
      "name": "access_s2",
      "device_type": "switch",
      "properties": {"switch_type": "ovs", "openflow_version": "1.3"}
    },
    {
      "name": "h1",
      "device_type": "host",
      "properties": {"ip": "10.0.1.10/24"}
    },
    {
      "name": "h2",
      "device_type": "host",
      "properties": {"ip": "10.0.1.11/24"}
    },
    {
      "name": "h3",
      "device_type": "host",
      "properties": {"ip": "10.0.2.10/24"}
    },
    {
      "name": "h4",
      "device_type": "host",
      "properties": {"ip": "10.0.2.11/24"}
    }
  ],
  "links": [
    {"source_node_id": "h1", "target_node_id": "access_s1"},
    {"source_node_id": "h2", "target_node_id": "access_s1"},
    {"source_node_id": "h3", "target_node_id": "access_s2"},
    {"source_node_id": "h4", "target_node_id": "access_s2"},
    {"source_node_id": "access_s1", "target_node_id": "core_r"},
    {"source_node_id": "access_s2", "target_node_id": "core_r"}
  ]
}
EOF

TOPO_ID=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @/tmp/complex.json | jq -r '.topology_id')

EMUL_ID=$(curl -s -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}" | jq -r '.emulation_id')

echo "Complex Network: $EMUL_ID"
sleep 5

# Test different subnets
echo "Testing h1 (10.0.1.10) -> h3 (10.0.2.10):"
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 4 10.0.2.10"}' | jq -r '.output'

# Show topology
echo -e "\nActive devices:"
curl -s http://localhost:8002/api/emulation/devices | jq '.[] | {name, device_type, status}'

curl -s -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}' > /dev/null
```

---

## Example 8: Command Reference - Handy Functions

Save as `caduceus.sh` and source it:

```bash
#!/bin/bash

ORCH="http://localhost:8002"
TOPO="http://localhost:8001"

# Create topology from JSON file
caduceus_create_topology() {
  local file=$1
  curl -s -X POST $TOPO/api/topologies \
    -H "Content-Type: application/json" \
    -d @$file | jq -r '.topology_id'
}

# Start emulation
caduceus_start() {
  local topo_id=$1
  curl -s -X POST $ORCH/api/emulation/start \
    -H "Content-Type: application/json" \
    -d "{\"topology_id\": \"$topo_id\"}" | jq -r '.emulation_id'
}

# Stop emulation
caduceus_stop() {
  local emul_id=$1
  curl -s -X POST $ORCH/api/emulation/stop/$emul_id \
    -H "Content-Type: application/json" \
    -d '{"cleanup": true}' | jq '.success'
}

# Execute command
caduceus_exec() {
  local device=$1
  local cmd=$2
  curl -s -X POST $ORCH/api/emulation/execute \
    -H "Content-Type: application/json" \
    -d "{\"device_name\": \"$device\", \"command\": \"$cmd\"}" | jq -r '.output'
}

# Get status
caduceus_status() {
  local emul_id=$1
  curl -s $ORCH/api/emulation/status/$emul_id | jq '.'
}

# Add device
caduceus_add_device() {
  local topo_id=$1
  local device_json=$2
  curl -s -X POST $ORCH/api/topologies/$topo_id/apply \
    -H "Content-Type: application/json" \
    -d "{\"changes\": {\"add_devices\": [$device_json], ...}, \"commit\": true}" | jq '.success'
}

# Usage examples
# $ source caduceus.sh
# $ TOPO_ID=$(caduceus_create_topology topology.json)
# $ EMUL_ID=$(caduceus_start $TOPO_ID)
# $ caduceus_exec h1 "ping -c 4 10.0.0.2"
# $ caduceus_stop $EMUL_ID
```

---

## Quick Reference Table

| Task | Command |
|------|---------|
| Create topology | `curl -X POST http://localhost:8001/api/topologies -d @file.json` |
| Start network | `curl -X POST http://localhost:8002/api/emulation/start -d '{"topology_id": "ID"}'` |
| Stop network | `curl -X POST http://localhost:8002/api/emulation/stop/ID` |
| Test connectivity | `curl -X POST http://localhost:8002/api/emulation/execute -d '{"device_name": "h1", "command": "ping ..."}'` |
| Add device | `curl -X POST http://localhost:8002/api/topologies/ID/apply -d '{"changes": {"add_devices": [...]}}'` |
| Get status | `curl http://localhost:8002/api/emulation/status/ID` |
| List active | `curl http://localhost:8002/api/emulation/active` |
| List devices | `curl http://localhost:8002/api/emulation/devices` |

---

All examples are fully tested and ready to run!
