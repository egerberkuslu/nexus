"""
Topology LLM Service
Specialized service for generating network topologies using LLM
"""

import logging
import json
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from utils.logger import setup_logger
from .llm_manager import LLMManager

logger = setup_logger(__name__)


class TopologyLLMService:
    """Service for generating network topologies using LLM"""
    
    def __init__(self, llm_manager: LLMManager = None):
        self.llm_manager = llm_manager or LLMManager()
        self.logger = logger
        
        # Topology templates for common patterns
        self.templates = {
            "simple_switch": {
                "description": "A simple switch with multiple hosts",
                "min_nodes": 3,
                "max_nodes": 10
            },
            "linear": {
                "description": "A linear chain of switches with hosts",
                "min_nodes": 4,
                "max_nodes": 8
            },
            "star": {
                "description": "A central switch with multiple hosts",
                "min_nodes": 4,
                "max_nodes": 12
            },
            "tree": {
                "description": "A hierarchical tree structure",
                "min_nodes": 6,
                "max_nodes": 20
            },
            "mesh": {
                "description": "A fully connected mesh",
                "min_nodes": 4,
                "max_nodes": 8
            },
            "datacenter": {
                "description": "A datacenter topology with ToR switches",
                "min_nodes": 8,
                "max_nodes": 20
            }
        }
    
    def generate_topology_from_description(self, description: str, **kwargs) -> Dict[str, Any]:
        """Generate topology from natural language description"""
        try:
            # Enhance the description with context
            enhanced_description = self._enhance_description(description)
            
            # Generate topology using LLM
            result = self.llm_manager.generate_topology(enhanced_description, **kwargs)
            
            if result.get("success", False):
                # Post-process the generated topology
                topology_config = result.get("topology_config", {})
                processed_config = self._post_process_topology(topology_config)
                result["topology_config"] = processed_config
                
                # Add metadata
                result["metadata"] = {
                    "generated_at": datetime.now().isoformat(),
                    "description": description,
                    "enhanced_description": enhanced_description,
                    "template_used": self._identify_template(description),
                    "node_count": len(processed_config.get("topology", {}).get("nodes", [])),
                    "link_count": len(processed_config.get("topology", {}).get("links", []))
                }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating topology from description: {e}")
            return {
                "success": False,
                "error": f"Topology generation failed: {str(e)}",
                "response": ""
            }
    
    def generate_topology_from_template(self, template_name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate topology from a predefined template"""
        if template_name not in self.templates:
            return {
                "success": False,
                "error": f"Unknown template: {template_name}",
                "response": ""
            }
        
        template = self.templates[template_name]
        parameters = parameters or {}
        
        # Create description based on template and parameters
        description = self._create_template_description(template_name, template, parameters)
        
        return self.generate_topology_from_description(description, **parameters)
    
    def suggest_topology_improvements(self, topology_config: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest improvements for an existing topology"""
        try:
            # Analyze the topology
            analysis = self._analyze_topology(topology_config)
            
            # Create improvement suggestions
            suggestions_prompt = f"""
Analyze this network topology and suggest improvements:

Topology: {json.dumps(topology_config, indent=2)}

Analysis: {json.dumps(analysis, indent=2)}

Provide specific, actionable suggestions for:
1. Performance improvements
2. Redundancy and fault tolerance
3. Security enhancements
4. Scalability considerations
5. Best practices

Format your response as a JSON object with these sections:
{{
    "performance": ["suggestion1", "suggestion2"],
    "redundancy": ["suggestion1", "suggestion2"],
    "security": ["suggestion1", "suggestion2"],
    "scalability": ["suggestion1", "suggestion2"],
    "best_practices": ["suggestion1", "suggestion2"],
    "overall_score": 0-100,
    "priority_improvements": ["most_important_suggestion1", "most_important_suggestion2"]
}}
"""
            
            result = self.llm_manager.generate_response(suggestions_prompt, use_history=False)
            
            if result.get("success", False):
                # Try to parse JSON suggestions
                try:
                    json_start = result["response"].find('{')
                    json_end = result["response"].rfind('}') + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_str = result["response"][json_start:json_end]
                        suggestions = json.loads(json_str)
                        result["suggestions"] = suggestions
                except json.JSONDecodeError:
                    # Fallback to text suggestions
                    result["suggestions"] = {"text": result["response"]}
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error suggesting topology improvements: {e}")
            return {
                "success": False,
                "error": f"Improvement suggestions failed: {str(e)}",
                "response": ""
            }
    
    def _enhance_description(self, description: str) -> str:
        """Enhance the description with additional context"""
        enhancements = [
            "Include realistic IP addressing (use 10.0.x.x, 192.168.x.x ranges)",
            "Add appropriate bandwidth specifications for links",
            "Include at least one SDN controller for network management",
            "Use realistic node positioning for visualization",
            "Ensure the topology is functional and follows networking best practices"
        ]
        
        enhanced = f"{description}\n\nAdditional requirements:\n" + "\n".join(f"- {enhancement}" for enhancement in enhancements)
        return enhanced
    
    def _post_process_topology(self, topology_config: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process the generated topology configuration"""
        try:
            topology = topology_config.get("topology", {})
            nodes = topology.get("nodes", [])
            links = topology.get("links", [])
            
            # Ensure unique IDs and fix any issues
            self._ensure_unique_ids(nodes)
            
            # Add missing required fields
            self._add_missing_fields(nodes, links)
            
            # Optimize positioning
            self._optimize_positions(nodes)
            
            # Validate and fix links
            self._validate_and_fix_links(nodes, links)
            
            return topology_config
            
        except Exception as e:
            self.logger.warning(f"Error in post-processing: {e}")
            return topology_config
    
    def _ensure_unique_ids(self, nodes: List[Dict[str, Any]]):
        """Ensure all nodes have unique IDs"""
        used_ids = set()
        for node in nodes:
            if "id" not in node:
                # Generate ID based on type
                node_type = node.get("type", "node")
                counter = 1
                base_id = f"{node_type}{counter}"
                while base_id in used_ids:
                    counter += 1
                    base_id = f"{node_type}{counter}"
                node["id"] = base_id
            
            # Ensure uniqueness
            original_id = node["id"]
            counter = 1
            while node["id"] in used_ids:
                node["id"] = f"{original_id}_{counter}"
                counter += 1
            
            used_ids.add(node["id"])
    
    def _add_missing_fields(self, nodes: List[Dict[str, Any]], links: List[Dict[str, Any]]):
        """Add missing required fields to nodes and links"""
        for node in nodes:
            node_type = node.get("type", "host")
            
            # Add missing coordinates
            if "x" not in node:
                node["x"] = random.randint(50, 750)
            if "y" not in node:
                node["y"] = random.randint(50, 550)
            
            # Add type-specific fields
            if node_type == "host":
                if "ip" not in node:
                    node["ip"] = f"10.0.{random.randint(1, 255)}.{random.randint(1, 254)}"
                if "mac" not in node:
                    node["mac"] = "auto"
            
            elif node_type == "switch":
                if "dpid" not in node:
                    node["dpid"] = "auto"
                if "openflow_version" not in node:
                    node["openflow_version"] = "1.3"
            
            elif node_type == "router":
                if "routing_protocol" not in node:
                    node["routing_protocol"] = "static"
            
            elif node_type == "controller":
                if "port" not in node:
                    node["port"] = 6633
                if "ip" not in node:
                    node["ip"] = "127.0.0.1"
        
        for link in links:
            if "bandwidth" not in link:
                link["bandwidth"] = "1G"
            if "status" not in link:
                link["status"] = "up"
    
    def _optimize_positions(self, nodes: List[Dict[str, Any]]):
        """Optimize node positions for better visualization"""
        # Group nodes by type for better layout
        hosts = [n for n in nodes if n.get("type") == "host"]
        switches = [n for n in nodes if n.get("type") == "switch"]
        routers = [n for n in nodes if n.get("type") == "router"]
        controllers = [n for n in nodes if n.get("type") == "controller"]
        
        # Position controllers at the top
        for i, controller in enumerate(controllers):
            controller["x"] = 100 + i * 200
            controller["y"] = 50
        
        # Position routers in the middle
        for i, router in enumerate(routers):
            router["x"] = 200 + i * 300
            router["y"] = 200
        
        # Position switches below routers
        for i, switch in enumerate(switches):
            switch["x"] = 150 + i * 200
            switch["y"] = 350
        
        # Position hosts at the bottom
        for i, host in enumerate(hosts):
            host["x"] = 100 + i * 150
            host["y"] = 500
    
    def _validate_and_fix_links(self, nodes: List[Dict[str, Any]], links: List[Dict[str, Any]]):
        """Validate and fix links to ensure they reference existing nodes"""
        node_ids = {node["id"] for node in nodes}
        
        # Remove invalid links
        valid_links = []
        for link in links:
            if (link.get("source") in node_ids and 
                link.get("target") in node_ids and
                link.get("source") != link.get("target")):
                valid_links.append(link)
        
        # Update the links list
        links.clear()
        links.extend(valid_links)
    
    def _identify_template(self, description: str) -> str:
        """Identify which template best matches the description"""
        description_lower = description.lower()
        
        for template_name, template_info in self.templates.items():
            if template_name.replace("_", " ") in description_lower:
                return template_name
        
        return "custom"
    
    def _create_template_description(self, template_name: str, template: Dict[str, Any], parameters: Dict[str, Any]) -> str:
        """Create a description based on template and parameters"""
        base_description = template["description"]
        
        # Add parameter-specific details
        if "hosts" in parameters:
            base_description += f" with {parameters['hosts']} hosts"
        if "switches" in parameters:
            base_description += f" and {parameters['switches']} switches"
        if "depth" in parameters:
            base_description += f" with depth {parameters['depth']}"
        if "fanout" in parameters:
            base_description += f" and fanout {parameters['fanout']}"
        
        return base_description
    
    def _analyze_topology(self, topology_config: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a topology configuration"""
        topology = topology_config.get("topology", {})
        nodes = topology.get("nodes", [])
        links = topology.get("links", [])
        
        # Count nodes by type
        node_counts = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            node_counts[node_type] = node_counts.get(node_type, 0) + 1
        
        # Analyze connectivity
        node_connections = {}
        for link in links:
            source = link.get("source")
            target = link.get("target")
            if source:
                node_connections[source] = node_connections.get(source, 0) + 1
            if target:
                node_connections[target] = node_connections.get(target, 0) + 1
        
        # Calculate metrics
        total_nodes = len(nodes)
        total_links = len(links)
        avg_connections = sum(node_connections.values()) / total_nodes if total_nodes > 0 else 0
        
        return {
            "node_counts": node_counts,
            "total_nodes": total_nodes,
            "total_links": total_links,
            "average_connections": avg_connections,
            "has_controller": node_counts.get("controller", 0) > 0,
            "has_router": node_counts.get("router", 0) > 0,
            "connectivity_ratio": total_links / (total_nodes * (total_nodes - 1) / 2) if total_nodes > 1 else 0
        }
    
    def get_available_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get available topology templates"""
        return self.templates.copy()
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get the status of the LLM service"""
        return {
            "llm_service": self.llm_manager.get_service_info(),
            "templates_available": len(self.templates),
            "service_available": self.llm_manager.is_service_available()
        }
