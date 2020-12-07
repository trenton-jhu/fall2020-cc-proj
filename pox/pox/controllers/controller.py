import logging
from struct import pack
from zlib import crc32

from pox.core import core
from pox.lib.util import dpidToStr
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.udp import udp
from pox.lib.packet.tcp import tcp

from src.mn import topos

from mininet.util import makeNumeric

from src.loadbalancerouting import HashedMode, RoundRobinMode, RandomMode

MISS_SEND_LEN = 2000
IDLE_TIMEOUT = 10

DEF_ROUTING = 'hashed'
ROUTING = {
    'rr': RoundRobinMode,
    'random': RandomMode,
    'hashed': HashedMode
}


class Switch(object):
    def __init__(self):
        self.connection, self.ports, self.dpid = None, None, None
        self._listeners = None

    def __repr__(self):
        return dpidToStr(self.dpid)

    def attach_controller(self):
        if self.connection is not None:
            self.connection.removeListeners(self._listeners)
            self.connection = None
            self._listeners = None

    def distach_controller(self, connection):
        if self.dpid is None:
            self.dpid = connection.dpid
        if self.ports is None:
            self.ports = connection.features.ports
        self.attach_controller()
        self.connection = connection
        self._listeners = connection.addListeners(self)

    def send_packet(self, outport, data=None):
        if self.connection is None:
            return
        msg = of.ofp_packet_out(in_port=of.OFPP_NONE, data=data)
        msg.actions.append(of.ofp_action_output(port=outport))
        self.connection.send(msg)

    def install(self, port, match, buf=None, idle_timeout=0, hard_timeout=0, priority=of.OFP_DEFAULT_PRIORITY):
        msg = of.ofp_flow_mod()
        msg.match = match
        msg.idle_timeout = idle_timeout
        msg.hard_timeout = hard_timeout
        msg.priority = priority
        msg.actions.append(of.ofp_action_output(port=port))
        msg.buffer_id = buf
        self.connection.send(msg)

    def install_multiple(self, actions, match, buf=None, idle_timeout=0, hard_timeout=0, priority=of.OFP_DEFAULT_PRIORITY):
        msg = of.ofp_flow_mod()
        msg.match = match
        msg.idle_timeout = idle_timeout
        msg.hard_timeout = hard_timeout
        msg.priority = priority
        for action in actions:
            msg.actions.append(action)
        msg.buffer_id = buf
        self.connection.send(msg)

    def _handle_ConnectionDown(self, event):
        self.attach_controller()
        pass


class Controller(object):
    def __init__(self, topology, routing):
        self.switches = {}
        self.topo = topology
        self.router = routing
        self.macTable = {}
        self.all_switches_up = False
        core.openflow.addListeners(self, priority=0)

    def _hash(self, packet):
        hash_input = [0] * 5
        if isinstance(packet.next, ipv4):
            ip = packet.next
            hash_input[0] = ip.srcip.toUnsigned()
            hash_input[1] = ip.dstip.toUnsigned()
            hash_input[2] = ip.protocol
            if isinstance(ip.next, tcp) or isinstance(ip.next, udp):
                l4 = ip.next
                hash_input[3] = l4.srcport
                hash_input[4] = l4.dstport
                return crc32(pack('LLHHH', *hash_input))
        return 0

    def _install_reactive_path(self, event, out_dpid, final_out_port, packet):
        route = self.router.get_route(
            self.topo.id_gen(dpid=event.dpid).name_str(),
            self.topo.id_gen(dpid=out_dpid).name_str(),
            self._hash(packet),
            False
        )
        if route is None:
            return
        match = of.ofp_match.from_packet(packet)
        for i, node in enumerate(route):
            node_dpid = self.topo.id_gen(name=node).dpid
            if i < len(route) - 1:
                next_node = route[i + 1]
                out_port, next_in_port = self.topo.port(node, next_node)
            else:
                out_port = final_out_port
            self.switches[node_dpid].install(out_port, match, idle_timeout=IDLE_TIMEOUT)

    def _handle_packet_reactive(self, event):
        packet = event.parsed
        dpid = event.dpid
        in_port = event.port

        self.macTable[packet.src] = (dpid, in_port)

        if packet.dst in self.macTable:
            out_dpid, out_port = self.macTable[packet.dst]
            self._install_reactive_path(event, out_dpid, out_port, packet)
            self.switches[out_dpid].send_packet(out_port, event.data)
        else:
            dpid = event.dpid
            in_port = event.port
            topology = self.topo

            for switch in [self.topo.id_gen(name=a).dpid for a in topology.layer_nodes(topology.LAYER_EDGE)]:
                ports = []
                switch_name = topology.id_gen(dpid=switch).name_str()
                for host in topology.down_nodes(switch_name):
                    sw_port, host_port = topology.port(switch_name, host)
                    if switch != dpid or (switch == dpid and in_port != sw_port):
                        ports.append(sw_port)
                for port in ports:
                    self.switches[switch].send_packet(port, event.data)

    def _handle_PacketIn(self, event):
        return self._handle_packet_reactive(event) if self.all_switches_up else None

    def _handle_ConnectionUp(self, event):
        switch = self.switches.get(event.dpid)
        if self.topo.id_gen(dpid=event.dpid).name_str() not in self.topo.switches():
            return
        if switch is None:
            switch = Switch()
            self.switches[event.dpid] = switch
        switch.distach_controller(event.connection)
        switch.connection.send(of.ofp_set_config(miss_send_len=MISS_SEND_LEN))
        if len(self.switches) == len(self.topo.switches()):
            self.all_switches_up = True


def launch(topo, routing=None):
    topology_args = topo.split(',')
    topology_name, topo_params = topology_args[0], topology_args[1:]
    topology = topos[topology_name](
        *[makeNumeric(s) for s in [s for s in topo_params if '=' not in s]],
        **{k:makeNumeric(v) for k, v in [p.split('=') for p in topo_params if '=' in p]}
    )
    core.registerNew(Controller, topology, ROUTING[routing](topology))
