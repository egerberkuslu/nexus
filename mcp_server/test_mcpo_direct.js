#!/usr/bin/env node
/**
 * Test script to use MCPO server directly via HTTP
 */

const MCPO_BASE = "http://localhost:3001/mininet-fastmcp";

async function callMcpoTool(toolName, method = "POST", data = null) {
  const url = `${MCPO_BASE}/${toolName}`;
  
  try {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' }
    };
    
    if (data && method === 'POST') {
      options.body = JSON.stringify(data);
    }
    
    const response = await fetch(url, options);
    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return result;
  } catch (error) {
    return { error: error.message };
  }
}

async function main() {
  console.log("=== Testing MCPO Server Directly ===\n");
  
  // Test 1: Generate network topology
  console.log("1. Generating network topology...");
  const topologyData = {
    description: "Create a network with h4 -> s1 -> r1 -> s2 -> h6, c1 -> r1 with POX controller",
    use_llm: true,
    context_type: "design"
  };
  
  const result = await callMcpoTool("generate_network_topology", "POST", topologyData);
  console.log(`Result: ${JSON.stringify(result, null, 2).substring(0, 200)}...`);
  
  // Test 2: Get network status
  console.log("\n2. Getting network status...");
  const status = await callMcpoTool("get_network_status", "POST");
  console.log(`Status: ${JSON.stringify(status, null, 2).substring(0, 200)}...`);
  
  // Test 3: Get topology
  console.log("\n3. Getting topology...");
  const topology = await callMcpoTool("get_topology", "GET");
  console.log(`Topology: ${JSON.stringify(topology, null, 2).substring(0, 200)}...`);
}

main().catch(console.error);
