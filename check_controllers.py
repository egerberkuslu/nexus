#!/usr/bin/env python3
"""
Comprehensive controller installation checker and installer
Checks and installs Ryu, POX, os-ken, and OpenDaylight controllers
"""

import sys
import os
import subprocess
import time
import requests
import shutil
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def check_java():
    """Check Java installation for OpenDaylight"""
    try:
        result = subprocess.run(['java', '-version'],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode == 0:
            import re
            version_match = re.search(r'version "(\d+)', result.stdout)
            if version_match:
                version = int(version_match.group(1))
                return version >= 11, version
        return False, None
    except:
        return False, None

def check_ryu():
    """Check if Ryu/os-ken is installed"""
    try:
        result = subprocess.run(['python3', '-c', 'import ryu; print("OK")'],
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def install_ryu():
    """Install Ryu/os-ken"""
    try:
        print("Installing Ryu (includes os-ken)...")
        result = subprocess.run(['pip', 'install', 'ryu'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ryu/os-ken installed successfully")
            return True
        else:
            print(f"❌ Failed to install Ryu: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error installing Ryu: {e}")
        return False

def check_pox():
    """Check if POX is installed"""
    pox_path = os.path.expanduser('~/pox')
    pox_py = os.path.join(pox_path, 'pox.py')
    return os.path.exists(pox_py)

def install_pox():
    """Install POX from GitHub"""
    try:
        pox_path = os.path.expanduser('~/pox')
        if os.path.exists(pox_path):
            shutil.rmtree(pox_path)
        
        print("Installing POX from GitHub...")
        result = subprocess.run(['git', 'clone', 'https://github.com/noxrepo/pox.git', pox_path],
                              capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            # Make pox.py executable
            pox_py = os.path.join(pox_path, 'pox.py')
            if os.path.exists(pox_py):
                os.chmod(pox_py, 0o755)
                print("✅ POX installed successfully")
                return True
        
        print(f"❌ Failed to install POX: {result.stderr}")
        return False
    except Exception as e:
        print(f"❌ Error installing POX: {e}")
        return False

def check_opendaylight():
    """Check if OpenDaylight is installed"""
    odl_home = os.path.expanduser('~/opendaylight')
    karaf_bin = os.path.join(odl_home, 'bin', 'karaf')
    return os.path.exists(karaf_bin)

def install_opendaylight():
    """Install OpenDaylight"""
    try:
        odl_home = os.path.expanduser('~/opendaylight')
        distribution_name = 'opendaylight-0.18.1'
        download_url = f'https://nexus.opendaylight.org/content/repositories/opendaylight.release/org/opendaylight/integration/opendaylight/0.18.1/{distribution_name}.tar.gz'
        
        print("Installing OpenDaylight...")
        print(f"Download URL: {download_url}")
        
        # Create installation directory
        os.makedirs(odl_home, exist_ok=True)
        
        # Download the distribution
        tarball_path = os.path.join(odl_home, f'{distribution_name}.tar.gz')
        
        print("Downloading OpenDaylight distribution (this may take a while)...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(tarball_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rProgress: {progress:.1f}%", end='', flush=True)
        
        print("\nDownload completed, extracting...")
        
        # Extract the tarball
        import tarfile
        with tarfile.open(tarball_path, 'r:gz') as tar:
            tar.extractall(odl_home)
        
        # Move contents to odl_home if extracted to subdirectory
        extracted_dir = os.path.join(odl_home, distribution_name)
        if os.path.exists(extracted_dir):
            for item in os.listdir(extracted_dir):
                src = os.path.join(extracted_dir, item)
                dst = os.path.join(odl_home, item)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(src, dst)
            os.rmdir(extracted_dir)
        
        # Clean up tarball
        os.remove(tarball_path)
        
        # Make karaf script executable
        karaf_script = os.path.join(odl_home, 'bin', 'karaf')
        if os.path.exists(karaf_script):
            os.chmod(karaf_script, 0o755)
            
            # Create initial configuration
            config_dir = os.path.join(odl_home, 'etc')
            os.makedirs(config_dir, exist_ok=True)
            
            custom_props = os.path.join(config_dir, 'custom.properties')
            with open(custom_props, 'w') as f:
                f.write("""# Custom OpenDaylight properties
# Memory settings
wrapper.java.maxmemory=2048
wrapper.java.initmemory=512

# Additional properties
org.ops4j.pax.url.mvn.repositories=https://nexus.opendaylight.org/content/repositories/opendaylight.release/@id=opendaylight.release
""")
            
            print("✅ OpenDaylight installed successfully")
            return True
        else:
            print("❌ Karaf script not found after extraction")
            return False
            
    except Exception as e:
        print(f"❌ Error installing OpenDaylight: {e}")
        return False

def test_controller_imports():
    """Test if controller managers can be imported"""
    try:
        from core.mininet_manager import MininetManager
        manager = MininetManager()
        
        # Test controller factory
        controllers = manager.get_available_controllers()
        print(f"Available controllers: {controllers}")
        
        # Test controller info
        info = manager.get_all_controller_info()
        for controller_type, controller_info in info.items():
            status = "✅ Ready" if controller_info.get('status', {}).get('running') is not None else "❓ Unknown"
            print(f"  {controller_type}: {status}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing controller imports: {e}")
        return False

def main():
    """Main function to check and install all controllers"""
    print("SDN Controller Installation Checker")
    print("=" * 50)
    
    # Check system requirements
    print("\n1. Checking System Requirements...")
    
    # Check Java for OpenDaylight
    java_ok, java_version = check_java()
    if java_ok:
        print(f"✅ Java {java_version} - suitable for OpenDaylight")
    else:
        print("❌ Java 11+ required for OpenDaylight")
        print("  Install with: sudo apt install openjdk-11-jdk")
    
    # Check Git for POX
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
        print("✅ Git available for POX installation")
    except:
        print("❌ Git required for POX installation")
        print("  Install with: sudo apt install git")
    
    # Check pip for Ryu
    try:
        subprocess.run(['pip', '--version'], capture_output=True, check=True)
        print("✅ pip available for Ryu installation")
    except:
        print("❌ pip required for Ryu installation")
        print("  Install with: sudo apt install python3-pip")
    
    print("\n2. Checking Controller Installations...")
    
    # Check and install controllers
    controllers_status = {}
    
    # Ryu/os-ken
    if check_ryu():
        print("✅ Ryu/os-ken already installed")
        controllers_status['ryu'] = True
        controllers_status['osken'] = True
    else:
        print("❌ Ryu/os-ken not installed")
        if input("Install Ryu/os-ken? (y/n): ").lower() == 'y':
            controllers_status['ryu'] = install_ryu()
            controllers_status['osken'] = controllers_status['ryu']
        else:
            controllers_status['ryu'] = False
            controllers_status['osken'] = False
    
    # POX
    if check_pox():
        print("✅ POX already installed")
        controllers_status['pox'] = True
    else:
        print("❌ POX not installed")
        if input("Install POX? (y/n): ").lower() == 'y':
            controllers_status['pox'] = install_pox()
        else:
            controllers_status['pox'] = False
    
    # OpenDaylight
    if check_opendaylight():
        print("✅ OpenDaylight already installed")
        controllers_status['opendaylight'] = True
    else:
        print("❌ OpenDaylight not installed")
        if java_ok and input("Install OpenDaylight? (y/n): ").lower() == 'y':
            controllers_status['opendaylight'] = install_opendaylight()
        else:
            controllers_status['opendaylight'] = False
    
    print("\n3. Testing Controller Framework...")
    framework_ok = test_controller_imports()
    
    print("\n" + "=" * 50)
    print("INSTALLATION SUMMARY")
    print("=" * 50)
    
    for controller, status in controllers_status.items():
        status_text = "✅ Installed" if status else "❌ Not installed"
        print(f"{controller.upper():15}: {status_text}")
    
    framework_text = "✅ Working" if framework_ok else "❌ Issues"
    print(f"{'FRAMEWORK':15}: {framework_text}")
    
    if all(controllers_status.values()) and framework_ok:
        print("\n🎉 All controllers are ready!")
        print("\nYou can now run:")
        print("  python test_multi_controller.py")
        print("  python test_opendaylight.py")
        return 0
    else:
        print("\n❌ Some controllers are missing or have issues")
        return 1

if __name__ == '__main__':
    sys.exit(main())
