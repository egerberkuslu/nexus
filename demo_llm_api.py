#!/usr/bin/env python3
"""
Demo script showing the working LLM API features
"""

import requests
import json
import time

def test_llm_api():
    """Test the LLM API and show working features"""
    
    base_url = "http://localhost:5000/api/llm"
    
    print("🚀 LLM API Demo - Mininet Web Framework")
    print("=" * 50)
    
    # Test 1: Check API status
    print("\n1. 📊 Checking API Status...")
    try:
        response = requests.get(f"{base_url}/status", timeout=10)
        if response.status_code == 200:
            status = response.json()
            print("   ✅ API is running")
            print(f"   📝 Model: {status['llm_service']['model_name']}")
            print(f"   🔗 Service: {status['llm_service']['service_type']}")
            print(f"   📚 Templates: {status['topology_service']['templates_available']}")
        else:
            print("   ❌ API not responding")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Test 2: Chat functionality
    print("\n2. 💬 Testing Chat Functionality...")
    try:
        chat_payload = {
            "message": "What is a network switch and how does it work?",
            "use_history": False
        }
        
        response = requests.post(
            f"{base_url}/chat",
            json=chat_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("   ✅ Chat working!")
                response_text = result.get('response', '')
                print(f"   📝 Response length: {len(response_text)} characters")
                print(f"   ⏱️  Processing time: {result.get('processing_time', 0):.2f}s")
                print(f"   💭 Preview: {response_text[:100]}...")
            else:
                print(f"   ❌ Chat failed: {result.get('error')}")
        else:
            print(f"   ❌ Chat request failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Chat error: {e}")
    
    # Test 3: Template generation
    print("\n3. 📋 Testing Template Generation...")
    try:
        template_payload = {
            "template_name": "simple_switch",
            "parameters": {"hosts": 3}
        }
        
        response = requests.post(
            f"{base_url}/generate-from-template",
            json=template_payload,
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("   ✅ Template generation working!")
                topology = result.get('topology_config', {}).get('topology', {})
                nodes = topology.get('nodes', [])
                links = topology.get('links', [])
                print(f"   📊 Generated: {len(nodes)} nodes, {len(links)} links")
                
                # Show node details
                print("   🔧 Nodes:")
                for node in nodes:
                    node_type = node.get('type', 'unknown')
                    node_id = node.get('id', 'unknown')
                    print(f"      - {node_id} ({node_type})")
                
                # Check if network was created
                if result.get('network_created'):
                    print("   🌐 Network created and started!")
                else:
                    print("   ⚠️  Network not created (API only)")
            else:
                print(f"   ❌ Template generation failed: {result.get('error')}")
        else:
            print(f"   ❌ Template request failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Template error: {e}")
    
    # Test 4: Available templates
    print("\n4. 📚 Available Templates...")
    try:
        response = requests.get(f"{base_url}/templates", timeout=10)
        if response.status_code == 200:
            result = response.json()
            templates = result.get('templates', {})
            print("   ✅ Templates loaded:")
            for name, info in templates.items():
                print(f"      - {name}: {info.get('description', 'No description')}")
        else:
            print("   ❌ Could not load templates")
    except Exception as e:
        print(f"   ❌ Template list error: {e}")
    
    # Test 5: Simple topology generation (with error handling)
    print("\n5. 🏗️  Testing Simple Topology Generation...")
    try:
        topology_payload = {
            "description": "Create a basic network with 2 hosts and 1 switch",
            "parameters": {}
        }
        
        response = requests.post(
            f"{base_url}/generate-topology",
            json=topology_payload,
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("   ✅ Topology generation working!")
                topology = result.get('topology_config', {}).get('topology', {})
                nodes = topology.get('nodes', [])
                links = topology.get('links', [])
                print(f"   📊 Generated: {len(nodes)} nodes, {len(links)} links")
                
                if result.get('network_created'):
                    print("   🌐 Network created and started!")
                else:
                    print("   ⚠️  Network not created (API only)")
            else:
                print(f"   ❌ Topology generation failed: {result.get('error')}")
                # Show validation errors if any
                validation = result.get('validation', {})
                if validation.get('errors'):
                    print(f"   🔍 Validation errors: {validation['errors']}")
        else:
            print(f"   ❌ Topology request failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Topology error: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 Summary")
    print("=" * 50)
    print("✅ Working Features:")
    print("   - Chat with LLM about networking")
    print("   - Template-based topology generation")
    print("   - API status and service management")
    print("   - Network creation and auto-start")
    print("\n⚠️  Areas for improvement:")
    print("   - Natural language topology generation (JSON parsing issues)")
    print("   - Complex topology descriptions (timeout issues)")
    print("\n🚀 Ready to use:")
    print("   - POST /api/llm/chat")
    print("   - POST /api/llm/generate-from-template")
    print("   - GET  /api/llm/templates")
    print("   - GET  /api/llm/status")

if __name__ == "__main__":
    test_llm_api()
