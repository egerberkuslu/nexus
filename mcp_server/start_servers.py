#!/usr/bin/env python3
"""
MCPO and FastMCP Server Startup Script
Python version for Mininet Network Control
"""

import subprocess
import sys
import time
import requests
import os
from pathlib import Path

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(message, color):
    print(f"{color}{message}{Colors.NC}")

def check_dependencies():
    """Check and install required packages"""
    print_colored("Checking required packages...", Colors.YELLOW)

    required_packages = ['fastmcp', 'httpx', 'mcpo', 'requests']
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print_colored(f"Installing missing packages: {', '.join(missing_packages)}", Colors.YELLOW)
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
        print_colored("✅ Packages installed successfully!", Colors.GREEN)
    else:
        print_colored("✅ All packages available!", Colors.GREEN)

def check_flask_server():
    """Check if Flask server is running"""
    print_colored("Checking Flask server connection...", Colors.YELLOW)

    try:
        response = requests.get("http://localhost:5000/api/network/status", timeout=5)
        if response.status_code == 200:
            print_colored("✅ Flask server is running!", Colors.GREEN)
            return True
        else:
            print_colored(f"❌ Flask server returned error: {response.status_code}", Colors.RED)
            return False
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Cannot connect to Flask server: {str(e)}", Colors.RED)
        print_colored("To start Flask server:", Colors.YELLOW)
        print_colored("  cd ../backend && python app.py", Colors.YELLOW)
        return False

def stop_existing_servers():
    """Stop existing MCPO and FastMCP processes"""
    print_colored("Stopping existing server processes...", Colors.YELLOW)

    try:
        # Find and stop MCPO and FastMCP processes
        result = subprocess.run(['pgrep', '-f', 'mcpo|fastmcp_server.py|mcp-bridge.js'],
                              capture_output=True, text=True)

        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    subprocess.run(['kill', pid], check=True)
                    print_colored(f"✅ Process {pid} stopped", Colors.GREEN)
                except subprocess.CalledProcessError:
                    pass

        time.sleep(2)  # Wait for processes to fully stop
        print_colored("✅ Existing processes cleaned up!", Colors.GREEN)

    except subprocess.CalledProcessError:
        print_colored("ℹ️  No running processes found", Colors.BLUE)

def start_mcp_inspector():
    """Start MCP Inspector for debugging"""
    print_colored("Starting MCP Inspector...", Colors.GREEN)
    
    try:
        # Check if npx is available
        subprocess.run(['npx', '--version'], check=True, capture_output=True)
        
        # Set environment variables for MCP Inspector ports
        env = os.environ.copy()
        env['CLIENT_PORT'] = '6274'  # Web interface port
        env['SERVER_PORT'] = '6277'  # Proxy server port
        
        # Start MCP Inspector
        process = subprocess.Popen([
            'npx', '@modelcontextprotocol/inspector', 'node', 'mcp-bridge.js'
        ], env=env)
        
        print_colored("✅ MCP Inspector started!", Colors.GREEN)
        print_colored("MCP Inspector web interface: http://localhost:6274", Colors.BLUE)
        print_colored("MCP Inspector proxy server: http://localhost:6277", Colors.BLUE)
        return process
        
    except subprocess.CalledProcessError:
        print_colored("❌ npx not found! Install Node.js and npm first", Colors.RED)
        return None
    except FileNotFoundError:
        print_colored("❌ mcp-bridge.js not found!", Colors.RED)
        return None

def start_mcpo_server():
    """Start MCPO server"""
    print_colored("Starting MCPO server...", Colors.GREEN)
    print("Config: mcpo_config.json")

    # Check working directory
    if not Path("mcpo_config.json").exists():
        print_colored("❌ mcpo_config.json not found!", Colors.RED)
        print_colored("Run this script from the mcp_server directory", Colors.YELLOW)
        return False

    # Port conflict check
    mcpo_port = 3001
    if check_port_in_use(3001):
        print_colored("⚠️  Port 3001 already in use, stopping previous server...", Colors.YELLOW)
        stop_existing_servers()
        time.sleep(3)

        # If still running, try different port
        if check_port_in_use(3001):
            print_colored("🔄 Trying different port: 3002", Colors.YELLOW)
            mcpo_port = 3002

    print(f"Port: {mcpo_port}")
    print()

    try:
        # Start MCPO server
        process = subprocess.Popen([
            'mcpo',
            '--config', 'mcpo_config.json',
            '--host', '0.0.0.0',
            '--port', str(mcpo_port)
        ])

        print_colored(f"MCPO server started, waiting for connection (Port: {mcpo_port})...", Colors.YELLOW)

        # Wait for server to start
        for i in range(15):
            try:
                response = requests.get(f"http://localhost:{mcpo_port}/health", timeout=2)
                if response.status_code in [200, 404]:  # 404 is acceptable (health endpoint might not exist)
                    print_colored(f"✅ MCPO server started successfully! (Port: {mcpo_port})", Colors.GREEN)
                    break
            except requests.exceptions.RequestException:
                pass

            if i == 14:
                print_colored("❌ MCPO server failed to start", Colors.RED)
                return False

            time.sleep(1)

        # Check FastMCP connection
        try:
            response = requests.get(f"http://localhost:{mcpo_port}/mininet-fastmcp/openapi.json", timeout=5)
            if response.status_code == 200:
                print_colored("✅ FastMCP server connected successfully!", Colors.GREEN)
                
                # Start MCP Inspector as well
                print_colored("Starting MCP Inspector...", Colors.YELLOW)
                inspector_process = start_mcp_inspector()
                if inspector_process:
                    print_colored("✅ MCP Inspector started successfully!", Colors.GREEN)
                    return process, mcpo_port, inspector_process
                else:
                    print_colored("⚠️  MCP Inspector failed to start, but MCPO server is running", Colors.YELLOW)
                    return process, mcpo_port, None
            else:
                print_colored(f"❌ FastMCP server returned error: {response.status_code}", Colors.RED)
                return False, mcpo_port, None
        except requests.exceptions.RequestException as e:
            print_colored(f"❌ FastMCP server connection failed: {str(e)}", Colors.RED)
            return False, mcpo_port, None

    except subprocess.CalledProcessError as e:
        print_colored(f"❌ MCPO server startup error: {str(e)}", Colors.RED)
        return False, mcpo_port
    except FileNotFoundError:
        print_colored("❌ mcpo command not found!", Colors.RED)
        print_colored("Install mcpo package: pip install mcpo", Colors.YELLOW)
        return False, mcpo_port

def check_port_in_use(port):
    """Check if specified port is in use"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        return True
    except requests.exceptions.RequestException:
        return False

def stop_mininet_controller():
    """Stop Mininet controller"""
    print_colored("Stopping Mininet controller...", Colors.YELLOW)
    try:
        response = requests.post("http://localhost:5000/api/network/stop", 
                               json={}, timeout=10)
        if response.status_code == 200 and response.json().get("success"):
            print_colored("✅ Mininet controller stopped successfully!", Colors.GREEN)
            return True
        else:
            print_colored("❌ Failed to stop controller", Colors.RED)
            return False
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Error stopping controller: {str(e)}", Colors.RED)
        return False

def restart_mininet_controller():
    """Restart Mininet controller"""
    print_colored("Restarting Mininet controller...", Colors.YELLOW)
    
    # First stop
    stop_mininet_controller()
    time.sleep(2)
    
    # Then start
    try:
        response = requests.post("http://localhost:5000/api/network/restart", 
                               json={}, timeout=10)
        if response.status_code == 200 and response.json().get("success"):
            print_colored("✅ Mininet controller restarted successfully!", Colors.GREEN)
            return True
        else:
            print_colored("❌ Failed to restart controller", Colors.RED)
            return False
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Error restarting controller: {str(e)}", Colors.RED)
        return False

def show_menu():
    """Show menu"""
    print_colored("🚀 Mininet MCPO & FastMCP Server Management", Colors.BLUE)
    print("=" * 50)
    print("1. Start all servers")
    print("2. Stop Mininet controller")
    print("3. Restart Mininet controller")
    print("4. Start MCPO server only")
    print("5. Start MCP Inspector")
    print("6. Stop all servers")
    print("7. Check system status")
    print("0. Exit")
    print("=" * 50)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Mininet MCPO & FastMCP Server Management')
    parser.add_argument('--stop-controller', action='store_true',
                       help='Stop Mininet controller')
    parser.add_argument('--restart-controller', action='store_true',
                       help='Restart Mininet controller')
    parser.add_argument('--start-mcpo', action='store_true',
                       help='Start only MCPO server')
    parser.add_argument('--start-inspector', action='store_true',
                       help='Start MCP Inspector')
    parser.add_argument('--stop-all', action='store_true',
                       help='Stop all servers')
    parser.add_argument('--status', action='store_true',
                       help='Check system status')
    parser.add_argument('--interactive', action='store_true',
                       help='Interactive menu')

    args = parser.parse_args()

    # Check working directory
    current_dir = Path.cwd()
    if not (current_dir / "mcpo_config.json").exists():
        print_colored("❌ mcpo_config.json not found!", Colors.RED)
        print_colored("Run this script from the mcp_server directory", Colors.YELLOW)
        sys.exit(1)

    # Check dependencies
    check_dependencies()

    # Check Flask server
    flask_ok = check_flask_server()

    # Process command line arguments
    if args.stop_controller:
        if flask_ok:
            stop_mininet_controller()
        else:
            print_colored("❌ Flask server is not running!", Colors.RED)
        return

    elif args.restart_controller:
        if flask_ok:
            restart_mininet_controller()
        else:
            print_colored("❌ Flask server is not running!", Colors.RED)
        return

    elif args.start_mcpo:
        if flask_ok:
            stop_existing_servers()
            result = start_mcpo_server()
            if result and len(result) == 2:
                mcpo_process, mcpo_port = result
                print_success_info(mcpo_port)
                mcpo_process.wait()
            elif result and isinstance(result, tuple) and len(result) == 2:
                mcpo_process, mcpo_port = result
                print_success_info(mcpo_port)
                mcpo_process.wait()
            else:
                print_colored("❌ MCPO server failed to start!", Colors.RED)
        else:
            print_colored("❌ Flask server is not running!", Colors.RED)
        return

    elif args.start_inspector:
        stop_existing_servers()
        inspector_process = start_mcp_inspector()
        if inspector_process:
            print_colored("MCP Inspector is running. Press Ctrl+C to stop.", Colors.YELLOW)
            try:
                inspector_process.wait()
            except KeyboardInterrupt:
                print_colored("\n🛑 Stopping MCP Inspector...", Colors.YELLOW)
                inspector_process.terminate()
                inspector_process.wait()
                print_colored("✅ MCP Inspector stopped!", Colors.GREEN)
        else:
            print_colored("❌ MCP Inspector failed to start!", Colors.RED)
        return

    elif args.stop_all:
        stop_existing_servers()
        if flask_ok:
            stop_mininet_controller()
        return

    elif args.status:
        check_system_status()
        return

    elif args.interactive:
        interactive_menu()
        return

    # Interactive menu (default)
    if not any([args.stop_controller, args.restart_controller, args.start_mcpo,
                args.start_inspector, args.stop_all, args.status]):
        interactive_menu()
        return

    # Normal startup process
    if not flask_ok:
        response = input("Flask server is not running. Continue? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(1)

    # Stop existing servers
    stop_existing_servers()

    # Start MCPO server
    result = start_mcpo_server()
    if not result or not isinstance(result, tuple) or len(result) < 2:
        sys.exit(1)

    mcpo_process, mcpo_port = result[0], result[1]
    inspector_process = result[2] if len(result) > 2 else None
    
    print_success_info(mcpo_port)

    try:
        # Wait for processes
        if inspector_process:
            # Wait for either process to finish
            import select
            import sys
            while True:
                if mcpo_process.poll() is not None:
                    break
                if inspector_process.poll() is not None:
                    break
                time.sleep(1)
        else:
            mcpo_process.wait()
    except KeyboardInterrupt:
        print_colored("\n🛑 Stopping servers...", Colors.YELLOW)
        mcpo_process.terminate()
        if inspector_process:
            inspector_process.terminate()
        mcpo_process.wait()
        if inspector_process:
            inspector_process.wait()
        print_colored("✅ Servers stopped!", Colors.GREEN)

def interactive_menu():
    """Interactive menu"""
    while True:
        show_menu()
        try:
            choice = input("Your choice (0-7): ").strip()

            if choice == "0":
                print_colored("👋 Goodbye!", Colors.BLUE)
                break
            elif choice == "1":
                print_colored("🚀 Starting all servers...", Colors.BLUE)
                flask_ok = check_flask_server()
                if not flask_ok:
                    response = input("Flask server is not running. Continue? (y/N): ")
                    if response.lower() not in ['y', 'yes']:
                        continue

                stop_existing_servers()
                result = start_mcpo_server()
                if result and isinstance(result, tuple) and len(result) >= 2:
                    mcpo_process, mcpo_port = result[0], result[1]
                    inspector_process = result[2] if len(result) > 2 else None
                    print_success_info(mcpo_port)
                    print_colored("Servers are running. Press Ctrl+C to return to main menu.", Colors.YELLOW)
                    try:
                        if inspector_process:
                            while True:
                                if mcpo_process.poll() is not None or inspector_process.poll() is not None:
                                    break
                                time.sleep(1)
                        else:
                            mcpo_process.wait()
                    except KeyboardInterrupt:
                        pass
                else:
                    print_colored("❌ MCPO server failed to start!", Colors.RED)
                    input("Press Enter to continue...")
            elif choice == "2":
                if check_flask_server():
                    stop_mininet_controller()
                else:
                    print_colored("❌ Flask server is not running!", Colors.RED)
                input("Press Enter to continue...")
            elif choice == "3":
                if check_flask_server():
                    restart_mininet_controller()
                else:
                    print_colored("❌ Flask server is not running!", Colors.RED)
                input("Press Enter to continue...")
            elif choice == "4":
                if check_flask_server():
                    stop_existing_servers()
                    result = start_mcpo_server()
                    if result and isinstance(result, tuple) and len(result) == 2:
                        mcpo_process, mcpo_port = result
                        print_success_info(mcpo_port)
                        print_colored("MCPO server is running. Press Ctrl+C to return to main menu.", Colors.YELLOW)
                        mcpo_process.wait()
                    else:
                        print_colored("❌ MCPO server failed to start!", Colors.RED)
                else:
                    print_colored("❌ Flask server is not running!", Colors.RED)
                input("Press Enter to continue...")
            elif choice == "5":
                stop_existing_servers()
                inspector_process = start_mcp_inspector()
                if inspector_process:
                    print_colored("MCP Inspector is running. Press Ctrl+C to return to main menu.", Colors.YELLOW)
                    try:
                        inspector_process.wait()
                    except KeyboardInterrupt:
                        print_colored("\n🛑 Stopping MCP Inspector...", Colors.YELLOW)
                        inspector_process.terminate()
                        inspector_process.wait()
                        print_colored("✅ MCP Inspector stopped!", Colors.GREEN)
                else:
                    print_colored("❌ MCP Inspector failed to start!", Colors.RED)
                input("Press Enter to continue...")
            elif choice == "6":
                stop_existing_servers()
                if check_flask_server():
                    stop_mininet_controller()
                print_colored("✅ All servers stopped!", Colors.GREEN)
                input("Press Enter to continue...")
            elif choice == "7":
                check_system_status()
                input("Press Enter to continue...")
            else:
                print_colored("❌ Invalid choice!", Colors.RED)
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print_colored("\n👋 Goodbye!", Colors.BLUE)
            break
        except Exception as e:
            print_colored(f"❌ Error: {str(e)}", Colors.RED)
            input("Press Enter to continue...")

def check_system_status():
    """Check system status"""
    print_colored("🔍 System Status Check", Colors.BLUE)
    print("=" * 30)

    # Flask server check
    print("Flask Server (localhost:5000):")
    if check_flask_server():
        print_colored("  ✅ Running", Colors.GREEN)
    else:
        print_colored("  ❌ Not running", Colors.RED)

    # MCPO server check
    print("MCPO Server (localhost:3001):")
    try:
        response = requests.get("http://localhost:3001/health", timeout=3)
        print_colored("  ✅ Running", Colors.GREEN)
    except:
        print_colored("  ❌ Not running", Colors.RED)

    # FastMCP check
    print("FastMCP API:")
    try:
        response = requests.get("http://localhost:3001/mininet-fastmcp/openapi.json", timeout=3)
        if response.status_code == 200:
            print_colored("  ✅ Running", Colors.GREEN)
        else:
            print_colored(f"  ⚠️  Error response: {response.status_code}", Colors.YELLOW)
    except:
        print_colored("  ❌ Not running", Colors.RED)

    # OpenWebUI check
    print("OpenWebUI (localhost:8080):")
    try:
        response = requests.get("http://localhost:8080", timeout=3)
        print_colored("  ✅ Running", Colors.GREEN)
    except:
        print_colored("  ❌ Not running", Colors.RED)

    # MCP Inspector check
    print("MCP Inspector (localhost:6274):")
    try:
        response = requests.get("http://localhost:6274", timeout=3)
        print_colored("  ✅ Running", Colors.GREEN)
    except:
        print_colored("  ❌ Not running", Colors.RED)

    print()

def print_success_info(port=3001):
    """Show success information"""
    print()
    print_colored("🎉 All servers started successfully!", Colors.GREEN)
    print()
    print_colored("Access points:", Colors.BLUE)
    print_colored(f"• MCPO Server:     http://localhost:{port}", Colors.GREEN)
    print_colored(f"• FastMCP API:     http://localhost:{port}/mininet-fastmcp", Colors.GREEN)
    print_colored(f"• OpenAPI Spec:    http://localhost:{port}/mininet-fastmcp/openapi.json", Colors.GREEN)
    print_colored(f"• Swagger Docs:    http://localhost:{port}/mininet-fastmcp/docs", Colors.GREEN)
    print()
    print_colored("For OpenWebUI integration:", Colors.BLUE)
    print_colored(f"• OpenWebUI:       http://localhost:8080", Colors.GREEN)
    print_colored(f"• Tool URL:        http://localhost:{port}/mininet-fastmcp/openapi.json", Colors.GREEN)
    print()
    print_colored("For MCP Inspector debugging:", Colors.BLUE)
    print_colored(f"• Web Interface:  http://localhost:6274", Colors.GREEN)
    print_colored(f"• Proxy Server:   http://localhost:6277", Colors.GREEN)
    print_colored(f"• Command:         CLIENT_PORT=6274 SERVER_PORT=6277 npx @modelcontextprotocol/inspector node mcp-bridge.js", Colors.GREEN)
    print()
    print_colored("To stop servers: Ctrl+C", Colors.YELLOW)
    print()

if __name__ == "__main__":
    main()
