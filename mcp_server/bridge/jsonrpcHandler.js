/**
 * JSON-RPC 2.0 Protocol Handler
 * Handles JSON-RPC request/response formatting and validation
 */

export class JSONRPCHandler {
  constructor() {
    this.protocolVersion = "2024-11-05";
  }

  /**
   * Validate JSON-RPC 2.0 request
   * @param {Object} request - JSON-RPC request
   * @returns {Object} Validation result
   */
  validateRequest(request) {
    if (!request.jsonrpc || request.jsonrpc !== "2.0") {
      return {
        valid: false,
        error: {
          code: -32600,
          message: "Invalid Request",
          data: "Missing or invalid jsonrpc field"
        }
      };
    }

    if (!request.method) {
      return {
        valid: false,
        error: {
          code: -32600,
          message: "Invalid Request",
          data: "Missing method field"
        }
      };
    }

    return { valid: true };
  }

  /**
   * Create JSON-RPC 2.0 success response
   * @param {*} id - Request ID
   * @param {*} result - Response result
   * @returns {Object} JSON-RPC response
   */
  createSuccessResponse(id, result) {
    return {
      jsonrpc: "2.0",
      id: id,
      result: result
    };
  }

  /**
   * Create JSON-RPC 2.0 error response
   * @param {*} id - Request ID
   * @param {number} code - Error code
   * @param {string} message - Error message
   * @param {*} data - Additional error data
   * @returns {Object} JSON-RPC error response
   */
  createErrorResponse(id, code, message, data = null) {
    const error = { code, message };
    if (data !== null) {
      error.data = data;
    }

    return {
      jsonrpc: "2.0",
      id: id,
      error: error
    };
  }

  /**
   * Create initialization response
   * @returns {Object} MCP initialization response
   */
  createInitResponse() {
    return {
      jsonrpc: "2.0",
      id: 1,
      result: {
        protocolVersion: this.protocolVersion,
        capabilities: {
          tools: {},
          resources: {}
        },
        serverInfo: {
          name: "mininet-mcp-bridge",
          version: "1.0.0"
        }
      }
    };
  }

  /**
   * Create parse error response
   * @returns {Object} JSON-RPC parse error response
   */
  createParseErrorResponse() {
    return {
      jsonrpc: "2.0",
      id: null,
      error: {
        code: -32700,
        message: "Parse error"
      }
    };
  }

  /**
   * Create internal error response
   * @param {*} id - Request ID
   * @param {string} message - Error message
   * @returns {Object} JSON-RPC internal error response
   */
  createInternalErrorResponse(id, message) {
    return {
      jsonrpc: "2.0",
      id: id,
      error: {
        code: -32603,
        message: message
      }
    };
  }

  /**
   * Create method not found error response
   * @param {*} id - Request ID
   * @param {string} method - Method name
   * @returns {Object} JSON-RPC method not found error response
   */
  createMethodNotFoundErrorResponse(id, method) {
    return {
      jsonrpc: "2.0",
      id: id,
      error: {
        code: -32601,
        message: "Method not found",
        data: `Method '${method}' not found`
      }
    };
  }

  /**
   * Create invalid params error response
   * @param {*} id - Request ID
   * @param {string} message - Error message
   * @returns {Object} JSON-RPC invalid params error response
   */
  createInvalidParamsErrorResponse(id, message) {
    return {
      jsonrpc: "2.0",
      id: id,
      error: {
        code: -32602,
        message: "Invalid params",
        data: message
      }
    };
  }
}
