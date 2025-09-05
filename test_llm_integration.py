#!/usr/bin/env python3
"""
Test script for LLM integration
Tests the complete LLM topology generation flow
"""

import sys
import os
import json
import requests
import time

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)

def test_llm_service():
    """Test the LLM service directly"""
    print("Testing LLM service directly...")
    
    try:
        from core.llm import LLMFactory, LLMManager, TopologyLLMService
        
        # Test factory
        print("1. Testing LLM Factory...")
        available_services = LLMFactory.get_available_services()
        print(f"   Available services: {available_services}")
        
        # Test manager
        print("2. Testing LLM Manager...")
        llm_manager = LLMManager()
        print(f"   Service info: {llm_manager.get_service_info()}")
        
        # Test topology service
        print("3. Testing Topology LLM Service...")
        topology_service = TopologyLLMService(llm_manager)
        print(f"   Service status: {topology_service.get_service_status()}")
        
        # Test simple generation
        print("4. Testing topology generation...")
        description = "Create a simple network with 2 hosts connected to a switch"
        result = topology_service.generate_topology_from_description(description)
        
        if result.get('success'):
            print("   ✓ Topology generation successful!")
            print(f"   Generated {result.get('metadata', {}).get('node_count', 0)} nodes")
            print(f"   Generated {result.get('metadata', {}).get('link_count', 0)} links")
        else:
            print(f"   ✗ Topology generation failed: {result.get('error', 'Unknown error')}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"   ✗ Direct test failed: {e}")
        return False

def test_api_endpoints():
    """Test the API endpoints"""
    print("\nTesting API endpoints...")
    
    base_url = "http://localhost:5000/api/llm"
    
    try:
        # Test status endpoint
        print("1. Testing status endpoint...")
        response = requests.get(f"{base_url}/status", timeout=10)
        if response.status_code == 200:
            print("   ✓ Status endpoint working")
            status_data = response.json()
            print(f"   Available services: {status_data.get('available_services', {})}")
        else:
            print(f"   ✗ Status endpoint failed: {response.status_code}")
            return False
        
        # Test topology generation endpoint
        print("2. Testing topology generation endpoint...")
        test_description = "Create a network with 3 hosts, 2 switches, and 1 router"
        
        payload = {
            "description": test_description,
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
                print("   ✓ Topology generation API working!")
                print(f"   Generated topology with {len(result.get('topology_config', {}).get('topology', {}).get('nodes', []))} nodes")
            else:
                print(f"   ✗ Topology generation failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"   ✗ API request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        # Test chat endpoint
        print("3. Testing chat endpoint...")
        chat_payload = {
            "message": "What is a network topology?",
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
                print("   ✓ Chat endpoint working!")
                print(f"   Response length: {len(result.get('response', ''))}")
            else:
                print(f"   ✗ Chat failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"   ✗ Chat API request failed: {response.status_code}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to API server. Make sure the server is running.")
        return False
    except Exception as e:
        print(f"   ✗ API test failed: {e}")
        return False

def test_network_creation():
    """Test creating a network using the generated topology"""
    print("\nTesting network creation with generated topology...")
    
    base_url = "http://localhost:5000/api/llm"
    network_url = "http://localhost:5000/api/network"
    
    try:
        # Generate a simple topology
        print("1. Generating topology...")
        payload = {
            "description": "Create a simple network with 2 hosts connected to 1 switch and 1 controller",
            "parameters": {}
        }
        
        response = requests.post(
            f"{base_url}/generate-topology",
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200 or not response.json().get('success'):
            print("   ✗ Failed to generate topology")
            return False
        
        result = response.json()
        topology_config = result.get('topology_config', {})
        
        print("2. Creating network...")
        # Use the existing network creation API
        network_payload = topology_config
        
        response = requests.post(
            f"{network_url}/create",
            json=network_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            network_result = response.json()
            if network_result.get('success'):
                print("   ✓ Network created successfully!")
                print(f"   Message: {network_result.get('message', '')}")
                
                # Check network status
                status_response = requests.get(f"{network_url}/status")
                if status_response.status_code == 200:
                    status = status_response.json()
                    print(f"   Network running: {status.get('running', False)}")
                
                return True
            else:
                print(f"   ✗ Network creation failed: {network_result.get('error', 'Unknown error')}")
        else:
            print(f"   ✗ Network creation API failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
        return False
        
    except Exception as e:
        print(f"   ✗ Network creation test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("LLM Integration Test Suite")
    print("=" * 60)
    
    # Test 1: Direct service test
    direct_success = test_llm_service()
    
    # Test 2: API endpoints test
    api_success = test_api_endpoints()
    
    # Test 3: Network creation test
    network_success = test_network_creation()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    print(f"Direct Service Test: {'✓ PASS' if direct_success else '✗ FAIL'}")
    print(f"API Endpoints Test:  {'✓ PASS' if api_success else '✗ FAIL'}")
    print(f"Network Creation:    {'✓ PASS' if network_success else '✗ FAIL'}")
    
    if all([direct_success, api_success, network_success]):
        print("\n🎉 All tests passed! LLM integration is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
    
    print("\nAPI Endpoints available:")
    print("  GET  /api/llm/status")
    print("  POST /api/llm/generate-topology")
    print("  POST /api/llm/generate-from-template")
    print("  POST /api/llm/chat")
    print("  POST /api/llm/suggest-improvements")
    print("  GET  /api/llm/templates")
    print("  POST /api/llm/validate-topology")

if __name__ == "__main__":
    main()
