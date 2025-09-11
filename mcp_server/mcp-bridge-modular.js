#!/usr/bin/env node

/**
 * Modular MCP Bridge
 * Main entry point for the MCP server
 */

import { MCPServer } from './bridge/mcpServer.js';
import { JSONRPCHandler } from './bridge/jsonrpcHandler.js';

// Configuration
const FASTMCP_BASE = "http://localhost:3001/mininet-fastmcp";

// Create server instance
const server = new MCPServer(FASTMCP_BASE);
const jsonrpcHandler = new JSONRPCHandler();

// Track initialization state
let initialized = false;

// Handle stdin/stdout communication
process.stdin.on('data', async (data) => {
  try {
    const lines = data.toString().trim().split('\n');
    
    for (const line of lines) {
      if (line.trim()) {
        const request = JSON.parse(line);
        
        // Handle initialization request
        if (request.method === 'initialize') {
          const response = server.getInitResponse();
          response.id = request.id;
          console.log(JSON.stringify(response));
          initialized = true;
          continue;
        }
        
        // Only process other requests after initialization
        if (!initialized) {
          console.log(JSON.stringify(
            jsonrpcHandler.createErrorResponse(
              request.id || null,
              -32002,
              "Server not initialized"
            )
          ));
          continue;
        }
        
        // Validate JSON-RPC 2.0 request
        const validation = jsonrpcHandler.validateRequest(request);
        if (!validation.valid) {
          console.log(JSON.stringify(
            jsonrpcHandler.createErrorResponse(
              request.id || null,
              validation.error.code,
              validation.error.message,
              validation.error.data
            )
          ));
          continue;
        }
        
        const response = await server.handleRequest(request);
        
        if (response) {
          console.log(JSON.stringify(response));
        }
      }
    }
  } catch (error) {
    console.error('Error processing request:', error);
    console.log(JSON.stringify(
      jsonrpcHandler.createParseErrorResponse()
    ));
  }
});

// Handle process termination
process.on('SIGINT', () => {
  console.error('MCP Bridge shutting down...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.error('MCP Bridge shutting down...');
  process.exit(0);
});

// Log startup message
console.error('MCP Bridge started, connecting to FastMCP server at', FASTMCP_BASE);

// Test connection on startup
server.testConnection().then(connected => {
  if (connected) {
    console.error('✅ Connected to FastMCP server');
  } else {
    console.error('❌ Failed to connect to FastMCP server');
  }
});
