# Mininet Web Framework Usage Guide

## Getting Started

This guide provides practical examples and tutorials for using the Mininet Web Framework. Whether you're new to software-defined networking or an experienced network engineer, these examples will help you master the platform.

## Quick Start Tutorial

### 1. Basic Network Creation

#### Using the Web Interface

1. **Access the Web Interface**
   ```bash
   # Start all services
   sudo python backend/app.py &
   cd frontend && npm start &
   
   # Open browser
   open http://localhost:3000
   ```

2. **Create Your First Network**
   - Click "Create Network" button
   - Select "Linear Topology"
   - Set hosts to 4
   - Click "Generate"
   - Click "Start Network"

3. **Test Connectivity**
   - Click "Test All Connectivity"
   - View ping results in real-time
   - Check network metrics panel

#### Using the API

```bash
# Create a simple linear topology
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

# Test connectivity
curl -X POST http://localhost:5000/api/network/ping-all
```

#### Using the MCP Server (AI Assistant)

If you have Claude or another AI assistant configured:

```
Create a simple network with 4 hosts connected linearly, then start it and test connectivity between all hosts.
```

The AI assistant will automatically:
1. Generate the topology
2. Create the network
3. Start the network
4. Run connectivity tests
5. Report the results

## Network Topology Examples

### 1. Linear Topology

**Use Case**: Simple test network, educational purposes

```python
# Using Python SDK
from mininet_web_client import MininetWebClient

client = MininetWebClient('http://localhost:5000')

# Create linear topology
topology = {
    "type": "linear",
    "hosts": 6,
    "switches": 3,
    "controller": {
        "type": "ryu",
        "app": "simple_switch_13"
    }
}

result = await client.network.create_topology(topology)
await client.network.start()
```

**Expected Result**: 
```
h1---s1---h2---s2---h3---s3---h4
```

### 2. Tree Topology

**Use Case**: Hierarchical networks, data center simulation

```bash
# Create tree topology via API
curl -X POST http://localhost:5000/api/llm/generate-topology \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create a tree topology with depth 2 and fanout 3",
    "parameters": {
      "depth": 2,
      "fanout": 3,
      "controller_type": "ryu"
    }
  }'
```

**Web Interface**:
1. Go to "LLM Topology Generator"
2. Enter: "Create a tree network with 2 levels and 3 branches per level"
3. Click "Generate Topology"
4. Review the generated configuration
5. Click "Apply Topology"

### 3. Data Center Topology

**Use Case**: Enterprise networks, multi-tier architecture

```javascript
// Using Node.js SDK
const MininetClient = require('mininet-web-client');
const client = new MininetClient('http://localhost:5000');

const dataCenterConfig = {
  description: "3-tier data center with 4 edge switches, 2 aggregation switches, 1 core switch, and 16 servers",
  parameters: {
    tiers: 3,
    edge_switches: 4,
    aggregation_switches: 2,
    core_switches: 1,
    servers: 16,
    controller_type: "ryu",
    redundancy: true
  }
};

const result = await client.llm.generateTopology(dataCenterConfig);
console.log('Generated topology:', result.topology);

await client.network.createFromTopology(result.topology);
await client.network.start();
```

### 4. Custom Topology

**Use Case**: Specific network requirements, research scenarios

```python
# Detailed custom topology
custom_topology = {
    "hosts": [
        {"name": "web_server", "ip": "10.0.1.10", "mac": "00:00:00:00:01:10"},
        {"name": "db_server", "ip": "10.0.1.20", "mac": "00:00:00:00:01:20"},
        {"name": "client1", "ip": "10.0.2.10", "mac": "00:00:00:00:02:10"},
        {"name": "client2", "ip": "10.0.2.20", "mac": "00:00:00:00:02:20"}
    ],
    "switches": [
        {"name": "core_switch", "dpid": "0000000000000001"},
        {"name": "access_switch1", "dpid": "0000000000000002"},
        {"name": "access_switch2", "dpid": "0000000000000003"}
    ],
    "links": [
        {"source": "web_server", "target": "access_switch1", "bandwidth": "1Gbps"},
        {"source": "db_server", "target": "access_switch1", "bandwidth": "1Gbps"},
        {"source": "client1", "target": "access_switch2", "bandwidth": "100Mbps"},
        {"source": "client2", "target": "access_switch2", "bandwidth": "100Mbps"},
        {"source": "access_switch1", "target": "core_switch", "bandwidth": "10Gbps"},
        {"source": "access_switch2", "target": "core_switch", "bandwidth": "10Gbps"}
    ],
    "controllers": [
        {"name": "main_controller", "type": "ryu", "port": 6633}
    ]
}

# Create and configure
result = await client.network.create({"topology": custom_topology})
await client.network.start()

# Configure services on hosts
await client.devices.configure_host_service("web_server", "http", {
    "port": 80,
    "document_root": "/var/www/html"
})

await client.devices.configure_host_service("db_server", "mysql", {
    "port": 3306,
    "root_password": "secure_password"
})
```

## Advanced Configuration Examples

### 1. QoS and Traffic Shaping

```python
# Configure QoS on links
qos_config = {
    "links": [
        {
            "source": "client1",
            "target": "access_switch2",
            "bandwidth": "100Mbps",
            "delay": "5ms",
            "loss": "0.1%",
            "max_queue_size": 1000
        }
    ]
}

await client.network.configure_qos(qos_config)

# Set up traffic classes
traffic_classes = {
    "high_priority": {
        "dscp": 46,
        "bandwidth": "50Mbps",
        "description": "Voice traffic"
    },
    "medium_priority": {
        "dscp": 26,
        "bandwidth": "30Mbps",
        "description": "Video traffic"
    },
    "low_priority": {
        "dscp": 0,
        "bandwidth": "20Mbps",
        "description": "Best effort"
    }
}

await client.network.configure_traffic_classes(traffic_classes)
```

### 2. SDN Flow Rules

```bash
# Install specific flow rules
curl -X POST http://localhost:5000/api/controller/flows \
  -H "Content-Type: application/json" \
  -d '{
    "switch_id": "s1",
    "priority": 1000,
    "match": {
      "in_port": 1,
      "eth_type": 2048,
      "ipv4_src": "10.0.1.1",
      "ipv4_dst": "10.0.1.2"
    },
    "actions": [
      {"type": "set_field", "field": "ipv4_tos", "value": 184},
      {"type": "output", "port": 2}
    ],
    "idle_timeout": 0,
    "hard_timeout": 0
  }'

# Create load balancing rules
for i in range(1, 4):
    flow_rule = {
        "switch_id": "core_switch",
        "priority": 500 + i,
        "match": {
            "eth_type": 2048,
            "ipv4_dst": "10.0.1.100",
            "tcp_dst": 80
        },
        "actions": [
            {"type": "set_field", "field": "ipv4_dst", "value": f"10.0.1.{100+i}"},
            {"type": "set_field", "field": "eth_dst", "value": f"00:00:00:00:01:{100+i:02x}"},
            {"type": "output", "port": i}
        ]
    }
    await client.controller.install_flow(flow_rule)
```

### 3. Network Security Configuration

```python
# Configure firewall rules on hosts
firewall_rules = {
    "web_server": [
        {"action": "allow", "protocol": "tcp", "port": 80, "source": "any"},
        {"action": "allow", "protocol": "tcp", "port": 443, "source": "any"},
        {"action": "allow", "protocol": "tcp", "port": 22, "source": "10.0.2.0/24"},
        {"action": "deny", "protocol": "any", "port": "any", "source": "any"}
    ],
    "db_server": [
        {"action": "allow", "protocol": "tcp", "port": 3306, "source": "10.0.1.10"},
        {"action": "allow", "protocol": "tcp", "port": 22, "source": "10.0.2.0/24"},
        {"action": "deny", "protocol": "any", "port": "any", "source": "any"}
    ]
}

for host, rules in firewall_rules.items():
    await client.devices.configure_firewall(host, rules)

# Set up VLANs
vlan_config = {
    "vlans": [
        {"id": 100, "name": "servers", "subnet": "10.0.1.0/24"},
        {"id": 200, "name": "clients", "subnet": "10.0.2.0/24"}
    ],
    "port_assignments": {
        "s1": {
            "1": {"vlan": 100, "mode": "access"},
            "2": {"vlan": 100, "mode": "access"},
            "3": {"vlan": [100, 200], "mode": "trunk"}
        },
        "s2": {
            "1": {"vlan": 200, "mode": "access"},
            "2": {"vlan": 200, "mode": "access"},
            "3": {"vlan": [100, 200], "mode": "trunk"}
        }
    }
}

await client.network.configure_vlans(vlan_config)
```

## Performance Testing Examples

### 1. Basic Performance Tests

```bash
# Simple bandwidth test
curl -X POST http://localhost:5000/api/performance/test/comprehensive \
  -H "Content-Type: application/json" \
  -d '{
    "src_host": "h1",
    "dst_host": "h2",
    "duration": 30,
    "test_types": ["bandwidth", "latency", "jitter", "packet_loss"]
  }'

# Stress test with multiple flows
curl -X POST http://localhost:5000/api/performance/test/stress \
  -H "Content-Type: application/json" \
  -d '{
    "duration": 60,
    "concurrent_flows": 10,
    "flow_size": "100MB",
    "pattern": "all_to_all"
  }'
```

### 2. Automated Performance Monitoring

```python
# Set up continuous monitoring
monitoring_config = {
    "interval": 5,  # seconds
    "hosts": ["web_server", "db_server", "client1", "client2"],
    "metrics": ["bandwidth", "latency", "packet_loss", "jitter"],
    "duration": 3600,  # 1 hour
    "alert_thresholds": {
        "bandwidth_utilization": 80,  # percent
        "latency": 100,  # ms
        "packet_loss": 1.0  # percent
    }
}

monitoring_session = await client.performance.start_monitoring(monitoring_config)

# Set up alerts
def handle_alert(alert):
    print(f"Performance Alert: {alert['type']} - {alert['message']}")
    if alert['severity'] == 'critical':
        # Trigger automatic remediation
        await client.network.optimize_performance(alert['affected_links'])

client.performance.on_alert(handle_alert)

# Generate performance report
report = await client.performance.generate_report(
    session_id=monitoring_session['session_id'],
    format='html',
    include_analysis=True
)
```

### 3. Custom Performance Scenarios

```python
# Web application performance test
async def web_app_performance_test():
    # Start web servers
    await client.devices.start_service("web_server", "apache2")
    await client.devices.start_service("db_server", "mysql")
    
    # Configure load balancer
    load_balancer_config = {
        "virtual_ip": "10.0.1.100",
        "backend_servers": ["10.0.1.10", "10.0.1.11", "10.0.1.12"],
        "algorithm": "round_robin",
        "health_check": {"path": "/health", "interval": 30}
    }
    
    await client.devices.configure_load_balancer("core_switch", load_balancer_config)
    
    # Run load test
    load_test_config = {
        "target": "10.0.1.100",
        "concurrent_users": 100,
        "ramp_up_time": 30,
        "test_duration": 300,
        "request_pattern": "realistic_web_traffic"
    }
    
    results = await client.performance.run_load_test(load_test_config)
    
    return {
        "response_time": results['avg_response_time'],
        "throughput": results['requests_per_second'],
        "error_rate": results['error_percentage'],
        "resource_utilization": results['server_cpu_usage']
    }

# Run the test
performance_results = await web_app_performance_test()
print("Web Application Performance Results:", performance_results)
```

## AI-Powered Network Management

### 1. Natural Language Topology Generation

```python
# Using AI to create complex topologies
ai_prompts = [
    "Create a campus network with 4 departments, each having 20 computers and 1 server, connected through a hierarchical switch topology",
    "Design a cloud provider network with multiple availability zones, load balancers, and redundant connections",
    "Build a factory automation network with PLCs, HMIs, and SCADA servers in separate security zones"
]

for prompt in ai_prompts:
    topology = await client.llm.generate_topology(prompt)
    
    # Validate the generated topology
    validation = await client.llm.validate_topology(topology['topology'])
    
    if validation['valid']:
        # Create and test the network
        await client.network.create_from_topology(topology['topology'])
        await client.network.start()
        
        # Run automated tests
        test_results = await client.diagnostic.comprehensive_test()
        
        print(f"Topology: {prompt}")
        print(f"Network Health Score: {test_results['health_score']}")
        print(f"Recommendations: {test_results['recommendations']}")
        
        # Save successful topologies
        if test_results['health_score'] > 90:
            await client.storage.save_topology(f"ai_generated_{len(ai_prompts)}")
```

### 2. Intelligent Network Optimization

```python
# AI-powered network optimization
async def optimize_network_with_ai():
    # Get current network state
    topology = await client.topology.get_current()
    performance_data = await client.performance.get_historical_data(timeframe="24h")
    
    # Ask AI for optimization suggestions
    optimization_request = {
        "current_topology": topology,
        "performance_history": performance_data,
        "optimization_goals": ["minimize_latency", "maximize_throughput", "improve_reliability"],
        "constraints": ["budget_limit", "hardware_compatibility"]
    }
    
    suggestions = await client.llm.suggest_optimizations(optimization_request)
    
    # Implement approved suggestions
    for suggestion in suggestions['recommendations']:
        if suggestion['impact_score'] > 0.8:  # High impact suggestions
            print(f"Implementing: {suggestion['description']}")
            
            if suggestion['type'] == 'flow_rule':
                await client.controller.install_flow(suggestion['config'])
            elif suggestion['type'] == 'topology_change':
                await client.topology.modify(suggestion['changes'])
            elif suggestion['type'] == 'qos_adjustment':
                await client.network.configure_qos(suggestion['qos_config'])
    
    # Measure improvement
    await asyncio.sleep(60)  # Wait for changes to take effect
    new_performance = await client.performance.run_comprehensive_test()
    
    improvement = calculate_improvement(performance_data, new_performance)
    print(f"Performance improvement: {improvement}%")
    
    return improvement

# Run optimization
improvement = await optimize_network_with_ai()
```

### 3. Conversational Network Management

```python
# Chat-based network management
async def chat_network_manager():
    conversation_history = []
    
    while True:
        user_input = input("Network Management > ")
        
        if user_input.lower() in ['quit', 'exit']:
            break
        
        # Send query to AI
        response = await client.llm.chat(
            message=user_input,
            context_type="network_management",
            use_history=True
        )
        
        print(f"AI Assistant: {response['response']}")
        
        # Execute suggested actions
        if 'suggested_actions' in response:
            for action in response['suggested_actions']:
                confirm = input(f"Execute: {action['description']}? (y/n): ")
                if confirm.lower() == 'y':
                    result = await execute_action(action)
                    print(f"Result: {result}")

# Example conversation:
# User: "The latency between h1 and h4 is too high"
# AI: "I'll analyze the network path and suggest optimizations. Let me run a traceroute first."
# [AI automatically runs diagnostics and suggests flow rule optimizations]

await chat_network_manager()
```

## Monitoring and Diagnostics

### 1. Real-time Network Monitoring

```python
# Set up comprehensive monitoring dashboard
async def setup_monitoring_dashboard():
    # Configure real-time metrics collection
    metrics_config = {
        "collection_interval": 1,  # seconds
        "metrics": [
            "bandwidth_utilization",
            "packet_loss_rate",
            "latency",
            "jitter",
            "flow_table_utilization",
            "controller_response_time"
        ],
        "alert_rules": [
            {
                "metric": "bandwidth_utilization",
                "threshold": 85,
                "duration": 60,
                "severity": "warning"
            },
            {
                "metric": "packet_loss_rate",
                "threshold": 1.0,
                "duration": 30,
                "severity": "critical"
            }
        ]
    }
    
    monitoring_session = await client.monitoring.start_session(metrics_config)
    
    # Set up WebSocket connection for real-time updates
    ws_connection = await client.connect_websocket()
    
    @ws_connection.on('metric_update')
    async def handle_metric_update(data):
        metric_name = data['metric']
        value = data['value']
        timestamp = data['timestamp']
        
        # Update dashboard
        dashboard.update_metric(metric_name, value, timestamp)
        
        # Check for anomalies
        if is_anomaly(metric_name, value):
            await handle_anomaly(metric_name, value)
    
    @ws_connection.on('alert')
    async def handle_alert(alert):
        print(f"ALERT: {alert['message']}")
        
        # Automatic remediation for known issues
        if alert['type'] == 'high_bandwidth_utilization':
            await optimize_traffic_distribution()
        elif alert['type'] == 'controller_disconnect':
            await restart_controller()
    
    return monitoring_session

# Start monitoring
monitoring = await setup_monitoring_dashboard()
```

### 2. Automated Network Health Checks

```python
# Comprehensive health monitoring
async def network_health_monitor():
    health_checks = [
        "connectivity_test",
        "performance_baseline",
        "security_scan",
        "configuration_validation",
        "capacity_analysis"
    ]
    
    health_report = {}
    
    for check in health_checks:
        print(f"Running {check}...")
        
        if check == "connectivity_test":
            result = await client.diagnostic.ping_all()
            health_report[check] = {
                "status": "pass" if result['success_rate'] > 95 else "fail",
                "details": result
            }
        
        elif check == "performance_baseline":
            baseline = await client.performance.run_baseline_tests()
            health_report[check] = {
                "status": "pass" if baseline['meets_sla'] else "warning",
                "details": baseline
            }
        
        elif check == "security_scan":
            security_results = await client.diagnostic.security_scan()
            health_report[check] = {
                "status": "pass" if len(security_results['vulnerabilities']) == 0 else "warning",
                "details": security_results
            }
        
        elif check == "configuration_validation":
            config_validation = await client.network.validate_configuration()
            health_report[check] = {
                "status": "pass" if config_validation['valid'] else "fail",
                "details": config_validation
            }
        
        elif check == "capacity_analysis":
            capacity = await client.network.analyze_capacity()
            health_report[check] = {
                "status": "pass" if capacity['utilization'] < 80 else "warning",
                "details": capacity
            }
    
    # Generate overall health score
    total_checks = len(health_checks)
    passed_checks = sum(1 for check in health_report.values() if check['status'] == 'pass')
    health_score = (passed_checks / total_checks) * 100
    
    # Create health report
    report = {
        "timestamp": datetime.now().isoformat(),
        "overall_health": health_score,
        "status": "healthy" if health_score > 90 else "degraded" if health_score > 70 else "critical",
        "checks": health_report,
        "recommendations": generate_recommendations(health_report)
    }
    
    return report

# Schedule regular health checks
import schedule
schedule.every(15).minutes.do(lambda: asyncio.create_task(network_health_monitor()))
```

### 3. Performance Bottleneck Detection

```python
# Automated bottleneck detection and resolution
async def detect_and_resolve_bottlenecks():
    # Collect comprehensive network metrics
    metrics = await client.monitoring.get_detailed_metrics()
    
    # Analyze for bottlenecks
    analysis = await client.llm.analyze_performance_data(metrics, analysis_type="bottleneck_detection")
    
    bottlenecks = analysis['bottlenecks']
    
    for bottleneck in bottlenecks:
        print(f"Bottleneck detected: {bottleneck['location']} - {bottleneck['type']}")
        print(f"Impact: {bottleneck['impact_description']}")
        print(f"Suggested resolution: {bottleneck['resolution']}")
        
        # Automatic resolution for common bottlenecks
        if bottleneck['type'] == 'link_congestion':
            # Implement traffic engineering
            await implement_traffic_engineering(bottleneck['affected_links'])
        
        elif bottleneck['type'] == 'switch_cpu_overload':
            # Optimize flow rules
            await optimize_flow_rules(bottleneck['affected_switch'])
        
        elif bottleneck['type'] == 'controller_latency':
            # Scale controller or optimize applications
            await optimize_controller_setup(bottleneck['controller_id'])
    
    # Verify improvements
    await asyncio.sleep(60)  # Wait for changes to take effect
    post_optimization_metrics = await client.monitoring.get_detailed_metrics()
    
    improvement_analysis = await client.llm.compare_performance_data(
        before=metrics,
        after=post_optimization_metrics
    )
    
    print("Optimization Results:", improvement_analysis['summary'])
    
    return improvement_analysis

# Run bottleneck detection
bottleneck_results = await detect_and_resolve_bottlenecks()
```

## Integration Examples

### 1. Integration with External Monitoring Systems

```python
# Prometheus integration
async def setup_prometheus_integration():
    prometheus_config = {
        "metrics_endpoint": "/metrics",
        "port": 9090,
        "update_interval": 5,
        "exported_metrics": [
            "network_bandwidth_utilization",
            "switch_flow_count",
            "controller_response_time",
            "host_packet_count",
            "link_status"
        ]
    }
    
    # Start Prometheus exporter
    exporter = await client.monitoring.start_prometheus_exporter(prometheus_config)
    
    # Configure Grafana dashboard
    grafana_dashboard = {
        "title": "Mininet Network Dashboard",
        "panels": [
            {"title": "Network Topology", "type": "graph"},
            {"title": "Bandwidth Utilization", "type": "singlestat"},
            {"title": "Latency Distribution", "type": "heatmap"},
            {"title": "Flow Table Utilization", "type": "gauge"}
        ]
    }
    
    await client.monitoring.create_grafana_dashboard(grafana_dashboard)
    
    return exporter

# SNMP integration
async def setup_snmp_integration():
    snmp_config = {
        "community": "public",
        "version": "2c",
        "oids": [
            "1.3.6.1.2.1.2.2.1.10",  # ifInOctets
            "1.3.6.1.2.1.2.2.1.16",  # ifOutOctets
            "1.3.6.1.2.1.2.2.1.13",  # ifInDiscards
            "1.3.6.1.2.1.2.2.1.19"   # ifOutDiscards
        ]
    }
    
    snmp_agent = await client.monitoring.start_snmp_agent(snmp_config)
    return snmp_agent
```

### 2. CI/CD Pipeline Integration

```python
# Network testing in CI/CD pipeline
async def network_ci_cd_tests():
    """
    Run network tests as part of CI/CD pipeline
    """
    test_results = {
        "topology_validation": False,
        "performance_tests": False,
        "security_tests": False,
        "scalability_tests": False
    }
    
    try:
        # 1. Validate topology configuration
        topology_config = load_topology_from_file("network_config.yaml")
        validation = await client.network.validate_topology(topology_config)
        test_results["topology_validation"] = validation['valid']
        
        if not validation['valid']:
            raise Exception(f"Topology validation failed: {validation['errors']}")
        
        # 2. Create and start network
        await client.network.create(topology_config)
        await client.network.start()
        
        # 3. Run performance tests
        performance_tests = [
            {"src": "client", "dst": "server", "expected_bandwidth": "950Mbps"},
            {"src": "client", "dst": "server", "expected_latency": "<5ms"}
        ]
        
        for test in performance_tests:
            result = await client.performance.test_comprehensive(
                src_host=test["src"],
                dst_host=test["dst"],
                duration=30
            )
            
            if not meets_requirements(result, test):
                raise Exception(f"Performance test failed: {test}")
        
        test_results["performance_tests"] = True
        
        # 4. Run security tests
        security_result = await client.diagnostic.security_scan()
        if len(security_result['critical_issues']) > 0:
            raise Exception(f"Security issues found: {security_result['critical_issues']}")
        
        test_results["security_tests"] = True
        
        # 5. Run scalability tests
        scalability_result = await client.network.test_scalability(
            max_hosts=100,
            max_flows=1000
        )
        
        if not scalability_result['passed']:
            raise Exception(f"Scalability test failed: {scalability_result['issues']}")
        
        test_results["scalability_tests"] = True
        
        print("✅ All network tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Network tests failed: {e}")
        return False
    
    finally:
        # Cleanup
        await client.network.stop()
        await client.network.delete()
        
        # Generate test report
        generate_test_report(test_results)

# Use in GitHub Actions or Jenkins
if __name__ == "__main__":
    import sys
    success = await network_ci_cd_tests()
    sys.exit(0 if success else 1)
```

### 3. Kubernetes Network Testing

```python
# Test Kubernetes CNI plugins
async def test_kubernetes_networking():
    """
    Test Kubernetes networking scenarios
    """
    # Simulate Kubernetes cluster networking
    k8s_topology = {
        "nodes": [
            {"name": "master", "ip": "10.0.1.10", "type": "master"},
            {"name": "worker1", "ip": "10.0.1.20", "type": "worker"},
            {"name": "worker2", "ip": "10.0.1.21", "type": "worker"}
        ],
        "pods": [
            {"name": "web-pod-1", "ip": "192.168.1.10", "node": "worker1"},
            {"name": "web-pod-2", "ip": "192.168.1.11", "node": "worker1"},
            {"name": "db-pod", "ip": "192.168.2.10", "node": "worker2"}
        ],
        "services": [
            {
                "name": "web-service",
                "cluster_ip": "10.96.1.10",
                "pods": ["web-pod-1", "web-pod-2"],
                "port": 80
            }
        ]
    }
    
    # Create network topology
    await client.network.create_k8s_simulation(k8s_topology)
    
    # Test scenarios
    test_scenarios = [
        # Pod-to-pod communication within same node
        {
            "name": "intra-node-communication",
            "src": "web-pod-1",
            "dst": "web-pod-2",
            "expected": "success"
        },
        # Pod-to-pod communication across nodes
        {
            "name": "inter-node-communication",
            "src": "web-pod-1",
            "dst": "db-pod",
            "expected": "success"
        },
        # Service discovery and load balancing
        {
            "name": "service-load-balancing",
            "src": "external-client",
            "dst": "web-service",
            "expected": "load_balanced"
        },
        # Network policy enforcement
        {
            "name": "network-policy-deny",
            "src": "db-pod",
            "dst": "web-pod-1",
            "policy": "deny",
            "expected": "blocked"
        }
    ]
    
    results = {}
    for scenario in test_scenarios:
        print(f"Testing: {scenario['name']}")
        
        if scenario.get('policy'):
            await client.network.apply_network_policy(scenario['policy'])
        
        result = await client.diagnostic.test_connectivity(
            src=scenario['src'],
            dst=scenario['dst']
        )
        
        results[scenario['name']] = {
            "passed": result['status'] == scenario['expected'],
            "details": result
        }
    
    return results

# Run Kubernetes networking tests
k8s_results = await test_kubernetes_networking()
print("Kubernetes Networking Test Results:", k8s_results)
```

## Automation and Scripting

### 1. Network Automation Scripts

```bash
#!/bin/bash
# automated_network_deployment.sh

# Automated network deployment script
set -e

echo "Starting automated network deployment..."

# 1. Environment preparation
echo "Preparing environment..."
sudo python3 -m venv /opt/mininet-web/venv
source /opt/mininet-web/venv/bin/activate
pip install -r requirements.txt

# 2. Start services
echo "Starting services..."
sudo python3 backend/app.py &
BACKEND_PID=$!

cd frontend
npm start &
FRONTEND_PID=$!
cd ..

cd mcp_server
python3 fastmcp_server.py &
MCP_PID=$!
cd ..

# Wait for services to start
sleep 10

# 3. Deploy network configurations
echo "Deploying network configurations..."

# Deploy production topology
curl -X POST http://localhost:5000/api/network/create \
  -H "Content-Type: application/json" \
  -d @configs/production-topology.json

# Start network
curl -X POST http://localhost:5000/api/network/start

# 4. Configure SDN rules
echo "Configuring SDN rules..."
for rule_file in configs/flow-rules/*.json; do
  echo "Installing flow rules from $rule_file"
  curl -X POST http://localhost:5000/api/controller/flows \
    -H "Content-Type: application/json" \
    -d @"$rule_file"
done

# 5. Set up monitoring
echo "Setting up monitoring..."
curl -X POST http://localhost:5000/api/stats/monitoring/start \
  -H "Content-Type: application/json" \
  -d '{"interval": 5, "devices": ["all"]}'

# 6. Run health checks
echo "Running health checks..."
curl -X GET http://localhost:5000/api/diagnostic/network-health

echo "Network deployment completed successfully!"

# Cleanup function
cleanup() {
  echo "Cleaning up..."
  kill $BACKEND_PID $FRONTEND_PID $MCP_PID 2>/dev/null || true
  sudo mn -c
}

trap cleanup EXIT
```

### 2. Python Automation Framework

```python
# network_automation.py
import asyncio
import yaml
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class NetworkDeployment:
    name: str
    topology_config: Dict
    flow_rules: List[Dict]
    monitoring_config: Dict
    validation_tests: List[Dict]

class NetworkAutomationFramework:
    def __init__(self, client):
        self.client = client
        self.deployments = {}
    
    async def load_deployment_config(self, config_file: str) -> NetworkDeployment:
        """Load network deployment configuration from YAML file"""
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        return NetworkDeployment(
            name=config['name'],
            topology_config=config['topology'],
            flow_rules=config.get('flow_rules', []),
            monitoring_config=config.get('monitoring', {}),
            validation_tests=config.get('validation_tests', [])
        )
    
    async def deploy_network(self, deployment: NetworkDeployment) -> Dict:
        """Deploy a complete network configuration"""
        results = {
            'deployment_name': deployment.name,
            'stages': {},
            'overall_success': False
        }
        
        try:
            # Stage 1: Create topology
            print(f"Deploying {deployment.name}: Creating topology...")
            topology_result = await self.client.network.create(
                {"topology": deployment.topology_config}
            )
            results['stages']['topology_creation'] = topology_result
            
            # Stage 2: Start network
            print("Starting network...")
            start_result = await self.client.network.start()
            results['stages']['network_start'] = start_result
            
            # Stage 3: Install flow rules
            if deployment.flow_rules:
                print("Installing flow rules...")
                flow_results = []
                for rule in deployment.flow_rules:
                    flow_result = await self.client.controller.install_flow(rule)
                    flow_results.append(flow_result)
                results['stages']['flow_rules'] = flow_results
            
            # Stage 4: Configure monitoring
            if deployment.monitoring_config:
                print("Setting up monitoring...")
                monitoring_result = await self.client.monitoring.start_session(
                    deployment.monitoring_config
                )
                results['stages']['monitoring'] = monitoring_result
            
            # Stage 5: Run validation tests
            if deployment.validation_tests:
                print("Running validation tests...")
                test_results = []
                for test in deployment.validation_tests:
                    test_result = await self.run_validation_test(test)
                    test_results.append(test_result)
                results['stages']['validation'] = test_results
            
            results['overall_success'] = True
            print(f"✅ Successfully deployed {deployment.name}")
            
        except Exception as e:
            print(f"❌ Failed to deploy {deployment.name}: {e}")
            results['error'] = str(e)
            
            # Cleanup on failure
            await self.cleanup_failed_deployment()
        
        return results
    
    async def run_validation_test(self, test_config: Dict) -> Dict:
        """Run a validation test"""
        test_type = test_config['type']
        
        if test_type == 'connectivity':
            return await self.client.diagnostic.test_connectivity(
                src=test_config['src'],
                dst=test_config['dst']
            )
        elif test_type == 'performance':
            return await self.client.performance.test_comprehensive(
                src_host=test_config['src'],
                dst_host=test_config['dst'],
                duration=test_config.get('duration', 30)
            )
        elif test_type == 'security':
            return await self.client.diagnostic.security_scan(
                target=test_config.get('target', 'all')
            )
        else:
            raise ValueError(f"Unknown test type: {test_type}")
    
    async def rollback_deployment(self, deployment_name: str) -> Dict:
        """Rollback a network deployment"""
        if deployment_name not in self.deployments:
            raise ValueError(f"Deployment {deployment_name} not found")
        
        # Stop network
        await self.client.network.stop()
        
        # Restore previous state if snapshot exists
        snapshots = await self.client.snapshots.list()
        rollback_snapshot = None
        
        for snapshot in snapshots:
            if snapshot['name'] == f"pre_{deployment_name}":
                rollback_snapshot = snapshot
                break
        
        if rollback_snapshot:
            await self.client.snapshots.restore(rollback_snapshot['id'])
            return {"status": "success", "restored_from": rollback_snapshot['name']}
        else:
            # Complete cleanup
            await self.client.network.delete()
            return {"status": "success", "action": "complete_cleanup"}

# Example usage
async def main():
    client = MininetWebClient('http://localhost:5000')
    automation = NetworkAutomationFramework(client)
    
    # Load deployment configurations
    deployments = [
        await automation.load_deployment_config('configs/production.yaml'),
        await automation.load_deployment_config('configs/testing.yaml'),
        await automation.load_deployment_config('configs/development.yaml')
    ]
    
    # Deploy networks
    for deployment in deployments:
        result = await automation.deploy_network(deployment)
        print(f"Deployment result for {deployment.name}:", result)
    
if __name__ == "__main__":
    asyncio.run(main())
```

This comprehensive usage guide provides practical examples for all aspects of the Mininet Web Framework, from basic network creation to advanced AI-powered automation and integration with external systems. Each example includes both web interface and programmatic approaches, making it suitable for users with different preferences and use cases.