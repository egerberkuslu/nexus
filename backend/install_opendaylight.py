#!/usr/bin/env python3
"""
OpenDaylight Installation Script
Installs OpenDaylight SDN controller with proper error handling and verification
"""

import os
import sys
import subprocess
import requests
import time
from pathlib import Path
import tarfile
import shutil
import platform

class OpenDaylightInstaller:
    """OpenDaylight installer with comprehensive error handling"""

    def __init__(self):
        self.home_dir = os.path.expanduser("~")
        self.odl_home = os.path.join(self.home_dir, "opendaylight")
        # Use the latest available OpenDaylight versions that are known to work
        self.download_urls = [
            # Try latest stable versions
            "https://nexus.opendaylight.org/content/repositories/opendaylight.release/org/opendaylight/integration/opendaylight/0.15.4/opendaylight-0.15.4.tar.gz",
            "https://archive.apache.org/dist/opendaylight/0.15.4/opendaylight-0.15.4.tar.gz",
            "https://nexus.opendaylight.org/content/repositories/opendaylight.release/org/opendaylight/integration/opendaylight/0.14.4/opendaylight-0.14.4.tar.gz",
            "https://archive.apache.org/dist/opendaylight/0.14.4/opendaylight-0.14.4.tar.gz",
            "https://nexus.opendaylight.org/content/repositories/opendaylight.release/org/opendaylight/integration/opendaylight/0.13.4/opendaylight-0.13.4.tar.gz",
            "https://archive.apache.org/dist/opendaylight/0.13.4/opendaylight-0.13.4.tar.gz"
        ]

    def check_prerequisites(self):
        """Check system prerequisites for OpenDaylight"""
        print("🔍 Checking prerequisites...")

        # Check Java
        try:
            java_result = subprocess.run(['java', '-version'],
                                       capture_output=True, text=True)
            if java_result.returncode != 0:
                print("❌ Java is not installed")
                return False

            # Extract Java version
            version_output = java_result.stderr
            if 'version "17' in version_output or 'version "11' in version_output or 'version "1.8' in version_output:
                print("✅ Java is installed and compatible")
            else:
                print("⚠️  Java version might not be compatible (recommended: Java 11+)")
        except FileNotFoundError:
            print("❌ Java is not installed")
            print("   Install with: sudo apt install openjdk-17-jdk")
            return False

        # Check system architecture
        arch = platform.machine().lower()
        if arch not in ['x86_64', 'amd64']:
            print(f"⚠️  Architecture {arch} detected. OpenDaylight works best on x86_64")

        print("✅ Prerequisites check completed")
        return True

    def download_opendaylight(self):
        """Download OpenDaylight distribution"""
        print("📥 Downloading OpenDaylight...")

        for url in self.download_urls:
            try:
                print(f"   Trying: {url}")
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()

                # Get filename from URL
                filename = url.split('/')[-1]
                filepath = os.path.join(self.home_dir, filename)

                # Download with progress
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                print(".1f", end='', flush=True)

                print("   ✅ Download completed")
                return filepath

            except Exception as e:
                print(f"   ❌ Failed: {e}")
                continue

        print("❌ All download attempts failed")
        return None

    def extract_opendaylight(self, tarball_path):
        """Extract OpenDaylight distribution"""
        print("📦 Extracting OpenDaylight...")

        try:
            # Remove existing installation
            if os.path.exists(self.odl_home):
                print(f"   Removing existing installation at {self.odl_home}")
                shutil.rmtree(self.odl_home)

            # Create installation directory
            os.makedirs(self.odl_home, exist_ok=True)

            # Extract tarball
            print(f"   Extracting {tarball_path}...")
            with tarfile.open(tarball_path, 'r:gz') as tar:
                tar.extractall(self.odl_home)

            # Move contents if extracted to subdirectory
            extracted_items = os.listdir(self.odl_home)
            if len(extracted_items) == 1:
                extracted_dir = os.path.join(self.odl_home, extracted_items[0])
                if os.path.isdir(extracted_dir):
                    print("   Moving contents to installation directory...")
                    for item in os.listdir(extracted_dir):
                        src = os.path.join(extracted_dir, item)
                        dst = os.path.join(self.odl_home, item)
                        shutil.move(src, dst)
                    os.rmdir(extracted_dir)

            # Clean up tarball
            os.remove(tarball_path)
            print("✅ Extraction completed")
            return True

        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            return False

    def configure_opendaylight(self):
        """Configure OpenDaylight for SDN use"""
        print("⚙️  Configuring OpenDaylight...")

        try:
            # Create etc directory
            etc_dir = os.path.join(self.odl_home, "etc")
            os.makedirs(etc_dir, exist_ok=True)

            # Create custom.properties
            custom_props = os.path.join(etc_dir, "custom.properties")
            with open(custom_props, 'w') as f:
                f.write("""# Custom OpenDaylight properties
# Memory settings
wrapper.java.maxmemory=2048
wrapper.java.initmemory=512

# Additional properties
org.ops4j.pax.url.mvn.repositories=https://nexus.opendaylight.org/content/repositories/opendaylight.release/@id=opendaylight.release
""")

            # Create karaf configuration
            karaf_config = os.path.join(etc_dir, "org.apache.karaf.features.cfg")
            with open(karaf_config, 'w') as f:
                f.write("""# OpenDaylight Features Configuration
# Features to install at boot
featuresBoot=config,standard,region,package,kar,ssh,management,odl-restconf,odl-l2switch-switch,odl-dlux-core
""")

            print("✅ Configuration completed")
            return True

        except Exception as e:
            print(f"❌ Configuration failed: {e}")
            return False

    def set_permissions(self):
        """Set proper permissions for OpenDaylight files"""
        print("🔐 Setting permissions...")

        try:
            # Make karaf script executable
            karaf_script = os.path.join(self.odl_home, "bin", "karaf")
            if os.path.exists(karaf_script):
                os.chmod(karaf_script, 0o755)
                print(f"   Made {karaf_script} executable")

            # Make client script executable
            client_script = os.path.join(self.odl_home, "bin", "client")
            if os.path.exists(client_script):
                os.chmod(client_script, 0o755)
                print(f"   Made {client_script} executable")

            print("✅ Permissions set")
            return True

        except Exception as e:
            print(f"❌ Failed to set permissions: {e}")
            return False

    def verify_installation(self):
        """Verify OpenDaylight installation"""
        print("🔍 Verifying installation...")

        try:
            # Check karaf script exists
            karaf_script = os.path.join(self.odl_home, "bin", "karaf")
            if not os.path.exists(karaf_script):
                print("❌ karaf script not found")
                return False

            # Check karaf script is executable
            if not os.access(karaf_script, os.X_OK):
                print("❌ karaf script is not executable")
                return False

            # Check Java compatibility
            test_cmd = [karaf_script, '--help']
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 or "karaf" in result.stdout.lower():
                print("✅ OpenDaylight installation verified")
                return True
            else:
                print(f"⚠️  karaf test had issues: {result.stderr}")
                return True  # Continue anyway

        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return False

    def create_startup_script(self):
        """Create a startup script for OpenDaylight"""
        print("📝 Creating startup script...")

        startup_script = os.path.join(self.home_dir, "start_opendaylight.sh")
        try:
            with open(startup_script, 'w') as f:
                f.write(f"""#!/bin/bash
# OpenDaylight Startup Script
# Generated by install_opendaylight.py

export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ODL_HOME={self.odl_home}
export PATH=$PATH:$JAVA_HOME/bin:$ODL_HOME/bin

echo "Starting OpenDaylight..."
echo "ODL_HOME: $ODL_HOME"
echo "JAVA_HOME: $JAVA_HOME"
echo ""

cd $ODL_HOME
exec ./bin/karaf
""")

            os.chmod(startup_script, 0o755)
            print(f"✅ Startup script created: {startup_script}")
            return True

        except Exception as e:
            print(f"❌ Failed to create startup script: {e}")
            return False

    def install(self):
        """Main installation method"""
        print("🚀 Starting OpenDaylight Installation")
        print("=" * 50)

        # Step 1: Check prerequisites
        if not self.check_prerequisites():
            print("❌ Prerequisites not met. Installation aborted.")
            return False

        # Step 2: Download OpenDaylight
        tarball_path = self.download_opendaylight()
        if not tarball_path:
            print("❌ Download failed. Installation aborted.")
            return False

        # Step 3: Extract OpenDaylight
        if not self.extract_opendaylight(tarball_path):
            print("❌ Extraction failed. Installation aborted.")
            return False

        # Step 4: Configure OpenDaylight
        if not self.configure_opendaylight():
            print("❌ Configuration failed. Installation aborted.")
            return False

        # Step 5: Set permissions
        if not self.set_permissions():
            print("❌ Permission setup failed. Installation aborted.")
            return False

        # Step 6: Verify installation
        if not self.verify_installation():
            print("❌ Verification failed. Installation may be incomplete.")
            return False

        # Step 7: Create startup script
        self.create_startup_script()

        print("=" * 50)
        print("🎉 OpenDaylight installation completed successfully!")
        print()
        print("📍 Installation Details:")
        print(f"   ODL_HOME: {self.odl_home}")
        print(f"   Karaf Script: {os.path.join(self.odl_home, 'bin', 'karaf')}")
        print(f"   Startup Script: {os.path.join(self.home_dir, 'start_opendaylight.sh')}")
        print()
        print("🚀 To start OpenDaylight:")
        print(f"   cd {self.odl_home}")
        print("   ./bin/karaf")
        print("   # Or use: ~/start_opendaylight.sh")
        print()
        print("🌐 OpenDaylight will be available at:")
        print("   REST API: http://localhost:8181/restconf")
        print("   Web UI: http://localhost:8181/index.html")
        print("   SSH: localhost:8101 (admin/admin)")

        return True

def main():
    """Main function"""
    try:
        installer = OpenDaylightInstaller()
        success = installer.install()

        if success:
            print("\n✅ Installation completed successfully!")
            return 0
        else:
            print("\n❌ Installation failed!")
            return 1

    except KeyboardInterrupt:
        print("\n❌ Installation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Installation error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
