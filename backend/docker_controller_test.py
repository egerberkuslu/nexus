#!/usr/bin/env python3
"""
Docker Controller Test Script
Tests all SDN controllers in the Docker environment
"""

import sys
import os
import time
import json
import subprocess

# Add the current directory to Python path
sys.path.insert(0, '/app')

def test_controller_imports():
    """Test if all controller managers can be imported"""
    print("=== Testing Controller Imports ===")
    
    try:
        from core.mininet_manager import MininetManager
        print("✓ MininetManager imported successfully")
        
        manager = MininetManager()
        print("✓ MininetManager instantiated successfully")
        
        # Test controller factory
        controllers = manager.get_available_controllers()
        print(f"✓ Available controllers: {controllers}")
        
        # Test controller info
        info = manager.get_all_controller_info()
        for controller_type, controller_info in info.items():
            status = controller_info.get('status', {})
            print(f"  {controller_type}: {status.get('name', 'Unknown')} - Ready")
        
        return True, manager
    except Exception as e:
        print(f"✗ Error importing controllers: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_individual_controllers(manager):
    """Test each controller individually"""
    print("\n=== Testing Individual Controllers ===")
    
    results = {}
    
    # Test POX
    print("\n--- Testing POX ---")
    try:
        pox_status = manager.get_pox_status()
        print(f"POX Status: {json.dumps(pox_status, indent=2)}")
        
        # Check POX installation
        pox_path = '/opt/pox/pox.py'
        if os.path.exists(pox_path):
            print("✓ POX binary found")
            results['pox'] = True
        else:
            print("✗ POX binary not found")
            results['pox'] = False
            
    except Exception as e:
        print(f"✗ POX test error: {e}")
        results['pox'] = False
    
    # Test Ryu/os-ken
    print("\n--- Testing Ryu/os-ken ---")
    try:
        ryu_status = manager.get_controller_status()
        print(f"Ryu Status: {json.dumps(ryu_status, indent=2)}")
        
        # Test Ryu import
        import ryu
        print("✓ Ryu/os-ken import successful")
        results['ryu'] = True
        results['osken'] = True
        
    except Exception as e:
        print(f"✗ Ryu/os-ken test error: {e}")
        results['ryu'] = False
        results['osken'] = False
    
    # Test OpenDaylight
    print("\n--- Testing OpenDaylight ---")
    try:
        odl_status = manager.get_opendaylight_status()
        print(f"OpenDaylight Status: {json.dumps(odl_status, indent=2)}")
        
        # Check OpenDaylight installation
        karaf_path = '/opt/opendaylight/bin/karaf'
        if os.path.exists(karaf_path):
            print("✓ OpenDaylight binary found")
            
            # Test Java
            java_result = subprocess.run(['java', '-version'], 
                                       capture_output=True, text=True)
            if java_result.returncode == 0:
                print("✓ Java available for OpenDaylight")
                results['opendaylight'] = True
            else:
                print("✗ Java not available")
                results['opendaylight'] = False
        else:
            print("✗ OpenDaylight binary not found")
            results['opendaylight'] = False
            
    except Exception as e:
        print(f"✗ OpenDaylight test error: {e}")
        results['opendaylight'] = False
    
    return results

def test_controller_startup():
    """Test starting controllers"""
    print("\n=== Testing Controller Startup ===")
    
    try:
        from core.mininet_manager import MininetManager
        manager = MininetManager()
        
        # Test POX startup (quick test)
        print("\n--- Testing POX Startup ---")
        try:
            success = manager.start_pox_controller('l2_learning', port=6634)  # Use different port
            if success:
                print("✓ POX started successfully")
                time.sleep(2)
                manager.stop_pox_controller()
                print("✓ POX stopped successfully")
            else:
                print("✗ POX startup failed")
        except Exception as e:
            print(f"✗ POX startup error: {e}")
        
        return True
    except Exception as e:
        print(f"✗ Controller startup test error: {e}")
        return False

def test_system_requirements():
    """Test system requirements"""
    print("\n=== Testing System Requirements ===")
    
    # Test Java
    try:
        result = subprocess.run(['java', '-version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Java available")
            print(f"  Version: {result.stderr.split()[2].strip('\"')}")
        else:
            print("✗ Java not available")
    except:
        print("✗ Java not found")
    
    # Test Python
    try:
        print(f"✓ Python version: {sys.version}")
    except:
        print("✗ Python version check failed")
    
    # Test Git
    try:
        result = subprocess.run(['git', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Git available: {result.stdout.strip()}")
        else:
            print("✗ Git not available")
    except:
        print("✗ Git not found")
    
    # Test OVS
    try:
        result = subprocess.run(['ovs-vsctl', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Open vSwitch available")
        else:
            print("✗ Open vSwitch not available")
    except:
        print("✗ Open vSwitch not found")

def main():
    """Main test function"""
    print("Docker SDN Controller Test Suite")
    print("=" * 50)
    
    # Test system requirements
    test_system_requirements()
    
    # Test controller imports
    import_success, manager = test_controller_imports()
    
    if not import_success:
        print("\n❌ Controller import test failed")
        return 1
    
    # Test individual controllers
    controller_results = test_individual_controllers(manager)
    
    # Test controller startup
    startup_success = test_controller_startup()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST RESULTS SUMMARY")
    print("=" * 50)
    
    print("\nController Availability:")
    for controller, status in controller_results.items():
        status_text = "✓ Available" if status else "✗ Not Available"
        print(f"  {controller.upper():15}: {status_text}")
    
    import_text = "✓ Success" if import_success else "✗ Failed"
    print(f"  {'IMPORTS':15}: {import_text}")
    
    startup_text = "✓ Success" if startup_success else "✗ Failed"
    print(f"  {'STARTUP':15}: {startup_text}")
    
    # Overall result
    total_available = sum(controller_results.values())
    total_controllers = len(controller_results)
    
    print(f"\nOverall: {total_available}/{total_controllers} controllers available")
    
    if total_available >= 2 and import_success:  # At least 2 controllers working
        print("\n🎉 Docker controller setup is working!")
        print("\nYou can now:")
        print("  1. Use the web interface at http://localhost:3000")
        print("  2. Access the API at http://localhost:5000")
        print("  3. Switch between controllers in the web UI")
        return 0
    else:
        print("\n⚠️  Some controllers are not working properly")
        print("Check the Docker logs for more details:")
        print("  docker-compose logs backend")
        return 1

if __name__ == '__main__':
    sys.exit(main())
