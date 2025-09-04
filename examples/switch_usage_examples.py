#!/usr/bin/env python3
"""
Switch Usage Examples for Mininet Web Framework
Demonstrates how to use the new multi-switch support
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.mininet_manager import MininetManager
from backend.core.managers.switch_factory import SwitchFactory


def example_linux_bridge_topology():
    """Create a topology with Linux Bridge switches"""
    print("=== Linux Bridge Topology Example ===")

    mgr = MininetManager()

    # Define topology with Linux Bridge switches
    topology_config = {
        'nodes': [
            {'id': 'h1', 'type': 'host', 'ip': '192.168.1.1', 'x': 100, 'y': 100},
            {'id': 'h2', 'type': 'host', 'ip': '192.168.1.2', 'x': 300, 'y': 100},
            {'id': 'h3', 'type': 'host', 'ip': '192.168.1.3', 'x': 500, 'y': 100},
            {'id': 'br1', 'type': 'switch', 'x': 200, 'y': 200},
            {'id': 'br2', 'type': 'switch', 'x': 400, 'y': 200},
        ],
        'links': [
            {'source': 'h1', 'target': 'br1'},
            {'source': 'h2', 'target': 'br1'},
            {'source': 'h2', 'target': 'br2'},
            {'source': 'h3', 'target': 'br2'},
            {'source': 'br1', 'target': 'br2'},
        ]
    }

    # Create topology with Linux Bridge switches
    success = mgr.create_custom_topology(topology_config, switch_type='linux_bridge')

    if success:
        print("✓ Linux Bridge topology created successfully")
        print("✓ Switches are operating as learning bridges")
        print("✓ No controller required for basic L2 forwarding")

        # Get switch information
        switch_info = mgr.get_switch_info()
        print(f"Active switches: {list(switch_info.keys())}")

        return True
    else:
        print("✗ Failed to create Linux Bridge topology")
        return False


def example_p4_switch_topology():
    """Create a topology with P4 switches"""
    print("\n=== P4 Switch Topology Example ===")

    mgr = MininetManager()

    # Define topology with P4 switches
    topology_config = {
        'nodes': [
            {'id': 'h1', 'type': 'host', 'ip': '10.0.1.1', 'x': 100, 'y': 100},
            {'id': 'h2', 'type': 'host', 'ip': '10.0.1.2', 'x': 300, 'y': 100},
            {'id': 'p4s1', 'type': 'switch', 'x': 200, 'y': 200, 'p4_program': 'basic_forwarding'},
        ],
        'links': [
            {'source': 'h1', 'target': 'p4s1'},
            {'source': 'h2', 'target': 'p4s1'},
        ]
    }

    # Create topology with P4 switches
    success = mgr.create_custom_topology(topology_config, switch_type='p4')

    if success:
        print("✓ P4 topology created successfully")
        print("✓ P4 program 'basic_forwarding' loaded")
        print("✓ P4Runtime API available for table management")

        # Demonstrate P4 table operations
        print("\n--- P4 Table Management ---")

        # Add a forwarding rule
        match_fields = {
            'hdr.ethernet.dstAddr': '00:00:00:00:00:02'  # h2's MAC
        }
        action_params = {'port': 2}  # Forward to h2's port

        success = mgr.add_p4_table_entry('dmac', match_fields, 'forward', action_params)
        if success:
            print("✓ Added forwarding rule: h1 -> h2")
        else:
            print("✗ Failed to add forwarding rule")

        # Get table entries
        entries = mgr.get_p4_table_entries('dmac')
        print(f"Table entries: {entries}")

        return True
    else:
        print("✗ Failed to create P4 topology")
        return False


def example_mixed_switch_topology():
    """Create a topology with mixed switch types"""
    print("\n=== Mixed Switch Topology Example ===")

    mgr = MininetManager()

    # Note: Mixed topologies require manual switch creation
    # since create_custom_topology uses a single switch_type

    # Create individual switches
    print("Creating mixed switch topology...")

    # Create Linux Bridge switch
    br_success = mgr.create_switch('linux_bridge', 'br1')
    if br_success:
        print("✓ Linux Bridge switch 'br1' created")

    # Create P4 switch
    p4_success = mgr.create_switch('p4', 'p4s1', program_name='basic_forwarding')
    if p4_success:
        print("✓ P4 switch 'p4s1' created")

    # Get information about all switches
    switch_info = mgr.get_switch_info()
    print(f"\nAvailable switches: {list(switch_info.keys())}")

    for switch_type, info in switch_info.items():
        if info and 'running' in info:
            print(f"- {switch_type}: {'Running' if info['running'] else 'Stopped'}")

    return br_success and p4_success


def example_switch_capabilities():
    """Demonstrate switch capabilities querying"""
    print("\n=== Switch Capabilities Example ===")

    mgr = MininetManager()

    switch_types = mgr.get_available_switches()
    print(f"Available switch types: {switch_types}")

    for switch_type in switch_types:
        capabilities = mgr.get_switch_capabilities(switch_type)
        print(f"\n--- {switch_type.upper()} Capabilities ---")
        print(f"Name: {capabilities.get('name', 'Unknown')}")
        print(f"Standalone operation: {capabilities.get('standalone_operation', False)}")
        print(f"OpenFlow support: {capabilities.get('supports_openflow', False)}")
        print(f"P4 programmable: {capabilities.get('supports_p4_programs', False)}")

        if 'supported_features' in capabilities:
            print("Features:")
            for feature in capabilities['supported_features']:
                print(f"  - {feature}")


def example_p4_program_templates():
    """Demonstrate P4 program template usage"""
    print("\n=== P4 Program Templates Example ===")

    mgr = MininetManager()

    # Create different types of P4 programs from templates
    templates = [
        ('l2_forwarding', 'Enhanced L2 forwarding with broadcast support'),
        ('l3_forwarding', 'IPv4 routing with TTL handling'),
        ('firewall', 'Packet filtering and access control'),
    ]

    for template_name, description in templates:
        print(f"\nCreating {template_name} program...")
        result = mgr.create_p4_program_template(f"example_{template_name}", template_name)

        if result:
            print(f"✓ Created {template_name} program: {result}")
            print(f"  Description: {description}")

            # Compile the program
            compile_success, compile_result = mgr.compile_p4_program(result)
            if compile_success:
                print(f"✓ Program compiled successfully: {compile_result}")
            else:
                print(f"✗ Compilation failed: {compile_result}")
        else:
            print(f"✗ Failed to create {template_name} program")


def main():
    """Run all examples"""
    print("Mininet Web Framework - Switch Usage Examples")
    print("=" * 50)

    # Check switch capabilities first
    example_switch_capabilities()

    # Run examples
    examples = [
        example_linux_bridge_topology,
        example_p4_switch_topology,
        example_mixed_switch_topology,
        example_p4_program_templates,
    ]

    results = []
    for example in examples:
        try:
            result = example()
            results.append(result)
        except Exception as e:
            print(f"✗ Example failed with error: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 50)
    print("EXAMPLES SUMMARY")
    print("=" * 50)

    successful = sum(results)
    total = len(results)

    print(f"Successful examples: {successful}/{total}")

    if successful == total:
        print("🎉 All examples completed successfully!")
    else:
        print("⚠️  Some examples failed. Check the output above for details.")

    print("\nNext steps:")
    print("1. Start the web server: python backend/app.py")
    print("2. Access the web interface at http://localhost:5000")
    print("3. Use the API endpoints documented in README_SWITCH_SUPPORT.md")


if __name__ == "__main__":
    main()
