# Modular MCP Bridge

This directory contains the modular MCP bridge implementation for Mininet network control.

## File Structure

```
bridge/
├── package.json              # Bridge dependencies
├── README.md                 # This file
├── mcpServer.js              # Main MCP server orchestrator
├── toolDefinitions.js        # Tool schemas and endpoint mappings
├── resourceDefinitions.js    # Resource schemas and endpoint mappings
├── fastmcpClient.js          # FastMCP API client
├── toolHandler.js            # Tool call handler
├── resourceHandler.js        # Resource read handler
└── jsonrpcHandler.js         # JSON-RPC 2.0 protocol handler
```

## Architecture

### Core Components

1. **MCPServer** (`mcpServer.js`)
   - Main orchestrator that coordinates all functionality
   - Handles incoming MCP requests and routes them appropriately

2. **ToolHandler** (`toolHandler.js`)
   - Manages tool definitions and handles tool calls
   - Forwards tool calls to FastMCP API

3. **ResourceHandler** (`resourceHandler.js`)
   - Manages resource definitions and handles resource reads
   - Forwards resource requests to FastMCP API

4. **FastMCPClient** (`fastmcpClient.js`)
   - HTTP client for communicating with FastMCP server
   - Handles API calls, connection testing, and health checks

5. **JSONRPCHandler** (`jsonrpcHandler.js`)
   - Handles JSON-RPC 2.0 protocol compliance
   - Validates requests and formats responses

6. **ToolDefinitions** (`toolDefinitions.js`)
   - Contains all tool schemas and endpoint mappings
   - Easy to extend with new tools

7. **ResourceDefinitions** (`resourceDefinitions.js`)
   - Contains all resource schemas and endpoint mappings
   - Easy to extend with new resources

## Usage

### Running the Modular Bridge

```bash
# From the mcp_server directory
node mcp-bridge-modular.js
```

### Adding New Tools

1. Add tool definition to `toolDefinitions.js`
2. Add endpoint mapping to `toolDefinitions.js`
3. The tool will automatically be available

### Adding New Resources

1. Add resource definition to `resourceDefinitions.js`
2. Add endpoint mapping to `resourceDefinitions.js`
3. The resource will automatically be available

## Benefits of Modular Structure

- **Maintainability**: Each component has a single responsibility
- **Extensibility**: Easy to add new tools and resources
- **Testability**: Individual components can be tested in isolation
- **Readability**: Clear separation of concerns
- **Reusability**: Components can be reused in other projects

## Dependencies

- Node.js 18+ (ES modules support)
- node-fetch for HTTP requests

## Configuration

The bridge connects to FastMCP server at `http://localhost:3001/mininet-fastmcp` by default.

To change the FastMCP server URL, modify the `FASTMCP_BASE` constant in `mcp-bridge-modular.js`.
