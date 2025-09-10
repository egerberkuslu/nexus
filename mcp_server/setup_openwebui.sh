#!/bin/bash

# Open WebUI Integration Script
# This script configures Open WebUI to use MCPO

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up Open WebUI Integration${NC}"
echo "====================================="

# Configuration
OPENWEBUI_URL="http://localhost:8080"
MCPO_URL="http://localhost:3001"
API_KEY="TBObawtR5n/WM7aN"

echo -e "${YELLOW}Checking MCPO server...${NC}"
if ! curl -s "$MCPO_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}Error: MCPO server is not running at $MCPO_URL${NC}"
    echo -e "${YELLOW}Please start MCPO first with: ./start_mcpo.sh${NC}"
    exit 1
fi

echo -e "${GREEN}MCPO server is running!${NC}"

echo -e "${YELLOW}Checking Open WebUI...${NC}"
if ! curl -s "$OPENWEBUI_URL" > /dev/null 2>&1; then
    echo -e "${RED}Error: Open WebUI is not running at $OPENWEBUI_URL${NC}"
    echo -e "${YELLOW}Please start Open WebUI first${NC}"
    exit 1
fi

echo -e "${GREEN}Open WebUI is running!${NC}"

echo -e "${YELLOW}Registering MCPO with Open WebUI...${NC}"

# Register MCPO as a function provider
curl -X POST "$OPENWEBUI_URL/api/v1/functions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"mcpo-bridge\",
    \"description\": \"MCPO Bridge for Mininet MCP Tools\",
    \"url\": \"$MCPO_URL\",
    \"api_key\": \"$API_KEY\"
  }" || echo -e "${YELLOW}Note: Function registration may have failed, but you can add it manually in Open WebUI${NC}"

echo -e "${GREEN}Integration setup complete!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Open WebUI: $OPENWEBUI_URL"
echo "2. Go to Settings → External Tools"
echo "3. Add Tool Server with URL: $MCPO_URL/openapi.json"
echo "4. Enable Function Calling in chat settings"
echo ""
echo -e "${BLUE}Test commands to try in Open WebUI:${NC}"
echo "- 'Show me the current network status'"
echo "- 'Create a simple network topology'"
echo "- 'List all available network tools'"
echo "- 'Test connectivity between hosts'"
