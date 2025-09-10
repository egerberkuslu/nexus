#!/usr/bin/env python3
"""
Mininet MCP Server
A proper MCP server for Mininet network control following MCP best practices
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (required for STDIO servers)
logging.basicConfig(level=logging.INFO, stream=os.sys.stderr)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("mininet-network-control")

# Global HTTP client and Flask URL
FLASK_BASE_URL = os.getenv("FLASK_URL", "http://localhost:5000").rstrip('/')
http_client = httpx.AsyncClient(timeout=30.0)

async def make_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Make HTTP request to Flask API"""
    url = f"{FLASK_BASE_URL}{endpoint}"
    try:
        response = await http_client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

# ============================================================================
# 🏗️ NETWORK LIFECYCLE MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
async def create_network(
    topology_type: str = "simple",
    topology_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a new Mininet network topology with specified configuration.
    Supports simple, predefined, and custom topology types with automatic network startup.
    
    Args:
        topology_type: Type of topology to create ("simple", "predefined", "custom")
        topology_config: Detailed topology configuration (optional)
    """
    data = {"type": topology_type}
    if topology_config:
        data["topology"] = topology_config
    
    result = await make_request("POST", "/api/network/create", json=data)
    return json.dumps(result, indent=2)

@mcp.tool()
async def start_network() -> str:
    """
    Start the currently created Mininet network simulation.
    Initializes all network components, starts controllers, and enables host communication.
    """
    result = await make_request("POST", "/api/network/start")
    return json.dumps(result, indent=2)

@mcp.tool()
async def stop_network() -> str:
    """
    Gracefully stop the running Mininet network simulation.
    Safely shuts down all network components and cleans up resources.
    """
    result = await make_request("POST", "/api/network/stop")
    return json.dumps(result, indent=2)

@mcp.tool()
async def restart_network() -> str:
    """
    Restart the network simulation by stopping and starting it again.
    Useful for applying configuration changes or recovering from issues.
    """
    result = await make_request("POST", "/api/network/restart")
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_network_status() -> str:
    """
    Get comprehensive status information about the current network simulation.
    Provides real-time information about all network components and their states.
    """
    result = await make_request("GET", "/api/network/status")
    return json.dumps(result, indent=2)

@mcp.tool()
async def delete_network() -> str:
    """
    Permanently delete the current network topology and all associated data.
    This is a destructive operation that cannot be undone.
    """
    result = await make_request("POST", "/api/network/delete")
    return json.dumps(result, indent=2)

@mcp.tool()
async def reset_network() -> str:
    """
    Perform a complete network reset, clearing all data and returning to initial state.
    More comprehensive than delete_network as it also clears statistics and logs.
    """
    result = await make_request("POST", "/api/network/reset")
    return json.dumps(result, indent=2)

# ============================================================================
# 📋 TOPOLOGY INFORMATION AND MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
async def get_topology() -> str:
    """
    Get comprehensive information about the current network topology.
    Includes all nodes, links, controllers, and their detailed configurations.
    """
    result = await make_request("GET", "/api/topology/full")
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_topology_nodes(node_type: Optional[str] = None) -> str:
    """
    Get information about network nodes with optional filtering by type.
    Provides detailed information about hosts, switches, routers, and controllers.
    
    Args:
        node_type: Filter by specific node type (host, switch, router, controller)
    """
    params = {"type": node_type} if node_type else {}
    result = await make_request("GET", "/api/topology/nodes", params=params)
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_topology_links() -> str:
    """
    Get information about all network links in the current topology.
    Includes link statistics, bandwidth information, and connection status.
    """
    result = await make_request("GET", "/api/topology/links")
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_topology_controllers() -> str:
    """
    Get detailed information about all SDN controllers in the topology.
    Includes controller status, configuration, and connection details.
    """
    result = await make_request("GET", "/api/topology/controllers")
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_topology_stats() -> str:
    """
    Get comprehensive statistics about the current network topology.
    Provides metrics for performance analysis and network monitoring.
    """
    result = await make_request("GET", "/api/topology/stats")
    return json.dumps(result, indent=2)

# ============================================================================
# 🔧 DYNAMIC TOPOLOGY MODIFICATION TOOLS
# ============================================================================

@mcp.tool()
async def add_topology_node(
    node_id: str,
    node_type: str,
    ip_address: Optional[str] = None,
    mac_address: Optional[str] = None,
    additional_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Dynamically add a new node to the currently running network topology.
    Supports hosts, switches, routers, and controllers with custom configurations.
    
    Args:
        node_id: Unique identifier for the new node
        node_type: Type of node to add ("host", "switch", "router", "controller")
        ip_address: IP address for host nodes (optional)
        mac_address: MAC address for host nodes (optional)
        additional_config: Additional node-specific configuration (optional)
    """
    data = {"id": node_id, "type": node_type}
    if ip_address:
        data["ip"] = ip_address
    if mac_address:
        data["mac"] = mac_address
    if additional_config:
        data.update(additional_config)
    
    result = await make_request("POST", "/api/topology/nodes", json=data)
    return json.dumps(result, indent=2)

@mcp.tool()
async def remove_topology_node(node_id: str) -> str:
    """
    Dynamically remove a node from the currently running network topology.
    Automatically handles link cleanup and resource deallocation.
    
    Args:
        node_id: ID of the node to remove
    """
    result = await make_request("DELETE", f"/api/topology/nodes/{node_id}")
    return json.dumps(result, indent=2)

@mcp.tool()
async def add_topology_link(
    source_node: str,
    target_node: str,
    bandwidth: Optional[str] = None,
    link_type: Optional[str] = None,
    additional_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Dynamically add a network link between two nodes in the running topology.
    Supports bandwidth configuration and various link types.
    
    Args:
        source_node: ID of the source node
        target_node: ID of the target node
        bandwidth: Link bandwidth (e.g., "100Mbps", "1Gbps") (optional)
        link_type: Type of link to create (optional)
        additional_config: Additional link configuration (optional)
    """
    data = {"source": source_node, "target": target_node}
    if bandwidth:
        data["bandwidth"] = bandwidth
    if link_type:
        data["link_type"] = link_type
    if additional_config:
        data.update(additional_config)
    
    result = await make_request("POST", "/api/topology/links", json=data)
    return json.dumps(result, indent=2)

@mcp.tool()
async def remove_topology_link(source_node: str, target_node: str) -> str:
    """
    Dynamically remove a network link between two nodes in the running topology.
    Automatically updates network connectivity and statistics.
    
    Args:
        source_node: ID of the source node
        target_node: ID of the target node
    """
    data = {"source": source_node, "target": target_node}
    result = await make_request("DELETE", "/api/topology/links", json=data)
    return json.dumps(result, indent=2)

# ============================================================================
# 🤖 AI-POWERED TOPOLOGY GENERATION TOOLS
# ============================================================================

@mcp.tool()
async def generate_network_topology(
    description: str,
    generation_parameters: Optional[Dict[str, Any]] = None
) -> str:
    """
    Use AI/LLM to generate network topologies from natural language descriptions.
    Supports complex network requirements and automatically creates appropriate configurations.
    
    Args:
        description: Natural language description of desired topology
        generation_parameters: Additional generation parameters (optional)
    """
    data = {
        "description": description,
        "parameters": generation_parameters or {}
    }
    result = await make_request("POST", "/api/llm/generate-topology", json=data)
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_available_templates() -> str:
    """
    Get a list of available pre-built topology templates.
    Templates provide quick starting points for common network configurations.
    """
    result = await make_request("GET", "/api/llm/templates")
    return json.dumps(result, indent=2)

@mcp.tool()
async def suggest_topology_improvements(
    current_topology: Dict[str, Any],
    improvement_focus: Optional[str] = None
) -> str:
    """
    Use AI to analyze current topology and suggest improvements for performance,
    security, scalability, or other network aspects.
    
    Args:
        current_topology: Current topology configuration to analyze
        improvement_focus: Specific area to focus improvements on (optional)
    """
    data = {
        "topology_config": current_topology,
        "focus": improvement_focus
    }
    result = await make_request("POST", "/api/llm/suggest-improvements", json=data)
    return json.dumps(result, indent=2)

@mcp.tool()
async def chat_with_llm(
    message: str,
    use_conversation_history: bool = True,
    context_type: str = "general"
) -> str:
    """
    Provide a conversational interface with AI for network-related questions,
    troubleshooting, and general assistance.
    
    Args:
        message: Your question or message to the AI
        use_conversation_history: Whether to use previous conversation context
        context_type: Type of context for the AI response
    """
    data = {
        "message": message,
        "use_history": use_conversation_history,
        "context_type": context_type
    }
    result = await make_request("POST", "/api/llm/chat", json=data)
    return json.dumps(result, indent=2)

# ============================================================================
# 🖥️ HOST MANAGEMENT AND CONFIGURATION TOOLS
# ============================================================================

@mcp.tool()
async def get_host_status(host_id: str) -> str:
    """
    Get comprehensive status information about a specific host in the network.
    Includes system information, network configuration, and performance metrics.
    
    Args:
        host_id: Unique identifier of the host to query
    """
    result = await make_request("GET", f"/api/host-management/devices/{host_id}/host/status")
    return json.dumps(result, indent=2)

@mcp.tool()
async def execute_host_command(
    host_id: str,
    command: str,
    timeout: int = 30,
    capture_output: bool = True
) -> str:
    """
    Execute a shell command on a specific host in the network.
    Useful for configuration, testing, and troubleshooting.
    
    Args:
        host_id: ID of the host to execute command on
        command: Shell command to execute
        timeout: Command timeout in seconds (default: 30)
        capture_output: Whether to capture command output (default: True)
    """
    data = {
        "command": command,
        "timeout": timeout,
        "capture_output": capture_output
    }
    result = await make_request("POST", f"/api/network/hosts/{host_id}/cmd", json=data)
    return json.dumps(result, indent=2)

@mcp.tool()
async def configure_host_interface(
    host_id: str,
    interface_name: str,
    ip_address: str,
    netmask: str = "255.255.255.0",
    gateway: Optional[str] = None,
    additional_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Configure network interface settings on a specific host.
    Sets IP address, netmask, gateway, and other interface parameters.
    
    Args:
        host_id: ID of the host to configure
        interface_name: Name of the interface to configure
        ip_address: IP address to assign
        netmask: Network mask (default: "255.255.255.0")
        gateway: Default gateway IP address (optional)
        additional_config: Additional interface configuration (optional)
    """
    data = {
        "interface": interface_name,
        "ip": ip_address,
        "netmask": netmask
    }
    if gateway:
        data["gateway"] = gateway
    if additional_config:
        data.update(additional_config)
    
    result = await make_request("POST", f"/api/host-management/devices/{host_id}/host/interfaces", json=data)
    return json.dumps(result, indent=2)

@mcp.tool()
async def test_connectivity(
    source_host: str,
    target_host: str,
    test_type: str = "ping",
    packet_count: int = 4,
    timeout: int = 5
) -> str:
    """
    Test network connectivity between two hosts using various methods.
    Supports ping, traceroute, and custom connectivity tests.
    
    Args:
        source_host: ID of the source host
        target_host: ID or IP of the target host
        test_type: Type of connectivity test to perform (default: "ping")
        packet_count: Number of packets to send (for ping) (default: 4)
        timeout: Test timeout in seconds (default: 5)
    """
    data = {
        "count": packet_count,
        "test_type": test_type,
        "timeout": timeout
    }
    result = await make_request("POST", f"/api/network/ping/{source_host}/{target_host}", json=data)
    return json.dumps(result, indent=2)

# ============================================================================
# 🧪 NETWORK TESTING AND DIAGNOSTICS TOOLS
# ============================================================================

@mcp.tool()
async def run_ping_test() -> str:
    """
    Execute ping tests between all hosts in the network to verify connectivity.
    Provides comprehensive connectivity matrix and performance metrics.
    """
    result = await make_request("POST", "/api/network/ping")
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_flow_stats() -> str:
    """
    Get OpenFlow flow statistics from all switches in the network.
    Provides detailed information about packet flows and switch performance.
    """
    result = await make_request("GET", "/api/network/flows")
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_available_topologies() -> str:
    """
    Get a list of all available predefined network topologies.
    Includes both built-in and custom topology templates.
    """
    result = await make_request("GET", "/api/network/topologies")
    return json.dumps(result, indent=2)

@mcp.tool()
async def validate_topology(
    topology_type: str,
    topology_config: Dict[str, Any],
    validation_level: str = "full"
) -> str:
    """
    Validate a topology configuration before creation to ensure it's correct and complete.
    Checks for errors, missing parameters, and configuration issues.
    
    Args:
        topology_type: Type of topology being validated
        topology_config: Topology configuration to validate
        validation_level: Level of validation to perform (default: "full")
    """
    data = {
        "type": topology_type,
        "topology": topology_config,
        "validation_level": validation_level
    }
    result = await make_request("POST", "/api/network/validate", json=data)
    return json.dumps(result, indent=2)

# ============================================================================
# 📤📥 TOPOLOGY IMPORT/EXPORT TOOLS
# ============================================================================

@mcp.tool()
async def export_topology(
    export_format: str = "json",
    include_statistics: bool = True,
    include_configuration: bool = True
) -> str:
    """
    Export the current network topology configuration in various formats.
    Useful for backup, sharing, or integration with other tools.
    
    Args:
        export_format: Export format ("json", "yaml", "dot", "xml") (default: "json")
        include_statistics: Include network statistics in export (default: True)
        include_configuration: Include detailed configuration (default: True)
    """
    params = {
        "format": export_format,
        "include_stats": include_statistics,
        "include_config": include_configuration
    }
    result = await make_request("GET", "/api/topology/export", params=params)
    return json.dumps(result, indent=2)

@mcp.tool()
async def import_topology(
    topology_config: Dict[str, Any],
    validate_before_import: bool = True,
    merge_with_existing: bool = False
) -> str:
    """
    Import a network topology configuration from external data.
    Supports validation and merging with existing topology.
    
    Args:
        topology_config: Topology configuration to import
        validate_before_import: Validate configuration before importing (default: True)
        merge_with_existing: Merge with existing topology instead of replacing (default: False)
    """
    data = {
        "topology_config": topology_config,
        "validate": validate_before_import,
        "merge": merge_with_existing
    }
    result = await make_request("POST", "/api/topology/import", json=data)
    return json.dumps(result, indent=2)

# ============================================================================
# 🧹 CLEANUP AND SHUTDOWN
# ============================================================================

async def cleanup():
    """Cleanup resources on shutdown"""
    await http_client.aclose()

if __name__ == "__main__":
    import signal
    import sys
    
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        asyncio.create_task(cleanup())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info(f"Starting Mininet MCP Server with Flask URL: {FLASK_BASE_URL}")
    # Use stdio transport as required by MCP specification
    mcp.run(transport='stdio')
