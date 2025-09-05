#!/usr/bin/env python3
"""
P4-Utils Installation Script
Install P4-Utils for easier P4 switch management in Mininet
Based on: https://nsg-ethz.github.io/p4-utils/usage.html
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

def run_command(cmd, description, check=True):
    """Run a command with error handling"""
    print(f"🔄 {description}...")
    try:
        if isinstance(cmd, str):
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {description} - SUCCESS")
            return True
        else:
            print(f"❌ {description} - FAILED")
            if result.stderr:
                print(f"   Error: {result.stderr.strip()}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        if e.stderr:
            print(f"   Error: {e.stderr.strip()}")
        return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def check_prerequisites():
    """Check if required tools are available"""
    print_header("CHECKING PREREQUISITES")
    
    prerequisites = [
        ('git', 'Git version control'),
        ('python3', 'Python 3'),
        ('pip3', 'Python package manager')
    ]
    
    all_good = True
    for cmd, desc in prerequisites:
        result = subprocess.run(['which', cmd], capture_output=True)
        if result.returncode == 0:
            print(f"✅ {desc}: FOUND")
        else:
            print(f"❌ {desc}: NOT FOUND")
            all_good = False
    
    return all_good

def install_p4_utils():
    """Install P4-Utils from GitHub"""
    print_header("INSTALLING P4-UTILS")
    
    # Install P4-Utils via pip (if available)
    print("Attempting to install P4-Utils via pip...")
    if run_command('pip3 install p4utils', "Installing P4-Utils via pip", check=False):
        return True
    
    # If pip fails, install from source
    print("Pip installation failed, trying from source...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # Clone P4-Utils repository
        if not run_command('git clone https://github.com/nsg-ethz/p4-utils.git', 
                          "Cloning P4-Utils repository"):
            return False
        
        os.chdir('p4-utils')
        
        # Install P4-Utils
        if not run_command('pip3 install .', "Installing P4-Utils from source"):
            return False
    
    return True

def install_p4_dependencies():
    """Install P4 runtime dependencies"""
    print_header("INSTALLING P4 DEPENDENCIES")
    
    # Install basic dependencies
    dependencies = [
        'protobuf-compiler',
        'libprotobuf-dev', 
        'python3-protobuf'
    ]
    
    success_count = 0
    for dep in dependencies:
        if run_command(f'sudo apt-get install -y {dep}', f"Installing {dep}", check=False):
            success_count += 1
    
    # Install Python packages
    python_packages = [
        'grpcio',
        'grpcio-tools', 
        'protobuf',
        'scapy',
        'networkx'
    ]
    
    for package in python_packages:
        run_command(f'pip3 install {package}', f"Installing {package}", check=False)
    
    return success_count > 0

def create_p4_test_network():
    """Create a simple P4 test network using P4-Utils"""
    print_header("CREATING P4 TEST NETWORK")
    
    try:
        # Create test directory
        test_dir = Path.home() / "p4_test_network"
        test_dir.mkdir(exist_ok=True)
        
        # Create simple P4 program
        p4_program = '''
/* Simple L2 Forwarding P4 Program */
#include <core.p4>
#include <v1model.p4>

typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

struct metadata {
    /* empty */
}

struct headers {
    ethernet_t   ethernet;
}

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {   
    apply {  }
}

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {
    
    action drop() {
        mark_to_drop(standard_metadata);
    }
    
    action forward(bit<9> port) {
        standard_metadata.egress_spec = port;
    }
    
    table dmac {
        key = {
            hdr.ethernet.dstAddr: exact;
        }
        actions = {
            forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = drop();
    }
    
    apply {
        if (hdr.ethernet.isValid()) {
            dmac.apply();
        }
    }
}

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

control MyComputeChecksum(inout headers  hdr, inout metadata meta) {
     apply {
    }
}

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
    }
}

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
'''
        
        # Write P4 program
        with open(test_dir / "l2_forwarding.p4", "w") as f:
            f.write(p4_program)
        
        # Create Python network script using P4-Utils
        network_script = '''#!/usr/bin/env python3

from p4utils.mininetlib.network_API import NetworkAPI

net = NetworkAPI()

# Set log level
net.setLogLevel('info')

# Add network elements
net.addP4Switch('s1')
net.addHost('h1')
net.addHost('h2')
net.addHost('h3')
net.addHost('h4')

# Set P4 source
net.setP4Source('s1', 'l2_forwarding.p4')

# Add links
net.addLink('s1', 'h1')
net.addLink('s1', 'h2') 
net.addLink('s1', 'h3')
net.addLink('s1', 'h4')

# Set interface ports
net.setIntfPort('s1', 'h1', 1)
net.setIntfPort('s1', 'h2', 2)
net.setIntfPort('s1', 'h3', 3)
net.setIntfPort('s1', 'h4', 4)

# Use L2 assignment strategy
net.l2()

# Enable CLI and logging
net.enableCli()
net.enableLogAll()
net.enablePcapDumpAll()

# Start network
net.startNetwork()
'''
        
        with open(test_dir / "network.py", "w") as f:
            f.write(network_script)
        
        # Make executable
        os.chmod(test_dir / "network.py", 0o755)
        
        # Create switch commands file
        switch_commands = '''table_add dmac forward 00:00:0a:00:00:01 => 1
table_add dmac forward 00:00:0a:00:00:02 => 2
table_add dmac forward 00:00:0a:00:00:03 => 3
table_add dmac forward 00:00:0a:00:00:04 => 4
'''
        
        with open(test_dir / "s1-commands.txt", "w") as f:
            f.write(switch_commands)
        
        print(f"✅ P4 test network created at {test_dir}")
        print(f"   Files created:")
        print(f"     - l2_forwarding.p4 (P4 program)")
        print(f"     - network.py (Network topology)")
        print(f"     - s1-commands.txt (Switch configuration)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating test network: {e}")
        return False

def create_integration_script():
    """Create script to integrate P4-Utils with the existing framework"""
    print_header("CREATING INTEGRATION SCRIPT")
    
    try:
        integration_script = '''#!/usr/bin/env python3
"""
P4-Utils Integration with Mininet Web Framework
Bridge between P4-Utils and existing switch factory
"""

import sys
import os
from pathlib import Path

# Add P4-Utils to path
try:
    from p4utils.mininetlib.network_API import NetworkAPI
    print("✅ P4-Utils successfully imported")
except ImportError as e:
    print(f"❌ P4-Utils import failed: {e}")
    print("   Run: pip3 install p4utils")
    sys.exit(1)

class P4UtilsWrapper:
    """Wrapper to integrate P4-Utils with existing switch factory"""
    
    def __init__(self):
        self.net = None
        self.switches = {}
        
    def create_p4_network(self, topology_config):
        """Create P4 network from topology configuration"""
        self.net = NetworkAPI()
        self.net.setLogLevel('info')
        
        # Add nodes from config
        for node in topology_config.get('nodes', []):
            if node['type'] == 'switch' and node.get('switch_type') == 'p4':
                switch_id = node['id']
                self.net.addP4Switch(switch_id)
                self.switches[switch_id] = node
                
                # Set P4 program if specified
                p4_program = node.get('p4_program', 'basic_forwarding.p4')
                self.net.setP4Source(switch_id, p4_program)
                
            elif node['type'] == 'host':
                self.net.addHost(node['id'])
        
        # Add links
        for link in topology_config.get('links', []):
            self.net.addLink(link['source'], link['target'])
            
            # Set bandwidth if specified
            if 'bandwidth' in link:
                self.net.setBw(link['source'], link['target'], link['bandwidth'])
        
        # Use appropriate assignment strategy
        assignment = topology_config.get('assignment_strategy', 'l2')
        if assignment == 'l2':
            self.net.l2()
        elif assignment == 'l3':
            self.net.l3()
        elif assignment == 'mixed':
            self.net.mixed()
        
        return self.net
    
    def start_network(self, enable_cli=True):
        """Start the P4 network"""
        if self.net:
            if enable_cli:
                self.net.enableCli()
            self.net.enableLogAll()
            self.net.startNetwork()
            return True
        return False
    
    def get_switch_info(self):
        """Get information about P4 switches"""
        return {
            'p4_switches': list(self.switches.keys()),
            'network_api': self.net is not None
        }

def test_p4_utils():
    """Test P4-Utils functionality"""
    print("🧪 Testing P4-Utils functionality...")
    
    # Simple test configuration
    test_config = {
        'nodes': [
            {'id': 's1', 'type': 'switch', 'switch_type': 'p4'},
            {'id': 'h1', 'type': 'host'},
            {'id': 'h2', 'type': 'host'}
        ],
        'links': [
            {'source': 's1', 'target': 'h1'},
            {'source': 's1', 'target': 'h2'}
        ],
        'assignment_strategy': 'l2'
    }
    
    wrapper = P4UtilsWrapper()
    net = wrapper.create_p4_network(test_config)
    
    if net:
        print("✅ P4-Utils network creation test passed")
        return True
    else:
        print("❌ P4-Utils network creation test failed")
        return False

if __name__ == "__main__":
    test_p4_utils()
'''
        
        with open("p4_utils_integration.py", "w") as f:
            f.write(integration_script)
        
        os.chmod("p4_utils_integration.py", 0o755)
        
        print("✅ Integration script created: p4_utils_integration.py")
        return True
        
    except Exception as e:
        print(f"❌ Error creating integration script: {e}")
        return False

def verify_installation():
    """Verify P4-Utils installation"""
    print_header("VERIFYING P4-UTILS INSTALLATION")
    
    try:
        # Test import
        result = subprocess.run([
            'python3', '-c', 
            'from p4utils.mininetlib.network_API import NetworkAPI; print("P4-Utils import successful")'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ P4-Utils Python import: SUCCESS")
            print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print("❌ P4-Utils Python import: FAILED")
            print(f"   Error: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying installation: {e}")
        return False

def main():
    print_header("P4-UTILS INSTALLATION")
    print("Installing P4-Utils for easier P4 switch management")
    print("Based on: https://nsg-ethz.github.io/p4-utils/usage.html")
    
    # Check prerequisites
    if not check_prerequisites():
        print("❌ Prerequisites not met. Please install missing tools first.")
        return False
    
    # Install P4 dependencies
    if not install_p4_dependencies():
        print("⚠️  Some dependencies failed to install, continuing...")
    
    # Install P4-Utils
    if not install_p4_utils():
        print("❌ P4-Utils installation failed")
        return False
    
    # Verify installation
    if not verify_installation():
        print("❌ P4-Utils verification failed")
        return False
    
    # Create test network
    create_p4_test_network()
    
    # Create integration script
    create_integration_script()
    
    print_header("INSTALLATION COMPLETE")
    print("✅ P4-Utils installed successfully!")
    print("\n🎯 What you can do now:")
    print("   1. Use P4-Utils NetworkAPI for P4 switch topologies")
    print("   2. Run test network: cd ~/p4_test_network && sudo python3 network.py")
    print("   3. Integrate with existing framework using p4_utils_integration.py")
    print("\n📚 Documentation: https://nsg-ethz.github.io/p4-utils/usage.html")
    print("📚 Examples: https://github.com/nsg-ethz/p4-learning")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
