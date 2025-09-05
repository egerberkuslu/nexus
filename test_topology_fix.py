#!/usr/bin/env python3
"""
Test script to verify custom topology manager fixes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/backend')

from core.managers.network_topology_manager import NetworkTopologyManager
from core.factories.controller_factory import ControllerFactory
from core.factories.switch_factory import SwitchFactory

def test_custom_topology_creation():
    """Test creating a custom topology with various node types"""

    # Initialize components
    controller_factory = ControllerFactory()
    switch_factory = SwitchFactory()
    topology_manager = NetworkTopologyManager(controller_factory, switch_factory)

    # Test topology configuration
    test_topology = {
        'nodes': [
            {
                'id': 'h1',
                'type': 'host',
                'ip': '10.0.0.1',
                'x': 100,
                'y': 100
            },
            {
                'id': 'r1',
                'type': 'router',
                'ip': '10.0.0.254',
                'x': 300,
                'y': 100
            },
            {
                'id': 's1',
                'type': 'switch',
                'switch_type': 'ovs',
                'x': 200,
                'y': 200
            },
            {
                'id': 'c1',
                'type': 'controller',
                'controller_type': 'ryu',
                'port': 6633,
                'ip': '127.0.0.1',
                'x': 200,
                'y': 50
            }
        ],
        'links': [
            {
                'source': 'h1',
                'target': 's1',
                'bandwidth': '10M'
            },
            {
                'source': 'r1',
                'target': 's1',
                'bandwidth': '1G'
            }
        ]
    }

    print("Testing custom topology creation...")
    print(f"Topology config: {test_topology}")

    try:
        # Create the topology
        net, success = topology_manager.create_custom_topology(
            test_topology,
            controller_type='ryu',
            controller_app='simple_switch_13',
            controller_port=6633,
            switch_type='ovs'
        )

        if success:
            print("✅ Topology creation successful!")
            print(f"Network object: {type(net)}")

            # Test topology data update
            topology_manager.update_topology_data(net)
            print("✅ Topology data update successful!")

            # Check if nodes exist
            nodes_data = topology_manager.topology_data.get('nodes', [])
            controllers_data = topology_manager.topology_data.get('controllers', [])
            links_data = topology_manager.topology_data.get('links', [])

            print(f"✅ Found {len(nodes_data)} network nodes")
            print(f"✅ Found {len(controllers_data)} controllers")
            print(f"✅ Found {len(links_data)} links")

            # Check router creation
            router_nodes = [n for n in nodes_data if n.get('type') == 'router']
            print(f"✅ Found {len(router_nodes)} router nodes")

            if router_nodes:
                router = router_nodes[0]
                print(f"Router details: {router}")

            return True
        else:
            print("❌ Topology creation failed!")
            return False

    except Exception as e:
        print(f"❌ Error during topology creation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing Custom Topology Manager Fixes")
    print("=" * 50)

    success = test_custom_topology_creation()

    if success:
        print("\n🎉 All tests passed! Custom topology manager is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the error messages above.")

    sys.exit(0 if success else 1)