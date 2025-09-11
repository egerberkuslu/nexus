/**
 * Tool Definitions for MCP Bridge
 * Contains all tool schemas and endpoint mappings
 */

export class ToolDefinitions {
  constructor() {
    this.tools = new Map();
    this.endpointMap = new Map();
    this.setupTools();
    this.setupEndpointMappings();
  }

  setupTools() {
    // Network Lifecycle Management
    this.tools.set("start_network", {
      name: "start_network",
      description: "Start a new Mininet network simulation with the current topology configuration",
      inputSchema: {
        type: "object",
        properties: {},
        required: []
      }
    });

    this.tools.set("stop_network", {
      name: "stop_network", 
      description: "Gracefully stop the running Mininet network simulation",
      inputSchema: {
        type: "object",
        properties: {},
        required: []
      }
    });

    this.tools.set("restart_network", {
      name: "restart_network",
      description: "Restart the Mininet network simulation (stop then start)",
      inputSchema: {
        type: "object",
        properties: {},
        required: []
      }
    });

    this.tools.set("delete_network", {
      name: "delete_network",
      description: "Delete the current network configuration and stop any running simulation",
      inputSchema: {
        type: "object",
        properties: {},
        required: []
      }
    });

    this.tools.set("reset_network", {
      name: "reset_network",
      description: "Reset the network to default state, clearing all configurations",
      inputSchema: {
        type: "object",
        properties: {},
        required: []
      }
    });

    this.tools.set("get_network_status", {
      name: "get_network_status",
      description: "Get the current status of the Mininet network simulation",
      inputSchema: {
        type: "object",
        properties: {},
        required: []
      }
    });

    // Topology Management
    this.tools.set("get_topology", {
      name: "get_topology",
      description: "Get the current network topology configuration",
      inputSchema: {
        type: "object",
        properties: {
          include_statistics: {
            type: "boolean",
            description: "Include network statistics in the response",
            default: false
          }
        },
        required: []
      }
    });

    // Snapshot Management Tools
    this.tools.set("create_snapshot", {
      name: "create_snapshot",
      description: "Create a snapshot of the current network state",
      inputSchema: {
        type: "object",
        properties: {
          name: {
            type: "string",
            description: "Name for the snapshot"
          },
          description: {
            type: "string",
            description: "Description of the snapshot"
          },
          snapshot_type: {
            type: "string",
            description: "Type of snapshot",
            enum: ["full", "topology_only", "config_only"],
            default: "full"
          },
          include_topology_data: {
            type: "boolean",
            description: "Include topology data in snapshot",
            default: true
          }
        },
        required: []
      }
    });

    this.tools.set("list_snapshots", {
      name: "list_snapshots",
      description: "List all available network snapshots",
      inputSchema: {
        type: "object",
        properties: {
          limit: {
            type: "integer",
            description: "Maximum number of snapshots to return",
            default: 50
          },
          offset: {
            type: "integer",
            description: "Number of snapshots to skip",
            default: 0
          },
          snapshot_type: {
            type: "string",
            description: "Filter by snapshot type",
            enum: ["all", "full", "topology_only", "config_only"]
          }
        },
        required: []
      }
    });

    this.tools.set("get_snapshot", {
      name: "get_snapshot",
      description: "Get detailed information about a specific snapshot",
      inputSchema: {
        type: "object",
        properties: {
          snapshot_id: {
            type: "string",
            description: "ID of the snapshot to retrieve"
          }
        },
        required: ["snapshot_id"]
      }
    });

    this.tools.set("update_snapshot", {
      name: "update_snapshot",
      description: "Update metadata for an existing snapshot",
      inputSchema: {
        type: "object",
        properties: {
          snapshot_id: {
            type: "string",
            description: "ID of the snapshot to update"
          },
          name: {
            type: "string",
            description: "New name for the snapshot"
          },
          description: {
            type: "string",
            description: "New description for the snapshot"
          }
        },
        required: ["snapshot_id"]
      }
    });

    this.tools.set("delete_snapshot", {
      name: "delete_snapshot",
      description: "Delete a specific snapshot",
      inputSchema: {
        type: "object",
        properties: {
          snapshot_id: {
            type: "string",
            description: "ID of the snapshot to delete"
          }
        },
        required: ["snapshot_id"]
      }
    });

    this.tools.set("restore_snapshot", {
      name: "restore_snapshot",
      description: "Restore the network to a previous snapshot state",
      inputSchema: {
        type: "object",
        properties: {
          snapshot_id: {
            type: "string",
            description: "ID of the snapshot to restore"
          },
          preserve_current: {
            type: "boolean",
            description: "Create snapshot of current state before restoring",
            default: true
          }
        },
        required: ["snapshot_id"]
      }
    });

    this.tools.set("compare_snapshots", {
      name: "compare_snapshots",
      description: "Compare two snapshots and show differences",
      inputSchema: {
        type: "object",
        properties: {
          snapshot1_id: {
            type: "string",
            description: "ID of the first snapshot"
          },
          snapshot2_id: {
            type: "string",
            description: "ID of the second snapshot"
          },
          compare_type: {
            type: "string",
            description: "Type of comparison",
            enum: ["full", "topology_only", "config_only"],
            default: "full"
          }
        },
        required: ["snapshot1_id", "snapshot2_id"]
      }
    });

    this.tools.set("export_snapshot", {
      name: "export_snapshot",
      description: "Export a snapshot as a complete JSON package",
      inputSchema: {
        type: "object",
        properties: {
          snapshot_id: {
            type: "string",
            description: "ID of the snapshot to export"
          }
        },
        required: ["snapshot_id"]
      }
    });

    // AI/LLM Tools
    this.tools.set("generate_network_topology", {
      name: "generate_network_topology",
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
          use_llm: { 
            type: "boolean", 
            default: true, 
            description: "Whether to use LLM for generation" 
          },
          template_name: { 
            type: "string", 
            description: "Use a specific template as base" 
          },
          context_type: { 
            type: "string", 
            enum: ["design", "troubleshooting", "optimization"], 
            default: "design", 
            description: "Context type for LLM" 
          }
        },
        required: ["description"]
      }
    });
  }

  setupEndpointMappings() {
    // Network Lifecycle
    this.endpointMap.set("start_network", { endpoint: "/start_network", method: "POST" });
    this.endpointMap.set("stop_network", { endpoint: "/stop_network", method: "POST" });
    this.endpointMap.set("restart_network", { endpoint: "/restart_network", method: "POST" });
    this.endpointMap.set("delete_network", { endpoint: "/delete_network", method: "POST" });
    this.endpointMap.set("reset_network", { endpoint: "/reset_network", method: "POST" });
    this.endpointMap.set("get_network_status", { endpoint: "/get_network_status", method: "POST" });

    // Topology Management
    this.endpointMap.set("get_topology", { endpoint: "/get_topology", method: "POST" });

    // Snapshots
    this.endpointMap.set("create_snapshot", { endpoint: "/create_snapshot", method: "POST" });
    this.endpointMap.set("list_snapshots", { endpoint: "/list_snapshots", method: "POST" });
    this.endpointMap.set("get_snapshot", { endpoint: "/get_snapshot", method: "POST" });
    this.endpointMap.set("update_snapshot", { endpoint: "/update_snapshot", method: "POST" });
    this.endpointMap.set("delete_snapshot", { endpoint: "/delete_snapshot", method: "POST" });
    this.endpointMap.set("restore_snapshot", { endpoint: "/restore_snapshot", method: "POST" });
    this.endpointMap.set("compare_snapshots", { endpoint: "/compare_snapshots", method: "POST" });
    this.endpointMap.set("export_snapshot", { endpoint: "/export_snapshot", method: "POST" });

    // AI/LLM Tools
    this.endpointMap.set("generate_network_topology", { endpoint: "/generate_network_topology", method: "POST" });
  }

  getTool(name) {
    return this.tools.get(name);
  }

  getAllTools() {
    return Array.from(this.tools.values());
  }

  getEndpointMapping(name) {
    return this.endpointMap.get(name);
  }
}
