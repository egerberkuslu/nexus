"""
Topology Generator Service (Port 8009)
Auto-generates network topologies using various algorithms
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import math

# Import shared components
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Caduceus-Flux Topology Generator Service",
    description="Automatic topology generation with various algorithms",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service clients
consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()

SERVICE_PORT = 8009


# Pydantic models
class TopologyGeneratorRequest(BaseModel):
    topology_type: str = Field(..., description="Topology type: tree, linear, mesh, ring, star, fat_tree, datacenter")
    name: str = Field(..., description="Topology name")
    description: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Topology-specific parameters")


class GeneratedTopology(BaseModel):
    name: str
    description: str
    topology_type: str
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    generated_at: datetime


# Topology Generators
class TreeTopologyGenerator:
    """Generate tree topology"""
    
    @staticmethod
    def generate(name: str, params: Dict) -> Dict:
        depth = params.get("depth", 2)
        fanout = params.get("fanout", 2)
        
        nodes = []
        links = []
        node_counter = 0
        
        # Generate switches in tree structure
        switches_per_level = [1]
        for level in range(1, depth):
            switches_per_level.append(switches_per_level[-1] * fanout)
        
        switch_id = 0
        level_switches = {}
        
        for level in range(depth):
            level_switches[level] = []
            for i in range(switches_per_level[level]):
                switch_name = f"s{switch_id + 1}"
                nodes.append({
                    "name": switch_name,
                    "device_type": "switch",
                    "x": (i + 1) * (800 / (switches_per_level[level] + 1)),
                    "y": (level + 1) * 100,
                    "properties": {
                        "dpid": f"{switch_id + 1:016x}",
                        "openflow_version": "1.3"
                    }
                })
                level_switches[level].append(switch_name)
                switch_id += 1
        
        # Connect switches hierarchically
        for level in range(depth - 1):
            for i, parent in enumerate(level_switches[level]):
                for j in range(fanout):
                    child_idx = i * fanout + j
                    if child_idx < len(level_switches[level + 1]):
                        child = level_switches[level + 1][child_idx]
                        links.append({
                            "source_node": {"name": parent},
                            "target_node": {"name": child},
                            "bandwidth": 100,
                            "delay": 1
                        })
        
        # Add hosts to leaf switches
        host_id = 0
        hosts_per_switch = params.get("hosts_per_switch", 2)
        leaf_switches = level_switches[depth - 1]
        
        for switch in leaf_switches:
            for i in range(hosts_per_switch):
                host_name = f"h{host_id + 1}"
                nodes.append({
                    "name": host_name,
                    "device_type": "host",
                    "x": nodes[0]["x"] + (i - hosts_per_switch/2) * 30,
                    "y": depth * 100 + 50,
                    "properties": {
                        "ip": f"10.0.{host_id}.1/24",
                        "mac": f"00:00:00:00:{host_id:02x}:01"
                    }
                })
                links.append({
                    "source_node": {"name": host_name},
                    "target_node": {"name": switch},
                    "bandwidth": 100,
                    "delay": 1
                })
                host_id += 1
        
        return {
            "name": name,
            "nodes": nodes,
            "links": links,
            "topology_type": "tree",
            "parameters": {"depth": depth, "fanout": fanout, "hosts_per_switch": hosts_per_switch}
        }


class LinearTopologyGenerator:
    """Generate linear topology"""
    
    @staticmethod
    def generate(name: str, params: Dict) -> Dict:
        num_switches = params.get("num_switches", 3)
        hosts_per_switch = params.get("hosts_per_switch", 1)
        
        nodes = []
        links = []
        
        # Generate switches in a line
        for i in range(num_switches):
            switch_name = f"s{i + 1}"
            nodes.append({
                "name": switch_name,
                "device_type": "switch",
                "x": (i + 1) * 150,
                "y": 200,
                "properties": {
                    "dpid": f"{i + 1:016x}",
                    "openflow_version": "1.3"
                }
            })
            
            # Connect to previous switch
            if i > 0:
                links.append({
                    "source_node": {"name": f"s{i}"},
                    "target_node": {"name": switch_name},
                    "bandwidth": 100,
                    "delay": 1
                })
        
        # Add hosts
        host_id = 0
        for i in range(num_switches):
            switch_name = f"s{i + 1}"
            for j in range(hosts_per_switch):
                host_name = f"h{host_id + 1}"
                nodes.append({
                    "name": host_name,
                    "device_type": "host",
                    "x": (i + 1) * 150 + (j - hosts_per_switch/2) * 30,
                    "y": 300,
                    "properties": {
                        "ip": f"10.{i}.{j}.1/24",
                        "mac": f"00:00:00:00:{host_id:02x}:01"
                    }
                })
                links.append({
                    "source_node": {"name": host_name},
                    "target_node": {"name": switch_name},
                    "bandwidth": 100,
                    "delay": 1
                })
                host_id += 1
        
        return {
            "name": name,
            "nodes": nodes,
            "links": links,
            "topology_type": "linear",
            "parameters": {"num_switches": num_switches, "hosts_per_switch": hosts_per_switch}
        }


class MeshTopologyGenerator:
    """Generate full mesh topology"""
    
    @staticmethod
    def generate(name: str, params: Dict) -> Dict:
        num_switches = params.get("num_switches", 4)
        hosts_per_switch = params.get("hosts_per_switch", 1)
        
        nodes = []
        links = []
        
        # Generate switches in a circle
        radius = 150
        center_x, center_y = 400, 250
        
        for i in range(num_switches):
            angle = (2 * math.pi * i) / num_switches
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            switch_name = f"s{i + 1}"
            nodes.append({
                "name": switch_name,
                "device_type": "switch",
                "x": x,
                "y": y,
                "properties": {
                    "dpid": f"{i + 1:016x}",
                    "openflow_version": "1.3"
                }
            })
        
        # Connect all switches to all others (full mesh)
        for i in range(num_switches):
            for j in range(i + 1, num_switches):
                links.append({
                    "source_node": {"name": f"s{i + 1}"},
                    "target_node": {"name": f"s{j + 1}"},
                    "bandwidth": 100,
                    "delay": 1
                })
        
        # Add hosts
        host_id = 0
        for i in range(num_switches):
            angle = (2 * math.pi * i) / num_switches
            x = center_x + (radius + 80) * math.cos(angle)
            y = center_y + (radius + 80) * math.sin(angle)
            
            switch_name = f"s{i + 1}"
            for j in range(hosts_per_switch):
                host_name = f"h{host_id + 1}"
                nodes.append({
                    "name": host_name,
                    "device_type": "host",
                    "x": x + (j - hosts_per_switch/2) * 20,
                    "y": y,
                    "properties": {
                        "ip": f"10.{i}.{j}.1/24",
                        "mac": f"00:00:00:00:{host_id:02x}:01"
                    }
                })
                links.append({
                    "source_node": {"name": host_name},
                    "target_node": {"name": switch_name},
                    "bandwidth": 100,
                    "delay": 1
                })
                host_id += 1
        
        return {
            "name": name,
            "nodes": nodes,
            "links": links,
            "topology_type": "mesh",
            "parameters": {"num_switches": num_switches, "hosts_per_switch": hosts_per_switch}
        }


class RingTopologyGenerator:
    """Generate ring topology"""
    
    @staticmethod
    def generate(name: str, params: Dict) -> Dict:
        num_switches = params.get("num_switches", 4)
        hosts_per_switch = params.get("hosts_per_switch", 1)
        
        nodes = []
        links = []
        
        # Generate switches in a ring
        radius = 150
        center_x, center_y = 400, 250
        
        for i in range(num_switches):
            angle = (2 * math.pi * i) / num_switches
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            switch_name = f"s{i + 1}"
            nodes.append({
                "name": switch_name,
                "device_type": "switch",
                "x": x,
                "y": y,
                "properties": {
                    "dpid": f"{i + 1:016x}",
                    "openflow_version": "1.3"
                }
            })
        
        # Connect switches in a ring
        for i in range(num_switches):
            next_i = (i + 1) % num_switches
            links.append({
                "source_node": {"name": f"s{i + 1}"},
                "target_node": {"name": f"s{next_i + 1}"},
                "bandwidth": 100,
                "delay": 1
            })
        
        # Add hosts
        host_id = 0
        for i in range(num_switches):
            angle = (2 * math.pi * i) / num_switches
            x = center_x + (radius + 80) * math.cos(angle)
            y = center_y + (radius + 80) * math.sin(angle)
            
            switch_name = f"s{i + 1}"
            for j in range(hosts_per_switch):
                host_name = f"h{host_id + 1}"
                nodes.append({
                    "name": host_name,
                    "device_type": "host",
                    "x": x,
                    "y": y,
                    "properties": {
                        "ip": f"10.{i}.{j}.1/24",
                        "mac": f"00:00:00:00:{host_id:02x}:01"
                    }
                })
                links.append({
                    "source_node": {"name": host_name},
                    "target_node": {"name": switch_name},
                    "bandwidth": 100,
                    "delay": 1
                })
                host_id += 1
        
        return {
            "name": name,
            "nodes": nodes,
            "links": links,
            "topology_type": "ring",
            "parameters": {"num_switches": num_switches, "hosts_per_switch": hosts_per_switch}
        }


class StarTopologyGenerator:
    """Generate star topology"""
    
    @staticmethod
    def generate(name: str, params: Dict) -> Dict:
        num_edge_switches = params.get("num_edge_switches", 4)
        hosts_per_switch = params.get("hosts_per_switch", 2)
        
        nodes = []
        links = []
        
        # Central switch
        nodes.append({
            "name": "s1",
            "device_type": "switch",
            "x": 400,
            "y": 250,
            "properties": {
                "dpid": "0000000000000001",
                "openflow_version": "1.3"
            }
        })
        
        # Edge switches in a circle around central switch
        radius = 150
        for i in range(num_edge_switches):
            angle = (2 * math.pi * i) / num_edge_switches
            x = 400 + radius * math.cos(angle)
            y = 250 + radius * math.sin(angle)
            
            switch_name = f"s{i + 2}"
            nodes.append({
                "name": switch_name,
                "device_type": "switch",
                "x": x,
                "y": y,
                "properties": {
                    "dpid": f"{i + 2:016x}",
                    "openflow_version": "1.3"
                }
            })
            
            # Connect to central switch
            links.append({
                "source_node": {"name": "s1"},
                "target_node": {"name": switch_name},
                "bandwidth": 100,
                "delay": 1
            })
        
        # Add hosts to edge switches
        host_id = 0
        for i in range(num_edge_switches):
            angle = (2 * math.pi * i) / num_edge_switches
            x = 400 + (radius + 80) * math.cos(angle)
            y = 250 + (radius + 80) * math.sin(angle)
            
            switch_name = f"s{i + 2}"
            for j in range(hosts_per_switch):
                host_name = f"h{host_id + 1}"
                nodes.append({
                    "name": host_name,
                    "device_type": "host",
                    "x": x + (j - hosts_per_switch/2) * 20,
                    "y": y,
                    "properties": {
                        "ip": f"10.{i}.{j}.1/24",
                        "mac": f"00:00:00:00:{host_id:02x}:01"
                    }
                })
                links.append({
                    "source_node": {"name": host_name},
                    "target_node": {"name": switch_name},
                    "bandwidth": 100,
                    "delay": 1
                })
                host_id += 1
        
        return {
            "name": name,
            "nodes": nodes,
            "links": links,
            "topology_type": "star",
            "parameters": {"num_edge_switches": num_edge_switches, "hosts_per_switch": hosts_per_switch}
        }


class FatTreeTopologyGenerator:
    """Generate Fat-Tree datacenter topology"""
    
    @staticmethod
    def generate(name: str, params: Dict) -> Dict:
        k = params.get("k", 4)  # Number of ports per switch
        
        nodes = []
        links = []
        
        # Core switches
        num_core = (k // 2) ** 2
        for i in range(num_core):
            nodes.append({
                "name": f"core_{i + 1}",
                "device_type": "switch",
                "x": (i + 1) * (800 / (num_core + 1)),
                "y": 50,
                "properties": {
                    "dpid": f"{1000 + i:016x}",
                    "openflow_version": "1.3"
                }
            })
        
        # Aggregation and edge switches
        num_pods = k
        for pod in range(num_pods):
            pod_x_offset = (pod + 1) * (800 / (num_pods + 1))
            
            # Aggregation switches
            for agg in range(k // 2):
                switch_name = f"agg_{pod}_{agg}"
                nodes.append({
                    "name": switch_name,
                    "device_type": "switch",
                    "x": pod_x_offset + (agg - (k//2)/2) * 40,
                    "y": 150,
                    "properties": {
                        "dpid": f"{2000 + pod * 100 + agg:016x}",
                        "openflow_version": "1.3"
                    }
                })
                
                # Connect to core switches
                for core in range(k // 2):
                    core_idx = agg * (k // 2) + core
                    if core_idx < num_core:
                        links.append({
                            "source_node": {"name": switch_name},
                            "target_node": {"name": f"core_{core_idx + 1}"},
                            "bandwidth": 1000,
                            "delay": 1
                        })
            
            # Edge switches
            for edge in range(k // 2):
                switch_name = f"edge_{pod}_{edge}"
                nodes.append({
                    "name": switch_name,
                    "device_type": "switch",
                    "x": pod_x_offset + (edge - (k//2)/2) * 40,
                    "y": 250,
                    "properties": {
                        "dpid": f"{3000 + pod * 100 + edge:016x}",
                        "openflow_version": "1.3"
                    }
                })
                
                # Connect to aggregation switches
                for agg in range(k // 2):
                    links.append({
                        "source_node": {"name": switch_name},
                        "target_node": {"name": f"agg_{pod}_{agg}"},
                        "bandwidth": 1000,
                        "delay": 1
                    })
                
                # Add hosts
                for host in range(k // 2):
                    host_name = f"h_{pod}_{edge}_{host}"
                    nodes.append({
                        "name": host_name,
                        "device_type": "host",
                        "x": pod_x_offset + (edge - (k//2)/2) * 40 + (host - (k//2)/2) * 15,
                        "y": 350,
                        "properties": {
                            "ip": f"10.{pod}.{edge}.{host + 1}/24",
                            "mac": f"00:00:{pod:02x}:{edge:02x}:{host:02x}:01"
                        }
                    })
                    links.append({
                        "source_node": {"name": host_name},
                        "target_node": {"name": switch_name},
                        "bandwidth": 1000,
                        "delay": 1
                    })
        
        return {
            "name": name,
            "nodes": nodes,
            "links": links,
            "topology_type": "fat_tree",
            "parameters": {"k": k}
        }


# Helper function
def publish_event(event_type: str, data: Dict):
    """Publish topology generation event"""
    try:
        rabbitmq_publisher.publish(
            exchange="caduceus",
            routing_key=f"topology_generator.{event_type}",
            message=data
        )
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")


# API endpoints

@app.on_event("startup")
async def startup_event():
    """Service startup"""
    logger.info("Starting Topology Generator Service...")
    try:
        consul_client.register_service("topology-generator", SERVICE_PORT)
        rabbitmq_publisher.connect()
        logger.info("Topology Generator Service started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown"""
    logger.info("Shutting down Topology Generator Service...")
    consul_client.deregister_service("topology-generator")
    rabbitmq_publisher.disconnect()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "topology-generator",
        "supported_types": ["tree", "linear", "mesh", "ring", "star", "fat_tree"],
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/generate", response_model=GeneratedTopology)
async def generate_topology(request: TopologyGeneratorRequest):
    """
    Generate a topology based on specified algorithm
    
    Supported types:
    - tree: Hierarchical tree (depth, fanout, hosts_per_switch)
    - linear: Linear chain (num_switches, hosts_per_switch)
    - mesh: Full mesh (num_switches, hosts_per_switch)
    - ring: Ring topology (num_switches, hosts_per_switch)
    - star: Star topology (num_edge_switches, hosts_per_switch)
    - fat_tree: Fat-tree datacenter (k)
    """
    try:
        logger.info(f"Generating {request.topology_type} topology: {request.name}")

        topology_data = None

        if request.topology_type.lower() == "tree":
            topology_data = TreeTopologyGenerator.generate(request.name, request.parameters)
            
        elif request.topology_type.lower() == "linear":
            topology_data = LinearTopologyGenerator.generate(request.name, request.parameters)
            
        elif request.topology_type.lower() == "mesh":
            topology_data = MeshTopologyGenerator.generate(request.name, request.parameters)
            
        elif request.topology_type.lower() == "ring":
            topology_data = RingTopologyGenerator.generate(request.name, request.parameters)
            
        elif request.topology_type.lower() == "star":
            topology_data = StarTopologyGenerator.generate(request.name, request.parameters)
            
        elif request.topology_type.lower() == "fat_tree":
            topology_data = FatTreeTopologyGenerator.generate(request.name, request.parameters)
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported topology type: {request.topology_type}"
            )

        topology_data["description"] = request.description or f"Auto-generated {request.topology_type} topology"
        topology_data["generated_at"] = datetime.utcnow()

        # Publish event
        publish_event("generated", {
            "topology_type": request.topology_type,
            "name": request.name,
            "node_count": len(topology_data["nodes"]),
            "link_count": len(topology_data["links"])
        })

        return GeneratedTopology(**topology_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/templates")
async def list_templates():
    """List available topology templates with parameter descriptions"""
    return {
        "templates": [
            {
                "type": "tree",
                "name": "Tree Topology",
                "description": "Hierarchical tree structure",
                "parameters": {
                    "depth": {"type": "int", "default": 2, "description": "Tree depth"},
                    "fanout": {"type": "int", "default": 2, "description": "Children per node"},
                    "hosts_per_switch": {"type": "int", "default": 2, "description": "Hosts per leaf switch"}
                }
            },
            {
                "type": "linear",
                "name": "Linear Topology",
                "description": "Linear chain of switches",
                "parameters": {
                    "num_switches": {"type": "int", "default": 3, "description": "Number of switches"},
                    "hosts_per_switch": {"type": "int", "default": 1, "description": "Hosts per switch"}
                }
            },
            {
                "type": "mesh",
                "name": "Mesh Topology",
                "description": "Full mesh - all switches connected",
                "parameters": {
                    "num_switches": {"type": "int", "default": 4, "description": "Number of switches"},
                    "hosts_per_switch": {"type": "int", "default": 1, "description": "Hosts per switch"}
                }
            },
            {
                "type": "ring",
                "name": "Ring Topology",
                "description": "Switches connected in a ring",
                "parameters": {
                    "num_switches": {"type": "int", "default": 4, "description": "Number of switches"},
                    "hosts_per_switch": {"type": "int", "default": 1, "description": "Hosts per switch"}
                }
            },
            {
                "type": "star",
                "name": "Star Topology",
                "description": "Central switch with edge switches",
                "parameters": {
                    "num_edge_switches": {"type": "int", "default": 4, "description": "Number of edge switches"},
                    "hosts_per_switch": {"type": "int", "default": 2, "description": "Hosts per edge switch"}
                }
            },
            {
                "type": "fat_tree",
                "name": "Fat-Tree Topology",
                "description": "Datacenter fat-tree topology",
                "parameters": {
                    "k": {"type": "int", "default": 4, "description": "Number of ports per switch (must be even)"}
                }
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
