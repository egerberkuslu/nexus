"""
Flow Manager
Handles OpenFlow flow table management and flow statistics
"""

import subprocess
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from utils.logger import setup_logger

logger = setup_logger(__name__)


class FlowManager:
    """Manages OpenFlow flow tables and flow statistics"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.flow_cache = {}  # Cache for flow statistics
        self.last_update = None

    def get_flow_stats(self, net, switch_name: str = None) -> Dict[str, Any]:
        """Get flow statistics from switches"""
        try:
            flow_stats = {
                'total_flows': 0,
                'flows_by_switch': {},
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_packets': 0,
                    'total_bytes': 0,
                    'active_flows': 0
                }
            }

            switches_to_check = []
            if switch_name:
                # Check specific switch
                for switch in net.switches:
                    if switch.name == switch_name:
                        switches_to_check = [switch]
                        break
            else:
                # Check all switches
                switches_to_check = net.switches

            for switch in switches_to_check:
                try:
                    switch_flows = self._get_switch_flows(switch)
                    flow_stats['flows_by_switch'][switch.name] = switch_flows
                    flow_stats['total_flows'] += switch_flows.get('count', 0)

                    # Update summary
                    for flow in switch_flows.get('flows', []):
                        packets = self._parse_flow_counter(flow.get('n_packets', '0'))
                        bytes_val = self._parse_flow_counter(flow.get('n_bytes', '0'))

                        flow_stats['summary']['total_packets'] += packets
                        flow_stats['summary']['total_bytes'] += bytes_val
                        flow_stats['summary']['active_flows'] += 1

                except Exception as e:
                    self.logger.warning(f"Error getting flows for switch {switch.name}: {e}")
                    flow_stats['flows_by_switch'][switch.name] = {
                        'count': 0,
                        'flows': [],
                        'error': str(e)
                    }

            # Cache the results
            self.flow_cache = flow_stats
            self.last_update = datetime.now()

            return flow_stats

        except Exception as e:
            self.logger.error(f"Error getting flow stats: {e}")
            return {'error': str(e)}

    def _get_switch_flows(self, switch) -> Dict[str, Any]:
        """Get flows from a specific switch"""
        try:
            flows = []
            total_count = 0

            # Try different methods to get flows
            if hasattr(switch, 'dpctl') and switch.dpctl:
                # Use dpctl if available
                flows = self._get_flows_via_dpctl(switch)
            elif hasattr(switch, 'vsctl'):
                # Use ovs-vsctl if available
                flows = self._get_flows_via_ovs(switch.name)
            else:
                # Fallback method
                flows = self._get_flows_via_command(switch.name)

            return {
                'count': len(flows),
                'flows': flows
            }

        except Exception as e:
            self.logger.warning(f"Error getting flows from switch {switch.name}: {e}")
            return {
                'count': 0,
                'flows': [],
                'error': str(e)
            }

    def _get_flows_via_dpctl(self, switch) -> List[Dict[str, Any]]:
        """Get flows using dpctl"""
        try:
            # This would use the switch's dpctl interface
            # For now, return placeholder
            return []
        except Exception as e:
            self.logger.warning(f"Error getting flows via dpctl: {e}")
            return []

    def _get_flows_via_ovs(self, switch_name: str) -> List[Dict[str, Any]]:
        """Get flows using ovs-ofctl"""
        try:
            result = subprocess.run(
                ['ovs-ofctl', 'dump-flows', switch_name],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                return self._parse_ovs_flows(result.stdout)
            else:
                self.logger.warning(f"ovs-ofctl failed for {switch_name}: {result.stderr}")
                return []

        except Exception as e:
            self.logger.warning(f"Error getting flows via ovs-ofctl: {e}")
            return []

    def _get_flows_via_command(self, switch_name: str) -> List[Dict[str, Any]]:
        """Fallback method to get flows"""
        try:
            # Try ovs-ofctl as fallback
            return self._get_flows_via_ovs(switch_name)
        except Exception as e:
            self.logger.warning(f"Fallback flow retrieval failed: {e}")
            return []

    def _parse_ovs_flows(self, output: str) -> List[Dict[str, Any]]:
        """Parse ovs-ofctl dump-flows output"""
        try:
            flows = []
            lines = output.strip().split('\n')

            for line in lines:
                if line.strip() and not line.startswith('NXST_FLOW'):
                    flow = self._parse_flow_line(line)
                    if flow:
                        flows.append(flow)

            return flows

        except Exception as e:
            self.logger.warning(f"Error parsing OVS flows: {e}")
            return []

    def _parse_flow_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single flow line"""
        try:
            # Basic flow parsing
            flow = {}

            # Split by comma and parse key-value pairs
            parts = line.split(',')
            for part in parts:
                part = part.strip()
                if '=' in part:
                    key, value = part.split('=', 1)
                    flow[key.strip()] = value.strip()
                elif part.startswith('actions='):
                    flow['actions'] = part[8:]  # Remove 'actions=' prefix

            # Add parsed counters
            if 'n_packets' in flow:
                flow['packet_count'] = self._parse_flow_counter(flow['n_packets'])
            if 'n_bytes' in flow:
                flow['byte_count'] = self._parse_flow_counter(flow['n_bytes'])

            return flow

        except Exception as e:
            self.logger.warning(f"Error parsing flow line: {e}")
            return None

    def _parse_flow_counter(self, counter_str: str) -> int:
        """Parse flow counter string to integer"""
        try:
            # Remove any non-numeric characters and parse
            clean_str = ''.join(c for c in counter_str if c.isdigit())
            return int(clean_str) if clean_str else 0
        except:
            return 0

    def add_flow(self, switch_name: str, **flow_params) -> bool:
        """Add a flow to a switch"""
        try:
            # Build flow string
            flow_parts = []

            # Add priority if specified
            if 'priority' in flow_params:
                flow_parts.append(f"priority={flow_params['priority']}")

            # Add match fields
            match_fields = ['in_port', 'dl_src', 'dl_dst', 'dl_type', 'nw_src', 'nw_dst', 'tp_src', 'tp_dst']
            for field in match_fields:
                if field in flow_params:
                    flow_parts.append(f"{field}={flow_params[field]}")

            # Add actions
            if 'actions' in flow_params:
                flow_parts.append(f"actions={flow_params['actions']}")

            flow_string = ','.join(flow_parts)

            # Add flow using ovs-ofctl
            result = subprocess.run(
                ['ovs-ofctl', 'add-flow', switch_name, flow_string],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                self.logger.info(f"Flow added to {switch_name}: {flow_string}")
                return True
            else:
                self.logger.error(f"Failed to add flow to {switch_name}: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error adding flow: {e}")
            return False

    def delete_flow(self, switch_name: str, **match_params) -> bool:
        """Delete flows from a switch"""
        try:
            # Build match string
            match_parts = []

            # Add match fields
            for key, value in match_params.items():
                match_parts.append(f"{key}={value}")

            if not match_parts:
                # Delete all flows if no match specified
                match_string = ""
            else:
                match_string = ','.join(match_parts)

            # Delete flows using ovs-ofctl
            cmd = ['ovs-ofctl', 'del-flows', switch_name]
            if match_string:
                cmd.append(match_string)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                self.logger.info(f"Flows deleted from {switch_name}")
                return True
            else:
                self.logger.error(f"Failed to delete flows from {switch_name}: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error deleting flow: {e}")
            return False

    def get_flow_table_summary(self, net) -> Dict[str, Any]:
        """Get a summary of all flow tables"""
        try:
            summary = {
                'total_switches': len(net.switches),
                'total_flows': 0,
                'switches': {},
                'timestamp': datetime.now().isoformat()
            }

            for switch in net.switches:
                switch_stats = self.get_flow_stats(net, switch.name)
                switch_flows = switch_stats.get('flows_by_switch', {}).get(switch.name, {})

                summary['switches'][switch.name] = {
                    'flow_count': switch_flows.get('count', 0),
                    'has_error': 'error' in switch_flows
                }

                summary['total_flows'] += switch_flows.get('count', 0)

            return summary

        except Exception as e:
            self.logger.error(f"Error getting flow table summary: {e}")
            return {'error': str(e)}

    def monitor_flow_changes(self, net, interval: int = 30) -> None:
        """Monitor flow table changes over time"""
        try:
            self.logger.info(f"Starting flow monitoring with {interval}s interval")

            while True:
                current_stats = self.get_flow_stats(net)

                # Compare with previous stats
                if self.flow_cache:
                    changes = self._detect_flow_changes(self.flow_cache, current_stats)
                    if changes:
                        self.logger.info(f"Flow changes detected: {changes}")

                # Wait for next check
                time.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info("Flow monitoring stopped")
        except Exception as e:
            self.logger.error(f"Error in flow monitoring: {e}")

    def _detect_flow_changes(self, old_stats: Dict[str, Any], new_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Detect changes between flow statistics"""
        try:
            changes = {
                'new_flows': 0,
                'removed_flows': 0,
                'switches_changed': []
            }

            old_switches = old_stats.get('flows_by_switch', {})
            new_switches = new_stats.get('flows_by_switch', {})

            for switch_name in set(old_switches.keys()) | set(new_switches.keys()):
                old_count = old_switches.get(switch_name, {}).get('count', 0)
                new_count = new_switches.get(switch_name, {}).get('count', 0)

                if old_count != new_count:
                    changes['switches_changed'].append({
                        'switch': switch_name,
                        'old_count': old_count,
                        'new_count': new_count,
                        'difference': new_count - old_count
                    })

                    if new_count > old_count:
                        changes['new_flows'] += (new_count - old_count)
                    else:
                        changes['removed_flows'] += (old_count - new_count)

            return changes

        except Exception as e:
            self.logger.warning(f"Error detecting flow changes: {e}")
            return {}

    def export_flows(self, net, file_path: str) -> bool:
        """Export all flows to a file"""
        try:
            flow_stats = self.get_flow_stats(net)

            with open(file_path, 'w') as f:
                import json
                json.dump(flow_stats, f, indent=2)

            self.logger.info(f"Flows exported to {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exporting flows: {e}")
            return False

    def get_cached_flow_stats(self) -> Optional[Dict[str, Any]]:
        """Get cached flow statistics"""
        if self.flow_cache and self.last_update:
            # Check if cache is still fresh (less than 5 minutes old)
            if (datetime.now() - self.last_update).total_seconds() < 300:
                return self.flow_cache

        return None
