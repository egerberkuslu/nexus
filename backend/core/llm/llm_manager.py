"""
LLM Manager
Manages LLM requests, responses, and conversation history
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from utils.logger import setup_logger
from .llm_factory import LLMFactory, BaseLLMService

logger = setup_logger(__name__)


class ConversationHistory:
    """Manages conversation history for context"""
    
    def __init__(self, max_history: int = 10):
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add a message to the conversation history"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.history.append(message)
        
        # Keep only the last max_history messages
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def get_context(self, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """Get conversation context for LLM"""
        context = []
        for message in self.history:
            context_msg = {
                "role": message["role"],
                "content": message["content"]
            }
            if include_metadata:
                context_msg["metadata"] = message["metadata"]
            context.append(context_msg)
        return context
    
    def clear(self):
        """Clear conversation history"""
        self.history = []
    
    def get_last_message(self) -> Optional[Dict[str, Any]]:
        """Get the last message in the conversation"""
        return self.history[-1] if self.history else None


class LLMManager:
    """Manages LLM interactions and conversation state"""
    
    def __init__(self, service_type: str = "ollama", **service_kwargs):
        self.service_type = service_type
        self.service_kwargs = service_kwargs
        self.llm_service: BaseLLMService = None
        self.conversation_history = ConversationHistory()
        self.logger = logger
        self._config_id = None  # Track current configuration ID
        
        # Initialize the LLM service
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize the LLM service"""
        try:
            self.llm_service = LLMFactory.create_service(
                self.service_type, 
                **self.service_kwargs
            )
            self.logger.info(f"Initialized {self.service_type} LLM service")
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM service: {e}")
            # Fallback to default service
            self.llm_service = LLMFactory.get_default_service()
    
    def switch_service(self, service_type: str, **service_kwargs):
        """Switch to a different LLM service"""
        try:
            self.logger.info(f"Switching to {service_type} LLM service with kwargs: {list(service_kwargs.keys())}")
            self.service_type = service_type
            self.service_kwargs = service_kwargs
            self.llm_service = LLMFactory.create_service(service_type, **service_kwargs)
            self.logger.info(f"Successfully switched to {service_type} LLM service")
            self.logger.info(f"New service model: {getattr(self.llm_service, 'model_name', 'unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to switch to {service_type} service: {e}")
            self.logger.error(f"Service kwargs were: {service_kwargs}")
            return False
    
    def is_service_available(self) -> bool:
        """Check if the current LLM service is available"""
        return self.llm_service.is_available() if self.llm_service else False
    
    def generate_response(self, prompt: str, use_history: bool = True, **kwargs) -> Dict[str, Any]:
        """Generate a response from the LLM"""
        if not self.llm_service:
            return {
                "success": False,
                "error": "No LLM service available",
                "response": ""
            }
        
        # Add user message to history
        self.conversation_history.add_message("user", prompt)
        
        # Prepare the prompt with context if using history
        if use_history and len(self.conversation_history.history) > 1:
            context = self.conversation_history.get_context()
            # Create a context-aware prompt
            context_str = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in context[:-1]  # Exclude the current user message
            ])
            full_prompt = f"Previous conversation:\n{context_str}\n\nCurrent request: {prompt}"
        else:
            full_prompt = prompt
        
        # Generate response
        start_time = time.time()
        result = self.llm_service.generate_response(full_prompt, **kwargs)
        end_time = time.time()
        
        # Add timing information
        result["processing_time"] = end_time - start_time
        
        # Add assistant response to history if successful
        if result.get("success", False):
            self.conversation_history.add_message(
                "assistant", 
                result.get("response", ""),
                {
                    "model": result.get("model", ""),
                    "processing_time": result["processing_time"]
                }
            )
        
        return result
    
    def generate_topology(self, description: str, **kwargs) -> Dict[str, Any]:
        """Generate network topology from natural language description"""
        # Create a specialized prompt for topology generation
        topology_prompt = f"""
You are a network topology expert. I will describe a network and you will create the JSON configuration.

DESCRIPTION: {description}

STEP 1: Understand what I want
- What devices do I want? (hosts, switches, routers, controllers)
- What are their names/IDs? (use EXACT names I mention like h4, h6, s1, s2, r1, c1)
- What IP addresses do I want? (use EXACT IPs I mention)
- What controller type do I want? (use EXACT type I mention)
- How are they connected? (include ALL connections I describe)
- IMPORTANT: Include EVERY device I mention - don't skip any!

STEP 2: Create the JSON
Use this EXACT format:

{{
    "type": "custom",
    "topology": {{
        "name": "Network Name",
        "nodes": [
            {{"id": "c1", "type": "controller", "x": 400, "y": 100, "port": 6633, "ip": "127.0.0.1", "mac": "N/A", "status": "active", "controller_type": "pox", "protocol": "OpenFlow", "version": "1.3"}},
            {{"id": "h1", "type": "host", "x": 100, "y": 300, "ip": "10.0.1.1", "mac": "00:00:00:00:00:01", "status": "active"}},
            {{"id": "h2", "type": "host", "x": 300, "y": 300, "ip": "10.0.1.2", "mac": "00:00:00:00:00:02", "status": "active"}},
            {{"id": "s1", "type": "switch", "x": 200, "y": 200, "dpid": "auto", "openflow_version": "1.3", "ip": "", "mac": "N/A", "status": "active", "switch_type": "ovs", "controller": "c1"}},
            {{"id": "r1", "type": "router", "x": 300, "y": 150, "ip": "10.0.0.1", "mac": "00:00:00:00:01:00", "status": "active"}}
        ],
        "links": [
            {{"source": "h1", "target": "s1", "bandwidth": "100Mbit", "status": "up", "type": "physical"}},
            {{"source": "h2", "target": "s1", "bandwidth": "100Mbit", "status": "up", "type": "physical"}},
            {{"source": "s1", "target": "r1", "bandwidth": "1Gbit", "status": "up", "type": "physical"}},
            {{"source": "r1", "target": "c1", "bandwidth": "N/A", "status": "up", "type": "control"}}
        ]
    }}
}}

IMPORTANT RULES:
- If I mention specific names/IDs, use them exactly (h4, h6, s1, s2, r1, c1)
- If I mention specific IPs, use them exactly (10.0.1.10, 10.0.2.10, 10.0.0.3)
- If I mention "POX" controller, use "controller_type": "pox"
- If I mention "Ryu" controller, use "controller_type": "ryu"  
- If I mention "OpenDaylight" controller, use "controller_type": "opendaylight"
- If I mention "OsKen" controller, use "controller_type": "osken"
- Controller IP should always be 127.0.0.1 (localhost)
- Controller must have: port: 6633, protocol: "OpenFlow", version: "1.3"
- Include EVERY device I mention - don't skip routers, hosts, or switches
- Create ALL connections I describe in the exact order
- IMPORTANT: If I mention router-to-controller connection, include it as "type": "control"
- IMPORTANT: If I mention host-to-switch connection, use "type": "physical"
- IMPORTANT: If I mention switch-to-router connection, use "type": "physical"
- Use coordinates to position devices nicely (x: 0-800, y: 0-600)
- Use MAC addresses like 00:00:00:00:00:01, 00:00:00:00:00:02, etc.

Return ONLY the JSON. No explanations, no text before or after.
"""
        
        result = self.generate_response(topology_prompt, use_history=False, **kwargs)
        
        if result.get("success", False):
            # Try to extract JSON from the response
            response_text = result.get("response", "")
            try:
                # Look for JSON in the response
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    topology_config = json.loads(json_str)
                    
                    # Validate the topology structure
                    validation_result = self._validate_topology_config(topology_config)
                    
                    result["topology_config"] = topology_config
                    result["validation"] = validation_result
                    
                    if not validation_result["valid"]:
                        result["success"] = False
                        result["error"] = f"Generated topology is invalid: {validation_result['errors']}"
                else:
                    result["success"] = False
                    result["error"] = "No valid JSON found in LLM response"
                    
            except json.JSONDecodeError as e:
                # Try to create a fallback topology
                fallback_result = self._create_fallback_topology(description, str(e), response_text)
                if fallback_result["success"]:
                    return fallback_result
                else:
                    result["success"] = False
                    result["error"] = f"Invalid JSON in LLM response: {str(e)}"
        
        return result
    
    def _create_fallback_topology(self, description: str, error: str, raw_response: str) -> Dict[str, Any]:
        """Create a simple fallback topology when LLM fails"""
        try:
            # Extract basic information from description
            description_lower = description.lower()
            
            # Determine controller type
            controller_type = "ryu"  # default
            if "pox" in description_lower:
                controller_type = "pox"
            elif "opendaylight" in description_lower:
                controller_type = "opendaylight"
            elif "osken" in description_lower:
                controller_type = "osken"
            elif "ryu" in description_lower:
                controller_type = "ryu"
            
            # Extract specific device names and counts
            import re
            
            # Look for specific device names mentioned
            host_matches = re.findall(r'h\d+', description_lower)
            switch_matches = re.findall(r's\d+', description_lower)
            router_matches = re.findall(r'r\d+', description_lower)
            controller_matches = re.findall(r'c\d+', description_lower)
            
            # Count devices mentioned
            host_count = len(set(host_matches)) if host_matches else description_lower.count("host") + description_lower.count("computer") + description_lower.count("pc")
            switch_count = len(set(switch_matches)) if switch_matches else description_lower.count("switch")
            router_count = len(set(router_matches)) if router_matches else description_lower.count("router")
            
            # Extract specific IP addresses mentioned
            ip_matches = re.findall(r'\d+\.\d+\.\d+\.\d+', description)
            specific_ips = {}
            for i, ip in enumerate(ip_matches):
                if i < len(host_matches):
                    specific_ips[host_matches[i]] = ip
                elif i < len(host_matches) + len(router_matches):
                    specific_ips[router_matches[i - len(host_matches)]] = ip
            
            # Create basic topology
            nodes = []
            links = []
            
            # Add controller
            nodes.append({
                "id": "c1",
                "type": "controller",
                "x": 400,
                "y": 100,
                "port": 6633,
                "ip": "127.0.0.1",
                "mac": "N/A",
                "status": "active",
                "controller_type": controller_type,
                "protocol": "OpenFlow",
                "version": "1.3"
            })
            
            # Add hosts with specific names and IPs
            if host_matches:
                for i, host_id in enumerate(host_matches):
                    ip = specific_ips.get(host_id, f"10.0.1.{i+10}")
                    nodes.append({
                        "id": host_id,
                        "type": "host",
                        "x": 100 + (i * 200),
                        "y": 300,
                        "ip": ip,
                        "mac": f"00:00:00:00:00:{i+1:02d}",
                        "status": "active"
                    })
            else:
                for i in range(max(1, host_count)):
                    nodes.append({
                        "id": f"h{i+1}",
                        "type": "host",
                        "x": 100 + (i * 200),
                        "y": 300,
                        "ip": f"10.0.1.{i+10}",
                        "mac": f"00:00:00:00:00:{i+1:02d}",
                        "status": "active"
                    })
            
            # Add switches with specific names
            if switch_matches:
                for i, switch_id in enumerate(switch_matches):
                    nodes.append({
                        "id": switch_id,
                        "type": "switch",
                        "x": 200 + (i * 200),
                        "y": 200,
                        "dpid": "auto",
                        "openflow_version": "1.3",
                        "ip": "",
                        "mac": "N/A",
                        "status": "active",
                        "switch_type": "ovs",
                        "controller": "c1"
                    })
            else:
                for i in range(max(1, switch_count)):
                    nodes.append({
                        "id": f"s{i+1}",
                        "type": "switch",
                        "x": 200 + (i * 200),
                        "y": 200,
                        "dpid": "auto",
                        "openflow_version": "1.3",
                        "ip": "",
                        "mac": "N/A",
                        "status": "active",
                        "switch_type": "ovs",
                        "controller": "c1"
                    })
            
            # Add routers with specific names and IPs
            if router_matches:
                for i, router_id in enumerate(router_matches):
                    ip = specific_ips.get(router_id, f"10.0.0.{i+1}")
                    nodes.append({
                        "id": router_id,
                        "type": "router",
                        "x": 300 + (i * 200),
                        "y": 150,
                        "ip": ip,
                        "mac": f"00:00:00:00:0{i+1}:00",
                        "status": "active"
                    })
            else:
                for i in range(router_count):
                    nodes.append({
                        "id": f"r{i+1}",
                        "type": "router",
                        "x": 300 + (i * 200),
                        "y": 150,
                        "ip": f"10.0.0.{i+1}",
                        "mac": f"00:00:00:00:0{i+1}:00",
                        "status": "active"
                    })
            
            # Create links based on description pattern
            if nodes:
                # Get device lists
                hosts = [n for n in nodes if n["type"] == "host"]
                switches = [n for n in nodes if n["type"] == "switch"]
                routers = [n for n in nodes if n["type"] == "router"]
                
                # Create links based on the described pattern:
                # h4 -> s1 -> r1 -> s2 -> h6, c1 -> r1
                if len(hosts) >= 2 and len(switches) >= 2 and len(routers) >= 1:
                    # h4 -> s1
                    links.append({
                        "source": hosts[0]["id"],
                        "target": switches[0]["id"],
                        "bandwidth": "100Mbit",
                        "status": "up",
                        "type": "physical"
                    })
                    
                    # s1 -> r1
                    links.append({
                        "source": switches[0]["id"],
                        "target": routers[0]["id"],
                        "bandwidth": "1Mbit",
                        "status": "up",
                        "type": "physical"
                    })
                    
                    # r1 -> s2
                    links.append({
                        "source": routers[0]["id"],
                        "target": switches[1]["id"],
                        "bandwidth": "1Mbit",
                        "status": "up",
                        "type": "physical"
                    })
                    
                    # s2 -> h6
                    links.append({
                        "source": switches[1]["id"],
                        "target": hosts[1]["id"],
                        "bandwidth": "100Mbit",
                        "status": "up",
                        "type": "physical"
                    })
                    
                    # r1 -> c1 (controller connection)
                    links.append({
                        "source": routers[0]["id"],
                        "target": "c1",
                        "bandwidth": "N/A",
                        "status": "up",
                        "type": "control"
                    })
                else:
                    # Fallback: connect all hosts to first switch
                    first_switch = switches[0] if switches else None
                    if first_switch:
                        for host in hosts:
                            links.append({
                                "source": host["id"],
                                "target": first_switch["id"],
                                "bandwidth": "100Mbit",
                                "status": "up",
                                "type": "physical"
                            })
                        
                        # Connect switch to controller
                        links.append({
                            "source": first_switch["id"],
                            "target": "c1",
                            "bandwidth": "N/A",
                            "status": "up",
                            "type": "control"
                        })
            
            topology_json = {
                "type": "custom",
                "topology": {
                    "name": f"Generated Network ({controller_type})",
                    "nodes": nodes,
                    "links": links
                }
            }
            
            return {
                "success": True,
                "topology_config": topology_json,
                "validation": {"valid": True, "errors": []},
                "raw_response": f"Fallback topology created due to: {error}",
                "fallback_used": True
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Both LLM and fallback failed: {str(e)}",
                "raw_response": raw_response
            }
    
    def _validate_topology_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the generated topology configuration"""
        validation = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Check top-level structure
            if "type" not in config or config["type"] != "custom":
                validation["errors"].append("Topology type must be 'custom'")
                validation["valid"] = False
            
            if "topology" not in config:
                validation["errors"].append("Missing 'topology' section")
                validation["valid"] = False
                return validation
            
            topology = config["topology"]
            
            # Check required sections
            if "nodes" not in topology:
                validation["errors"].append("Missing 'nodes' section")
                validation["valid"] = False
            
            if "links" not in topology:
                validation["errors"].append("Missing 'links' section")
                validation["valid"] = False
            
            if not validation["valid"]:
                return validation
            
            nodes = topology["nodes"]
            links = topology["links"]
            
            # Validate nodes
            if len(nodes) == 0:
                validation["errors"].append("At least one node is required")
                validation["valid"] = False
            
            node_ids = set()
            for i, node in enumerate(nodes):
                if "id" not in node:
                    validation["errors"].append(f"Node {i} missing 'id'")
                    validation["valid"] = False
                elif node["id"] in node_ids:
                    validation["errors"].append(f"Duplicate node ID: {node['id']}")
                    validation["valid"] = False
                else:
                    node_ids.add(node["id"])
                
                if "type" not in node:
                    validation["errors"].append(f"Node {i} missing 'type'")
                    validation["valid"] = False
                elif node["type"] not in ["host", "switch", "router", "controller"]:
                    validation["errors"].append(f"Invalid node type: {node['type']}")
                    validation["valid"] = False
            
            # Validate links
            for i, link in enumerate(links):
                if "source" not in link or "target" not in link:
                    validation["errors"].append(f"Link {i} missing source or target")
                    validation["valid"] = False
                elif link["source"] not in node_ids:
                    validation["errors"].append(f"Link {i} source '{link['source']}' not found in nodes")
                    validation["valid"] = False
                elif link["target"] not in node_ids:
                    validation["errors"].append(f"Link {i} target '{link['target']}' not found in nodes")
                    validation["valid"] = False
            
            # Check for at least one controller
            has_controller = any(node.get("type") == "controller" for node in nodes)
            if not has_controller:
                validation["warnings"].append("No controller found - SDN functionality may be limited")
            
        except Exception as e:
            validation["valid"] = False
            validation["errors"].append(f"Validation error: {str(e)}")
        
        return validation
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history.clear()
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.conversation_history.history
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the current LLM service"""
        return {
            "service_type": self.service_type,
            "model_name": getattr(self.llm_service, 'model_name', 'unknown'),
            "base_url": getattr(self.llm_service, 'base_url', 'unknown'),
            "available": self.is_service_available(),
            "history_length": len(self.conversation_history.history),
            "config_id": self._config_id
        }
    
    def initialize_from_config(self, config_id: str) -> bool:
        """
        Initialize LLM service from a stored configuration
        
        Args:
            config_id: Configuration ID to load
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from database.llm_config_service import get_llm_config_service
            
            service = get_llm_config_service()
            config = service.get_config(config_id)
            
            if not config:
                self.logger.error(f"Configuration {config_id} not found")
                return False
            
            # Get decrypted API key
            api_key = config.get_api_key()
            
            # Prepare service kwargs based on service type
            if config.service_type == 'ollama':
                service_kwargs = {
                    'model_name': config.model_name,
                    'base_url': config.base_url or 'http://localhost:11434'
                }
            elif config.service_type in ['openai', 'gemini', 'claude']:
                service_kwargs = {
                    'model_name': config.model_name,
                    'api_key': api_key
                }
            else:
                service_kwargs = {
                    'model_name': config.model_name,
                    'base_url': config.base_url
                }
                if api_key:
                    service_kwargs['api_key'] = api_key
            
            # Switch to the new service
            success = self.switch_service(config.service_type, **service_kwargs)
            
            if success:
                self._config_id = config_id
                self.logger.info(f"Initialized LLM service from configuration: {config.name}")
                return True
            else:
                self.logger.error(f"Failed to initialize service from configuration: {config.name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error initializing from configuration {config_id}: {e}")
            return False
    
    def initialize_from_active_config(self) -> bool:
        """
        Initialize LLM service from the currently active configuration
        
        Returns:
            True if successful, False otherwise
        """
        try:
            from database.llm_config_service import get_llm_config_service
            
            service = get_llm_config_service()
            config = service.get_active_config()
            
            if not config:
                self.logger.warning("No active LLM configuration found, using default")
                return False
            
            return self.initialize_from_config(str(config._id))
            
        except Exception as e:
            self.logger.error(f"Error initializing from active configuration: {e}")
            return False
    
    def reload_from_config(self) -> bool:
        """
        Reload the current configuration (useful after configuration updates)
        
        Returns:
            True if successful, False otherwise
        """
        # Always reload from the current active configuration, not the stored config_id
        return self.initialize_from_active_config()
