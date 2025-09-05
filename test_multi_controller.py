#!/usr/bin/env python3
"""
Test script for multi-controller support in MininetManager
Tests Ryu, POX, and os-ken controllers
"""

import sys
import time
import json
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from core.mininet_manager import MininetManager

def test_controller_factory():
    """Test the controller factory functionality"""
    print("=== Testing Controller Factory ===")

    manager = MininetManager()

    # Test available controllers
    available = manager.get_available_controllers()
    print(f"Available controllers: {available}")

    # Test controller info
    info = manager.get_all_controller_info()
    print(f"Controller info: {json.dumps(info, indent=2)}")

    return manager

def test_individual_controllers(manager):
    """Test each controller individually"""
    print("\n=== Testing Individual Controllers ===")

    controllers_to_test = [
        ('ryu', 'simple_switch_13'),
        ('osken', 'simple_switch_13'),
        ('pox', 'l2_learning')
    ]

    for controller_type, app in controllers_to_test:
        print(f"\n--- Testing {controller_type} with {app} ---")

        try:
            # Start controller
            success = manager.start_controller(controller_type, app)
            print(f"Start {controller_type}: {'SUCCESS' if success else 'FAILED'}")

            if success:
                # Get status
                status = manager.get_controller_status()
                print(f"Status: {json.dumps(status, indent=2)}")

                # Get logs
                logs = manager.get_controller_logs()
                print(f"Logs (last 3 lines): {logs['logs'][-3:] if logs['logs'] else 'No logs'}")

                # Wait a bit
                time.sleep(2)

                # Stop controller
                stopped = manager.stop_controller()
                print(f"Stop {controller_type}: {'SUCCESS' if stopped else 'FAILED'}")

        except Exception as e:
            print(f"Error testing {controller_type}: {e}")

def test_controller_switching(manager):
    """Test switching between controllers"""
    print("\n=== Testing Controller Switching ===")

    # Start Ryu
    print("Starting Ryu controller...")
    manager.start_controller('ryu', 'simple_switch_13')

    time.sleep(2)
    status1 = manager.get_controller_status()
    print(f"Active controller: {status1.get('controller_framework', 'none')}")

    # Switch to POX
    print("Switching to POX controller...")
    manager.switch_controller('pox', 'l2_learning')

    time.sleep(2)
    status2 = manager.get_controller_status()
    print(f"Active controller: {status2.get('controller_framework', 'none')}")

    # Switch to os-ken
    print("Switching to os-ken controller...")
    manager.switch_controller('osken', 'simple_switch_13')

    time.sleep(2)
    status3 = manager.get_controller_status()
    print(f"Active controller: {status3.get('controller_framework', 'none')}")

    # Stop active controller
    manager.stop_controller()

def test_topology_creation(manager):
    """Test topology creation with different controllers"""
    print("\n=== Testing Topology Creation ===")

    # Simple topology configuration
    topology_config = {
        'nodes': [
            {'id': 'h1', 'type': 'host', 'ip': '10.0.1.10/24'},
            {'id': 'h2', 'type': 'host', 'ip': '10.0.1.11/24'},
            {'id': 's1', 'type': 'switch'},
            {'id': 'c0', 'type': 'controller', 'ip': '127.0.0.1', 'port': 6633}
        ],
        'links': [
            {'source': 'h1', 'target': 's1'},
            {'source': 'h2', 'target': 's1'}
        ]
    }

    controllers_to_test = [
        ('ryu', 'simple_switch_13'),
        ('osken', 'simple_switch_13'),
        ('pox', 'l2_learning'),
        ('opendaylight', 'l2switch')
    ]

    for controller_type, app in controllers_to_test:
        print(f"\n--- Creating topology with {controller_type} ---")

        try:
            # Adjust configuration for OpenDaylight
            if controller_type == 'opendaylight':
                # Update topology config for ODL port
                odl_config = topology_config.copy()
                odl_config['nodes'] = [
                    node if node['type'] != 'controller'
                    else {**node, 'port': 8181}
                    for node in odl_config['nodes']
                ]
                config_to_use = odl_config
            else:
                config_to_use = topology_config

            # Create topology with specific controller
            success = manager.create_custom_topology(
                config_to_use,
                controller_type=controller_type,
                controller_app=app
            )

            print(f"Topology creation: {'SUCCESS' if success else 'FAILED'}")

            if success:
                # Get controller status
                status = manager.get_controller_status()
                print(f"Controller status: {json.dumps(status, indent=2)}")

                # Clean up
                if hasattr(manager, 'net') and manager.net:
                    manager.net.stop()
                    manager.net = None

        except Exception as e:
            print(f"Error creating topology with {controller_type}: {e}")

def test_benchmarking(manager):
    """Test controller benchmarking"""
    print("\n=== Testing Controller Benchmarking ===")

    try:
        # Benchmark available controllers
        controllers_to_benchmark = ['ryu', 'osken', 'opendaylight']
        results = manager.benchmark_controllers(
            controllers=controllers_to_benchmark,
            app='simple_switch_13',
            duration=5  # Short duration for testing
        )

        print("Benchmark results:")
        for controller, result in results.items():
            if 'error' in result:
                print(f"  {controller}: ERROR - {result['error']}")
            else:
                print(f"  {controller}: {result['duration']}s duration")

    except Exception as e:
        print(f"Benchmarking error: {e}")

def main():
    """Main test function"""
    print("Multi-Controller Test Suite")
    print("=" * 50)

    try:
        # Test controller factory
        manager = test_controller_factory()

        # Test individual controllers
        test_individual_controllers(manager)

        # Test controller switching
        test_controller_switching(manager)

        # Test topology creation
        test_topology_creation(manager)

        # Test benchmarking
        test_benchmarking(manager)

        # Cleanup
        print("\n=== Cleanup ===")
        manager.stop_controller()
        print("Test completed successfully!")

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
