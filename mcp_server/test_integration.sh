#!/bin/bash

# Complete Integration Test Script
# This script tests the entire MCPO + Mininet integration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Testing Complete Integration${NC}"
echo "================================="

# Configuration
FLASK_URL="http://localhost:5000"
MCPO_URL="http://localhost:3001"
OPENWEBUI_URL="http://localhost:8080"

echo -e "${YELLOW}1. Testing Flask/Mininet Server...${NC}"
if curl -s "$FLASK_URL/api/network/status" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Flask server is running${NC}"
else
    echo -e "${RED}❌ Flask server is not running at $FLASK_URL${NC}"
    echo -e "${YELLOW}Please start it with: cd ../backend && python app.py${NC}"
    exit 1
fi

echo -e "${YELLOW}2. Testing FastMCP Server...${NC}"
if python3 -c "import fastmcp; print('FastMCP available')" 2>/dev/null; then
    echo -e "${GREEN}✅ FastMCP is installed${NC}"
else
    echo -e "${RED}❌ FastMCP is not installed${NC}"
    echo -e "${YELLOW}Installing FastMCP...${NC}"
    pip install fastmcp
fi

echo -e "${YELLOW}3. Testing MCPO Server...${NC}"
if curl -s "$MCPO_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MCPO server is running${NC}"
    
    echo -e "${YELLOW}4. Testing MCPO OpenAPI endpoint...${NC}"
    if curl -s "$MCPO_URL/openapi.json" | head -5 | grep -q "openapi"; then
        echo -e "${GREEN}✅ OpenAPI spec is available${NC}"
    else
        echo -e "${RED}❌ OpenAPI spec not found${NC}"
    fi
    
    echo -e "${YELLOW}5. Testing MCP server registration...${NC}"
    if curl -s "$MCPO_URL/mcp/servers" | grep -q "mininet-controller"; then
        echo -e "${GREEN}✅ MCP server is registered${NC}"
    else
        echo -e "${RED}❌ MCP server not registered${NC}"
    fi
    
    echo -e "${YELLOW}6. Testing available tools...${NC}"
    TOOLS=$(curl -s "$MCPO_URL/mcp/servers/mininet-controller/tools" 2>/dev/null | jq -r '.tools[].name' 2>/dev/null || echo "")
    if [ -n "$TOOLS" ]; then
        echo -e "${GREEN}✅ Tools available:${NC}"
        echo "$TOOLS" | head -5
    else
        echo -e "${RED}❌ No tools found${NC}"
    fi
    
else
    echo -e "${RED}❌ MCPO server is not running at $MCPO_URL${NC}"
    echo -e "${YELLOW}Please start it with: ./start_mcpo.sh${NC}"
    exit 1
fi

echo -e "${YELLOW}7. Testing Open WebUI...${NC}"
if curl -s "$OPENWEBUI_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Open WebUI is running${NC}"
else
    echo -e "${RED}❌ Open WebUI is not running at $OPENWEBUI_URL${NC}"
    echo -e "${YELLOW}Please start Open WebUI first${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Integration Test Complete!${NC}"
echo ""
echo -e "${BLUE}Summary:${NC}"
echo "• Flask Server: $FLASK_URL"
echo "• MCPO Bridge: $MCPO_URL"
echo "• Open WebUI: $OPENWEBUI_URL"
echo "• OpenAPI Spec: $MCPO_URL/openapi.json"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Open WebUI: $OPENWEBUI_URL"
echo "2. Add External Tool: $MCPO_URL/openapi.json"
echo "3. Enable Function Calling"
echo "4. Test with: 'Create a network topology'"
