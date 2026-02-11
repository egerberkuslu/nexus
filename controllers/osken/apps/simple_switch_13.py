"""
Simple OpenFlow 1.3 Learning Switch
Compatible with OS-Ken SDN Controller
"""

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet
from os_ken.lib.packet import ethernet
from os_ken.lib.packet import ether_types


class SimpleSwitch13(app_manager.OSKenApp):
    """
    Simple learning switch implementation for OpenFlow 1.3
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        # MAC address table: {dpid: {mac_address: port}}
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Handle switch features message
        Install table-miss flow entry
        """
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        self.logger.info("Switch connected: DPID=%s", 
                        hex(datapath.id))

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=0):
        """
        Add flow entry to switch
        
        Args:
            datapath: Switch datapath object
            priority: Flow priority
            match: Match criteria
            actions: Actions to apply
            buffer_id: Buffer ID for packet-out
            idle_timeout: Idle timeout in seconds
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, idle_timeout=idle_timeout)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst,
                                    idle_timeout=idle_timeout)
        
        datapath.send_msg(mod)
        
        self.logger.debug("Flow added: priority=%d, match=%s", priority, match)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        Handle packet-in messages
        Learn MAC addresses and forward packets
        """
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # Ignore LLDP packets
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        # Initialize MAC table for this switch
        self.mac_to_port.setdefault(dpid, {})

        # Learn MAC address
        self.mac_to_port[dpid][src] = in_port
        self.logger.debug("Learned: DPID=%s, MAC=%s, Port=%s", 
                         hex(dpid), src, in_port)

        # Determine output port
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Install flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            
            # Verify buffer_id is valid
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id, idle_timeout=300)
                return
            else:
                self.add_flow(datapath, 1, match, actions, idle_timeout=300)

        # Send packet out
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

        self.logger.debug("Packet forwarded: DPID=%s, in_port=%s, out_port=%s", 
                         hex(dpid), in_port, out_port)

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        """
        Handle port status changes
        """
        msg = ev.msg
        reason = msg.reason
        port_no = msg.desc.port_no
        dpid = msg.datapath.id

        ofproto = msg.datapath.ofproto
        if reason == ofproto.OFPPR_ADD:
            self.logger.info("Port added: DPID=%s, Port=%s", hex(dpid), port_no)
        elif reason == ofproto.OFPPR_DELETE:
            self.logger.info("Port deleted: DPID=%s, Port=%s", hex(dpid), port_no)
        elif reason == ofproto.OFPPR_MODIFY:
            self.logger.info("Port modified: DPID=%s, Port=%s", hex(dpid), port_no)
        else:
            self.logger.info("Port status changed: DPID=%s, Port=%s, Reason=%s", 
                           hex(dpid), port_no, reason)

