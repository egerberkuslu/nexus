#!/usr/bin/env python3
"""
Switch Availability Diagnostic Script
Check which switch types are available and why others aren't
"""

import os
import subprocess
import sys

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

def check_command(cmd, description):
    """Check if a command is available"""
    try:
        result = subprocess.run(['which', cmd], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description}: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {description}: NOT FOUND")
            return False
    except Exception as e:
        print(f"❌ {description}: ERROR - {e}")
        return False

def check_linux_bridge():
    """Check Linux Bridge availability"""
    print_header("LINUX BRIDGE DIAGNOSTICS")
    
    # Check brctl
    brctl_available = check_command('brctl', 'Bridge Control (brctl)')
    
    # Check bridge module
    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        if 'bridge' in result.stdout:
            print("✅ Bridge kernel module: LOADED")
            bridge_module = True
        else:
            print("❌ Bridge kernel module: NOT LOADED")
            bridge_module = False
    except Exception as e:
        print(f"❌ Bridge kernel module check failed: {e}")
        bridge_module = False
    
    # Check if we can create a test bridge (requires sudo)
    print("\n📋 Linux Bridge Requirements:")
    print("   - brctl command (bridge-utils package)")
    print("   - bridge kernel module")
    print("   - sudo privileges")
    
    if not brctl_available:
        print("\n🔧 To install Linux Bridge support:")
        print("   sudo apt-get update")
        print("   sudo apt-get install bridge-utils")
    
    if not bridge_module:
        print("\n🔧 To load bridge module:")
        print("   sudo modprobe bridge")
    
    return brctl_available and bridge_module

def check_p4_switch():
    """Check P4 switch availability"""
    print_header("P4 SWITCH DIAGNOSTICS")
    
    # Check P4 compiler
    p4c_available = check_command('p4c', 'P4 Compiler (p4c)')
    if not p4c_available:
        p4c_available = check_command('p4c-bm2-ss', 'P4 Compiler (p4c-bm2-ss)')
    
    # Check simple_switch
    simple_switch = check_command('simple_switch', 'P4 Simple Switch')
    if not simple_switch:
        simple_switch = check_command('simple_switch_grpc', 'P4 Simple Switch gRPC')
    
    # Check BMv2
    bmv2_available = check_command('simple_switch_CLI', 'BMv2 CLI')
    
    print("\n📋 P4 Switch Requirements:")
    print("   - P4 compiler (p4c or p4c-bm2-ss)")
    print("   - Behavioral Model v2 (BMv2)")
    print("   - simple_switch executable")
    print("   - P4Runtime libraries (optional)")
    
    if not any([p4c_available, simple_switch, bmv2_available]):
        print("\n🔧 To install P4 support:")
        print("   # Install dependencies")
        print("   sudo apt-get install -y python3-pip cmake g++")
        print("   # Install P4 tools (complex installation)")
        print("   # See: https://github.com/p4lang/tutorials")
    
    return p4c_available or simple_switch

def check_ovs():
    """Check OVS availability"""
    print_header("OPENVSWITCH (OVS) DIAGNOSTICS")
    
    ovs_vsctl = check_command('ovs-vsctl', 'OVS Control (ovs-vsctl)')
    ovs_ofctl = check_command('ovs-ofctl', 'OVS OpenFlow Control (ovs-ofctl)')
    
    # Check OVS daemon
    try:
        result = subprocess.run(['sudo', 'ovs-vsctl', 'show'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ OVS Daemon: RUNNING")
            ovs_daemon = True
        else:
            print("❌ OVS Daemon: NOT RUNNING")
            ovs_daemon = False
    except Exception as e:
        print(f"❌ OVS Daemon check failed: {e}")
        ovs_daemon = False
    
    print("\n📋 OVS Requirements:")
    print("   - openvswitch-switch package")
    print("   - ovs-vsctl and ovs-ofctl commands")
    print("   - OVS daemon running")
    
    if not ovs_vsctl:
        print("\n🔧 To install OVS support:")
        print("   sudo apt-get install openvswitch-switch")
        print("   sudo systemctl start openvswitch-switch")
        print("   sudo systemctl enable openvswitch-switch")
    
    return ovs_vsctl and ovs_daemon

def check_mininet():
    """Check Mininet switch support"""
    print_header("MININET SWITCH SUPPORT")
    
    # Check mn command
    mn_available = check_command('mn', 'Mininet Command (mn)')
    
    # Try to import mininet
    try:
        import mininet.node
        print("✅ Mininet Python module: AVAILABLE")
        mininet_python = True
    except ImportError:
        print("❌ Mininet Python module: NOT AVAILABLE")
        mininet_python = False
    
    return mn_available and mininet_python

def main():
    print_header("SWITCH AVAILABILITY DIAGNOSTIC")
    print("Checking which switch types are available...")
    
    results = {}
    
    # Check each switch type
    results['ovs'] = check_ovs()
    results['linux_bridge'] = check_linux_bridge()
    results['p4'] = check_p4_switch()
    results['mininet'] = check_mininet()
    
    # Summary
    print_header("SUMMARY")
    
    available_switches = []
    unavailable_switches = []
    
    for switch_type, available in results.items():
        if available:
            available_switches.append(switch_type)
            print(f"✅ {switch_type.upper()}: AVAILABLE")
        else:
            unavailable_switches.append(switch_type)
            print(f"❌ {switch_type.upper()}: NOT AVAILABLE")
    
    print(f"\n📊 Available: {len(available_switches)} switch types")
    print(f"📊 Unavailable: {len(unavailable_switches)} switch types")
    
    if available_switches:
        print(f"\n✅ You can use: {', '.join(available_switches)}")
    
    if unavailable_switches:
        print(f"\n❌ Need to install: {', '.join(unavailable_switches)}")
        print("\n💡 Recommendation: Start with OVS switches - they're the most commonly used")
        print("   OVS provides OpenFlow support and works well with SDN controllers")
    
    return len(available_switches) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
