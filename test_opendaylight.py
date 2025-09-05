#!/usr/bin/env python3
"""
Test script for OpenDaylight Controller Manager
Tests enterprise-grade SDN controller functionality
"""

import sys
import time
import json
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from core.mininet_manager import MininetManager

def test_opendaylight_basic():
    """Test basic OpenDaylight functionality"""
    print("=== Testing OpenDaylight Controller ===")

    manager = MininetManager()

    # Check Java requirements
    odl_controller = manager.controller_factory.controllers.get('opendaylight')
    if odl_controller:
        java_version = odl_controller.java_version
        print(f"Java version: {java_version}")
        if not java_version or java_version < 11:
            print("❌ Java 11+ required for OpenDaylight")
            return False

    # Test controller info
    info = manager.get_all_controller_info()
    odl_info = info.get('opendaylight', {})
    print(f"OpenDaylight info: {json.dumps(odl_info, indent=2)}")

    return True

def test_opendaylight_installation():
    """Test OpenDaylight installation"""
    print("\n=== Testing OpenDaylight Installation ===")

    manager = MininetManager()

    try:
        # Test installation
        print("Installing OpenDaylight...")
        success = manager.install_opendaylight()
        print(f"Installation: {'SUCCESS' if success else 'FAILED'}")

        if success:
            # Get system info
            system_info = manager.get_opendaylight_system_info()
            print(f"System info: {json.dumps(system_info, indent=2)}")

        return success

    except Exception as e:
        print(f"Installation error: {e}")
        return False

def test_opendaylight_startup():
    """Test OpenDaylight startup and basic operations"""
    print("\n=== Testing OpenDaylight Startup ===")

    manager = MininetManager()

    try:
        # Start OpenDaylight
        print("Starting OpenDaylight controller...")
        success = manager.start_opendaylight_controller('l2switch', 8181)
        print(f"Startup: {'SUCCESS' if success else 'FAILED'}")

        if success:
            # Wait for startup
            time.sleep(10)

            # Get status
            status = manager.get_opendaylight_status()
            print(f"Status: {json.dumps(status, indent=2)}")

            # Get API endpoints
            endpoints = manager.get_opendaylight_api_endpoints()
            print(f"API endpoints: {json.dumps(endpoints, indent=2)}")

            # Test karaf commands
            print("Testing karaf commands...")

            # List features
            features_result = manager.list_opendaylight_features()
            print(f"Features list: {'SUCCESS' if features_result.get('success') else 'FAILED'}")

            # List bundles
            bundles_result = manager.list_opendaylight_bundles()
            print(f"Bundles list: {'SUCCESS' if bundles_result.get('success') else 'FAILED'}")

            # Get logs
            logs = manager.get_opendaylight_logs()
            print(f"Logs (last 5 lines): {logs['logs'][-5:] if logs['logs'] else 'No logs'}")

            # Stop controller
            stopped = manager.stop_opendaylight_controller()
            print(f"Stop: {'SUCCESS' if stopped else 'FAILED'}")

        return success

    except Exception as e:
        print(f"Startup error: {e}")
        return False

def test_opendaylight_topology_creation():
    """Test topology creation with OpenDaylight"""
    print("\n=== Testing Topology Creation with OpenDaylight ===")

    manager = MininetManager()

    # Simple topology configuration
    topology_config = {
        'nodes': [
            {'id': 'h1', 'type': 'host', 'ip': '10.0.1.10/24'},
            {'id': 'h2', 'type': 'host', 'ip': '10.0.1.11/24'},
            {'id': 's1', 'type': 'switch'},
            {'id': 'c0', 'type': 'controller', 'ip': '127.0.0.1', 'port': 8181}
        ],
        'links': [
            {'source': 'h1', 'target': 's1'},
            {'source': 'h2', 'target': 's1'}
        ]
    }

    try:
        # Create topology with OpenDaylight
        print("Creating topology with OpenDaylight...")
        success = manager.create_custom_topology(
            topology_config,
            controller_type='opendaylight',
            controller_app='l2switch'
        )

        print(f"Topology creation: {'SUCCESS' if success else 'FAILED'}")

        if success:
            # Get controller status
            status = manager.get_opendaylight_status()
            print(f"Controller status: {json.dumps(status, indent=2)}")

            # Clean up
            if hasattr(manager, 'net') and manager.net:
                manager.net.stop()
                manager.net = None

        return success

    except Exception as e:
        print(f"Topology creation error: {e}")
        return False

def test_opendaylight_feature_management():
    """Test OpenDaylight feature management"""
    print("\n=== Testing OpenDaylight Feature Management ===")

    manager = MininetManager()

    try:
        # Start controller
        print("Starting OpenDaylight for feature testing...")
        success = manager.start_opendaylight_controller('l2switch')

        if success:
            time.sleep(15)  # Wait for full startup

            # Test feature installation
            print("Installing additional feature...")
            install_result = manager.install_opendaylight_feature('odl-netconf-topology')
            print(f"Feature install: {'SUCCESS' if install_result.get('success') else 'FAILED'}")

            # Test feature uninstallation
            print("Uninstalling feature...")
            uninstall_result = manager.uninstall_opendaylight_feature('odl-netconf-topology')
            print(f"Feature uninstall: {'SUCCESS' if uninstall_result.get('success') else 'FAILED'}")

            # Stop controller
            manager.stop_opendaylight_controller()

        return success

    except Exception as e:
        print(f"Feature management error: {e}")
        return False

def test_opendaylight_karaf_commands():
    """Test various karaf commands"""
    print("\n=== Testing Karaf Commands ===")

    manager = MininetManager()

    try:
        # Start controller
        success = manager.start_opendaylight_controller('l2switch')

        if success:
            time.sleep(10)

            # Test various karaf commands
            commands = [
                'feature:list | grep -i l2',
                'bundle:list | head -5',
                'system:property'
            ]

            for cmd in commands:
                print(f"Executing: {cmd}")
                result = manager.execute_opendaylight_command(cmd, timeout=10)
                print(f"Result: {'SUCCESS' if result.get('success') else 'FAILED'}")
                if result.get('success'):
                    print(f"Output: {result.get('stdout', '')[:200]}...")

            # Stop controller
            manager.stop_opendaylight_controller()

        return success

    except Exception as e:
        print(f"Karaf commands error: {e}")
        return False

def main():
    """Main test function"""
    print("OpenDaylight Controller Test Suite")
    print("=" * 50)

    try:
        # Test basic functionality
        if not test_opendaylight_basic():
            print("❌ Basic test failed")
            return 1

        # Test installation
        if not test_opendaylight_installation():
            print("❌ Installation test failed")
            return 1

        # Test startup
        if not test_opendaylight_startup():
            print("❌ Startup test failed")
            return 1

        # Test topology creation
        if not test_opendaylight_topology_creation():
            print("❌ Topology creation test failed")
            return 1

        # Test feature management
        if not test_opendaylight_feature_management():
            print("❌ Feature management test failed")
            return 1

        # Test karaf commands
        if not test_opendaylight_karaf_commands():
            print("❌ Karaf commands test failed")
            return 1

        print("\n🎉 All OpenDaylight tests completed successfully!")
        return 0

    except Exception as e:
        print(f"Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
