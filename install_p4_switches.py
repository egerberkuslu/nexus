#!/usr/bin/env python3
"""
P4 Switch Installation Script
Install P4 compiler and BMv2 behavioral model for P4 switches
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
        print(f"   Error: {e}")
        return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def check_prerequisites():
    """Check if required tools are available"""
    print_header("CHECKING PREREQUISITES")
    
    prerequisites = [
        ('git', 'Git version control'),
        ('cmake', 'CMake build system'),
        ('g++', 'GNU C++ compiler'),
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

def install_dependencies():
    """Install required system dependencies"""
    print_header("INSTALLING DEPENDENCIES")
    
    packages = [
        'git', 'cmake', 'g++', 'automake', 'libtool', 'pkg-config',
        'libgc-dev', 'libfl-dev', 'libgmp-dev', 'libboost-dev',
        'libboost-iostreams-dev', 'libboost-graph-dev',
        'llvm', 'clang', 'libclang-dev', 'python3-pip'
    ]
    
    print("Installing system packages...")
    cmd = ['sudo', 'apt-get', 'install', '-y'] + packages
    return run_command(cmd, "Installing system dependencies", check=False)

def install_protobuf():
    """Install Protocol Buffers"""
    print_header("INSTALLING PROTOBUF")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # Clone protobuf
        if not run_command('git clone https://github.com/protocolbuffers/protobuf.git', 
                          "Cloning protobuf", check=False):
            return False
        
        os.chdir('protobuf')
        
        # Configure and build
        commands = [
            './autogen.sh',
            './configure',
            'make -j4',
            'sudo make install',
            'sudo ldconfig'
        ]
        
        for cmd in commands:
            if not run_command(cmd, f"Protobuf: {cmd}", check=False):
                return False
    
    return True

def install_grpc():
    """Install gRPC"""
    print_header("INSTALLING GRPC")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # Clone gRPC
        if not run_command('git clone --recurse-submodules -b v1.43.0 https://github.com/grpc/grpc', 
                          "Cloning gRPC", check=False):
            return False
        
        os.chdir('grpc')
        
        # Build gRPC
        commands = [
            'mkdir -p cmake/build',
            'cd cmake/build && cmake -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF ../',
            'cd cmake/build && make -j4',
            'cd cmake/build && sudo make install'
        ]
        
        for cmd in commands:
            if not run_command(cmd, f"gRPC: {cmd}", check=False):
                return False
    
    return True

def install_p4c():
    """Install P4 compiler"""
    print_header("INSTALLING P4 COMPILER")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # Clone p4c
        if not run_command('git clone --recursive https://github.com/p4lang/p4c.git', 
                          "Cloning P4C", check=False):
            return False
        
        os.chdir('p4c')
        
        # Build P4C
        commands = [
            'mkdir build',
            'cd build && cmake ..',
            'cd build && make -j4',
            'cd build && sudo make install'
        ]
        
        for cmd in commands:
            if not run_command(cmd, f"P4C: {cmd}", check=False):
                return False
    
    return True

def install_bmv2():
    """Install Behavioral Model v2"""
    print_header("INSTALLING BMV2")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # Clone BMv2
        if not run_command('git clone https://github.com/p4lang/behavioral-model.git', 
                          "Cloning BMv2", check=False):
            return False
        
        os.chdir('behavioral-model')
        
        # Build BMv2
        commands = [
            './autogen.sh',
            './configure --enable-debugger',
            'make -j4',
            'sudo make install'
        ]
        
        for cmd in commands:
            if not run_command(cmd, f"BMv2: {cmd}", check=False):
                return False
    
    return True

def create_simple_installation():
    """Create a simpler P4 installation using package manager where possible"""
    print_header("SIMPLE P4 INSTALLATION")
    
    print("🎯 Installing P4 tools via package manager (where available)...")
    
    # Install available packages one by one to handle missing packages
    packages = [
        'protobuf-compiler', 'libprotobuf-dev', 'python3-protobuf'
    ]
    
    success_count = 0
    for package in packages:
        cmd = ['sudo', 'apt-get', 'install', '-y', package]
        if run_command(cmd, f"Installing {package}", check=False):
            success_count += 1
        else:
            print(f"⚠️  {package} not available via apt")
    
    # Install Python packages via pip (more reliable)
    print("\n🐍 Installing Python packages via pip...")
    python_packages = [
        ('grpcio', 'gRPC Python library'),
        ('grpcio-tools', 'gRPC Python tools'),
        ('protobuf', 'Protocol Buffers Python'),
        ('scapy', 'Packet manipulation library')
    ]
    
    pip_success = 0
    for package, desc in python_packages:
        if run_command(f'pip3 install {package}', f"Installing {desc}", check=False):
            pip_success += 1
        else:
            print(f"⚠️  {package} installation failed (will try alternative)")
    
    # Try alternative P4 packages
    print("\n🔧 Installing P4-specific packages...")
    p4_packages = ['p4runtime', 'p4runtime-shell']
    for package in p4_packages:
        run_command(f'pip3 install {package}', f"Installing {package}", check=False)
    
    # Create a simple P4 program template for testing
    create_p4_test_program()
    
    print("\n💡 Simple P4 installation completed!")
    print("   - Basic P4Runtime support installed")
    print("   - For full P4 compiler support, use option 2 (full installation)")
    print("   - Test P4 program template created")
    
    return success_count > 0 or pip_success > 0

def create_p4_test_program():
    """Create a simple P4 program for testing"""
    try:
        # Use user's home directory instead of /tmp for permissions
        p4_dir = Path.home() / "p4_test"
        p4_dir.mkdir(exist_ok=True)
        
        test_program = """
/* Simple P4 Test Program */
#include <core.p4>
#include <v1model.p4>

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

struct headers {
    ethernet_t ethernet;
}

struct metadata { }

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
    
    table forwarding {
        key = {
            hdr.ethernet.dstAddr: exact;
        }
        actions = {
            forward;
            drop;
        }
        default_action = drop();
    }
    
    apply {
        forwarding.apply();
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
"""
        
        with open(p4_dir / "test.p4", "w") as f:
            f.write(test_program)
        
        print(f"✅ Test P4 program created at {p4_dir}/test.p4")
        
    except Exception as e:
        print(f"⚠️  Could not create test P4 program: {e}")

def verify_installation():
    """Verify P4 installation"""
    print_header("VERIFYING INSTALLATION")
    
    checks = [
        ('p4c', 'P4 Compiler'),
        ('simple_switch', 'Simple Switch'),
        ('simple_switch_grpc', 'Simple Switch gRPC'),
    ]
    
    success_count = 0
    for cmd, desc in checks:
        result = subprocess.run(['which', cmd], capture_output=True)
        if result.returncode == 0:
            print(f"✅ {desc}: FOUND")
            success_count += 1
        else:
            print(f"❌ {desc}: NOT FOUND")
    
    return success_count > 0

def main():
    print_header("P4 SWITCH INSTALLATION")
    print("This script will install P4 compiler and BMv2 behavioral model.")
    print("⚠️  Warning: This is a complex installation that may take 30+ minutes.")
    
    # Check if user wants to proceed
    response = input("\nDo you want to proceed? (y/N): ").lower().strip()
    if response != 'y':
        print("Installation cancelled.")
        return False
    
    # Check what type of installation
    print("\nChoose installation type:")
    print("1. Simple installation (basic P4Runtime support)")
    print("2. Full installation (complete P4 toolchain - takes longer)")
    
    choice = input("Enter choice (1-2): ").strip()
    
    original_dir = os.getcwd()
    
    try:
        if choice == "2":
            # Full installation
            if not check_prerequisites():
                print("❌ Prerequisites not met. Please install missing tools first.")
                return False
            
            steps = [
                install_dependencies,
                install_protobuf,
                install_grpc,
                install_p4c,
                install_bmv2
            ]
            
            for step in steps:
                if not step():
                    print(f"❌ Installation failed at step: {step.__name__}")
                    return False
        
        else:
            # Simple installation
            if not create_simple_installation():
                print("❌ Simple installation failed")
                return False
        
        # Verify installation
        if verify_installation():
            print_header("INSTALLATION COMPLETE")
            print("✅ P4 tools installed successfully!")
            print("\n🎯 Next steps:")
            print("   - Run the switch diagnostic script to verify")
            print("   - Try creating P4 switches in your network topology")
            return True
        else:
            print("⚠️  Installation completed but verification failed")
            print("   Some P4 tools may not be available in PATH")
            return False
            
    except KeyboardInterrupt:
        print("\n❌ Installation cancelled by user")
        return False
    except Exception as e:
        print(f"❌ Installation failed: {e}")
        return False
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
