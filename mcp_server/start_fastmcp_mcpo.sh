#!/bin/bash

# FastMCP Server with MCPO Startup Script
# This script starts the FastMCP server and bridges it to OpenAPI via MCPO

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default configuration
FLASK_URL=${FLASK_URL:-"http://localhost:5000"}
MCPO_PORT=${MCPO_PORT:-"8000"}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}
PYTHON_PATH=${PYTHON_PATH:-"python3"}
MCPO_CONFIG_FILE="mcpo_config.json"

echo -e "${GREEN}FastMCP Server with MCPO Startup${NC}"
echo "========================================"

# Check if Python is available
if ! command -v $PYTHON_PATH &> /dev/null; then
    echo -e "${RED}Error: Python not found. Please install Python 3.7+${NC}"
    exit 1
fi

# Check if required packages are installed
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! $PYTHON_PATH -c "import mcp, httpx, fastmcp, mcpo" 2>/dev/null; then
    echo -e "${YELLOW}Installing required packages...${NC}"
    pip install -r requirements_mcp.txt fastmcp mcpo
fi

# Check if Flask server is running
echo -e "${YELLOW}Checking Flask server connection...${NC}"
if ! curl -s "$FLASK_URL/api/network/status" > /dev/null 2>&1; then
    echo -e "${RED}Warning: Cannot connect to Flask server at $FLASK_URL${NC}"
    echo -e "${YELLOW}Please ensure your Flask server is running before starting the MCP server${NC}"
    echo -e "${YELLOW}You can start it with: cd backend && python app.py${NC}"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Set environment variables
export FLASK_URL="$FLASK_URL"
export LOG_LEVEL="$LOG_LEVEL"

echo -e "${GREEN}Starting FastMCP Server via MCPO...${NC}"
echo "Flask URL: $FLASK_URL"
echo "MCPO Port: $MCPO_PORT"
echo "Log Level: $LOG_LEVEL"
echo "MCPO Config: $MCPO_CONFIG_FILE"
echo ""

# Start MCPO with the FastMCP server configuration
exec mcpo --config "$MCPO_CONFIG_FILE" --port "$MCPO_PORT" --host "0.0.0.0"
