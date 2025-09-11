#!/usr/bin/env node

/**
 * Test script for modular MCP bridge
 */

import { MCPServer } from './mcpServer.js';
import { JSONRPCHandler } from './jsonrpcHandler.js';

async function testMCPServer() {
  console.log('🧪 Testing Modular MCP Bridge...\n');

  // Create server instance
  const server = new MCPServer();
  const jsonrpcHandler = new JSONRPCHandler();

  // Test 1: Server initialization
  console.log('1. Testing server initialization...');
  const initResponse = server.getInitResponse();
  console.log('✅ Init response:', JSON.stringify(initResponse, null, 2));
  console.log();

  // Test 2: Tool listing
  console.log('2. Testing tool listing...');
  const toolListRequest = {
    jsonrpc: "2.0",
    id: 1,
    method: "tools/list",
    params: {}
  };
  
  const toolListResponse = await server.handleRequest(toolListRequest);
  console.log('✅ Tool list response:', JSON.stringify(toolListResponse, null, 2));
  console.log();

  // Test 3: Resource listing
  console.log('3. Testing resource listing...');
  const resourceListRequest = {
    jsonrpc: "2.0",
    id: 2,
    method: "resources/list",
    params: {}
  };
  
  const resourceListResponse = await server.handleRequest(resourceListRequest);
  console.log('✅ Resource list response:', JSON.stringify(resourceListResponse, null, 2));
  console.log();

  // Test 4: Invalid request handling
  console.log('4. Testing invalid request handling...');
  const invalidRequest = {
    jsonrpc: "1.0", // Wrong version
    id: 3,
    method: "tools/list",
    params: {}
  };
  
  const validation = jsonrpcHandler.validateRequest(invalidRequest);
  console.log('✅ Invalid request validation:', validation);
  console.log();

  // Test 5: Connection test
  console.log('5. Testing FastMCP connection...');
  const connected = await server.testConnection();
  console.log(`✅ FastMCP connection: ${connected ? 'Connected' : 'Failed'}`);
  console.log();

  // Test 6: Health status
  console.log('6. Testing health status...');
  const healthStatus = await server.getHealthStatus();
  console.log('✅ Health status:', healthStatus);
  console.log();

  console.log('🎉 All tests completed!');
}

// Run tests
testMCPServer().catch(error => {
  console.error('❌ Test failed:', error);
  process.exit(1);
});
