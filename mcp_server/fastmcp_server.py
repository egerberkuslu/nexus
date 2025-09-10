#!/usr/bin/env python3
"""
FastMCP Server for Mininet Network Control
This server provides MCP tools for controlling Mininet network simulations
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastMCP app
mcp = FastMCP("Mininet Network Control", version="1.0.0")

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
async def start_network() -> Dict[str, Any]:
    """
    ▶️ START NETWORK SIMULATION
    
    Starts the currently created Mininet network simulation.
    Initializes all network components, starts controllers, and enables host communication.
    
    **Behavior:**
    - Powers on all network switches and hosts
    - Starts configured SDN controllers (Ryu, OpenDaylight, etc.)
    - Establishes network connectivity and routing
    - Updates network status and topology information
    
    **Prerequisites:**
    - Network topology must be created first
    - Controllers must be properly configured
    
    **Returns:**
        Dict containing start status, network info, and any warnings
    
    **Example:**
        ```python
        result = await start_network()
        if result.get("success"):
            print(f"Network started with {result.get('host_count', 0)} hosts")
        ```
    """
    return await make_request("POST", "/api/network/start")

@mcp.tool()
async def stop_network() -> Dict[str, Any]:
    """
    🛑 STOP NETWORK SIMULATION
    
    Gracefully stops the running Mininet network simulation.
    Safely shuts down all network components and cleans up resources.
    
    **Behavior:**
    - Stops all running hosts and switches
    - Terminates SDN controller processes
    - Cleans up network interfaces and namespaces
    - Preserves topology configuration for restart
    
    **Safety:**
    - Graceful shutdown prevents data loss
    - Network can be restarted without recreation
    - Resources are properly cleaned up
    
    **Returns:**
        Dict containing stop status and cleanup information
    
    **Example:**
        ```python
        result = await stop_network()
        if result.get("success"):
            print("Network stopped successfully")
        ```
    """
    return await make_request("POST", "/api/network/stop")

@mcp.tool()
async def restart_network() -> Dict[str, Any]:
    """
    🔄 RESTART NETWORK SIMULATION
    
    Restarts the network simulation by stopping and starting it again.
    Useful for applying configuration changes or recovering from issues.
    
    **Behavior:**
    - Stops the current network gracefully
    - Waits for complete shutdown
    - Starts the network with current configuration
    - Verifies successful restart
    
    **Use Cases:**
    - Apply new controller configurations
    - Recover from network issues
    - Refresh network state
    
    **Returns:**
        Dict containing restart status and network information
    
    **Example:**
        ```python
        result = await restart_network()
        if result.get("success"):
            print("Network restarted successfully")
        ```
    """
    return await make_request("POST", "/api/network/restart")

@mcp.tool()
async def get_network_status() -> Dict[str, Any]:
    """
    📊 GET DETAILED NETWORK STATUS
    
    Retrieves comprehensive status information about the current network simulation.
    Provides real-time information about all network components and their states.
    
    **Information Included:**
    - Network running status and uptime
    - Host count and individual host status
    - Switch count and OpenFlow connection status
    - Controller status and connection details
    - Interface statistics and link status
    - Error logs and warnings
    
    **Returns:**
        Dict containing detailed network status, component information, and metrics
    
    **Example:**
        ```python
        status = await get_network_status()
        print(f"Network running: {status.get('running', False)}")
        print(f"Hosts: {status.get('host_count', 0)}")
        print(f"Switches: {status.get('switch_count', 0)}")
        ```
    """
    return await make_request("GET", "/api/network/status")

@mcp.tool()
async def delete_network() -> Dict[str, Any]:
    """
    🗑️ DELETE NETWORK TOPOLOGY COMPLETELY
    
    Permanently deletes the current network topology and all associated data.
    This is a destructive operation that cannot be undone.
    
    **Behavior:**
    - Stops the network if running
    - Removes all topology configuration
    - Cleans up all network resources
    - Resets the Mininet manager state
    
    **Warning:**
    - This operation is irreversible
    - All network configuration will be lost
    - Network must be recreated from scratch
    
    **Use Cases:**
    - Complete network reset
    - Switching to completely different topology
    - Cleaning up after testing
    
    **Returns:**
        Dict containing deletion status and confirmation
    
    **Example:**
        ```python
        result = await delete_network()
        if result.get("success"):
            print("Network topology deleted completely")
        ```
    """
    return await make_request("POST", "/api/network/delete")

@mcp.tool()
async def reset_network() -> Dict[str, Any]:
    """
    🔄 RESET NETWORK AND CLEAR ALL DATA
    
    Performs a complete network reset, clearing all data and returning to initial state.
    More comprehensive than delete_network as it also clears statistics and logs.
    
    **Behavior:**
    - Stops and deletes current network
    - Clears all statistics and monitoring data
    - Resets configuration to defaults
    - Cleans up all temporary files and logs
    
    **Use Cases:**
    - Starting fresh after testing
    - Clearing accumulated statistics
    - Resolving configuration conflicts
    - Preparing for new test scenarios
    
    **Returns:**
        Dict containing reset status and confirmation
    
    **Example:**
        ```python
        result = await reset_network()
        if result.get("success"):
            print("Network completely reset to initial state")
        ```
    """
    return await make_request("POST", "/api/network/reset")

# ============================================================================
# 📋 TOPOLOGY INFORMATION AND MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
async def get_topology() -> Dict[str, Any]:
    """
    📋 GET COMPLETE TOPOLOGY INFORMATION
    
    Retrieves comprehensive information about the current network topology.
    Includes all nodes, links, controllers, and their detailed configurations.
    
    **Information Included:**
    - Complete node list with types, IDs, and configurations
    - All network links with bandwidth and status
    - Controller details and connection status
    - Switch configurations and OpenFlow settings
    - Host IP addresses and interface information
    - Topology statistics and metrics
    
    **Returns:**
        Dict containing complete topology structure with all components
    
    **Example:**
        ```python
        topology = await get_topology()
        nodes = topology.get("nodes", [])
        links = topology.get("links", [])
        print(f"Topology has {len(nodes)} nodes and {len(links)} links")
        ```
    """
    return await make_request("GET", "/api/topology/full")

@mcp.tool()
async def get_topology_nodes(node_type: Optional[str] = None) -> Dict[str, Any]:
    """
    📝 GET TOPOLOGY NODES WITH FILTERING
    
    Retrieves information about network nodes with optional filtering by type.
    Provides detailed information about hosts, switches, routers, and controllers.
    
    **Node Types:**
    - `host`: End-user devices and servers
    - `switch`: Network switches (OpenFlow, OVS, etc.)
    - `router`: Layer 3 routing devices
    - `controller`: SDN controllers (Ryu, OpenDaylight, etc.)
    
    **Args:**
        node_type (str, optional): Filter by specific node type
            - If None: Returns all nodes
            - If specified: Returns only nodes of that type
    
    **Returns:**
        Dict containing filtered node list with detailed information
    
    **Example:**
        ```python
        # Get all nodes
        all_nodes = await get_topology_nodes()
        
        # Get only hosts
        hosts = await get_topology_nodes("host")
        
        # Get only switches
        switches = await get_topology_nodes("switch")
        ```
    """
    params = {"type": node_type} if node_type else {}
    return await make_request("GET", "/api/topology/nodes", params=params)

@mcp.tool()
async def get_topology_links() -> Dict[str, Any]:
    """
    🔗 GET ALL TOPOLOGY LINKS
    
    Retrieves information about all network links in the current topology.
    Includes link statistics, bandwidth information, and connection status.
    
    **Information Included:**
    - Source and target node IDs
    - Link bandwidth and capacity
    - Connection status and health
    - Traffic statistics and utilization
    - Link type and configuration
    
    **Returns:**
        Dict containing complete link information with statistics
    
    **Example:**
        ```python
        links = await get_topology_links()
        for link in links.get("links", []):
            print(f"Link: {link['source']} -> {link['target']}")
            print(f"Bandwidth: {link.get('bandwidth', 'N/A')}")
        ```
    """
    return await make_request("GET", "/api/topology/links")

@mcp.tool()
async def get_topology_controllers() -> Dict[str, Any]:
    """
    🎮 GET TOPOLOGY CONTROLLERS
    
    Retrieves detailed information about all SDN controllers in the topology.
    Includes controller status, configuration, and connection details.
    
    **Information Included:**
    - Controller type and version
    - Connection status and health
    - OpenFlow port and protocol version
    - Running applications and modules
    - Performance metrics and statistics
    
    **Returns:**
        Dict containing controller information and status
    
    **Example:**
        ```python
        controllers = await get_topology_controllers()
        for ctrl in controllers.get("controllers", []):
            print(f"Controller: {ctrl['id']} ({ctrl['type']})")
            print(f"Status: {ctrl.get('status', 'unknown')}")
        ```
    """
    return await make_request("GET", "/api/topology/controllers")

@mcp.tool()
async def get_topology_stats() -> Dict[str, Any]:
    """
    📊 GET TOPOLOGY STATISTICS SUMMARY
    
    Retrieves comprehensive statistics about the current network topology.
    Provides metrics for performance analysis and network monitoring.
    
    **Statistics Included:**
    - Node counts by type (hosts, switches, controllers)
    - Link counts and total bandwidth
    - Network diameter and connectivity metrics
    - Traffic patterns and utilization
    - Error rates and performance indicators
    
    **Returns:**
        Dict containing topology statistics and metrics
    
    **Example:**
        ```python
        stats = await get_topology_stats()
        print(f"Total nodes: {stats.get('total_nodes', 0)}")
        print(f"Total links: {stats.get('total_links', 0)}")
        print(f"Network diameter: {stats.get('diameter', 'N/A')}")
        ```
    """
    return await make_request("GET", "/api/topology/stats")

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
) -> Dict[str, Any]:
    """
    ➕ ADD NODE TO RUNNING TOPOLOGY
    
    Dynamically adds a new node to the currently running network topology.
    Supports hosts, switches, routers, and controllers with custom configurations.
    
    **Node Types:**
    - `host`: End-user device with IP configuration
    - `switch`: Network switch (OVS, OpenFlow, etc.)
    - `router`: Layer 3 routing device
    - `controller`: SDN controller (Ryu, OpenDaylight, etc.)
    
    **Args:**
        node_id (str): Unique identifier for the new node
        node_type (str): Type of node to add ("host", "switch", "router", "controller")
        ip_address (str, optional): IP address for host nodes
        mac_address (str, optional): MAC address for host nodes
        additional_config (Dict[str, Any], optional): Additional node-specific configuration
    
    **Returns:**
        Dict containing addition status and node information
    
    **Example:**
        ```python
        # Add a host
        result = await add_topology_node("h3", "host", "10.0.1.3")
        
        # Add a switch with custom config
        config = {"switch_type": "ovs", "dpid": "0000000000000003"}
        result = await add_topology_node("s2", "switch", additional_config=config)
        ```
    """
    data = {"id": node_id, "type": node_type}
    if ip_address:
        data["ip"] = ip_address
    if mac_address:
        data["mac"] = mac_address
    if additional_config:
        data.update(additional_config)
    return await make_request("POST", "/api/topology/nodes", json=data)

@mcp.tool()
async def remove_topology_node(node_id: str) -> Dict[str, Any]:
    """
    ➖ REMOVE NODE FROM RUNNING TOPOLOGY
    
    Dynamically removes a node from the currently running network topology.
    Automatically handles link cleanup and resource deallocation.
    
    **Behavior:**
    - Removes the specified node
    - Automatically removes all connected links
    - Cleans up associated network resources
    - Updates topology statistics
    
    **Args:**
        node_id (str): ID of the node to remove
    
    **Warning:**
    - This operation removes the node and all its connections
    - Cannot be undone without recreating the node
    - May affect network connectivity
    
    **Returns:**
        Dict containing removal status and cleanup information
    
    **Example:**
        ```python
        result = await remove_topology_node("h3")
        if result.get("success"):
            print("Node h3 removed successfully")
        ```
    """
    return await make_request("DELETE", f"/api/topology/nodes/{node_id}")

@mcp.tool()
async def add_topology_link(
    source_node: str,
    target_node: str,
    bandwidth: Optional[str] = None,
    link_type: Optional[str] = None,
    additional_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    🔗 ADD LINK BETWEEN NODES
    
    Dynamically adds a network link between two nodes in the running topology.
    Supports bandwidth configuration and various link types.
    
    **Link Types:**
    - `ethernet`: Standard Ethernet link
    - `wireless`: Wireless connection simulation
    - `fiber`: High-speed fiber optic link
    - `custom`: Custom link with specific properties
    
    **Args:**
        source_node (str): ID of the source node
        target_node (str): ID of the target node
        bandwidth (str, optional): Link bandwidth (e.g., "100Mbps", "1Gbps")
        link_type (str, optional): Type of link to create
        additional_config (Dict[str, Any], optional): Additional link configuration
    
    **Returns:**
        Dict containing link creation status and information
    
    **Example:**
        ```python
        # Add simple link
        result = await add_topology_link("h1", "s1")
        
        # Add high-bandwidth link
        result = await add_topology_link("s1", "s2", "10Gbps", "fiber")
        ```
    """
    data = {"source": source_node, "target": target_node}
    if bandwidth:
        data["bandwidth"] = bandwidth
    if link_type:
        data["link_type"] = link_type
    if additional_config:
        data.update(additional_config)
    return await make_request("POST", "/api/topology/links", json=data)

@mcp.tool()
async def remove_topology_link(source_node: str, target_node: str) -> Dict[str, Any]:
    """
    🔗 REMOVE LINK BETWEEN NODES
    
    Dynamically removes a network link between two nodes in the running topology.
    Automatically updates network connectivity and statistics.
    
    **Args:**
        source_node (str): ID of the source node
        target_node (str): ID of the target node
    
    **Behavior:**
    - Removes the specified link
    - Updates network connectivity
    - Cleans up associated resources
    - Updates topology statistics
    
    **Returns:**
        Dict containing link removal status and information
    
    **Example:**
        ```python
        result = await remove_topology_link("h1", "s1")
        if result.get("success"):
            print("Link between h1 and s1 removed")
        ```
    """
    data = {"source": source_node, "target": target_node}
    return await make_request("DELETE", "/api/topology/links", json=data)

# ============================================================================
# 📤📥 TOPOLOGY IMPORT/EXPORT TOOLS
# ============================================================================

@mcp.tool()
async def export_topology(
    export_format: str = "json",
    include_statistics: bool = True,
    include_configuration: bool = True
) -> Dict[str, Any]:
    """
    📤 EXPORT TOPOLOGY CONFIGURATION
    
    Exports the current network topology configuration in various formats.
    Useful for backup, sharing, or integration with other tools.
    
    **Export Formats:**
    - `json`: JSON format (default, most compatible)
    - `yaml`: YAML format (human-readable)
    - `dot`: Graphviz DOT format (for visualization)
    - `xml`: XML format (for enterprise tools)
    
    **Args:**
        export_format (str): Export format ("json", "yaml", "dot", "xml")
        include_statistics (bool): Include network statistics in export
        include_configuration (bool): Include detailed configuration
    
    **Returns:**
        Dict containing exported topology data and metadata
    
    **Example:**
        ```python
        # Export as JSON
        result = await export_topology("json")
        
        # Export for visualization
        result = await export_topology("dot", include_statistics=False)
        ```
    """
    params = {
        "format": export_format,
        "include_stats": include_statistics,
        "include_config": include_configuration
    }
    return await make_request("GET", "/api/topology/export", params=params)

@mcp.tool()
async def import_topology(
    topology_config: Dict[str, Any],
    validate_before_import: bool = True,
    merge_with_existing: bool = False
) -> Dict[str, Any]:
    """
    📥 IMPORT TOPOLOGY CONFIGURATION
    
    Imports a network topology configuration from external data.
    Supports validation and merging with existing topology.
    
    **Import Behavior:**
    - Validates topology configuration before import
    - Can merge with existing topology or replace it
    - Automatically enhances configuration with defaults
    - Updates all network components
    
    **Args:**
        topology_config (Dict[str, Any]): Topology configuration to import
        validate_before_import (bool): Validate configuration before importing
        merge_with_existing (bool): Merge with existing topology instead of replacing
    
    **Returns:**
        Dict containing import status and topology information
    
    **Example:**
        ```python
        config = {
            "nodes": [
                {"id": "h1", "type": "host", "ip": "10.0.1.1"},
                {"id": "s1", "type": "switch"}
            ],
            "links": [{"source": "h1", "target": "s1"}]
        }
        result = await import_topology(config)
        ```
    """
    data = {
        "topology_config": topology_config,
        "validate": validate_before_import,
        "merge": merge_with_existing
    }
    return await make_request("POST", "/api/topology/import", json=data)

# ============================================================================
# 🤖 AI-POWERED TOPOLOGY GENERATION TOOLS
# ============================================================================

@mcp.tool()
async def generate_network_topology(
    description: str,
    generation_parameters: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
    template_name: Optional[str] = None,
    context_type: str = "design"
) -> Dict[str, Any]:
    """
    🎨 GENERATE NETWORK TOPOLOGY FROM NATURAL LANGUAGE
    
    Uses AI/LLM to generate network topologies from natural language descriptions.
    Integrates with the backend LLM service for intelligent topology generation.
    
    **Description Examples:**
    - "Create a 3-tier data center with 10 servers, 2 switches, and 1 router"
    - "Build a campus network with 5 buildings connected by fiber"
    - "Design a small office network with wireless access points"
    - "Create a mesh network for IoT devices"
    - "h4 -> s1 -> r1 -> s2 -> h6, c1 -> r1 with POX controller"
    
    **Args:**
        description (str): Natural language description of desired topology
        generation_parameters (Dict[str, Any], optional): Additional generation parameters
            - `node_count`: Target number of nodes
            - `complexity`: Network complexity level ("simple", "medium", "complex")
            - `topology_style`: Preferred topology style ("star", "mesh", "tree", "ring")
            - `bandwidth_requirements`: Bandwidth specifications
            - `controller_type`: SDN controller type ("pox", "ryu", "opendaylight", "osken")
        use_llm (bool): Whether to use LLM for generation (default: True)
        template_name (str, optional): Use a specific template as base
        context_type (str): Context type for LLM ("design", "troubleshooting", "optimization")
    
    **Returns:**
        Dict containing generated topology configuration, validation results, and metadata
    
    **Example:**
        ```python
        # Simple description
        result = await generate_network_topology("Create a simple 2-host network")
        
        # Complex description with specific controller
        params = {
            "node_count": 20,
            "complexity": "complex",
            "topology_style": "mesh",
            "controller_type": "pox"
        }
        result = await generate_network_topology(
            "Create a mesh network for a smart city",
            params
        )
        
        # Use template as base
        result = await generate_network_topology(
            "Modify this datacenter template for 50 servers",
            template_name="datacenter"
        )
        ```
    """
    # Prepare the request data
    data = {
        "description": description,
        "parameters": generation_parameters or {},
        "use_llm": use_llm,
        "context_type": context_type
    }
    
    # Add template name if provided
    if template_name:
        data["template_name"] = template_name
    
    # Call the LLM service endpoint
    result = await make_request("POST", "/api/llm/generate-topology", json=data)
    
    # If successful and network was created, add additional metadata
    if result.get("success", False) and result.get("network_created", False):
        # Get the created network status
        try:
            network_status = await get_network_status()
            result["network_status"] = network_status
        except:
            pass  # Don't fail if we can't get status
    
    return result

@mcp.tool()
async def generate_topology_from_template(
    template_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    🎨 GENERATE TOPOLOGY FROM TEMPLATE
    
    Generates a network topology using a predefined template as the base.
    Templates provide quick starting points for common network configurations.
    
    **Available Templates:**
    - `simple_switch`: A simple switch with multiple hosts
    - `linear`: A linear chain of switches with hosts
    - `star`: A central switch with multiple hosts
    - `tree`: A hierarchical tree structure
    - `mesh`: A fully connected mesh
    - `datacenter`: A datacenter topology with ToR switches
    
    **Args:**
        template_name (str): Name of the template to use
        parameters (Dict[str, Any], optional): Template-specific parameters
            - `hosts`: Number of hosts to create
            - `switches`: Number of switches to create
            - `depth`: Tree depth for hierarchical topologies
            - `fanout`: Fanout factor for tree structures
        use_llm (bool): Whether to use LLM for generation (default: True)
    
    **Returns:**
        Dict containing generated topology configuration and metadata
    
    **Example:**
        ```python
        # Use datacenter template
        result = await generate_topology_from_template("datacenter")
        
        # Use tree template with specific parameters
        params = {"hosts": 20, "depth": 3, "fanout": 4}
        result = await generate_topology_from_template("tree", params)
        ```
    """
    data = {
        "template_name": template_name,
        "parameters": parameters or {},
        "use_llm": use_llm
    }
    
    # Call the LLM service endpoint for template generation
    result = await make_request("POST", "/api/llm/generate-from-template", json=data)
    
    # If successful and network was created, add additional metadata
    if result.get("success", False) and result.get("network_created", False):
        try:
            network_status = await get_network_status()
            result["network_status"] = network_status
        except:
            pass  # Don't fail if we can't get status
    
    return result

@mcp.tool()
async def get_available_templates() -> Dict[str, Any]:
    """
    📋 GET AVAILABLE TOPOLOGY TEMPLATES
    
    Retrieves a list of available pre-built topology templates.
    Templates provide quick starting points for common network configurations.
    
    **Template Categories:**
    - `basic`: Simple topologies for learning
    - `enterprise`: Corporate network configurations
    - `data_center`: Data center topologies
    - `campus`: Campus and university networks
    - `iot`: Internet of Things networks
    - `wireless`: Wireless network configurations
    
    **Returns:**
        Dict containing available templates with descriptions and parameters
    
    **Example:**
        ```python
        templates = await get_available_templates()
        for template in templates.get("templates", []):
            print(f"Template: {template['name']}")
            print(f"Description: {template['description']}")
        ```
    """
    return await make_request("GET", "/api/llm/templates")

@mcp.tool()
async def suggest_topology_improvements(
    current_topology: Dict[str, Any],
    improvement_focus: Optional[str] = None
) -> Dict[str, Any]:
    """
    💡 SUGGEST TOPOLOGY IMPROVEMENTS
    
    Uses AI to analyze current topology and suggest improvements for performance,
    security, scalability, or other network aspects.
    
    **Improvement Focus Areas:**
    - `performance`: Optimize for speed and throughput
    - `security`: Enhance security and access control
    - `scalability`: Improve for growth and expansion
    - `reliability`: Increase fault tolerance and redundancy
    - `cost`: Optimize for cost efficiency
    - `general`: General improvements across all areas
    
    **Args:**
        current_topology (Dict[str, Any]): Current topology configuration to analyze
        improvement_focus (str, optional): Specific area to focus improvements on
    
    **Returns:**
        Dict containing improvement suggestions and implementation details
    
    **Example:**
        ```python
        topology = await get_topology()
        suggestions = await suggest_topology_improvements(
            topology, "performance"
        )
        for suggestion in suggestions.get("improvements", []):
            print(f"Improvement: {suggestion['title']}")
            print(f"Description: {suggestion['description']}")
        ```
    """
    data = {
        "topology_config": current_topology,
        "focus": improvement_focus
    }
    return await make_request("POST", "/api/llm/suggest-improvements", json=data)

@mcp.tool()
async def get_llm_service_status() -> Dict[str, Any]:
    """
    📊 GET LLM SERVICE STATUS
    
    Retrieves comprehensive status information about the LLM service.
    Includes service availability, configuration, and performance metrics.
    
    **Information Included:**
    - Current LLM service type and model
    - Service availability and health status
    - Available LLM services and their status
    - Template availability and counts
    - Service configuration details
    
    **Returns:**
        Dict containing LLM service status and configuration information
    
    **Example:**
        ```python
        status = await get_llm_service_status()
        print(f"Current service: {status.get('llm_service', {}).get('model_name')}")
        print(f"Service available: {status.get('llm_service', {}).get('available')}")
        ```
    """
    return await make_request("GET", "/api/llm/status")

@mcp.tool()
async def chat_with_llm(
    message: str,
    use_conversation_history: bool = True,
    context_type: str = "general"
) -> Dict[str, Any]:
    """
    💬 CHAT WITH AI FOR NETWORK QUESTIONS
    
    Provides a conversational interface with AI for network-related questions,
    troubleshooting, and general assistance.
    
    **Context Types:**
    - `general`: General network questions and advice
    - `troubleshooting`: Network problem diagnosis and solutions
    - `design`: Network design and architecture guidance
    - `configuration`: Specific configuration help
    - `optimization`: Performance optimization advice
    
    **Args:**
        message (str): Your question or message to the AI
        use_conversation_history (bool): Whether to use previous conversation context
        context_type (str): Type of context for the AI response
    
    **Returns:**
        Dict containing AI response and conversation metadata
    
    **Example:**
        ```python
        # General question
        response = await chat_with_llm("How do I optimize network performance?")
        
        # Troubleshooting with context
        response = await chat_with_llm(
            "My hosts can't ping each other",
            context_type="troubleshooting"
        )
        ```
    """
    data = {
        "message": message,
        "use_history": use_conversation_history,
        "context_type": context_type
    }
    return await make_request("POST", "/api/llm/chat", json=data)

# ============================================================================
# 🖥️ HOST MANAGEMENT AND CONFIGURATION TOOLS
# ============================================================================

@mcp.tool()
async def get_host_status(host_id: str) -> Dict[str, Any]:
    """
    📊 GET HOST STATUS AND INFORMATION
    
    Retrieves comprehensive status information about a specific host in the network.
    Includes system information, network configuration, and performance metrics.
    
    **Information Included:**
    - Host system status and uptime
    - Network interface configuration
    - IP addresses and routing table
    - Running services and processes
    - Performance metrics (CPU, memory, disk)
    - Network connectivity status
    
    **Args:**
        host_id (str): Unique identifier of the host to query
    
    **Returns:**
        Dict containing detailed host status and configuration
    
    **Example:**
        ```python
        status = await get_host_status("h1")
        print(f"Host h1 status: {status.get('status', 'unknown')}")
        print(f"IP address: {status.get('ip_address', 'N/A')}")
        ```
    """
    return await make_request("GET", f"/api/host-management/devices/{host_id}/host/status")

@mcp.tool()
async def execute_host_command(
    host_id: str,
    command: str,
    timeout: int = 30,
    capture_output: bool = True
) -> Dict[str, Any]:
    """
    💻 EXECUTE COMMAND ON HOST
    
    Executes a shell command on a specific host in the network.
    Useful for configuration, testing, and troubleshooting.
    
    **Command Types:**
    - Network configuration (ip, route, iptables)
    - Service management (systemctl, service)
    - File operations (ls, cat, grep, etc.)
    - Network testing (ping, traceroute, curl)
    - System monitoring (top, ps, df, etc.)
    
    **Args:**
        host_id (str): ID of the host to execute command on
        command (str): Shell command to execute
        timeout (int): Command timeout in seconds (default: 30)
        capture_output (bool): Whether to capture command output
    
    **Returns:**
        Dict containing command execution results and output
    
    **Example:**
        ```python
        # Check host IP configuration
        result = await execute_host_command("h1", "ip addr show")
        
        # Ping another host
        result = await execute_host_command("h1", "ping -c 3 h2")
        
        # Check running processes
        result = await execute_host_command("h1", "ps aux")
        ```
    """
    data = {
        "command": command,
        "timeout": timeout,
        "capture_output": capture_output
    }
    return await make_request("POST", f"/api/network/hosts/{host_id}/cmd", json=data)

@mcp.tool()
async def configure_host_interface(
    host_id: str,
    interface_name: str,
    ip_address: str,
    netmask: str = "255.255.255.0",
    gateway: Optional[str] = None,
    additional_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    🔧 CONFIGURE HOST NETWORK INTERFACE
    
    Configures network interface settings on a specific host.
    Sets IP address, netmask, gateway, and other interface parameters.
    
    **Configuration Options:**
    - IP address and subnet mask
    - Default gateway and routing
    - Interface up/down status
    - Additional interface parameters
    
    **Args:**
        host_id (str): ID of the host to configure
        interface_name (str): Name of the interface to configure
        ip_address (str): IP address to assign
        netmask (str): Network mask (default: "255.255.255.0")
        gateway (str, optional): Default gateway IP address
        additional_config (Dict[str, Any], optional): Additional interface configuration
    
    **Returns:**
        Dict containing configuration status and interface information
    
    **Example:**
        ```python
        # Basic interface configuration
        result = await configure_host_interface("h1", "eth0", "10.0.1.10")
        
        # Advanced configuration with gateway
        result = await configure_host_interface(
            "h1", "eth0", "192.168.1.100", 
            "255.255.255.0", "192.168.1.1"
        )
        ```
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
    return await make_request("POST", f"/api/host-management/devices/{host_id}/host/interfaces", json=data)

@mcp.tool()
async def test_connectivity(
    source_host: str,
    target_host: str,
    test_type: str = "ping",
    packet_count: int = 4,
    timeout: int = 5
) -> Dict[str, Any]:
    """
    🔍 TEST NETWORK CONNECTIVITY
    
    Tests network connectivity between two hosts using various methods.
    Supports ping, traceroute, and custom connectivity tests.
    
    **Test Types:**
    - `ping`: ICMP ping test (default)
    - `traceroute`: Route tracing to target
    - `tcp`: TCP connection test
    - `udp`: UDP connectivity test
    - `http`: HTTP connectivity test
    
    **Args:**
        source_host (str): ID of the source host
        target_host (str): ID or IP of the target host
        test_type (str): Type of connectivity test to perform
        packet_count (int): Number of packets to send (for ping)
        timeout (int): Test timeout in seconds
    
    **Returns:**
        Dict containing test results and connectivity information
    
    **Example:**
        ```python
        # Basic ping test
        result = await test_connectivity("h1", "h2")
        
        # Traceroute test
        result = await test_connectivity("h1", "h2", "traceroute")
        
        # HTTP connectivity test
        result = await test_connectivity("h1", "192.168.1.1", "http")
        ```
    """
    data = {
        "count": packet_count,
        "test_type": test_type,
        "timeout": timeout
    }
    return await make_request("POST", f"/api/network/ping/{source_host}/{target_host}", json=data)

# ============================================================================
# 🧪 NETWORK TESTING AND DIAGNOSTICS TOOLS
# ============================================================================

@mcp.tool()
async def run_ping_test() -> Dict[str, Any]:
    """
    🔍 RUN COMPREHENSIVE PING TEST
    
    Executes ping tests between all hosts in the network to verify connectivity.
    Provides comprehensive connectivity matrix and performance metrics.
    
    **Test Coverage:**
    - All-to-all host connectivity
    - Round-trip time measurements
    - Packet loss statistics
    - Connectivity matrix generation
    - Performance analysis
    
    **Returns:**
        Dict containing comprehensive ping test results and connectivity matrix
    
    **Example:**
        ```python
        results = await run_ping_test()
        connectivity = results.get("connectivity_matrix", {})
        print(f"Connectivity test completed: {results.get('success', False)}")
        ```
    """
    return await make_request("POST", "/api/network/ping")

@mcp.tool()
async def get_flow_stats() -> Dict[str, Any]:
    """
    📊 GET OPENFLOW FLOW STATISTICS
    
    Retrieves OpenFlow flow statistics from all switches in the network.
    Provides detailed information about packet flows and switch performance.
    
    **Statistics Included:**
    - Flow table entries and counts
    - Packet and byte counters
    - Flow match criteria
    - Action statistics
    - Switch performance metrics
    
    **Returns:**
        Dict containing flow statistics from all switches
    
    **Example:**
        ```python
        flows = await get_flow_stats()
        for switch_id, stats in flows.get("switches", {}).items():
            print(f"Switch {switch_id}: {stats.get('flow_count', 0)} flows")
        ```
    """
    return await make_request("GET", "/api/network/flows")

@mcp.tool()
async def get_available_topologies() -> Dict[str, Any]:
    """
    📋 GET AVAILABLE PREDEFINED TOPOLOGIES
    
    Retrieves a list of all available predefined network topologies.
    Includes both built-in and custom topology templates.
    
    **Topology Categories:**
    - `basic`: Simple topologies for learning
    - `enterprise`: Corporate network configurations
    - `data_center`: Data center architectures
    - `campus`: Campus and university networks
    - `wireless`: Wireless network topologies
    - `custom`: User-defined topology templates
    
    **Returns:**
        Dict containing available topologies with descriptions and parameters
    
    **Example:**
        ```python
        topologies = await get_available_topologies()
        for topo in topologies.get("topologies", []):
            print(f"Topology: {topo['name']}")
            print(f"Description: {topo['description']}")
        ```
    """
    return await make_request("GET", "/api/network/topologies")

@mcp.tool()
async def validate_topology(
    topology_type: str,
    topology_config: Dict[str, Any],
    validation_level: str = "full"
) -> Dict[str, Any]:
    """
    ✅ VALIDATE TOPOLOGY CONFIGURATION
    
    Validates a topology configuration before creation to ensure it's correct and complete.
    Checks for errors, missing parameters, and configuration issues.
    
    **Validation Levels:**
    - `basic`: Basic syntax and structure validation
    - `full`: Comprehensive validation including connectivity and configuration
    - `strict`: Strict validation with all requirements enforced
    
    **Validation Checks:**
    - Node ID uniqueness and format
    - Link connectivity and validity
    - IP address configuration
    - Controller and switch compatibility
    - Network reachability
    
    **Args:**
        topology_type (str): Type of topology being validated
        topology_config (Dict[str, Any]): Topology configuration to validate
        validation_level (str): Level of validation to perform
    
    **Returns:**
        Dict containing validation results and any errors found
    
    **Example:**
        ```python
        config = {
            "nodes": [{"id": "h1", "type": "host", "ip": "10.0.1.1"}],
            "links": [{"source": "h1", "target": "s1"}]
        }
        result = await validate_topology("custom", config, "full")
        if result.get("valid"):
            print("Topology configuration is valid")
        else:
            print(f"Validation errors: {result.get('errors', [])}")
        ```
    """
    data = {
        "type": topology_type,
        "topology": topology_config,
        "validation_level": validation_level
    }
    return await make_request("POST", "/api/network/validate", json=data)

# ============================================================================
# 📁 RESOURCE PROVIDERS
# ============================================================================

@mcp.resource("topology://current")
async def get_current_topology() -> str:
    """
    📁 CURRENT NETWORK TOPOLOGY RESOURCE
    
    Provides the current network topology as a resource that can be accessed by other tools.
    Returns topology information in JSON format for easy consumption.
    
    **Returns:**
        JSON string containing current topology configuration
    """
    result = await get_topology()
    return json.dumps(result, indent=2)

@mcp.resource("topology://status")
async def get_network_status_resource() -> str:
    """
    📁 NETWORK STATUS RESOURCE
    
    Provides the current network status as a resource.
    Returns status information in JSON format for monitoring and analysis.
    
    **Returns:**
        JSON string containing current network status
    """
    result = await get_network_status()
    return json.dumps(result, indent=2)

@mcp.resource("topology://templates")
async def get_templates_resource() -> str:
    """
    📁 TOPOLOGY TEMPLATES RESOURCE
    
    Provides available topology templates as a resource.
    Returns template information in JSON format for easy access.
    
    **Returns:**
        JSON string containing available topology templates
    """
    result = await get_available_templates()
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
        print("\nShutting down...")
        asyncio.create_task(cleanup())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info(f"Starting FastMCP Mininet Server with Flask URL: {FLASK_BASE_URL}")
    mcp.run()