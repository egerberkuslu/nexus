#!/usr/bin/env python3
"""
Convenience script to run the MCP server from the main project directory
"""

import sys
import os
import subprocess

def main():
    """Run the MCP server from the mcp_server directory"""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_dir = os.path.join(script_dir, 'mcp_server')
    
    # Change to the MCP server directory
    os.chdir(mcp_dir)
    
    # Run the MCP server
    try:
        subprocess.run([sys.executable, 'mcp_server.py'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running MCP server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nMCP server stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
