#!/usr/bin/env python3
"""
Fix Mininet Import Issues
Resolve distutils and other import problems for Mininet
"""

import os
import sys
import subprocess

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

def run_command(cmd, description):
    """Run a command with error handling"""
    print(f"🔄 {description}...")
    try:
        if isinstance(cmd, str):
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        print(f"✅ {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        if e.stderr:
            print(f"   Error: {e.stderr.strip()}")
        return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def fix_distutils_issue():
    """Fix distutils import issue for Python 3.12+"""
    print_header("FIXING DISTUTILS ISSUE")
    
    # Install setuptools which provides distutils
    success = run_command('pip3 install setuptools', "Installing setuptools")
    
    # Also try installing distutils directly
    if not success:
        run_command('pip3 install distutils-extra', "Installing distutils-extra")
    
    # For conda environments, ensure setuptools is available
    conda_prefix = os.environ.get('CONDA_PREFIX')
    if conda_prefix:
        run_command('conda install setuptools -y', "Installing setuptools via conda")
    
    return success

def create_distutils_shim():
    """Create a distutils compatibility shim for Python 3.12+"""
    print_header("CREATING DISTUTILS COMPATIBILITY SHIM")
    
    try:
        # Create a simple distutils shim
        shim_content = '''
"""
Distutils compatibility shim for Python 3.12+
"""

try:
    # Try the original distutils
    from distutils.version import StrictVersion
    from distutils.version import LooseVersion
except ImportError:
    # Fallback to setuptools implementation
    try:
        from setuptools._distutils.version import StrictVersion
        from setuptools._distutils.version import LooseVersion
    except ImportError:
        # Last resort: create minimal implementation
        class StrictVersion:
            def __init__(self, vstring):
                self.version = vstring
            
            def __str__(self):
                return self.version
            
            def __eq__(self, other):
                return str(self) == str(other)
            
            def __lt__(self, other):
                return str(self) < str(other)
        
        class LooseVersion(StrictVersion):
            pass

# Make available for import
__all__ = ['StrictVersion', 'LooseVersion']
'''
        
        # Find Python site-packages directory
        import site
        site_packages = site.getsitepackages()
        
        for site_pkg in site_packages:
            if os.access(site_pkg, os.W_OK):
                distutils_dir = os.path.join(site_pkg, 'distutils')
                os.makedirs(distutils_dir, exist_ok=True)
                
                shim_file = os.path.join(distutils_dir, '__init__.py')
                version_file = os.path.join(distutils_dir, 'version.py')
                
                with open(shim_file, 'w') as f:
                    f.write('# Distutils compatibility shim\n')
                
                with open(version_file, 'w') as f:
                    f.write(shim_content)
                
                print(f"✅ Created distutils shim at {distutils_dir}")
                return True
        
        print("⚠️  Could not find writable site-packages directory")
        return False
        
    except Exception as e:
        print(f"❌ Error creating distutils shim: {e}")
        return False

def test_mininet_import():
    """Test if Mininet can be imported now"""
    print_header("TESTING MININET IMPORT")
    
    try:
        # Test basic imports
        import mininet
        print("✅ Basic mininet import: SUCCESS")
        
        import mininet.node
        print("✅ mininet.node import: SUCCESS")
        
        import mininet.net
        print("✅ mininet.net import: SUCCESS")
        
        import mininet.cli
        print("✅ mininet.cli import: SUCCESS")
        
        print("\n🎉 All Mininet imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Mininet import failed: {e}")
        
        # Try to identify the specific issue
        if 'distutils' in str(e):
            print("   Issue: distutils not available")
            print("   Solution: Install setuptools or create compatibility shim")
        elif 'No module named' in str(e):
            print("   Issue: Mininet not installed or not in Python path")
            print("   Solution: Install mininet package or check PYTHONPATH")
        
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def fix_python_path():
    """Fix Python path issues for Mininet"""
    print_header("FIXING PYTHON PATH")
    
    # Common Mininet installation paths
    mininet_paths = [
        '/usr/lib/python3/dist-packages',
        '/usr/local/lib/python3.*/dist-packages',
        '/home/ege/anaconda3/lib/python3.12/site-packages'
    ]
    
    for path in mininet_paths:
        if os.path.exists(path):
            mininet_dir = os.path.join(path, 'mininet')
            if os.path.exists(mininet_dir):
                print(f"✅ Found Mininet at: {path}")
                
                # Add to Python path if not already there
                if path not in sys.path:
                    sys.path.insert(0, path)
                    print(f"✅ Added {path} to Python path")
                
                return True
    
    print("⚠️  Mininet installation not found in common paths")
    return False

def main():
    print_header("MININET IMPORT FIX")
    print("Attempting to fix Mininet import issues...")
    
    # Step 1: Fix distutils issue
    fix_distutils_issue()
    
    # Step 2: Test import
    if test_mininet_import():
        print("\n🎉 Mininet imports are working!")
        return True
    
    # Step 3: Create distutils shim if needed
    print("\n🔧 Creating distutils compatibility shim...")
    create_distutils_shim()
    
    # Step 4: Fix Python path
    fix_python_path()
    
    # Step 5: Final test
    if test_mininet_import():
        print("\n🎉 Mininet imports fixed successfully!")
        return True
    else:
        print("\n❌ Could not fix Mininet imports")
        print("   Manual steps needed:")
        print("   1. Ensure Mininet is installed: sudo apt-get install mininet")
        print("   2. Check Python version compatibility")
        print("   3. Verify PYTHONPATH includes Mininet")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
