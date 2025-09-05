#!/usr/bin/env python3
"""
Example script demonstrating LLM-based topology generation
"""

import requests
import json
import time

def generate_topology_example():
    """Example of generating a topology using natural language"""
    
    # API endpoint
    base_url = "http://localhost:5000/api/llm"
    
    # Example descriptions
    examples = [
        "Create a simple network with 2 hosts connected to 1 switch",
        "Build a datacenter topology with 4 hosts, 2 switches, and 1 router",
        "Design a star topology with 5 hosts connected to a central switch and controller",
        "Create a linear network with 3 switches and 6 hosts",
        "Build a mesh network with 4 switches and 8 hosts"
    ]
    
    print("LLM Topology Generation Examples")
    print("=" * 50)
    
    for i, description in enumerate(examples, 1):
        print(f"\nExample {i}: {description}")
        print("-" * 40)
        
        try:
            # Generate topology
            payload = {
                "description": description,
                "parameters": {}
            }
            
            response = requests.post(
                f"{base_url}/generate-topology",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    topology_config = result.get('topology_config', {})
                    topology = topology_config.get('topology', {})
                    nodes = topology.get('nodes', [])
                    links = topology.get('links', [])
                    
                    print(f"✓ Generated successfully!")
                    print(f"  Nodes: {len(nodes)}")
                    print(f"  Links: {len(links)}")
                    
                    # Show node details
                    print("  Node details:")
                    for node in nodes:
                        node_type = node.get('type', 'unknown')
                        node_id = node.get('id', 'unknown')
                        print(f"    - {node_id} ({node_type})")
                    
                    # Show link details
                    print("  Link details:")
                    for link in links:
                        source = link.get('source', 'unknown')
                        target = link.get('target', 'unknown')
                        bandwidth = link.get('bandwidth', 'unknown')
                        print(f"    - {source} -> {target} ({bandwidth})")
                    
                    # Check if network was created
                    if result.get('network_created'):
                        print("  ✓ Network created and started")
                    else:
                        print("  ⚠ Network not created (API only)")
                    
                else:
                    print(f"✗ Generation failed: {result.get('error', 'Unknown error')}")
            
            else:
                print(f"✗ API request failed: {response.status_code}")
                print(f"  Response: {response.text}")
        
        except requests.exceptions.ConnectionError:
            print("✗ Cannot connect to server. Make sure the backend is running.")
            break
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Small delay between examples
        time.sleep(1)

def chat_example():
    """Example of chatting with the LLM about networking"""
    
    base_url = "http://localhost:5000/api/llm"
    
    print("\n\nLLM Chat Example")
    print("=" * 30)
    
    questions = [
        "What is a network topology?",
        "Explain the difference between a switch and a router",
        "What is SDN and how does it work?",
        "Describe the benefits of a mesh network topology"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}: {question}")
        print("-" * 40)
        
        try:
            payload = {
                "message": question,
                "use_history": False
            }
            
            response = requests.post(
                f"{base_url}/chat",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    response_text = result.get('response', '')
                    print(f"✓ Response received ({len(response_text)} characters)")
                    print(f"Response: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
                else:
                    print(f"✗ Chat failed: {result.get('error', 'Unknown error')}")
            else:
                print(f"✗ API request failed: {response.status_code}")
        
        except Exception as e:
            print(f"✗ Error: {e}")
        
        time.sleep(1)

def template_example():
    """Example of using predefined templates"""
    
    base_url = "http://localhost:5000/api/llm"
    
    print("\n\nTemplate Generation Example")
    print("=" * 35)
    
    # Get available templates
    try:
        response = requests.get(f"{base_url}/templates", timeout=10)
        if response.status_code == 200:
            result = response.json()
            templates = result.get('templates', {})
            
            print("Available templates:")
            for name, info in templates.items():
                print(f"  - {name}: {info.get('description', 'No description')}")
            
            # Generate from a template
            print(f"\nGenerating from 'simple_switch' template...")
            
            payload = {
                "template_name": "simple_switch",
                "parameters": {
                    "hosts": 4
                }
            }
            
            response = requests.post(
                f"{base_url}/generate-from-template",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    topology_config = result.get('topology_config', {})
                    topology = topology_config.get('topology', {})
                    nodes = topology.get('nodes', [])
                    links = topology.get('links', [])
                    
                    print(f"✓ Generated from template successfully!")
                    print(f"  Nodes: {len(nodes)}")
                    print(f"  Links: {len(links)}")
                else:
                    print(f"✗ Template generation failed: {result.get('error', 'Unknown error')}")
            else:
                print(f"✗ API request failed: {response.status_code}")
        
    except Exception as e:
        print(f"✗ Error: {e}")

def main():
    """Run all examples"""
    print("Starting LLM Topology Generation Examples...")
    print("Make sure the backend server is running on http://localhost:5000")
    print("Press Ctrl+C to stop at any time\n")
    
    try:
        # Test server availability
        response = requests.get("http://localhost:5000/api/llm/status", timeout=5)
        if response.status_code != 200:
            print("✗ Server not available. Please start the backend server first.")
            return
        
        print("✓ Server is available\n")
        
        # Run examples
        generate_topology_example()
        chat_example()
        template_example()
        
        print("\n" + "=" * 50)
        print("Examples completed!")
        print("\nYou can now use the API endpoints:")
        print("  POST /api/llm/generate-topology")
        print("  POST /api/llm/chat")
        print("  POST /api/llm/generate-from-template")
        print("  GET  /api/llm/templates")
        print("  GET  /api/llm/status")
        
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Please start the backend server first.")
        print("Run: sudo python backend/app.py")
    except KeyboardInterrupt:
        print("\n\nExamples stopped by user.")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

if __name__ == "__main__":
    main()
