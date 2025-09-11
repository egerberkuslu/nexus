/**
 * Resource Definitions for MCP Bridge
 * Contains all resource schemas and endpoint mappings
 */

export class ResourceDefinitions {
  constructor() {
    this.resources = new Map();
    this.endpointMap = new Map();
    this.setupResources();
    this.setupEndpointMappings();
  }

  setupResources() {
    this.resources.set("snapshots://list", {
      uri: "snapshots://list",
      name: "Network Snapshots List",
      description: "List of all available network snapshots",
      mimeType: "application/json"
    });

    this.resources.set("topology://current", {
      uri: "topology://current", 
      name: "Current Network Topology",
      description: "Current network topology configuration",
      mimeType: "application/json"
    });

    this.resources.set("network://status", {
      uri: "network://status",
      name: "Network Status",
      description: "Current network status and statistics",
      mimeType: "application/json"
    });
  }

  setupEndpointMappings() {
    this.endpointMap.set("snapshots://list", {
      endpoint: "/list_snapshots",
      method: "POST",
      data: { limit: 100 }
    });

    this.endpointMap.set("topology://current", {
      endpoint: "/get_topology",
      method: "POST",
      data: { include_statistics: true }
    });

    this.endpointMap.set("network://status", {
      endpoint: "/get_network_status",
      method: "POST",
      data: {}
    });
  }

  getResource(uri) {
    return this.resources.get(uri);
  }

  getAllResources() {
    return Array.from(this.resources.values());
  }

  getEndpointMapping(uri) {
    return this.endpointMap.get(uri);
  }
}
