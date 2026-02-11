"""
BGP Protocol Plugin
Implements BGP v4 routing protocol support
"""

import logging
from typing import Dict, Any, List, Optional
from shared.plugins.protocol_plugin import RoutingProtocolPlugin, ProtocolStatus

logger = logging.getLogger(__name__)


class BGPPlugin(RoutingProtocolPlugin):
    """BGP routing protocol plugin"""

    name = "bgp"
    version = "4.0"
    description = "BGP (Border Gateway Protocol) v4"
    supported_devices = ["router"]

    def __init__(self):
        self.active_configs: Dict[str, Dict[str, Any]] = {}

    def configure(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure BGP on a router

        Config parameters:
            - as_number: BGP AS number (required)
            - router_id: BGP router ID (required)
            - neighbors: List of BGP neighbors
            - networks: Networks to advertise
        """
        try:
            validation = self.validate_config(config)
            if not validation['valid']:
                return {
                    'success': False,
                    'message': f"Invalid configuration: {validation['errors']}",
                    'config': None
                }

            as_number = config['as_number']
            router_id = config['router_id']
            neighbors = config.get('neighbors', [])
            networks = config.get('networks', [])

            bgp_config = self._generate_frr_config(as_number, router_id, neighbors, networks)

            self.active_configs[device] = {
                'as_number': as_number,
                'router_id': router_id,
                'neighbors': neighbors,
                'networks': networks,
                'config_text': bgp_config
            }

            logger.info(f"BGP configured on {device} with AS {as_number}")

            return {
                'success': True,
                'message': f"BGP configured successfully on {device}",
                'config': bgp_config
            }

        except Exception as e:
            logger.error(f"Failed to configure BGP on {device}: {e}")
            return {'success': False, 'message': str(e), 'config': None}

    def enable(self, device: str) -> Dict[str, Any]:
        """Enable BGP on a router"""
        try:
            if device not in self.active_configs:
                return {
                    'success': False,
                    'message': f"BGP not configured on {device}",
                    'status': ProtocolStatus.DISABLED
                }

            logger.info(f"Enabling BGP on {device}")
            # Execute via gRPC in production

            return {
                'success': True,
                'message': f"BGP enabled on {device}",
                'status': ProtocolStatus.ENABLED
            }

        except Exception as e:
            logger.error(f"Failed to enable BGP on {device}: {e}")
            return {'success': False, 'message': str(e), 'status': ProtocolStatus.ERROR}

    def disable(self, device: str) -> Dict[str, Any]:
        """Disable BGP on a router"""
        try:
            logger.info(f"Disabling BGP on {device}")

            if device in self.active_configs:
                del self.active_configs[device]

            return {'success': True, 'message': f"BGP disabled on {device}"}

        except Exception as e:
            logger.error(f"Failed to disable BGP on {device}: {e}")
            return {'success': False, 'message': str(e)}

    def get_status(self, device: str) -> Dict[str, Any]:
        """Get BGP status"""
        if device not in self.active_configs:
            return {
                'status': ProtocolStatus.DISABLED,
                'details': {},
                'version': self.version,
                'config': {}
            }

        config = self.active_configs[device]
        return {
            'status': ProtocolStatus.ENABLED,
            'details': {
                'as_number': config['as_number'],
                'router_id': config['router_id'],
                'neighbors': config['neighbors'],
                'networks': config['networks']
            },
            'version': self.version,
            'config': config
        }

    def switch_from(self, device: str, to_protocol: str, preserve_config: bool = True) -> Dict[str, Any]:
        """Switch from BGP to another protocol"""
        preserved_state = {}
        if preserve_config:
            preserved_state = {
                'routing_table': self.get_routing_table(device),
                'as_number': self.active_configs.get(device, {}).get('as_number'),
                'router_id': self.active_configs.get(device, {}).get('router_id')
            }

        self.disable(device)
        return {'success': True, 'message': 'Switched from BGP', 'preserved_state': preserved_state}

    def switch_to(self, device: str, from_protocol: str, preserved_state: Optional[Dict] = None) -> Dict[str, Any]:
        """Switch to BGP from another protocol"""
        config = preserved_state if preserved_state else self.get_default_config()

        result = self.configure(device, config)
        if result['success']:
            self.enable(device)

        return {'success': result['success'], 'message': 'Switched to BGP', 'status': ProtocolStatus.ENABLED}

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate BGP configuration"""
        errors = []

        if 'as_number' not in config:
            errors.append("as_number is required")
        elif not (1 <= config['as_number'] <= 4294967295):
            errors.append("as_number must be between 1 and 4294967295")

        if 'router_id' not in config:
            errors.append("router_id is required")

        return {'valid': len(errors) == 0, 'errors': errors, 'warnings': []}

    def get_default_config(self) -> Dict[str, Any]:
        """Get default BGP configuration"""
        return {
            'as_number': 65000,
            'router_id': '1.1.1.1',
            'neighbors': [],
            'networks': []
        }

    def get_routing_table(self, device: str) -> List[Dict[str, Any]]:
        """Get BGP routing table"""
        return []

    def get_neighbors(self, device: str) -> List[Dict[str, Any]]:
        """Get BGP neighbors"""
        return []

    def get_metrics(self, device: str) -> Dict[str, Any]:
        """Get BGP metrics"""
        return {'neighbors_count': 0, 'prefixes_count': 0, 'paths_count': 0}

    def _generate_frr_config(self, as_number: int, router_id: str,
                             neighbors: List[Dict], networks: List[str]) -> str:
        """Generate FRRouting BGP configuration"""
        config_lines = [
            "!",
            f"router bgp {as_number}",
            f"  bgp router-id {router_id}",
        ]

        for neighbor in neighbors:
            neighbor_ip = neighbor['ip']
            remote_as = neighbor['remote_as']
            config_lines.append(f"  neighbor {neighbor_ip} remote-as {remote_as}")

        for network in networks:
            config_lines.append(f"  network {network}")

        config_lines.append("!")
        return "\n".join(config_lines)
