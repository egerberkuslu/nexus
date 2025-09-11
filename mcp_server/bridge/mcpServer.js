/**
 * Main MCP Server
 * Orchestrates all MCP functionality
 */

import { FastMCPClient } from './fastmcpClient.js';
import { ToolHandler } from './toolHandler.js';
import { ResourceHandler } from './resourceHandler.js';
import { JSONRPCHandler } from './jsonrpcHandler.js';

export class MCPServer {
  constructor(baseUrl = "http://localhost:3001/mininet-fastmcp") {
    this.fastmcpClient = new FastMCPClient(baseUrl);
    this.toolHandler = new ToolHandler(this.fastmcpClient);
    this.resourceHandler = new ResourceHandler(this.fastmcpClient);
    this.jsonrpcHandler = new JSONRPCHandler();
  }

  /**
   * Handle incoming MCP request
   * @param {Object} request - JSON-RPC request
   * @returns {Promise<Object>} JSON-RPC response
   */
  async handleRequest(request) {
    try {
      const { method, params, id } = request;

      let result;
      switch (method) {
        case "tools/list":
          result = {
            tools: this.toolHandler.getAllTools()
          };
          break;

        case "tools/call":
          result = await this.toolHandler.handleToolCall(params);
          break;

        case "resources/list":
          result = {
            resources: this.resourceHandler.getAllResources()
          };
          break;

        case "resources/read":
          result = await this.resourceHandler.handleResourceRead(params);
          break;

        default:
          throw new Error(`Unknown method: ${method}`);
      }

      return this.jsonrpcHandler.createSuccessResponse(id, result);
    } catch (error) {
      console.error('Request handling error:', error);
      return this.jsonrpcHandler.createInternalErrorResponse(
        request.id, 
        error.message
      );
    }
  }

  /**
   * Get server initialization response
   * @returns {Object} MCP initialization response
   */
  getInitResponse() {
    return this.jsonrpcHandler.createInitResponse();
  }

  /**
   * Test connection to FastMCP server
   * @returns {Promise<boolean>} Connection status
   */
  async testConnection() {
    return await this.fastmcpClient.testConnection();
  }

  /**
   * Get server health status
   * @returns {Promise<Object>} Health status
   */
  async getHealthStatus() {
    return await this.fastmcpClient.getHealthStatus();
  }
}
