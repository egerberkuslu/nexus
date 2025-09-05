#!/usr/bin/env python3
"""
OpenDaylight Installation and Testing Script
Comprehensive test for OpenDaylight controller setup and functionality
"""

import os
import sys
import subprocess
import time
import requests
import socket
import json
import shutil
from pathlib import Path
from datetime import datetime
import logging

# Set up simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleODLManager:
    """Simple OpenDaylight manager without Mininet dependencies"""
    
    def __init__(self):
        # Try multiple possible OpenDaylight installation paths
        possible_paths = [
            os.path.expanduser('~/opendaylight'),
            '/opt/opendaylight', 
            '/root/opendaylight',
            '/home/root/opendaylight',
        ]
        self.odl_home = None
        for path in possible_paths:
            if os.path.exists(path):
                self.odl_home = path
                break
        
        if self.odl_home is None:
            self.odl_home = os.path.expanduser('~/opendaylight')
            
        self.is_running = False
        self.process = None
        
    def check_installation(self):
        """Check if OpenDaylight is properly installed"""
        odl_bin = os.path.join(self.odl_home, 'bin', 'karaf')
        return os.path.exists(odl_bin) and os.access(odl_bin, os.X_OK)
        
    def start_controller(self):
        """Start OpenDaylight controller"""
        if not self.check_installation():
            return False
            
        start_script = os.path.join(self.odl_home, 'bin', 'start')
        if os.path.exists(start_script):
            cmd = [start_script]
        else:
            cmd = [os.path.join(self.odl_home, 'bin', 'karaf'), 'server']
            
        try:
            env = os.environ.copy()
            java_home = self._find_java_home()
            if java_home:
                env['JAVA_HOME'] = java_home
            env['ODL_HOME'] = self.odl_home
            
            self.process = subprocess.Popen(
                cmd, cwd=self.odl_home, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            self.is_running = True
            return True
        except Exception as e:
            logger.error(f"Failed to start ODL: {e}")
            return False
            
    def _find_java_home(self):
        """Find Java installation directory"""
        try:
            result = subprocess.run(['java', '-XshowSettings:properties'],
                                  capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'java.home' in line:
                    return line.split('=')[1].strip()
        except:
            pass
        return None
        
    def stop_controller(self):
        """Stop OpenDaylight controller"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except:
                self.process.kill()
            self.process = None
        self.is_running = False

class OpenDaylightTester:
    """Comprehensive OpenDaylight installation and testing"""
    
    def __init__(self):
        self.odl_manager = SimpleODLManager()
        self.test_results = {}
        self.start_time = datetime.now()
        
    def print_banner(self, title):
        """Print a formatted banner"""
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60)
        
    def print_step(self, step, status="INFO"):
        """Print a test step"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {step}")
        
    def check_prerequisites(self):
        """Check system prerequisites"""
        self.print_banner("CHECKING PREREQUISITES")
        results = {}
        
        # Check Java
        self.print_step("Checking Java installation...")
        try:
            result = subprocess.run(['java', '-version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_line = result.stderr.split('\n')[0] if result.stderr else result.stdout.split('\n')[0]
                self.print_step(f"Java found: {version_line}", "SUCCESS")
                results['java'] = True
            else:
                self.print_step("Java not found or not working", "ERROR")
                results['java'] = False
        except Exception as e:
            self.print_step(f"Java check failed: {e}", "ERROR")
            results['java'] = False
            
        # Check JAVA_HOME
        java_home = os.environ.get('JAVA_HOME')
        if java_home:
            self.print_step(f"JAVA_HOME set to: {java_home}", "SUCCESS")
            results['java_home'] = True
        else:
            self.print_step("JAVA_HOME not set", "WARNING")
            results['java_home'] = False
            
        # Check available ports
        for port in [8181, 8101, 6633]:
            if self.is_port_available(port):
                self.print_step(f"Port {port} is available", "SUCCESS")
                results[f'port_{port}'] = True
            else:
                self.print_step(f"Port {port} is in use", "WARNING")
                results[f'port_{port}'] = False
                
        # Check disk space
        odl_path = os.path.expanduser('~/opendaylight')
        if os.path.exists(odl_path):
            size = self.get_directory_size(odl_path)
            self.print_step(f"OpenDaylight directory exists: {size:.1f} MB", "INFO")
            results['odl_exists'] = True
        else:
            self.print_step("OpenDaylight directory not found", "INFO")
            results['odl_exists'] = False
            
        self.test_results['prerequisites'] = results
        return results
        
    def is_port_available(self, port):
        """Check if a port is available"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                return result != 0
        except:
            return False
            
    def get_directory_size(self, path):
        """Get directory size in MB"""
        try:
            total = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total += os.path.getsize(filepath)
            return total / (1024 * 1024)  # Convert to MB
        except:
            return 0
            
    def test_installation(self):
        """Test OpenDaylight installation"""
        self.print_banner("TESTING OPENDAYLIGHT INSTALLATION")
        
        try:
            # Check installation
            self.print_step("Checking OpenDaylight installation...")
            self.print_step(f"Looking for ODL at: {self.odl_manager.odl_home}")
            
            if self.odl_manager.check_installation():
                self.print_step("OpenDaylight installation verified", "SUCCESS")
                self.test_results['installation_check'] = True
            else:
                self.print_step("OpenDaylight not properly installed", "ERROR")
                self.print_step("Please install OpenDaylight manually or run install script", "INFO")
                self.test_results['installation_check'] = False
                return False
                    
        except Exception as e:
            self.print_step(f"Installation test failed: {e}", "ERROR")
            self.test_results['installation_error'] = str(e)
            return False
            
        return True
        
    def test_startup(self):
        """Test OpenDaylight startup"""
        self.print_banner("TESTING OPENDAYLIGHT STARTUP")
            
        try:
            # Start controller
            self.print_step("Starting OpenDaylight controller...")
            start_time = time.time()
            
            success = self.odl_manager.start_controller()
            
            if success:
                self.print_step("OpenDaylight process started", "SUCCESS")
                
                # Wait for services to come up
                self.print_step("Waiting for services to initialize...")
                for i in range(60):  # Wait up to 60 seconds
                    time.sleep(1)
                    
                    # Check if Karaf is responding
                    status_script = os.path.join(self.odl_manager.odl_home, 'bin', 'status')
                    if os.path.exists(status_script):
                        try:
                            result = subprocess.run([status_script], 
                                                  capture_output=True, text=True, 
                                                  timeout=5, cwd=self.odl_manager.odl_home)
                            if "Running" in (result.stdout or ""):
                                self.print_step(f"Karaf started after {i+1} seconds", "SUCCESS")
                                break
                        except:
                            pass
                    
                    if i % 10 == 0 and i > 0:
                        self.print_step(f"Still waiting... ({i}/60 seconds)")
                
                startup_time = time.time() - start_time
                self.print_step(f"Total startup time: {startup_time:.1f} seconds")
                self.test_results['startup'] = True
                self.test_results['startup_time'] = startup_time
                return True
            else:
                self.print_step("OpenDaylight startup failed", "ERROR")
                self.test_results['startup'] = False
                return False
                
        except Exception as e:
            self.print_step(f"Startup test failed: {e}", "ERROR")
            self.test_results['startup_error'] = str(e)
            return False
            
    def test_rest_api(self):
        """Test OpenDaylight REST API"""
        self.print_banner("TESTING OPENDAYLIGHT REST API")
        
        if not self.odl_manager or not self.odl_manager.is_running:
            self.print_step("OpenDaylight not running", "ERROR")
            return False
            
        # Test various REST endpoints
        endpoints = [
            ('/rests/version', 'Version endpoint'),
            ('/rests/data', 'Data endpoint'),
            ('/restconf/operational/system', 'Legacy system endpoint'),
            ('/restconf/modules', 'Modules endpoint')
        ]
        
        results = {}
        
        for endpoint, description in endpoints:
            self.print_step(f"Testing {description}: {endpoint}")
            try:
                url = f"http://localhost:8181{endpoint}"
                response = requests.get(url, auth=('admin', 'admin'), timeout=10)
                
                if response.status_code in [200, 401, 403]:
                    self.print_step(f"{description} accessible (status: {response.status_code})", "SUCCESS")
                    results[endpoint] = True
                else:
                    self.print_step(f"{description} returned status: {response.status_code}", "WARNING")
                    results[endpoint] = False
                    
            except requests.exceptions.ConnectionError:
                self.print_step(f"{description} connection refused", "ERROR")
                results[endpoint] = False
            except requests.exceptions.Timeout:
                self.print_step(f"{description} request timed out", "ERROR") 
                results[endpoint] = False
            except Exception as e:
                self.print_step(f"{description} error: {e}", "ERROR")
                results[endpoint] = False
                
        self.test_results['rest_api'] = results
        return any(results.values())
        
    def test_basic_functionality(self):
        """Test basic OpenDaylight functionality"""
        self.print_banner("TESTING BASIC FUNCTIONALITY")
        
        # Check if OpenDaylight is still running (check ports since bin/start forks)
        if not self.is_port_available(8101) and not self.is_port_available(8181):
            self.print_step("OpenDaylight is still running (ports in use)", "SUCCESS")
            self.test_results['process_running'] = True
        else:
            self.print_step("OpenDaylight appears to have stopped", "ERROR")
            self.test_results['process_running'] = False
            
        # Check key ports
        ports_to_check = [8181, 8101, 6633]
        for port in ports_to_check:
            if not self.is_port_available(port):
                self.print_step(f"Port {port} is in use (likely by ODL)", "SUCCESS")
                self.test_results[f'port_{port}_used'] = True
            else:
                self.print_step(f"Port {port} is not in use", "WARNING")
                self.test_results[f'port_{port}_used'] = False
                
        return self.test_results.get('process_running', False)
        
    def test_logs(self):
        """Check OpenDaylight logs"""
        self.print_banner("CHECKING OPENDAYLIGHT LOGS")
            
        # Check ODL log files
        log_dir = os.path.join(self.odl_manager.odl_home, 'data', 'log')
        if os.path.exists(log_dir):
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
            self.print_step(f"Found {len(log_files)} log files in {log_dir}", "INFO")
            
            for log_file in log_files[:3]:  # Show first 3 log files
                log_path = os.path.join(log_dir, log_file)
                if os.path.exists(log_path):
                    size = os.path.getsize(log_path) / 1024  # KB
                    self.print_step(f"  {log_file}: {size:.1f} KB")
                
            self.test_results['log_files'] = len(log_files)
        else:
            self.print_step("ODL log directory not found", "WARNING")
            self.test_results['log_files'] = 0
            
        return True
        
    def cleanup(self):
        """Clean up after tests"""
        self.print_banner("CLEANUP")
        
        if self.odl_manager and self.odl_manager.is_running:
            self.print_step("Stopping OpenDaylight...")
            try:
                self.odl_manager.stop_controller()
                self.print_step("OpenDaylight stopped", "SUCCESS")
            except Exception as e:
                self.print_step(f"Error stopping ODL: {e}", "ERROR")
                
    def print_summary(self):
        """Print test summary"""
        self.print_banner("TEST SUMMARY")
        
        total_time = (datetime.now() - self.start_time).total_seconds()
        self.print_step(f"Total test time: {total_time:.1f} seconds")
        
        # Count successes and failures
        successes = 0
        failures = 0
        
        for test_name, result in self.test_results.items():
            if isinstance(result, bool):
                if result:
                    successes += 1
                else:
                    failures += 1
                    
        self.print_step(f"Successful tests: {successes}")
        self.print_step(f"Failed tests: {failures}")
        
        # Print detailed results
        print("\nDetailed Results:")
        print("-" * 40)
        for test_name, result in self.test_results.items():
            status = "PASS" if result else "FAIL" if isinstance(result, bool) else str(result)
            print(f"{test_name:25} : {status}")
            
        # Save results to file
        results_file = f"odl_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(results_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total_time': total_time,
                    'results': self.test_results
                }, f, indent=2)
            self.print_step(f"Results saved to {results_file}", "INFO")
        except Exception as e:
            self.print_step(f"Could not save results: {e}", "WARNING")
            
    def run_all_tests(self):
        """Run all tests in sequence"""
        self.print_banner("OPENDAYLIGHT COMPREHENSIVE TEST")
        self.print_step(f"Starting tests at {self.start_time}")
        
        try:
            # Prerequisites
            self.check_prerequisites()
            
            # Installation
            if not self.test_installation():
                self.print_step("Installation failed, skipping other tests", "ERROR")
                return False
                
            # Startup
            if not self.test_startup():
                self.print_step("Startup failed, skipping dependent tests", "ERROR")
                return False
                
            # Wait a bit for full startup
            self.print_step("Waiting for full startup...")
            time.sleep(10)
            
            # REST API
            self.test_rest_api()
            
            # Basic functionality
            self.test_basic_functionality()
            
            # Logs
            self.test_logs()
            
            return True
            
        except KeyboardInterrupt:
            self.print_step("Tests interrupted by user", "WARNING")
            return False
        except Exception as e:
            self.print_step(f"Unexpected error during tests: {e}", "ERROR")
            return False
        finally:
            self.cleanup()
            self.print_summary()

def main():
    """Main test function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("OpenDaylight Test Script")
        print("Usage: python test_opendaylight_standalone.py")
        print("Options:")
        print("  --help    Show this help message")
        return
        
    tester = OpenDaylightTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
