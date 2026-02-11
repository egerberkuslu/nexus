"""
Link Handler - Manages network links in the emulation
Handles creation, deletion, and runtime modification of links
"""

from __future__ import annotations

import logging
from mininet.link import TCLink, Intf
import emulation_pb2

logger = logging.getLogger(__name__)


class LinkHandler:
    """Handles all link-related operations"""

    def __init__(self, emulation_manager):
        self.emulation_manager = emulation_manager

    def add_link(self, node1, node2, port1, port2, params):
        """Add a link between two devices"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            net = self.emulation_manager.net

            # Get nodes
            device1 = self.emulation_manager.get_device(node1)
            device2 = self.emulation_manager.get_device(node2)

            if not device1 or not device2:
                raise ValueError(f"One or both devices not found: {node1}, {node2}")

            # Build link parameters
            link_params = {}
            if params:
                if params.bandwidth > 0:
                    link_params['bw'] = params.bandwidth
                if params.delay > 0:
                    link_params['delay'] = f'{params.delay}ms'
                if params.loss > 0:
                    link_params['loss'] = params.loss
                if params.max_queue_size > 0:
                    link_params['max_queue_size'] = params.max_queue_size
                if params.use_htb:
                    link_params['use_htb'] = params.use_htb

            # Add link
            link = net.addLink(
                device1,
                device2,
                cls=TCLink,
                **link_params
            )

            # Store link reference
            link_key = f"{node1}-{node2}"
            self.emulation_manager.links[link_key] = {
                'node1': node1,
                'node2': node2,
                'port1': port1 or link.intf1.name,
                'port2': port2 or link.intf2.name,
                'link': link,
                'params': params
            }

            logger.info(f"Added link: {node1} <-> {node2}")

            return emulation_pb2.Link(
                node1=node1,
                node2=node2,
                port1=link.intf1.name,
                port2=link.intf2.name,
                params=params,
                status='up'
            )

        except Exception as e:
            logger.error(f"Failed to add link {node1}-{node2}: {e}")
            raise

    def remove_link(self, node1, node2):
        """Remove a link between two devices"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            link_key = f"{node1}-{node2}"
            reverse_key = f"{node2}-{node1}"

            # Check both directions
            if link_key not in self.emulation_manager.links and reverse_key not in self.emulation_manager.links:
                raise ValueError(f"Link not found: {node1}-{node2}")

            # Get the actual key
            actual_key = link_key if link_key in self.emulation_manager.links else reverse_key
            link_info = self.emulation_manager.links[actual_key]

            net = self.emulation_manager.net
            link = link_info['link']

            # Delete link
            net.delLink(link)

            # Remove from tracking
            del self.emulation_manager.links[actual_key]

            logger.info(f"Removed link: {node1} <-> {node2}")

            return {'success': True, 'message': f"Link removed: {node1} <-> {node2}"}

        except Exception as e:
            logger.error(f"Failed to remove link {node1}-{node2}: {e}")
            return {'success': False, 'message': str(e)}

    def update_link(self, node1, node2, params):
        """Update link parameters at runtime"""
        try:
            logger.info(f"UpdateLink called with node1: '{node1}', node2: '{node2}'")
            link_key = f"{node1}-{node2}"
            reverse_key = f"{node2}-{node1}"

            if link_key not in self.emulation_manager.links and reverse_key not in self.emulation_manager.links:
                raise ValueError(f"Link not found: {node1}-{node2}")

            actual_key = link_key if link_key in self.emulation_manager.links else reverse_key
            link_info = self.emulation_manager.links[actual_key]
            link = link_info['link']

            # Update bandwidth
            if params.bandwidth >= 0:
                intf1 = link.intf1
                intf2 = link.intf2
                if intf1:
                    intf1.config(bw=params.bandwidth)
                if intf2:
                    intf2.config(bw=params.bandwidth)

            # Update delay
            if params.delay >= 0:
                intf1 = link.intf1
                intf2 = link.intf2
                if intf1:
                    intf1.config(delay=f'{params.delay}ms')
                if intf2:
                    intf2.config(delay=f'{params.delay}ms')

            # Update loss
            if params.loss >= 0:
                intf1 = link.intf1
                intf2 = link.intf2
                if intf1:
                    intf1.config(loss=params.loss)
                if intf2:
                    intf2.config(loss=params.loss)

            # Update stored params
            link_info['params'] = params

            logger.info(f"Updated link: {node1} <-> {node2}")

            return emulation_pb2.Link(
                node1=node1,
                node2=node2,
                port1=link.intf1.name,
                port2=link.intf2.name,
                params=params,
                status='up'
            )

        except Exception as e:
            logger.error(f"Failed to update link {node1}-{node2}: {e}")
            raise

    def get_link(self, node1, node2):
        """Get link information"""
        link_key = f"{node1}-{node2}"
        reverse_key = f"{node2}-{node1}"

        if link_key not in self.emulation_manager.links and reverse_key not in self.emulation_manager.links:
            raise ValueError(f"Link not found: {node1}-{node2}")

        actual_key = link_key if link_key in self.emulation_manager.links else reverse_key
        link_info = self.emulation_manager.links[actual_key]
        link = link_info['link']

        port1 = link_info.get('port1') or getattr(getattr(link, "intf1", None), "name", "") or ""
        port2 = link_info.get('port2') or getattr(getattr(link, "intf2", None), "name", "") or ""
        params = link_info.get('params', None)

        return emulation_pb2.Link(
            node1=link_info['node1'],
            node2=link_info['node2'],
            port1=port1,
            port2=port2,
            params=params,
            status='up' if link.intf1.isUp() and link.intf2.isUp() else 'down'
        )

    def list_links(self, node=None):
        """List all links, optionally filtered by node"""
        links = []

        for link_key, link_info in self.emulation_manager.links.items():
            if node and node not in [link_info['node1'], link_info['node2']]:
                continue

            link = link_info['link']
            port1 = link_info.get('port1') or getattr(getattr(link, "intf1", None), "name", "") or ""
            port2 = link_info.get('port2') or getattr(getattr(link, "intf2", None), "name", "") or ""
            params = link_info.get('params', None)

            links.append(emulation_pb2.Link(
                node1=link_info['node1'],
                node2=link_info['node2'],
                port1=port1,
                port2=port2,
                params=params,
                status='up' if link.intf1.isUp() and link.intf2.isUp() else 'down'
            ))

        return links
