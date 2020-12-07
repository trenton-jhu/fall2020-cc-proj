#!/usr/bin/env python
import sys

# change these paths as required
sys.path.append('/home/senzen/.local/lib/python3.8/site-packages')
sys.path.append('../mininet')

from mininet.topo import Topo

PORT_BASE = 1


class Host(object):
    def __init__(self, up_total, down_total, up_speed, down_speed, type_str=None):
        self.up_total, self.down_total = up_total, down_total
        self.up_speed, self.down_speed = up_speed, down_speed
        self.type_str = type_str


class Link(object):
    def __init__(self, speed=1.0):
        self.speed = speed


class NodeInfo(object):
    def __init__(self, pod=0, sw=0, host=0, dpid=None, name=None):
        if dpid:
            self.pod = (dpid & 0xff0000) >> 16
            self.sw = (dpid & 0xff00) >> 8
            self.host = (dpid & 0xff)
            self.dpid = dpid
        elif name:
            pod, sw, host = [int(s) for s in name.split('_')]
            self.pod = pod
            self.sw = sw
            self.host = host
            self.dpid = (pod << 16) + (sw << 8) + host
        else:
            self.pod = pod
            self.sw = sw
            self.host = host
            self.dpid = (pod << 16) + (sw << 8) + host

    def __str__(self):
        return "(%i, %i, %i)" % (self.pod, self.sw, self.host)

    def name_str(self):
        return "%i_%i_%i" % (self.pod, self.sw, self.host)

    def mac_str(self):
        return "00:00:00:%02x:%02x:%02x" % (self.pod, self.sw, self.host)

    def ip_str(self):
        return "10.%i.%i.%i" % (self.pod, self.sw, self.host)


class FatTreeTopo(Topo):
    def __init__(self, k=4, speed=1.0):
        self.LAYER_CORE, self.LAYER_AGG, self.LAYER_EDGE, self.LAYER_HOST = 0, 1, 2, 3
        core, agg, edge, host = Host(0, k, None, speed, 'core'), \
                                Host(k // 2, k // 2, speed, speed, 'agg'), \
                                Host(k // 2, k // 2, speed, speed, 'edge'), \
                                Host(1, 0, speed, None, 'host')
        node_specs, edge_specs = [core, agg, edge, host], [Link(speed)] * 3
        super(FatTreeTopo, self).__init__(node_specs, edge_specs)

        self.k, self.numPods, self.aggPerPod = k, k, k // 2
        self.id_gen = NodeInfo
        self.all_hosts = []
        self.port_handler = {
            (self.LAYER_HOST, self.LAYER_EDGE): lambda src_id, dst_id: (0, (src_id.host - 2) * 2 + 1),
            (self.LAYER_EDGE, self.LAYER_CORE): lambda src_id, dst_id: ((dst_id.sw - 2) * 2, src_id.pod),
            (self.LAYER_EDGE, self.LAYER_AGG): lambda src_id, dst_id: (
                (dst_id.sw - self.k // 2) * 2, src_id.sw * 2 + 1),
            (self.LAYER_AGG, self.LAYER_CORE): lambda src_id, dst_id: ((dst_id.host - 1) * 2, src_id.pod),
            (self.LAYER_CORE, self.LAYER_AGG): lambda src_id, dst_id: (dst_id.pod, (src_id.host - 1) * 2),
            (self.LAYER_AGG, self.LAYER_EDGE): lambda src_id, dst_id: (
                dst_id.sw * 2 + 1, (src_id.sw - self.k // 2) * 2),
            (self.LAYER_CORE, self.LAYER_EDGE): lambda src_id, dst_id: (dst_id.pod, (src_id.sw - 2) * 2),
            (self.LAYER_EDGE, self.LAYER_HOST): lambda src_id, dst_id: ((dst_id.host - 2) * 2 + 1, 0)
        }
        self.buildTopo(range(0, k), range(1, k // 2 + 1), range(k // 2, k), range(0, k // 2), range(2, k // 2 + 2))
        super(Topo, self).__init__()
        self.node_specs = node_specs
        self.edge_specs = edge_specs

    def buildTopo(self, pods, core_switches, agg_switches, edge_switches, hosts):
        for pod in pods:
            for edge in edge_switches:
                edge_id = self.id_gen(pod, edge, 1).name_str()
                edge_opts = self.def_nopts(self.LAYER_EDGE, edge_id)
                self.addSwitch(edge_id, **edge_opts)

                for host in hosts:
                    host_id = self.id_gen(pod, edge, host).name_str()
                    host_opts = self.def_nopts(self.LAYER_HOST, host_id)
                    self.addHost(host_id, **host_opts)
                    self.all_hosts.append(host_id)
                    self.addLink(host_id, edge_id)

                for agg in agg_switches:
                    agg_id = self.id_gen(pod, agg, 1).name_str()
                    agg_opts = self.def_nopts(self.LAYER_AGG, agg_id)
                    self.addSwitch(agg_id, **agg_opts)
                    self.addLink(edge_id, agg_id)

            for agg in agg_switches:
                agg_id = self.id_gen(pod, agg, 1).name_str()
                c_index = agg - self.k // 2 + 1
                for c in core_switches:
                    core_id = self.id_gen(self.k, c_index, c).name_str()
                    core_opts = self.def_nopts(self.LAYER_CORE, core_id)
                    self.addSwitch(core_id, **core_opts)
                    self.addLink(core_id, agg_id)

    def def_nopts(self, layer):
        return {'layer': layer}

    def layer(self, name):
        return self.nodeInfo(name)['layer']

    def port_up(self, port):
        return port % 2 == PORT_BASE

    def layer_nodes(self, layer):
        def is_layer(n):
            return self.layer(n) == layer

        return [n for n in self.g.nodes() if is_layer(n)]

    def up_nodes(self, name):
        layer = self.layer(name) - 1
        return [n for n in self.g[name] if self.layer(n) == layer]

    def down_nodes(self, name):
        layer = self.layer(name) + 1
        return [n for n in self.g[name] if self.layer(n) == layer]

    def up_edges(self, name):
        return [(name, n) for n in self.up_nodes(name)]

    def down_edges(self, name):
        return [(name, n) for n in self.down_nodes(name)]

    def def_nopts(self, layer, name=None):
        result = {'layer': layer}
        if name:
            id = self.id_gen(name=name)
            result['dpid'] = "%016x" % id.dpid
            if layer == self.LAYER_HOST:
                result['ip'] = id.ip_str()
                result['mac'] = id.mac_str()
        return result

    def get_all_hosts(self):
        return self.all_hosts

    def port(self, src, dst):
        src_layer, dst_layer = self.layer(src), self.layer(dst)
        src_id, dst_id = self.id_gen(name=src), self.id_gen(name=dst)
        try:
            src_port, dst_port = self.port_handler[(src_layer, dst_layer)](src_id, dst_id)
            return src_port if src_layer == self.LAYER_HOST else src_port + 1, dst_port if dst_layer == self.LAYER_HOST else dst_port + 1
        except:
            raise Exception("Could not discover port leading to dst switch")
            self.host = host