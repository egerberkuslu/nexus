#!/bin/bash

# MCPO Startup Script for Mininet Integration
# This script starts MCPO with the proper configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting MCPO for Mininet Integration${NC}"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}Error: config.yaml not found. Please run this script from the mcp_server directory.${NC}"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 not found. Please install Python 3.7+${NC}"
    exit 1
fi

# Check if MCPO is installed
if ! python3 -c "import mcpo" 2>/dev/null; then
    echo -e "${YELLOW}Installing MCPO...${NC}"
    pip install mcpo
fi

# Check if Flask server is running
echo -e "${YELLOW}Checking Flask server connection...${NC}"
if ! curl -s "http://localhost:5000/api/network/status" > /dev/null 2>&1; then
    echo -e "${RED}Warning: Cannot connect to Flask server at http://localhost:5000${NC}"
    echo -e "${YELLOW}Please ensure your Flask server is running before starting MCPO${NC}"
    echo -e "${YELLOW}You can start it with: cd ../backend && python app.py${NC}"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Set environment variables
export MCPO_LOG_LEVEL="INFO"
export FLASK_URL="http://localhost:5000"

echo -e "${GREEN}Starting MCPO Server...${NC}"
echo "Configuration: config.yaml"
echo "Port: 3001"
echo "Host: 0.0.0.0"
echo "Flask URL: $FLASK_URL"
echo ""

# Start MCPO
echo -e "${BLUE}MCPO will be available at: http://localhost:3001${NC}"
echo -e "${BLUE}OpenAPI spec: http://localhost:3001/openapi.json${NC}"
echo -e "${BLUE}Health check: http://localhost:3001/health${NC}"
echo ""

exec python3 -m mcpo --config config.yaml --port 3001 --host 0.0.0.0
