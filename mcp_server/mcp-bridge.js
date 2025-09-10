#!/usr/bin/env node

import { readFileSync } from 'fs';

const FASTMCP_BASE = "http://localhost:3001/mininet-fastmcp";
const OPENAPI_SPEC_URL = "http://localhost:3001/mininet-fastmcp/openapi.json";

// Simple MCP server implementation that properly handles tool arguments
class SimpleMCPServer {
  constructor() {
    this.tools = new Map();
    this.resources = new Map();
  }

  addTool(name, handler) {
    this.tools.set(name, handler);
  }

  addResource(name, handler) {
    this.resources.set(name, handler);
  }

  async handleRequest(request) {
    const { method, params, id } = request;

    try {
      switch (method) {
        case 'initialize':
          return {
            jsonrpc: "2.0",
            id,
            result: {
              protocolVersion: "2024-11-05",
              capabilities: {
                tools: {},
                resources: {}
              },
              serverInfo: {
                name: "mininet-mcpo-bridge",
                version: "1.0.0"
              }
            }
          };

        case 'tools/list':
          const toolList = Array.from(this.tools.keys()).map(name => {
            const tool = this.tools.get(name);
            return {
              name,
              description: tool.description || `Tool: ${name}`,
              inputSchema: tool.inputSchema || {
                type: "object",
                properties: {
                  description: { type: "string", description: "Network description" }
                },
                required: ["description"]
              }
            };
          });

          return {
            jsonrpc: "2.0",
            id,
            result: {
              tools: toolList
            }
          };

        case 'tools/call':
          const { name, arguments: toolArgs } = params;
          console.error(`DEBUG: Tool call - name: ${name}, args:`, JSON.stringify(toolArgs, null, 2));

          const tool = this.tools.get(name);
          if (tool) {
            const result = await tool.handler(toolArgs);
            return {
              jsonrpc: "2.0",
              id,
              result: {
                content: [{
                  type: "text",
                  text: JSON.stringify(result, null, 2)
                }]
              }
            };
          }

          return {
            jsonrpc: "2.0",
            id,
            error: {
              code: -32601,
              message: `Tool '${name}' not found`
            }
          };

        case 'resources/list':
          return {
            jsonrpc: "2.0",
            id,
            result: {
              resources: Array.from(this.resources.keys()).map(name => ({
                uri: name,
                name: name,
                mimeType: "application/json"
              }))
            }
          };

        default:
          return {
            jsonrpc: "2.0",
            id,
            error: {
              code: -32601,
              message: `Method '${method}' not found`
            }
          };
      }
    } catch (error) {
      console.error('Error handling request:', error);
      return {
        jsonrpc: "2.0",
        id,
        error: {
          code: -32603,
          message: "Internal error",
          data: error.message
        }
      };
    }
  }

  async callMCPOAPI(endpoint, method = "POST", data = null) {
    try {
      const url = `${FASTMCP_BASE}${endpoint}`;
      const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
      };
      
      if (data && (method === 'POST' || method === 'PUT')) {
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
      console.error('API call failed:', error);
      return { 
        error: error.message,
        success: false 
      };
    }
  }

  async start() {
    console.error("Starting Mininet MCPO Bridge Server...");
    
    // Add all the tools
    this.addTool('generate_network_topology', {
      description: "Generate network topology from natural language description using AI/LLM",
      inputSchema: {
        type: "object",
        properties: {
          description: { 
            type: "string", 
            description: "Natural language description of desired topology",
            title: "Network Description"
          },
          generation_parameters: { 
            type: "object", 
            description: "Additional generation parameters"
          },
          use_llm: { type: "boolean", default: true, description: "Whether to use LLM for generation" },
          template_name: { type: "string", description: "Use a specific template as base" },
          context_type: { type: "string", enum: ["design", "troubleshooting", "optimization"], default: "design", description: "Context type for LLM" }
        },
        required: ["description"]
      },
      handler: async (args) => {
        const description = args?.description;
        
        if (!description || description.trim() === "") {
          return {
            error: "Missing required parameter: description",
            message: "Please provide a description of the network topology you want to generate"
          };
        }

        const data = {
          description: description,
          parameters: args?.generation_parameters || {},
          use_llm: args?.use_llm ?? true,
          context_type: args?.context_type || "design"
        };

        if (args?.template_name) {
          data.template_name = args.template_name;
        }

        return await this.callMCPOAPI("/generate_network_topology", "POST", data);
      }
    });

    // Add other tools...
    this.addTool('get_network_status', {
      description: "Get current network status",
      inputSchema: { type: "object", properties: {} },
      handler: async () => await this.callMCPOAPI("/get_network_status", "POST")
    });

    this.addTool('start_network', {
      description: "Start the network simulation",
      inputSchema: { type: "object", properties: {} },
      handler: async () => await this.callMCPOAPI("/start_network", "POST")
    });

    this.addTool('stop_network', {
      description: "Stop the network simulation",
      inputSchema: { type: "object", properties: {} },
      handler: async () => await this.callMCPOAPI("/stop_network", "POST")
    });

    this.addTool('get_topology', {
      description: "Get complete topology information",
      inputSchema: { type: "object", properties: {} },
      handler: async () => await this.callMCPOAPI("/get_topology", "GET")
    });

    // Handle stdin/stdout communication
    process.stdin.setEncoding('utf8');
    
    let buffer = '';
    process.stdin.on('data', async (chunk) => {
      buffer += chunk;
      
      // Process complete JSON-RPC messages
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            const request = JSON.parse(line);
            const response = await this.handleRequest(request);
            console.log(JSON.stringify(response));
          } catch (error) {
            console.error('Error parsing request:', error);
          }
        }
      }
    });

    process.stdin.on('end', () => {
      console.error("MCP Server stdin ended");
      process.exit(0);
    });

    console.error("Mininet MCPO Bridge Server started successfully!");
    console.error("Available tools: generate_network_topology, get_network_status, start_network, stop_network, get_topology");
  }
}

// Start the server
const server = new SimpleMCPServer();
server.start().catch(console.error);