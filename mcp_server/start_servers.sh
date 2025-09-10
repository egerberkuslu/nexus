#!/bin/bash

# MCPO and FastMCP Server Startup Script
# For Mininet Network Control

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Mininet MCPO & FastMCP Server Startup${NC}"
echo "=============================================="

# Check working directory
if [ ! -f "mcpo_config.json" ]; then
    echo -e "${RED}Error: mcpo_config.json not found${NC}"
    echo -e "${YELLOW}Run this script from the mcp_server directory${NC}"
    exit 1
fi

# Python check
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 not found${NC}"
    exit 1
fi

# Node.js check for MCP Inspector
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}Warning: Node.js not found. MCP Inspector will not be available.${NC}"
    echo -e "${YELLOW}Install Node.js to use MCP Inspector: https://nodejs.org/${NC}"
fi

# Check required packages
echo -e "${YELLOW}Checking required packages...${NC}"
if ! python3 -c "import fastmcp, httpx, mcpo" 2>/dev/null; then
    echo -e "${YELLOW}Installing packages...${NC}"
    pip install fastmcp httpx mcpo
fi

# Function definitions
stop_mininet_controller() {
    echo -e "${YELLOW}Stopping Mininet controller...${NC}"
    if curl -s -X POST "http://localhost:5000/api/network/stop" -H "Content-Type: application/json" | grep -q "success"; then
        echo -e "${GREEN}✅ Mininet controller stopped successfully!${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to stop controller${NC}"
        return 1
    fi
}

restart_mininet_controller() {
    echo -e "${YELLOW}Restarting Mininet controller...${NC}"

    # First stop
    stop_mininet_controller
    sleep 2

    # Then start
    if curl -s -X POST "http://localhost:5000/api/network/restart" -H "Content-Type: application/json" | grep -q "success"; then
        echo -e "${GREEN}✅ Mininet controller restarted successfully!${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to restart controller${NC}"
        return 1
    fi
}

start_mcp_inspector() {
    echo -e "${YELLOW}Starting MCP Inspector...${NC}"
    if command -v npx &> /dev/null; then
        export CLIENT_PORT=6274
        export SERVER_PORT=6277
        npx @modelcontextprotocol/inspector node mcp-bridge.js &
        MCP_INSPECTOR_PID=$!
        echo -e "${GREEN}✅ MCP Inspector started!${NC}"
        echo -e "${BLUE}MCP Inspector web interface: http://localhost:6274${NC}"
        echo -e "${BLUE}MCP Inspector proxy server: http://localhost:6277${NC}"
        return 0
    else
        echo -e "${RED}❌ npx not found! Install Node.js first${NC}"
        return 1
    fi
}

check_system_status() {
    echo -e "${BLUE}🔍 System Status Check${NC}"
    echo "=============================="

    # Flask server check
    echo "Flask Server (localhost:5000):"
    if curl -s "http://localhost:5000/api/network/status" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Running${NC}"
    else
        echo -e "${RED}  ❌ Not running${NC}"
    fi

    # MCPO server check
    echo "MCPO Server (localhost:3001):"
    if curl -s "http://localhost:3001/health" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Running${NC}"
    else
        echo -e "${RED}  ❌ Not running${NC}"
    fi

    # FastMCP check
    echo "FastMCP API:"
    if curl -s "http://localhost:3001/mininet-fastmcp/openapi.json" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Running${NC}"
    else
        echo -e "${RED}  ❌ Not running${NC}"
    fi

    # OpenWebUI check
    echo "OpenWebUI (localhost:8080):"
    if curl -s "http://localhost:8080" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Running${NC}"
    else
        echo -e "${RED}  ❌ Not running${NC}"
    fi

    # MCP Inspector check
    echo "MCP Inspector (localhost:6274):"
    if curl -s "http://localhost:6274" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Running${NC}"
    else
        echo -e "${RED}  ❌ Not running${NC}"
    fi

    echo ""
}

show_menu() {
    echo -e "${BLUE}🚀 Mininet MCPO & FastMCP Server Management${NC}"
    echo "=============================================="
    echo "1. Start all servers"
    echo "2. Stop Mininet controller"
    echo "3. Restart Mininet controller"
    echo "4. Start MCPO server only"
    echo "5. Start MCP Inspector"
    echo "6. Stop all servers"
    echo "7. Check system status"
    echo "0. Exit"
    echo "=============================================="
}

interactive_menu() {
    while true; do
        show_menu
        read -p "Your choice (0-7): " choice

        case $choice in
            0)
                echo -e "${BLUE}👋 Goodbye!${NC}"
                break
                ;;
            1)
                echo -e "${BLUE}🚀 Starting all servers...${NC}"
                main_start
                ;;
            2)
                echo -e "${YELLOW}Stopping Mininet controller${NC}"
                if curl -s "http://localhost:5000/api/network/status" > /dev/null 2>&1; then
                    stop_mininet_controller
                else
                    echo -e "${RED}❌ Flask server is not running!${NC}"
                fi
                read -p "Press Enter to continue..."
                ;;
            3)
                echo -e "${YELLOW}Restarting Mininet controller${NC}"
                if curl -s "http://localhost:5000/api/network/status" > /dev/null 2>&1; then
                    restart_mininet_controller
                else
                    echo -e "${RED}❌ Flask server is not running!${NC}"
                fi
                read -p "Press Enter to continue..."
                ;;
            4)
                echo -e "${YELLOW}Starting MCPO server${NC}"
                if curl -s "http://localhost:5000/api/network/status" > /dev/null 2>&1; then
                    start_mcpo_only
                else
                    echo -e "${RED}❌ Flask server is not running!${NC}"
                fi
                read -p "Press Enter to continue..."
                ;;
            5)
                echo -e "${YELLOW}Starting MCP Inspector${NC}"
                start_mcp_inspector
                read -p "Press Enter to continue..."
                ;;
            6)
                echo -e "${YELLOW}Stopping all servers${NC}"
                stop_existing_servers
                if curl -s "http://localhost:5000/api/network/status" > /dev/null 2>&1; then
                    stop_mininet_controller
                fi
                echo -e "${GREEN}✅ All servers stopped!${NC}"
                read -p "Press Enter to continue..."
                ;;
            7)
                check_system_status
                read -p "Press Enter to continue..."
                ;;
            *)
                echo -e "${RED}❌ Invalid choice!${NC}"
                read -p "Press Enter to continue..."
                ;;
        esac
    done
}

stop_existing_servers() {
    echo -e "${YELLOW}Stopping existing server processes...${NC}"
    pkill -f "mcpo\|fastmcp_server.py\|mcp-bridge.js" || true
    sleep 2
    echo -e "${GREEN}✅ Existing processes cleaned up!${NC}"
}

start_mcpo_only() {
    # Stop existing servers
    stop_existing_servers

    # Start MCPO server
    echo -e "${GREEN}Starting MCPO server...${NC}"
    echo "Port: 3001"
    echo "Config: mcpo_config.json"
    echo ""

    mcpo --config mcpo_config.json --host 0.0.0.0 --port 3001 &
    MCPO_PID=$!

    # Check if startup was successful
    echo -e "${YELLOW}Waiting for MCPO server connection...${NC}"
    for i in {1..10}; do
        if curl -s "http://localhost:3001/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ MCPO server started successfully!${NC}"
            print_success_info
            return
        fi
        sleep 1
    done

    echo -e "${RED}❌ MCPO server failed to start${NC}"
}

main_start() {
    # Flask server check
    echo -e "${YELLOW}Checking Flask server connection...${NC}"
    if ! curl -s "http://localhost:5000/api/network/status" > /dev/null 2>&1; then
        echo -e "${RED}Warning: Flask server (localhost:5000) is not running${NC}"
        echo -e "${YELLOW}To start Flask server:${NC}"
        echo -e "${YELLOW}  cd ../backend && python app.py${NC}"
        echo ""
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi

    # Stop existing servers
    stop_existing_servers

    # Start MCPO server
    echo -e "${GREEN}Starting MCPO server...${NC}"
    echo "Port: 3001"
    echo "Config: mcpo_config.json"
    echo ""

    # Port conflict check
    if curl -s "http://localhost:3001/health" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Port 3001 already in use, stopping previous server...${NC}"
        pkill -f "mcpo" || true
        sleep 3

        # If still running, try different port
        if curl -s "http://localhost:3001/health" > /dev/null 2>&1; then
            echo -e "${YELLOW}🔄 Trying different port: 3002${NC}"
            mcpo --config mcpo_config.json --host 0.0.0.0 --port 3002 &
            MCPO_PID=$!
            MCPO_PORT=3002
        else
            mcpo --config mcpo_config.json --host 0.0.0.0 --port 3001 &
            MCPO_PID=$!
            MCPO_PORT=3001
        fi
    else
        mcpo --config mcpo_config.json --host 0.0.0.0 --port 3001 &
        MCPO_PID=$!
        MCPO_PORT=3001
    fi

    # Check if startup was successful
    echo -e "${YELLOW}Waiting for MCPO server connection (Port: $MCPO_PORT)...${NC}"
    for i in {1..15}; do
        if curl -s "http://localhost:$MCPO_PORT/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ MCPO server started successfully! (Port: $MCPO_PORT)${NC}"
            break
        fi
        if [ $i -eq 15 ]; then
            echo -e "${RED}❌ MCPO server failed to start${NC}"
            return 1
        fi
        sleep 1
    done

    # Check FastMCP connection
    if curl -s "http://localhost:$MCPO_PORT/mininet-fastmcp/openapi.json" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ FastMCP server connected successfully!${NC}"
        
        # Start MCP Inspector as well
        echo -e "${YELLOW}Starting MCP Inspector...${NC}"
        start_mcp_inspector
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ MCP Inspector started successfully!${NC}"
        else
            echo -e "${YELLOW}⚠️  MCP Inspector failed to start, but MCPO server is running${NC}"
        fi
    else
        echo -e "${RED}❌ FastMCP server connection failed${NC}"
        return 1
    fi

    print_success_info $MCPO_PORT
}

print_success_info() {
    local port=${1:-3001}
    echo ""
    echo -e "${GREEN}🎉 All servers started successfully!${NC}"
    echo ""
    echo -e "${BLUE}Access points:${NC}"
    echo -e "• MCPO Server:     ${GREEN}http://localhost:$port${NC}"
    echo -e "• FastMCP API:     ${GREEN}http://localhost:$port/mininet-fastmcp${NC}"
    echo -e "• OpenAPI Spec:    ${GREEN}http://localhost:$port/mininet-fastmcp/openapi.json${NC}"
    echo -e "• Swagger Docs:    ${GREEN}http://localhost:$port/mininet-fastmcp/docs${NC}"
    echo ""
    echo -e "${BLUE}For OpenWebUI integration:${NC}"
    echo -e "• OpenWebUI:       ${GREEN}http://localhost:8080${NC}"
    echo -e "• Tool URL:        ${GREEN}http://localhost:$port/mininet-fastmcp/openapi.json${NC}"
    echo ""
    echo -e "${BLUE}For MCP Inspector debugging:${NC}"
    echo -e "• Web Interface:  ${GREEN}http://localhost:6274${NC}"
    echo -e "• Proxy Server:   ${GREEN}http://localhost:6277${NC}"
    echo -e "• Command:         ${GREEN}CLIENT_PORT=6274 SERVER_PORT=6277 npx @modelcontextprotocol/inspector node mcp-bridge.js${NC}"
    echo ""
    echo -e "${YELLOW}To stop servers: Ctrl+C${NC}"
    echo ""
}

# Flask server check
echo -e "${YELLOW}Checking Flask server connection...${NC}"
if ! curl -s "http://localhost:5000/api/network/status" > /dev/null 2>&1; then
    echo -e "${RED}Warning: Flask server (localhost:5000) is not running${NC}"
    echo -e "${YELLOW}To start Flask server:${NC}"
    echo -e "${YELLOW}  cd ../backend && python app.py${NC}"
    echo ""
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Stop existing MCPO processes
echo -e "${YELLOW}Stopping existing MCPO processes...${NC}"
pkill -f "mcpo\|fastmcp_server.py\|mcp-bridge.js" || true
sleep 2

# Start MCPO server
echo -e "${GREEN}Starting MCPO server...${NC}"
echo "Port: 3001"
echo "Config: mcpo_config.json"
echo ""

# Run in background
mcpo --config mcpo_config.json --host 0.0.0.0 --port 3001 &
MCPO_PID=$!

# Check if startup was successful
echo -e "${YELLOW}Waiting for MCPO server connection...${NC}"
for i in {1..10}; do
    if curl -s "http://localhost:3001/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ MCPO server started successfully!${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}❌ MCPO server failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# OpenAPI spec check
if curl -s "http://localhost:3001/mininet-fastmcp/openapi.json" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ FastMCP server connected successfully!${NC}"
else
    echo -e "${RED}❌ FastMCP server connection failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 All servers started successfully!${NC}"
echo ""
echo -e "${BLUE}Access points:${NC}"
echo -e "• MCPO Server:     ${GREEN}http://localhost:3001${NC}"
echo -e "• FastMCP API:     ${GREEN}http://localhost:3001/mininet-fastmcp${NC}"
echo -e "• OpenAPI Spec:    ${GREEN}http://localhost:3001/mininet-fastmcp/openapi.json${NC}"
echo -e "• Swagger Docs:    ${GREEN}http://localhost:3001/mininet-fastmcp/docs${NC}"
echo ""
echo -e "${BLUE}For OpenWebUI integration:${NC}"
echo -e "• OpenWebUI:       ${GREEN}http://localhost:8080${NC}"
echo -e "• Tool URL:        ${GREEN}http://localhost:3001/mininet-fastmcp/openapi.json${NC}"
echo ""
echo -e "${BLUE}For MCP Inspector debugging:${NC}"
echo -e "• Web Interface:  ${GREEN}http://localhost:6274${NC}"
echo -e "• Proxy Server:   ${GREEN}http://localhost:6277${NC}"
echo -e "• Command:         ${GREEN}CLIENT_PORT=6274 SERVER_PORT=6277 npx @modelcontextprotocol/inspector node mcp-bridge.js${NC}"
echo ""
echo -e "${YELLOW}To stop servers: Ctrl+C${NC}"
echo ""

# Main menu or direct startup
if [ "$1" = "--interactive" ] || [ "$1" = "-i" ]; then
    interactive_menu
else
    main_start
fi
