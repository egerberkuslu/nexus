"""
P4 Switch Manager
Provides P4 behavioral model (BMv2) switch support with P4Runtime API
"""

import os
import json
import time
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .base_switch_manager import BaseSwitchManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

class P4SwitchManager(BaseSwitchManager):
    """P4 behavioral model switch implementation"""

    def __init__(self):
        super().__init__("P4 BMv2", "p4")
        self.p4_programs_dir = Path("/tmp/p4_programs")
        self.compiled_programs_dir = Path("/tmp/p4_compiled")
        self.templates_dir = Path(__file__).parent / "p4_templates"
        self.p4c_path = self._find_p4c_compiler()
        self.simple_switch_path = self._find_simple_switch()
        self.current_program = None
        self.table_entries = {}
        self.p4runtime_client = None

    def check_installation(self) -> bool:
        """Check if P4 tools and BMv2 are installed"""
        try:
            # Check for P4 compiler
            if not self.p4c_path:
                logger.warning("P4C compiler not found. P4 switches will not be available.")
                return False

            # Check for simple_switch (optional for basic functionality)
            if not self.simple_switch_path:
                logger.warning("simple_switch not found. P4Runtime features will be limited.")
                # Don't return False here, we can still compile P4 programs

            # Create necessary directories
            self.p4_programs_dir.mkdir(exist_ok=True)
            self.compiled_programs_dir.mkdir(exist_ok=True)

            return True
        except Exception as e:
            logger.error(f"Error checking P4 installation: {e}")
            return False

    def _find_p4c_compiler(self) -> Optional[str]:
        """Find P4 compiler executable"""
        possible_paths = [
            '/usr/local/bin/p4c',
            '/usr/bin/p4c',
            '/usr/local/bin/p4c-bm2-ss',
            '/usr/bin/p4c-bm2-ss'
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # Try to find in PATH
        try:
            result = subprocess.run(['which', 'p4c'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass

        return None

    def _find_simple_switch(self) -> Optional[str]:
        """Find simple_switch executable"""
        possible_paths = [
            '/usr/local/bin/simple_switch',
            '/usr/bin/simple_switch',
            '/usr/local/bin/simple_switch_grpc'
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # Try to find in PATH
        try:
            result = subprocess.run(['which', 'simple_switch'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass

        return None

    def _install_p4_tools(self) -> bool:
        """Install P4 development tools"""
        try:
            logger.info("Installing P4 development tools...")

            # Update package list
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)

            # Install dependencies
            deps = ['git', 'cmake', 'libgmp-dev', 'libboost-dev', 'libboost-iostreams-dev',
                   'libboost-graph-dev', 'libboost-filesystem-dev', 'python3-dev', 'autoconf',
                   'libtool', 'pkg-config', 'flex', 'bison', 'libfl-dev', 'zlib1g-dev']

            subprocess.run(['sudo', 'apt-get', 'install', '-y'] + deps, check=True)

            # Clone and build P4C
            p4c_dir = Path("/tmp/p4c")
            if not p4c_dir.exists():
                subprocess.run(['git', 'clone', 'https://github.com/p4lang/p4c.git', str(p4c_dir)], check=True)

            os.chdir(p4c_dir)
            p4c_dir.joinpath('build').mkdir(exist_ok=True)
            os.chdir(p4c_dir / 'build')

            subprocess.run(['cmake', '..', '-DCMAKE_BUILD_TYPE=Release'], check=True)
            subprocess.run(['make', '-j$(nproc)'], check=True)
            subprocess.run(['sudo', 'make', 'install'], check=True)

            logger.info("P4C compiler installed successfully")
            return True
        except Exception as e:
            logger.error(f"Error installing P4 tools: {e}")
            return False

    def _install_bmv2(self) -> bool:
        """Install behavioral model v2"""
        try:
            logger.info("Installing BMv2...")

            # Install dependencies
            deps = ['libgmp-dev', 'libboost-dev', 'libboost-iostreams-dev', 'libboost-graph-dev',
                   'libboost-filesystem-dev', 'python3-dev', 'autoconf', 'libtool', 'pkg-config']

            subprocess.run(['sudo', 'apt-get', 'install', '-y'] + deps, check=True)

            # Clone and build BMv2
            bmv2_dir = Path("/tmp/behavioral-model")
            if not bmv2_dir.exists():
                subprocess.run(['git', 'clone', 'https://github.com/p4lang/behavioral-model.git', str(bmv2_dir)], check=True)

            os.chdir(bmv2_dir)
            bmv2_dir.joinpath('build').mkdir(exist_ok=True)
            os.chdir(bmv2_dir / 'build')

            subprocess.run(['../configure'], check=True)
            subprocess.run(['make', '-j$(nproc)'], check=True)
            subprocess.run(['sudo', 'make', 'install'], check=True)

            # Install Python bindings
            os.chdir(bmv2_dir)
            subprocess.run(['sudo', 'pip3', 'install', '-e', '.'], check=True)

            logger.info("BMv2 installed successfully")
            return True
        except Exception as e:
            logger.error(f"Error installing BMv2: {e}")
            return False

    def _install_p4runtime_bindings(self) -> bool:
        """Install P4Runtime Python bindings"""
        try:
            logger.info("Installing P4Runtime Python bindings...")

            # Install gRPC and protobuf
            subprocess.run(['sudo', 'pip3', 'install', 'grpcio', 'protobuf'], check=True)

            # Install p4runtime-shell
            subprocess.run(['sudo', 'pip3', 'install', 'p4runtime-shell'], check=True)

            logger.info("P4Runtime bindings installed successfully")
            return True
        except Exception as e:
            logger.error(f"Error installing P4Runtime bindings: {e}")
            return False

    def create_p4_program(self, program_name: str, p4_code: str) -> bool:
        """Create a P4 program file"""
        try:
            program_file = self.p4_programs_dir / f"{program_name}.p4"
            with open(program_file, 'w') as f:
                f.write(p4_code)

            logger.info(f"P4 program {program_name} created at {program_file}")
            return True
        except Exception as e:
            logger.error(f"Error creating P4 program: {e}")
            return False

    def compile_p4_program(self, program_name: str) -> Tuple[bool, Optional[str]]:
        """Compile P4 program to JSON"""
        try:
            if not self.p4c_path:
                return False, "P4C compiler not found"

            program_file = self.p4_programs_dir / f"{program_name}.p4"
            if not program_file.exists():
                return False, f"P4 program {program_name} not found"

            output_file = self.compiled_programs_dir / f"{program_name}.json"

            cmd = [
                self.p4c_path,
                '--target', 'bmv2',
                '--arch', 'v1model',
                '--std', 'p4-16',
                '-o', str(self.compiled_programs_dir),
                str(program_file)
            ]

            logger.info(f"Compiling P4 program: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"P4 program {program_name} compiled successfully")
                return True, str(output_file)
            else:
                logger.error(f"P4 compilation failed: {result.stderr}")
                return False, result.stderr

        except Exception as e:
            logger.error(f"Error compiling P4 program: {e}")
            return False, str(e)

    def create_switch(self, switch_id: str, program_name: str = None, **kwargs) -> Any:
        """Create a P4 switch instance"""
        try:
            # Check if P4 tools are available
            if not self.check_installation():
                logger.warning(f"P4 tools not available, cannot create P4 switch {switch_id}")
                return None

            if not program_name:
                program_name = "basic_forwarding"

            # Ensure directories exist
            self.p4_programs_dir.mkdir(exist_ok=True)
            self.compiled_programs_dir.mkdir(exist_ok=True)

            # Copy template if program doesn't exist
            program_file = self.p4_programs_dir / f"{program_name}.p4"
            if not program_file.exists():
                template_file = self.templates_dir / f"{program_name}.p4"
                if template_file.exists():
                    import shutil
                    shutil.copy2(template_file, program_file)
                    logger.info(f"Copied P4 template {program_name}.p4 to programs directory")
                else:
                    # Create basic forwarding program if template doesn't exist
                    self._create_basic_forwarding_program(program_name)

            # Compile the program
            success, compile_result = self.compile_p4_program(program_name)
            if not success:
                logger.error(f"Failed to compile P4 program: {compile_result}")
                return None

            json_file = compile_result
            self.current_program = program_name

            logger.info(f"P4 switch {switch_id} created with program {program_name}")
            return switch_id

        except Exception as e:
            logger.error(f"Error creating P4 switch: {e}")
            return None

    def _create_basic_forwarding_program(self, program_name: str):
        """Create a basic L2 forwarding P4 program"""
        basic_forwarding_p4 = '''/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;
const bit<16> TYPE_ARP = 0x806;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header arp_t {
    bit<16> htype;
    bit<16> ptype;
    bit<8>  hlen;
    bit<8>  plen;
    bit<16> oper;
    macAddr_t sha;
    ip4Addr_t spa;
    macAddr_t tha;
    ip4Addr_t tpa;
}

struct metadata {
    /* empty */
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
    arp_t      arp;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            TYPE_ARP: parse_arp;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept;
    }

    state parse_arp {
        packet.extract(hdr.arp);
        transition accept;
    }
}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action mac_learn() {
        // No-op for now
    }

    action forward(bit<9> port) {
        standard_metadata.egress_spec = port;
    }

    table mac_table {
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
        if (hdr.ethernet.isValid()) {
            mac_table.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.arp);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
'''

        self.create_p4_program(program_name, basic_forwarding_p4)

    def start_p4_switch(self, switch_id: str, thrift_port: int = 9090,
                       grpc_port: int = 50051, **kwargs) -> bool:
        """Start the P4 switch process"""
        if not self.current_program:
            logger.error("No P4 program loaded")
            return False

        json_file = self.compiled_programs_dir / f"{self.current_program}.json"
        if not json_file.exists():
            logger.error(f"Compiled P4 program not found: {json_file}")
            return False

        cmd = [
            self.simple_switch_path,
            '--device-id', '1',
            '--thrift-port', str(thrift_port),
            '--log-level', 'info',
            str(json_file)
        ]

        # Add interfaces
        for i, interface in enumerate(kwargs.get('interfaces', [])):
            cmd.extend(['-i', f"{i}@{interface}"])

        logger.info(f"Starting P4 switch with command: {' '.join(cmd)}")

        env = os.environ.copy()
        env['P4RUNTIME_ENDPOINT'] = f"localhost:{grpc_port}"

        return self.start_switch_process(cmd, env)

    def add_table_entry(self, table_name: str, match_fields: Dict[str, Any],
                       action_name: str, action_params: Dict[str, Any] = None) -> bool:
        """Add an entry to a P4 table"""
        try:
            if action_params is None:
                action_params = {}

            entry = {
                'table': table_name,
                'match': match_fields,
                'action': action_name,
                'action_params': action_params
            }

            # Store the entry (in a real implementation, this would use P4Runtime)
            if table_name not in self.table_entries:
                self.table_entries[table_name] = []

            self.table_entries[table_name].append(entry)

            logger.info(f"Added table entry to {table_name}: {entry}")
            return True

        except Exception as e:
            logger.error(f"Error adding table entry: {e}")
            return False

    def remove_table_entry(self, table_name: str, entry_index: int) -> bool:
        """Remove an entry from a P4 table"""
        try:
            if table_name in self.table_entries and 0 <= entry_index < len(self.table_entries[table_name]):
                removed_entry = self.table_entries[table_name].pop(entry_index)
                logger.info(f"Removed table entry from {table_name}: {removed_entry}")
                return True
            else:
                logger.error(f"Invalid table entry index: {entry_index}")
                return False
        except Exception as e:
            logger.error(f"Error removing table entry: {e}")
            return False

    def get_table_entries(self, table_name: str = None) -> Dict[str, List[Dict]]:
        """Get table entries"""
        if table_name:
            return {table_name: self.table_entries.get(table_name, [])}
        else:
            return self.table_entries.copy()

    def get_switch_stats(self) -> Dict[str, Any]:
        """Get P4 switch statistics"""
        stats = {
            'current_program': self.current_program,
            'compiled_programs': list(self.compiled_programs_dir.glob("*.json")),
            'table_count': len(self.table_entries),
            'total_entries': sum(len(entries) for entries in self.table_entries.values()),
            'tables': {}
        }

        # Add table details
        for table_name, entries in self.table_entries.items():
            stats['tables'][table_name] = {
                'entry_count': len(entries),
                'entries': entries
            }

        return stats

    def get_bridge_status(self) -> Dict[str, Any]:
        """Get P4 switch status"""
        if not self.is_running:
            return {'status': 'stopped'}

        return {
            'status': 'running',
            'program': self.current_program,
            'table_entries': len(self.table_entries),
            'interfaces': list(self.switch_ports.keys())
        }

    def create_advanced_program(self, program_name: str, program_type: str = "l2_forwarding") -> str:
        """Create advanced P4 programs from templates"""
        try:
            template_file = self.templates_dir / f"{program_type}.p4"
            if template_file.exists():
                with open(template_file, 'r') as f:
                    template_content = f.read()

                # Customize the template if needed
                customized_content = self._customize_template(template_content, program_name)

                self.create_p4_program(program_name, customized_content)
                return program_name
            else:
                logger.error(f"Template {program_type}.p4 not found")
                return self._create_basic_forwarding_program(program_name)
        except Exception as e:
            logger.error(f"Error creating program from template: {e}")
            return self._create_basic_forwarding_program(program_name)

    def _customize_template(self, template_content: str, program_name: str) -> str:
        """Customize template content with program-specific information"""
        # For now, just return the template as-is
        # In the future, this could replace placeholders with actual values
        return template_content

    def _create_l3_forwarding_program(self, program_name: str) -> str:
        """Create L3 forwarding P4 program"""
        l3_program = '''/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;
const bit<16> TYPE_ARP = 0x806;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

struct metadata {
    bit<9> nhop_ipv4;
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept;
    }
}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {
        verify_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action set_nhop(bit<9> port) {
        meta.nhop_ipv4 = port;
    }

    action ipv4_forward(bit<48> dstAddr, bit<9> port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            set_nhop;
            drop;
        }
        size = 1024;
        default_action = drop();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            ipv4_lpm.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
'''
        self.create_p4_program(program_name, l3_program)
        return program_name

    def _create_l2_forwarding_program(self, program_name: str) -> str:
        """Create enhanced L2 forwarding P4 program"""
        # Use the basic forwarding program but with enhancements
        enhanced_l2 = '''/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;
const bit<16> TYPE_ARP = 0x806;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

struct metadata {
    bit<1> is_multicast;
    bit<9> ingress_port;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        meta.ingress_port = standard_metadata.ingress_port;
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action flood() {
        standard_metadata.mcast_grp = 1;
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
            flood;
        }
        size = 1024;
        default_action = flood();
    }

    table smac {
        key = {
            hdr.ethernet.srcAddr: exact;
        }
        actions = {
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    apply {
        // Learn source MAC
        smac.apply();

        // Forward based on destination MAC
        dmac.apply();

        // Handle broadcasts
        if (hdr.ethernet.dstAddr == 48w0xFFFFFFFFFFFF) {
            flood();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
'''
        self.create_p4_program(program_name, enhanced_l2)
        return program_name

    def _create_load_balancer_program(self, program_name: str) -> str:
        """Create load balancer P4 program"""
        lb_program = '''/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept;
    }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action set_server(bit<9> port, bit<48> dmac) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.dstAddr = dmac;
    }

    table load_balancer {
        key = {
            hdr.ipv4.dstAddr: exact;
        }
        actions = {
            set_server;
            drop;
        }
        size = 1024;
        default_action = drop();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            load_balancer.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
'''
        self.create_p4_program(program_name, lb_program)
        return program_name

    def _create_firewall_program(self, program_name: str) -> str:
        """Create firewall P4 program"""
        fw_program = '''/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept;
    }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action allow() {
        // Packet is allowed, continue processing
    }

    table firewall_rules {
        key = {
            hdr.ipv4.srcAddr: exact;
            hdr.ipv4.dstAddr: exact;
            hdr.ipv4.protocol: exact;
        }
        actions = {
            allow;
            drop;
        }
        size = 1024;
        default_action = allow();  // Default allow policy
    }

    apply {
        if (hdr.ipv4.isValid()) {
            firewall_rules.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
'''
        self.create_p4_program(program_name, fw_program)
        return program_name
