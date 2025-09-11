/**
 * Resource Handler
 * Handles MCP resource requests and forwards them to FastMCP API
 */

import { ResourceDefinitions } from './resourceDefinitions.js';
import { FastMCPClient } from './fastmcpClient.js';

export class ResourceHandler {
  constructor(fastmcpClient) {
    this.resourceDefinitions = new ResourceDefinitions();
    this.fastmcpClient = fastmcpClient;
  }

  /**
   * Handle resource read request
   * @param {Object} params - Resource read parameters
   * @returns {Promise<Object>} Resource read result
   */
  async handleResourceRead(params) {
    const { uri } = params;
    const resource = this.resourceDefinitions.getResource(uri);

    if (!resource) {
      throw new Error(`Unknown resource: ${uri}`);
    }

    const mapping = this.resourceDefinitions.getEndpointMapping(uri);
    if (!mapping) {
      throw new Error(`No endpoint mapping for resource: ${uri}`);
    }

    const result = await this.fastmcpClient.callAPI(
      mapping.endpoint, 
      mapping.method, 
      mapping.data
    );
    
    return {
      contents: [
        {
          uri,
          mimeType: resource.mimeType,
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }

  /**
   * Get all available resources
   * @returns {Array} List of resources
   */
  getAllResources() {
    return this.resourceDefinitions.getAllResources();
  }

  /**
   * Get specific resource definition
   * @param {string} uri - Resource URI
   * @returns {Object|null} Resource definition
   */
  getResource(uri) {
    return this.resourceDefinitions.getResource(uri);
  }
}
