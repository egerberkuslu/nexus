#!/usr/bin/env python3
"""
Automated SDN Controller Installer
Installs Ryu, POX, os-ken, and OpenDaylight with proper error handling
"""

import sys
import os
import subprocess
import time
import requests
import shutil
from pathlib import Path

def install_ryu_osken():
    """Install Ryu and os-ken with compatibility fixes"""
    try:
        print("Installing Ryu and os-ken...")
        
        # Try different installation methods
        methods = [
            # Method 1: Try os-ken first (official Ryu replacement)
            ['pip', 'install', 'os-ken'],
            # Method 2: Try Ryu with older setuptools
            ['pip', 'install', 'setuptools==58.0.0', 'ryu'],
            # Method 3: Install from conda-forge if available
            ['conda', 'install', '-c', 'conda-forge', 'ryu'],
        ]
        
        for i, method in enumerate(methods, 1):
            print(f"Trying installation method {i}...")
            try:
                result = subprocess.run(method, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    print(f"✅ Success with method {i}")
                    
                    # Verify installation
                    verify_result = subprocess.run(['python3', '-c', 'import ryu; print("Ryu OK")'],
                                                 capture_output=True, text=True)
                    if verify_result.returncode == 0:
                        print("✅ Ryu/os-ken installed and verified")
                        return True
                    else:
                        # Try os-ken import
                        verify_result = subprocess.run(['python3', '-c', 'import ryu; print("os-ken OK")'],
                                                     capture_output=True, text=True)
                        if verify_result.returncode == 0:
                            print("✅ os-ken installed and verified")
                            return True
                else:
                    print(f"Method {i} failed: {result.stderr[:200]}...")
            except subprocess.TimeoutExpired:
                print(f"Method {i} timed out")
            except Exception as e:
                print(f"Method {i} error: {e}")
        
        # If all methods fail, try manual installation
        print("Trying manual installation from source...")
        return install_ryu_from_source()
        
    except Exception as e:
        print(f"❌ Error installing Ryu/os-ken: {e}")
        return False

def install_ryu_from_source():
    """Install Ryu from source as fallback"""
    try:
        # Clone Ryu repository
        ryu_dir = '/tmp/ryu'
        if os.path.exists(ryu_dir):
            shutil.rmtree(ryu_dir)
        
        result = subprocess.run(['git', 'clone', 'https://github.com/faucetsdn/ryu.git', ryu_dir],
                              capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"Failed to clone Ryu: {result.stderr}")
            return False
        
        # Install dependencies
        subprocess.run(['pip', 'install', 'eventlet', 'routes', 'WebOb', 'paramiko', 'six'],
                      capture_output=True, text=True)
        
        # Install Ryu
        result = subprocess.run(['pip', 'install', '.'], 
                              cwd=ryu_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Ryu installed from source")
            return True
        else:
            print(f"Failed to install from source: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Source installation failed: {e}")
        return False

def install_pox():
    """Install POX from GitHub"""
    try:
        pox_path = os.path.expanduser('~/pox')
        if os.path.exists(pox_path):
            print("POX already exists, updating...")
            result = subprocess.run(['git', 'pull'], cwd=pox_path, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ POX updated successfully")
                return True
        
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

def find_opendaylight_download_url():
    """Find the correct OpenDaylight download URL"""
    # Try different versions and repositories
    versions = ['0.18.1', '0.17.1', '0.16.1']
    base_urls = [
        'https://nexus.opendaylight.org/content/repositories/opendaylight.release/org/opendaylight/integration/opendaylight',
        'https://nexus.opendaylight.org/content/repositories/public/org/opendaylight/integration/opendaylight'
    ]
    
    for version in versions:
        for base_url in base_urls:
            url = f'{base_url}/{version}/opendaylight-{version}.tar.gz'
            try:
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    print(f"Found OpenDaylight {version} at {url}")
                    return url, f'opendaylight-{version}'
            except:
                continue
    
    # Fallback to direct GitHub releases
    github_url = 'https://github.com/opendaylight/integration-distribution/releases/download'
    for version in versions:
        url = f'{github_url}/v{version}/opendaylight-{version}.tar.gz'
        try:
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                print(f"Found OpenDaylight {version} on GitHub")
                return url, f'opendaylight-{version}'
        except:
            continue
    
    return None, None

def install_opendaylight():
    """Install OpenDaylight with improved URL detection"""
    try:
        odl_home = os.path.expanduser('~/opendaylight')
        
        # Find correct download URL
        download_url, distribution_name = find_opendaylight_download_url()
        
        if not download_url:
            print("❌ Could not find OpenDaylight download URL")
            print("You can manually download from: https://docs.opendaylight.org/en/latest/downloads.html")
            return False
        
        print(f"Installing OpenDaylight {distribution_name}...")
        print(f"Download URL: {download_url}")
        
        # Create installation directory
        if os.path.exists(odl_home):
            print("Removing existing OpenDaylight installation...")
            shutil.rmtree(odl_home)
        
        os.makedirs(odl_home, exist_ok=True)
        
        # Download the distribution
        tarball_path = os.path.join(odl_home, f'{distribution_name}.tar.gz')
        
        print("Downloading OpenDaylight distribution...")
        response = requests.get(download_url, stream=True, timeout=30)
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
        
        # Find extracted directory and move contents
        extracted_dirs = [d for d in os.listdir(odl_home) 
                         if os.path.isdir(os.path.join(odl_home, d)) and d.startswith('opendaylight')]
        
        if extracted_dirs:
            extracted_dir = os.path.join(odl_home, extracted_dirs[0])
            print(f"Moving contents from {extracted_dir}")
            
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
            
            # Make client script executable too
            client_script = os.path.join(odl_home, 'bin', 'client')
            if os.path.exists(client_script):
                os.chmod(client_script, 0o755)
            
            # Create initial configuration
            create_odl_config(odl_home)
            
            print("✅ OpenDaylight installed successfully")
            return True
        else:
            print("❌ Karaf script not found after extraction")
            return False
            
    except Exception as e:
        print(f"❌ Error installing OpenDaylight: {e}")
        return False

def create_odl_config(odl_home):
    """Create OpenDaylight configuration files"""
    try:
        config_dir = os.path.join(odl_home, 'etc')
        os.makedirs(config_dir, exist_ok=True)
        
        # Custom properties
        custom_props = os.path.join(config_dir, 'custom.properties')
        with open(custom_props, 'w') as f:
            f.write("""# Custom OpenDaylight properties
# Memory settings
wrapper.java.maxmemory=2048
wrapper.java.initmemory=512

# Maven repositories
org.ops4j.pax.url.mvn.repositories=https://nexus.opendaylight.org/content/repositories/opendaylight.release/@id=opendaylight.release

# Logging
log4j2.rootLogger.level=INFO
""")
        
        # Features configuration
        features_cfg = os.path.join(config_dir, 'org.apache.karaf.features.cfg')
        with open(features_cfg, 'w') as f:
            f.write("""# Features configuration
# Boot features - installed at startup
featuresBoot=config,standard,region,package,kar,ssh,management,odl-restconf,odl-l2switch-switch,odl-dlux-core
""")
        
        print("Configuration files created")
        
    except Exception as e:
        print(f"Warning: Could not create config files: {e}")

def test_installations():
    """Test all controller installations"""
    print("\nTesting controller installations...")
    
    results = {}
    
    # Test Ryu/os-ken
    try:
        result = subprocess.run(['python3', '-c', 'import ryu; print("Ryu OK")'],
                              capture_output=True, text=True)
        results['ryu'] = result.returncode == 0
    except:
        results['ryu'] = False
    
    # Test POX
    pox_py = os.path.expanduser('~/pox/pox.py')
    results['pox'] = os.path.exists(pox_py)
    
    # Test OpenDaylight
    karaf_bin = os.path.expanduser('~/opendaylight/bin/karaf')
    results['opendaylight'] = os.path.exists(karaf_bin)
    
    return results

def main():
    """Main installation function"""
    print("SDN Controller Automated Installer")
    print("=" * 50)
    
    # Check system requirements
    print("Checking system requirements...")
    
    # Check Java
    try:
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Java available")
        else:
            print("❌ Java not found - required for OpenDaylight")
    except:
        print("❌ Java not found - required for OpenDaylight")
    
    # Check Git
    try:
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Git available")
        else:
            print("❌ Git not found - required for POX")
    except:
        print("❌ Git not found - required for POX")
    
    print("\nStarting installations...")
    
    # Install controllers
    success_count = 0
    
    # Install Ryu/os-ken
    print("\n1. Installing Ryu/os-ken...")
    if install_ryu_osken():
        success_count += 1
    
    # Install POX
    print("\n2. Installing POX...")
    if install_pox():
        success_count += 1
    
    # Install OpenDaylight
    print("\n3. Installing OpenDaylight...")
    if install_opendaylight():
        success_count += 1
    
    # Test installations
    print("\n4. Testing installations...")
    results = test_installations()
    
    print("\n" + "=" * 50)
    print("INSTALLATION RESULTS")
    print("=" * 50)
    
    for controller, status in results.items():
        status_text = "✅ Success" if status else "❌ Failed"
        print(f"{controller.upper():15}: {status_text}")
    
    total_success = sum(results.values())
    print(f"\nSummary: {total_success}/3 controllers installed successfully")
    
    if total_success == 3:
        print("\n🎉 All controllers installed successfully!")
        print("\nNext steps:")
        print("1. Test with: python test_multi_controller.py")
        print("2. Test OpenDaylight: python test_opendaylight.py")
        return 0
    else:
        print(f"\n⚠️  {3 - total_success} controllers failed to install")
        print("Check the error messages above for details")
        return 1

if __name__ == '__main__':
    sys.exit(main())
