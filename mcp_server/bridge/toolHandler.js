/**
 * Tool Handler
 * Handles MCP tool calls and forwards them to FastMCP API
 */

import { ToolDefinitions } from './toolDefinitions.js';
import { FastMCPClient } from './fastmcpClient.js';

export class ToolHandler {
  constructor(fastmcpClient) {
    this.toolDefinitions = new ToolDefinitions();
    this.fastmcpClient = fastmcpClient;
  }

  /**
   * Handle tool call request
   * @param {Object} params - Tool call parameters
   * @returns {Promise<Object>} Tool call result
   */
  async handleToolCall(params) {
    const { name, arguments: args } = params;
    const tool = this.toolDefinitions.getTool(name);

    if (!tool) {
      throw new Error(`Unknown tool: ${name}`);
    }

    const mapping = this.toolDefinitions.getEndpointMapping(name);
    if (!mapping) {
      throw new Error(`No endpoint mapping for tool: ${name}`);
    }

    const result = await this.fastmcpClient.callAPI(
      mapping.endpoint, 
      mapping.method, 
      args || {}
    );
    
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }

  /**
   * Get all available tools
   * @returns {Array} List of tools
   */
  getAllTools() {
    return this.toolDefinitions.getAllTools();
  }

  /**
   * Get specific tool definition
   * @param {string} name - Tool name
   * @returns {Object|null} Tool definition
   */
  getTool(name) {
    return this.toolDefinitions.getTool(name);
  }
}
