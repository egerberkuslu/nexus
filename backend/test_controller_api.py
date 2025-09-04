#!/usr/bin/env python3
"""
Test script for the controller installation API
"""

import sys
import os
import subprocess
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

def test_controller_installations():
    """Test the controller installations API endpoint"""
    try:
        print("Testing Controller Installation API")
        print("=" * 50)

        # Import the functions directly
        from api.controller_routes import (
            check_ryu_installation,
            check_pox_installation,
            check_opendaylight_installation,
            check_osken_installation
        )

        print("1. Testing Ryu installation...")
        ryu_status = check_ryu_installation()
        print(f"   Ryu: {'✓' if ryu_status['installed'] else '✗'} {ryu_status}")

        print("\n2. Testing POX installation...")
        pox_status = check_pox_installation()
        print(f"   POX: {'✓' if pox_status['installed'] else '✗'} {pox_status}")

        print("\n3. Testing OpenDaylight installation...")
        odl_status = check_opendaylight_installation()
        print(f"   OpenDaylight: {'✓' if odl_status['installed'] else '✗'} {odl_status}")

        print("\n4. Testing os-ken installation...")
        osken_status = check_osken_installation()
        print(f"   os-ken: {'✓' if osken_status['installed'] else '✗'} {osken_status}")

        # Summary
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)

        controllers = {
            'ryu': ryu_status,
            'pox': pox_status,
            'opendaylight': odl_status,
            'osken': osken_status
        }

        installed_count = sum(1 for status in controllers.values() if status['installed'])

        print(f"Total controllers: {len(controllers)}")
        print(f"Installed: {installed_count}")
        print(f"Missing: {len(controllers) - installed_count}")

        if installed_count == len(controllers):
            print("🎉 All controllers are properly installed!")
        else:
            print("⚠️  Some controllers are missing or have issues")

        # Show detailed results
        print("\nDetailed Status:")
        for name, status in controllers.items():
            status_icon = "✅" if status['installed'] else "❌"
            status_text = status.get('status', 'unknown')
            print(f"  {status_icon} {name.upper()}: {status_text}")

        return True

    except Exception as e:
        print(f"Error testing controller installations: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_controller_installations()
    sys.exit(0 if success else 1)
