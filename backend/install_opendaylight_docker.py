#!/usr/bin/env python3
"""
OpenDaylight Installation Script using Docker
Installs OpenDaylight SDN controller using Docker for easier deployment
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path

class OpenDaylightDockerInstaller:
    """OpenDaylight installer using Docker"""

    def __init__(self):
        self.home_dir = os.path.expanduser("~")
        self.docker_image = "glefevre/opendaylight"
        self.container_name = "mininet-opendaylight"
        self.odl_home = os.path.join(self.home_dir, "opendaylight-docker")

    def check_docker(self):
        """Check if Docker is installed and running"""
        print("🔍 Checking Docker installation...")

        try:
            # Check if docker command exists
            result = subprocess.run(['docker', '--version'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print("❌ Docker is not installed")
                print("   Install Docker with: sudo apt install docker.io")
                return False

            print(f"✅ Docker is installed: {result.stdout.strip()}")

            # Check if docker daemon is running
            result = subprocess.run(['docker', 'info'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print("❌ Docker daemon is not running")
                print("   Start Docker with: sudo systemctl start docker")
                return False

            print("✅ Docker daemon is running")
            return True

        except FileNotFoundError:
            print("❌ Docker is not installed")
            return False
        except Exception as e:
            print(f"❌ Docker check failed: {e}")
            return False

    def check_image_availability(self):
        """Check if OpenDaylight Docker image is available"""
        print("🔍 Checking OpenDaylight Docker image...")

        try:
            # Check if image exists locally
            result = subprocess.run(['docker', 'images', self.docker_image, '--format', 'json'],
                                  capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                print(f"✅ OpenDaylight image found locally: {self.docker_image}")
                return True

            # Try to pull the image
            print(f"📥 Pulling OpenDaylight image: {self.docker_image}")
            result = subprocess.run(['docker', 'pull', self.docker_image],
                                  capture_output=True, text=True, timeout=300)  # 5 minute timeout

            if result.returncode == 0:
                print("✅ OpenDaylight image pulled successfully")
                return True
            else:
                print(f"❌ Failed to pull image: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Image check failed: {e}")
            return False

    def create_directories(self):
        """Create necessary directories for OpenDaylight data persistence"""
        print("📁 Creating directories...")

        try:
            # Create main directory
            os.makedirs(self.odl_home, exist_ok=True)

            # Create subdirectories for data persistence
            data_dir = os.path.join(self.odl_home, "data")
            logs_dir = os.path.join(self.odl_home, "logs")
            cache_dir = os.path.join(self.odl_home, "cache")

            os.makedirs(data_dir, exist_ok=True)
            os.makedirs(logs_dir, exist_ok=True)
            os.makedirs(cache_dir, exist_ok=True)

            print(f"✅ Directories created in: {self.odl_home}")
            return True

        except Exception as e:
            print(f"❌ Failed to create directories: {e}")
            return False

    def start_container(self):
        """Start OpenDaylight container"""
        print("🚀 Starting OpenDaylight container...")

        try:
            # Stop existing container if running
            subprocess.run(['docker', 'stop', self.container_name],
                         capture_output=True, timeout=30)
            subprocess.run(['docker', 'rm', self.container_name],
                         capture_output=True, timeout=30)

            # Create docker run command
            cmd = [
                'docker', 'run', '-d',
                '--name', self.container_name,
                '-p', '8181:8181',    # REST API
                '-p', '8101:8101',    # SSH
                '-p', '6633:6633',    # OpenFlow
                '-p', '6640:6640',    # OVSDB
                '-e', 'JAVA_MAX_MEM=2048m',
                '-e', 'JAVA_MIN_MEM=512m',
                '-v', f'{self.odl_home}/data:/opt/opendaylight/data',
                '-v', f'{self.odl_home}/logs:/opt/opendaylight/data/log',
                '-v', f'{self.odl_home}/cache:/opt/opendaylight/cache',
                '--restart', 'unless-stopped',
                self.docker_image
            ]

            print(f"   Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                container_id = result.stdout.strip()
                print(f"✅ Container started successfully: {container_id[:12]}")
                return True
            else:
                print(f"❌ Failed to start container: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Container start failed: {e}")
            return False

    def wait_for_startup(self):
        """Wait for OpenDaylight to fully start up"""
        print("⏳ Waiting for OpenDaylight to start up...")

        max_attempts = 60  # 5 minutes
        attempt = 0

        while attempt < max_attempts:
            try:
                # Check if container is still running
                result = subprocess.run(['docker', 'ps', '--filter', f'name={self.container_name}', '--format', 'json'],
                                      capture_output=True, text=True, timeout=10)

                if result.returncode != 0 or not result.stdout.strip():
                    print("❌ Container is not running")
                    return False

                # Try to connect to REST API
                import requests
                response = requests.get('http://localhost:8181/restconf/operational/system',
                                      timeout=5, auth=('admin', 'admin'))

                if response.status_code == 200:
                    print("✅ OpenDaylight is ready!")
                    return True
                else:
                    print(f"   REST API returned status: {response.status_code}")

            except requests.exceptions.RequestException:
                print(f"   Attempt {attempt + 1}/{max_attempts}: Waiting for REST API...")
            except Exception as e:
                print(f"   Attempt {attempt + 1}/{max_attempts}: {e}")

            attempt += 1
            time.sleep(5)

        print("❌ OpenDaylight startup timeout")
        return False

    def create_management_scripts(self):
        """Create management scripts for OpenDaylight"""
        print("📝 Creating management scripts...")

        try:
            # Start script
            start_script = os.path.join(self.home_dir, "start_opendaylight.sh")
            with open(start_script, 'w') as f:
                f.write(f"""#!/bin/bash
# Start OpenDaylight Docker Container
echo "Starting OpenDaylight..."
docker start {self.container_name}
echo "OpenDaylight started. Waiting for REST API..."
sleep 30
echo "REST API: http://localhost:8181/restconf"
echo "Web UI: http://localhost:8181/index.html"
echo "SSH: localhost:8101 (admin/admin)"
""")

            # Stop script
            stop_script = os.path.join(self.home_dir, "stop_opendaylight.sh")
            with open(stop_script, 'w') as f:
                f.write(f"""#!/bin/bash
# Stop OpenDaylight Docker Container
echo "Stopping OpenDaylight..."
docker stop {self.container_name}
echo "OpenDaylight stopped."
""")

            # Status script
            status_script = os.path.join(self.home_dir, "status_opendaylight.sh")
            with open(status_script, 'w') as f:
                f.write(f"""#!/bin/bash
# Check OpenDaylight Status
echo "OpenDaylight Container Status:"
docker ps --filter name={self.container_name} --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"

echo ""
echo "OpenDaylight REST API Status:"
curl -s -o /dev/null -w "%{{http_code}}" http://localhost:8181/restconf/operational/system || echo "Not responding"
""")

            # Make scripts executable
            os.chmod(start_script, 0o755)
            os.chmod(stop_script, 0o755)
            os.chmod(status_script, 0o755)

            print("✅ Management scripts created:")
            print(f"   Start: {start_script}")
            print(f"   Stop: {stop_script}")
            print(f"   Status: {status_script}")

            return True

        except Exception as e:
            print(f"❌ Failed to create management scripts: {e}")
            return False

    def create_symlink(self):
        """Create symlink for compatibility with existing code"""
        print("🔗 Creating compatibility symlink...")

        try:
            odl_link = os.path.join(self.home_dir, "opendaylight")
            if os.path.exists(odl_link):
                os.remove(odl_link)
            os.symlink(self.odl_home, odl_link)
            print(f"✅ Symlink created: {odl_link} -> {self.odl_home}")
            return True

        except Exception as e:
            print(f"❌ Failed to create symlink: {e}")
            return False

    def install(self):
        """Main installation method"""
        print("🚀 Starting OpenDaylight Docker Installation")
        print("=" * 60)

        # Step 1: Check Docker
        if not self.check_docker():
            print("❌ Docker prerequisites not met. Installation aborted.")
            return False

        # Step 2: Check/create directories
        if not self.create_directories():
            print("❌ Directory creation failed. Installation aborted.")
            return False

        # Step 3: Check image availability
        if not self.check_image_availability():
            print("❌ OpenDaylight image not available. Installation aborted.")
            return False

        # Step 4: Start container
        if not self.start_container():
            print("❌ Container start failed. Installation aborted.")
            return False

        # Step 5: Wait for startup
        if not self.wait_for_startup():
            print("❌ Startup verification failed. Installation may be incomplete.")
            return False

        # Step 6: Create management scripts
        if not self.create_management_scripts():
            print("❌ Management scripts creation failed.")
            return False

        # Step 7: Create symlink
        self.create_symlink()

        print("=" * 60)
        print("🎉 OpenDaylight installation completed successfully!")
        print()
        print("📍 Installation Details:")
        print(f"   Docker Image: {self.docker_image}")
        print(f"   Container Name: {self.container_name}")
        print(f"   Data Directory: {self.odl_home}")
        print()
        print("🌐 OpenDaylight Access Points:")
        print("   REST API: http://localhost:8181/restconf")
        print("   Web UI: http://localhost:8181/index.html")
        print("   SSH: localhost:8101 (admin/admin)")
        print("   OpenFlow: localhost:6633")
        print()
        print("🚀 Management Commands:")
        print(f"   Start: ~/start_opendaylight.sh")
        print(f"   Stop: ~/stop_opendaylight.sh")
        print(f"   Status: ~/status_opendaylight.sh")
        print()
        print("🐳 Docker Commands:")
        print(f"   Logs: docker logs {self.container_name}")
        print(f"   Shell: docker exec -it {self.container_name} bash")
        print(f"   Stop: docker stop {self.container_name}")

        return True

def main():
    """Main function"""
    try:
        installer = OpenDaylightDockerInstaller()
        success = installer.install()

        if success:
            print("\n✅ Installation completed successfully!")
            print("You can now use OpenDaylight with Mininet!")
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
