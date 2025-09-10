# Mininet Web Framework

A comprehensive web-based framework for managing Mininet network simulations with a React frontend, Flask backend, and AI-powered topology generation.

## Project Structure

```
mininet-web-framework/
├── backend/                 # Flask backend API
├── frontend/               # React frontend application
├── mcp_server/            # Model Context Protocol server
├── examples/              # Usage examples
└── run_mcp_server.py      # Convenience script to run MCP server
```

## Features

### Backend (Flask)
- RESTful API for network management
- Mininet integration with multiple controller support
- LLM-powered topology generation
- Real-time network monitoring and diagnostics
- Host management and configuration
- Performance testing and statistics

### Frontend (React)
- Modern web interface for network visualization
- Real-time topology rendering
- Interactive network configuration
- Performance monitoring dashboard
- LLM integration for natural language topology generation

### MCP Server
- Model Context Protocol server for AI assistant integration
- 31 tools for comprehensive network management
- Natural language interface for topology control
- Dynamic network modification capabilities
- Export/import functionality for topology sharing

## Quick Start

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python app.py
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm start
```

### 3. MCP Server Setup
```bash
# Install MCP dependencies
cd mcp_server
pip install -r requirements_mcp.txt

# Run MCP server
./start_mcp_server.sh

# Or from the main directory
python run_mcp_server.py
```

## MCP Server

The MCP server provides an intelligent interface for AI assistants to control network simulations through natural language commands.

### Key Features
- **31 Tools** for network management, topology control, and testing
- **Natural Language Interface** for AI assistants
- **Dynamic Topology Management** - modify networks without restart
- **LLM Integration** - generate topologies from descriptions
- **Export/Import** - share and backup topology configurations

### Usage Examples
```python
# Create a custom datacenter topology
server = MininetMCPServer("http://localhost:5000")
result = await server._create_network({
    "type": "custom",
    "topology": {
        "nodes": [...],
        "links": [...]
    }
})
```

### Available Tools
- Network Management (create, start, stop, restart)
- Topology Management (get, modify, export/import)
- LLM Integration (generate from descriptions, chat)
- Host Management (configure, test connectivity)
- Network Testing (ping tests, flow statistics)

See `mcp_server/README.md` for detailed documentation.

## Documentation

- `backend/README.md` - Backend API documentation
- `frontend/README.md` - Frontend application documentation
- `mcp_server/README.md` - MCP server documentation
- `mcp_server/MCP_SERVER_SUMMARY.md` - Complete MCP server overview

## Examples

- `mcp_server/mcp_example_usage.py` - Basic MCP server usage
- `mcp_server/custom_topology_example.py` - Advanced topology examples
- `mcp_server/test_mcp_server.py` - MCP server test suite

## Requirements

- Python 3.7+
- Node.js 14+
- Mininet
- Docker (optional, for controller containers)

## License

This project is part of the Mininet Web Framework and follows the same licensing terms.
