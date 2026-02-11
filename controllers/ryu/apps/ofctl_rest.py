"""
OpenFlow Control REST API for Ryu
Provides REST endpoints for flow management
"""

from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import ofctl_v1_3
import json


class StatsController(ControllerBase):
    """REST API controller for OpenFlow statistics"""

    def __init__(self, req, link, data, **config):
        super(StatsController, self).__init__(req, link, data, **config)
        self.app = data['app']

    @route('stats', '/stats/switches', methods=['GET'])
    def list_switches(self, req, **kwargs):
        """Get list of all connected switches"""
        body = json.dumps([dpid for dpid in self.app.datapaths.keys()])
        return body

    @route('stats', '/stats/flow/{dpid}', methods=['GET'])
    def get_flows(self, req, **kwargs):
        """Get flow entries for a switch"""
        dpid = int(kwargs['dpid'])
        
        if dpid not in self.app.datapaths:
            return json.dumps({'error': 'Switch not found'})
        
        dp = self.app.datapaths[dpid]
        flows = ofctl_v1_3.get_flow_stats(dp, self.app.waiters)
        
        return json.dumps(flows)


class RestStatsApi(app_manager.RyuApp):
    """REST API application for OpenFlow stats"""
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(RestStatsApi, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.waiters = {}
        
        wsgi = kwargs['wsgi']
        wsgi.register(StatsController, {'app': self})

    @set_ev_cls(ofp_event.EventOFPStateChange)
    def state_change_handler(self, ev):
        """Handle datapath state changes"""
        datapath = ev.datapath
        if ev.state == 1:  # MAIN_DISPATCHER
            if datapath.id not in self.datapaths:
                self.logger.info('Register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == 0:  # DEAD_DISPATCHER
            if datapath.id in self.datapaths:
                self.logger.info('Unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

