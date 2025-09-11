/**
 * FastMCP API Client
 * Handles communication with the FastMCP server
 */

export class FastMCPClient {
  constructor(baseUrl = "http://localhost:3001/mininet-fastmcp") {
    this.baseUrl = baseUrl;
  }

  /**
   * Make HTTP request to FastMCP API
   * @param {string} endpoint - API endpoint
   * @param {string} method - HTTP method
   * @param {Object} data - Request data
   * @returns {Promise<Object>} API response
   */
  async callAPI(endpoint, method = "POST", data = null) {
    try {
      let url = `${this.baseUrl}${endpoint}`;
      
      const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
      };
      
      // For FastMCP, all requests use POST with JSON body
      if (data) {
        options.body = JSON.stringify(data);
      }
      
      const response = await fetch(url, options);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      } else {
        const text = await response.text();
        return { result: text };
      }
    } catch (error) {
      console.error('FastMCP API call failed:', error);
      return { 
        error: error.message,
        success: false 
      };
    }
  }

  /**
   * Test connection to FastMCP server
   * @returns {Promise<boolean>} Connection status
   */
  async testConnection() {
    try {
      const response = await this.callAPI("/get_network_status", "GET");
      return !response.error;
    } catch (error) {
      console.error('FastMCP connection test failed:', error);
      return false;
    }
  }

  /**
   * Get server health status
   * @returns {Promise<Object>} Health status
   */
  async getHealthStatus() {
    try {
      const response = await fetch(`${this.baseUrl.replace('/mininet-fastmcp', '')}/health`);
      if (response.ok) {
        return { status: 'healthy', server: 'FastMCP' };
      } else {
        return { status: 'unhealthy', error: `HTTP ${response.status}` };
      }
    } catch (error) {
      return { status: 'unhealthy', error: error.message };
    }
  }
}
