"""
REST API for Topology Discovery
Provides REST endpoints to query network topology
"""

import json
from os_ken.app.wsgi import ControllerBase, WSGIApplication, route
from os_ken.base import app_manager
from os_ken.topology import event
from os_ken.topology.api import get_switch, get_link
from os_ken.controller.handler import set_ev_cls


class RestTopologyAPI(app_manager.RyuApp):
    """
    REST API application for topology information
    """
    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(RestTopologyAPI, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(TopologyController, {'app': self})
        
        self.switches = []
        self.links = []

    @set_ev_cls(event.EventSwitchEnter)
    def get_switches(self, ev):
        """Handle switch enter events"""
        self.switches = get_switch(self, None)
        self.logger.info("Switch entered: %s switches total", len(self.switches))

    @set_ev_cls(event.EventLinkAdd)
    def get_links(self, ev):
        """Handle link add events"""
        self.links = get_link(self, None)
        self.logger.info("Link added: %s links total", len(self.links))


class TopologyController(ControllerBase):
    """REST controller for topology API"""

    def __init__(self, req, link, data, **config):
        super(TopologyController, self).__init__(req, link, data, **config)
        self.app = data['app']

    @route('topology', '/v1.0/topology/switches', methods=['GET'])
    def list_switches(self, req, **kwargs):
        """
        Get list of all switches
        Returns JSON array of switch information
        """
        switches = get_switch(self.app, None)
        
        result = []
        for switch in switches:
            result.append({
                'dpid': hex(switch.dp.id),
                'ports': [
                    {
                        'port_no': port.port_no,
                        'hw_addr': port.hw_addr,
                        'name': port.name.decode('utf-8') if isinstance(port.name, bytes) else port.name
                    }
                    for port in switch.ports
                ]
            })
        
        return json.dumps(result)

    @route('topology', '/v1.0/topology/links', methods=['GET'])
    def list_links(self, req, **kwargs):
        """
        Get list of all links
        Returns JSON array of link information
        """
        links = get_link(self.app, None)
        
        result = []
        for link in links:
            result.append({
                'src': {
                    'dpid': hex(link.src.dpid),
                    'port_no': link.src.port_no
                },
                'dst': {
                    'dpid': hex(link.dst.dpid),
                    'port_no': link.dst.port_no
                }
            })
        
        return json.dumps(result)

    @route('topology', '/v1.0/topology/summary', methods=['GET'])
    def topology_summary(self, req, **kwargs):
        """
        Get topology summary
        Returns switch and link counts
        """
        switches = get_switch(self.app, None)
        links = get_link(self.app, None)
        
        result = {
            'switch_count': len(switches),
            'link_count': len(links),
            'switches': [hex(s.dp.id) for s in switches]
        }
        
        return json.dumps(result)

