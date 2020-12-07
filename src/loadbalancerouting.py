#!/usr/bin/env python
from copy import copy
from random import choice


class BaseECMP(object):
    def __init__(self, topo, mode):
        self.topo = topo
        self.mode = mode
        self.routes = None
        self.src_paths, self.dst_paths = None, None
        self.src_path_layer, self.dst_path_layer = None, None
        self.src_paths_next, self.dst_paths_next = None, None
        self.max_len = None

    def _add_path_src(self, edge_node, src_path_list):
        if edge_node in self.dst_paths:
            for dst_path in self.dst_paths[edge_node]:
                dst_path_rev = copy(dst_path).reverse()
                for src_path in src_path_list:
                    self.routes.append(src_path + dst_path_rev if dst_path_rev else [])
        else:
            if edge_node not in self.src_paths_next:
                self.src_paths_next[edge_node] = []
            for src_path in src_path_list:
                self.src_paths_next[edge_node].append(src_path + [edge_node])

    def _add_path_dst(self, edge_node, dst_path_list):
        if edge_node in self.src_paths:
            for src_path in self.src_paths[edge_node]:
                for dst_path in dst_path_list:
                    dst_path_rev = copy(dst_path).reverse()
                    self.routes.append(src_path + dst_path_rev if dst_path_rev else [])
        else:
            if edge_node not in self.dst_paths_next:
                self.dst_paths_next[edge_node] = []
            for dst_path in dst_path_list:
                self.dst_paths_next[edge_node].append(dst_path + [edge_node])

    def _expand_src(self, node):
        src_path_list = self.src_paths[node]
        if not src_path_list or len(src_path_list) == 0:
            return False

        last = src_path_list[0][-1]

        up_edges, up_nodes = self.topo.up_edges(last), self.topo.up_nodes(last)
        if not up_edges or not up_nodes:
            return False

        for edge in sorted(up_edges):
            a, b = edge
            frontier_node = b
            self._add_path_src(frontier_node, src_path_list)

        return True

    def _expand_dst(self, node):
        dst_path_list = self.dst_paths[node]
        last = dst_path_list[0][-1]

        up_edges, up_nodes = self.topo.up_edges(last), self.topo.up_nodes(last)
        if not up_edges or not up_nodes:
            return False

        for edge in sorted(up_edges):
            a, b = edge
            frontier_node = b
            self._add_path_dst(frontier_node, dst_path_list)

        return True

    def _expand(self, edge_layer):
        self.routes = []
        if self.src_path_layer > edge_layer:
            self.src_paths_next = {}
            for node in sorted(self.src_paths):
                if not self._expand_src(node):
                    continue
            self.src_paths = self.src_paths_next
            self.src_path_layer -= 1
        if self.dst_path_layer > edge_layer:
            self.dst_paths_next = {}
            for node in self.dst_paths:
                if not self._expand_dst(node):
                    continue
            self.dst_paths = self.dst_paths_next
            self.dst_path_layer -= 1
        return self.routes

    def dfs(self, src, dst, routes, curr_route):
        if src not in curr_route:
            curr_route.append(src)
            if src == dst:
                new_path = copy(curr_route)
                routes.append(new_path)
                if len(new_path) < self.max_len:
                    self.max_len = len(new_path)
            elif len(curr_route) < self.max_len:
                for n in copy(self.topo.up_nodes(src)) + copy(self.topo.down_nodes(src)):
                    self.dfs(n, dst, routes, curr_route)

            curr_route.remove(src)

    def get_route(self, src, dst, hash_, isComplete):
        if src == dst:
            return [[src]] if isComplete else [src]

        self.src_paths, self.dst_paths = {src: [[src]]}, {dst: [[dst]]}
        src_layer, dst_layer = self.topo.layer(src), self.topo.layer(dst)
        self.src_path_layer, self.dst_path_layer = src_layer, dst_layer
        lowest_starting_layer = dst_layer if dst_layer > src_layer else src_layer

        for depth in range(lowest_starting_layer - 1, -1, -1):
            paths_found = self._expand(depth)
            if paths_found:
                return paths_found if isComplete else self.mode(paths_found, src, dst, hash_)
        return None


# pylint: disable-msg=W0613
class RoundRobinMode(BaseECMP):
    rr_counter = 0

    def __init__(self, topo):
        def choose_rr(paths, src, dst, hash_):
            n_paths = len(paths)
            select_path = paths[RoundRobinMode.rr_counter % n_paths]
            RoundRobinMode.rr_counter += 1
            return select_path

        super(RoundRobinMode, self).__init__(topo, choose_rr)


class RandomMode(BaseECMP):
    def __init__(self, topo):
        def choose_random(paths, src, dst, hash_):
            return choice(paths)

        super(RandomMode, self).__init__(topo, choose_random)


class HashedMode(BaseECMP):
    def __init__(self, topo):
        def choose_hashed(paths, src, dst, hash_):
            path = sorted(paths)[hash_ % len(paths)]
            return path

        super(HashedMode, self).__init__(topo, choose_hashed)
# pylint: enable-msg=W0613