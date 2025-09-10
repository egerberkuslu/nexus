#!/usr/bin/env python3
"""
Test script to use MCPO server directly via HTTP
"""

import requests
import json

# MCPO server base URL
MCPO_BASE = "http://localhost:3001/mininet-fastmcp"

def call_mcpo_tool(tool_name, method="POST", data=None):
    """Call a tool on the MCPO server"""
    url = f"{MCPO_BASE}/{tool_name}"
    
    try:
        if method == "GET":
            response = requests.get(url)
        else:
            response = requests.post(url, json=data)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def main():
    print("=== Testing MCPO Server Directly ===\n")
    
    # Test 1: Generate network topology
    print("1. Generating network topology...")
    topology_data = {
        "description": "Create a network with h4 -> s1 -> r1 -> s2 -> h6, c1 -> r1 with POX controller",
        "use_llm": True,
        "context_type": "design"
    }
    
    result = call_mcpo_tool("generate_network_topology", data=topology_data)
    print(f"Result: {json.dumps(result, indent=2)[:200]}...")
    
    # Test 2: Get network status
    print("\n2. Getting network status...")
    status = call_mcpo_tool("get_network_status")
    print(f"Status: {json.dumps(status, indent=2)[:200]}...")
    
    # Test 3: Get topology
    print("\n3. Getting topology...")
    topology = call_mcpo_tool("get_topology", method="GET")
    print(f"Topology: {json.dumps(topology, indent=2)[:200]}...")

if __name__ == "__main__":
    main()
