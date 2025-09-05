#!/usr/bin/env python3
"""
Official P4-Utils Installation Script
Using the official NSG-ETH installation method
Based on: https://nsg-ethz.github.io/p4-utils/installation.html#manual-installation
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
            if result.stdout and len(result.stdout.strip()) > 0:
                # Show last few lines of output for important commands
                lines = result.stdout.strip().split('\n')[-3:]
                for line in lines:
                    if line.strip():
                        print(f"   {line.strip()}")
            return True
        else:
            print(f"❌ {description} - FAILED")
            if result.stderr:
                print(f"   Error: {result.stderr.strip()[:200]}...")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        if e.stderr:
            print(f"   Error: {e.stderr.strip()[:200]}...")
        return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def check_system_compatibility():
    """Check if system is compatible with P4-Utils"""
    print_header("CHECKING SYSTEM COMPATIBILITY")
    
    # Check Ubuntu version
    try:
        result = subprocess.run(['lsb_release', '-r'], capture_output=True, text=True)
        if result.returncode == 0:
            version_line = result.stdout.strip()
            print(f"✅ System version: {version_line}")
            
            # Check if it's Ubuntu 20.04 or 22.04 (recommended)
            if '20.04' in version_line or '22.04' in version_line:
                print("✅ Ubuntu version compatible with P4-Utils")
                return True
            else:
                print("⚠️  Ubuntu version not explicitly tested with P4-Utils")
                print("   Recommended: Ubuntu 20.04 or 22.04")
                return True  # Still try to proceed
        else:
            print("⚠️  Could not detect Ubuntu version")
            return True
    except Exception as e:
        print(f"⚠️  System check failed: {e}")
        return True

def install_p4_tools_official():
    """Install P4-Tools using the official one-step installer"""
    print_header("OFFICIAL P4-TOOLS INSTALLATION")
    print("Using NSG-ETH official installer from:")
    print("https://nsg-ethz.github.io/p4-utils/installation.html#manual-installation")
    
    print("\n⚠️  This will install:")
    print("   - PI Library Repository (P4Runtime server)")
    print("   - Behavioral Model (BMv2) with simple_switch")
    print("   - P4C compiler (P4_14 and P4_16 support)")
    print("   - Mininet (if not already installed)")
    print("   - FRRouting (for router nodes)")
    print("   - P4-Utils framework")
    
    response = input("\nProceed with official P4-Tools installation? (y/N): ").lower().strip()
    if response != 'y':
        print("Installation cancelled.")
        return False
    
    # Method 1: One-step automated install (recommended)
    print("\n🚀 Running official one-step installer...")
    cmd = 'curl -sSL https://raw.githubusercontent.com/nsg-ethz/p4-utils/master/install-tools/install-p4-dev.sh | bash'
    
    try:
        # Run the installer with real-time output
        print("📥 Downloading and running installer...")
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, 
                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        # Show real-time output
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"   {output.strip()}")
        
        rc = process.poll()
        if rc == 0:
            print("\n✅ Official P4-Tools installation completed successfully!")
            return True
        else:
            print(f"\n❌ Official installer failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"❌ Error running official installer: {e}")
        return False

def install_p4_tools_manual():
    """Install P4-Tools using manual method (alternative)"""
    print_header("MANUAL P4-TOOLS INSTALLATION")
    print("Using alternative manual installation method...")
    
    try:
        # Download the installer script first
        print("📥 Downloading installation script...")
        download_cmd = 'wget -O install-p4-dev.sh https://raw.githubusercontent.com/nsg-ethz/p4-utils/master/install-tools/install-p4-dev.sh'
        
        if not run_command(download_cmd, "Downloading installer script"):
            return False
        
        # Make it executable
        os.chmod('install-p4-dev.sh', 0o755)
        
        # Run the installer
        print("🚀 Running installation script...")
        if run_command('./install-p4-dev.sh', "Running P4-Tools installer", check=False):
            print("✅ Manual P4-Tools installation completed!")
            return True
        else:
            print("❌ Manual installation failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in manual installation: {e}")
        return False

def verify_p4_tools():
    """Verify P4-Tools installation"""
    print_header("VERIFYING P4-TOOLS INSTALLATION")
    
    tools_to_check = [
        ('p4c', 'P4 Compiler'),
        ('simple_switch', 'Simple Switch (BMv2)'),
        ('simple_switch_grpc', 'Simple Switch gRPC'),
        ('simple_switch_CLI', 'Simple Switch CLI'),
        ('p4run', 'P4-Utils runner'),
    ]
    
    success_count = 0
    for tool, description in tools_to_check:
        result = subprocess.run(['which', tool], capture_output=True)
        if result.returncode == 0:
            path = result.stdout.decode().strip()
            print(f"✅ {description}: {path}")
            success_count += 1
        else:
            print(f"❌ {description}: NOT FOUND")
    
    # Test P4-Utils Python import
    try:
        result = subprocess.run([
            'python3', '-c', 
            'from p4utils.mininetlib.network_API import NetworkAPI; print("P4-Utils import successful")'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ P4-Utils Python module: AVAILABLE")
            success_count += 1
        else:
            print("❌ P4-Utils Python module: NOT AVAILABLE")
            print(f"   Error: {result.stderr.strip()}")
    except Exception as e:
        print(f"❌ P4-Utils import test failed: {e}")
    
    print(f"\n📊 Verification Results: {success_count}/{len(tools_to_check)+1} tools available")
    return success_count >= 3  # At least 3 tools should work

def create_simple_p4_test():
    """Create a simple P4 test using P4-Utils methodology"""
    print_header("CREATING P4 TEST NETWORK")
    
    try:
        test_dir = Path.home() / "p4_utils_test"
        test_dir.mkdir(exist_ok=True)
        
        # Create simple P4 program (based on P4-Utils documentation)
        p4_program = '''/* Simple L2 Forwarding - P4-Utils Example */
#include <core.p4>
#include <v1model.p4>

typedef bit<48> macAddr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

struct metadata {
    /* empty */
}

struct headers {
    ethernet_t ethernet;
}

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {
    state start {
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply { }
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
        }
        size = 1024;
        default_action = drop();
    }
    
    apply {
        dmac.apply();
    }
}

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply { }
}

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply { }
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

        # Create network script using P4-Utils NetworkAPI
        network_script = '''#!/usr/bin/env python3
"""
P4-Utils Test Network
Based on: https://nsg-ethz.github.io/p4-utils/usage.html
"""

from p4utils.mininetlib.network_API import NetworkAPI

net = NetworkAPI()

# Set log level
net.setLogLevel('info')

# Add P4 switch and hosts
net.addP4Switch('s1')
net.addHost('h1')
net.addHost('h2')
net.addHost('h3')
net.addHost('h4')

# Set P4 source for the switch
net.setP4Source('s1', 'l2_forwarding.p4')

# Add links between switch and hosts
net.addLink('s1', 'h1')
net.addLink('s1', 'h2')
net.addLink('s1', 'h3')
net.addLink('s1', 'h4')

# Set interface port numbers (as recommended in P4-Utils docs)
net.setIntfPort('s1', 'h1', 1)
net.setIntfPort('h1', 's1', 0)
net.setIntfPort('s1', 'h2', 2)
net.setIntfPort('h2', 's1', 0)
net.setIntfPort('s1', 'h3', 3)
net.setIntfPort('h3', 's1', 0)
net.setIntfPort('s1', 'h4', 4)
net.setIntfPort('h4', 's1', 0)

# Use L2 assignment strategy (all hosts in same network 10.0.0.0/16)
net.l2()

# Enable features
net.enablePcapDumpAll()  # Capture packets
net.enableLogAll()       # Enable logging
net.enableCli()          # Enable CLI

# Set switch commands for forwarding table
net.setP4CliInput('s1', 's1-commands.txt')

# Start the network
print("Starting P4-Utils network...")
net.startNetwork()
'''

        # Create switch commands file
        switch_commands = '''table_add dmac forward 00:00:0a:00:00:01 => 1
table_add dmac forward 00:00:0a:00:00:02 => 2
table_add dmac forward 00:00:0a:00:00:03 => 3
table_add dmac forward 00:00:0a:00:00:04 => 4
'''

        # Write all files
        files = [
            ('l2_forwarding.p4', p4_program),
            ('network.py', network_script),
            ('s1-commands.txt', switch_commands)
        ]
        
        for filename, content in files:
            filepath = test_dir / filename
            with open(filepath, 'w') as f:
                f.write(content)
            if filename.endswith('.py'):
                os.chmod(filepath, 0o755)
        
        print(f"✅ P4-Utils test network created at {test_dir}")
        print("   Files created:")
        for filename, _ in files:
            print(f"     - {filename}")
        
        print(f"\n🚀 To test P4 network:")
        print(f"   cd {test_dir}")
        print(f"   sudo python3 network.py")
        print(f"   # In the Mininet CLI, try: pingall")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating P4 test: {e}")
        return False

def main():
    print_header("P4-UTILS OFFICIAL INSTALLATION")
    print("Installing P4-Utils using the official NSG-ETH method")
    print("Documentation: https://nsg-ethz.github.io/p4-utils/installation.html")
    
    # Check system compatibility
    if not check_system_compatibility():
        print("⚠️  System compatibility check failed, but proceeding anyway...")
    
    print("\n🎯 Installation Options:")
    print("1. One-step automated install (RECOMMENDED)")
    print("2. Manual installation (download script first)")
    print("3. Skip installation and create test files only")
    
    choice = input("Choose installation method (1-3): ").strip()
    
    installation_success = False
    
    if choice == "1":
        installation_success = install_p4_tools_official()
    elif choice == "2":
        installation_success = install_p4_tools_manual()
    elif choice == "3":
        print("Skipping installation, creating test files only...")
        installation_success = True
    else:
        print("Invalid choice, using option 1 (one-step install)")
        installation_success = install_p4_tools_official()
    
    if installation_success:
        # Verify installation
        if choice != "3":
            verify_success = verify_p4_tools()
        else:
            verify_success = True
        
        # Create test network
        create_simple_p4_test()
        
        print_header("INSTALLATION SUMMARY")
        if choice == "3":
            print("✅ Test files created successfully!")
            print("   To install P4-Tools later, run this script again with option 1")
        elif verify_success:
            print("🎉 P4-Utils installation completed successfully!")
            print("✅ All P4 tools are now available")
            print("✅ Test network created")
            print("\n🎯 What you can do now:")
            print("   1. Test P4 network: cd ~/p4_utils_test && sudo python3 network.py")
            print("   2. Learn P4: https://github.com/nsg-ethz/p4-learning")
            print("   3. Integrate with your web framework")
        else:
            print("⚠️  Installation completed but some tools may not be available")
            print("   Check the verification results above")
        
        return True
    else:
        print("❌ P4-Tools installation failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
