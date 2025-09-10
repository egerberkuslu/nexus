#!/usr/bin/env python3
"""
Test script for Simple Mininet MCP Server
"""

import asyncio
import json
import subprocess
import sys
import time

def test_mcp_server():
    """Test the MCP server by running it and sending initialization requests"""
    
    print("🧪 Testing Simple Mininet MCP Server...")
    
    # Start the MCP server process
    process = subprocess.Popen(
        ["/home/ege/anaconda3/bin/python3", "simple_mininet_mcp.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Wait a moment for server to start
        time.sleep(2)
        
        # Send initialization request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("📤 Sending initialization request...")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"📥 Received response: {response.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
        
        # Send tools/list request
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        print("📤 Sending tools/list request...")
        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            tools = response.get('result', {}).get('tools', [])
            print(f"📥 Received {len(tools)} tools:")
            for i, tool in enumerate(tools[:5]):
                print(f"  {i+1}. {tool['name']}: {tool['description'][:50]}...")
        
        print("✅ MCP Server test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        # Clean up
        process.terminate()
        process.wait()

if __name__ == "__main__":
    test_mcp_server()
