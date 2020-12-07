#!/usr/bin/env python3
"""
Generates traffic flow matrices represented as json indicating the dst hosts for each sender
Output json files to flow_matrices/

usage: generate_flow_matrices.py [-h] k

Generate traffic flow matrices

positional arguments:
  k           Number of pods in fattree topology
"""

import os
import random
import json
import argparse


def strided(step, num_hosts):
    """
    Each host with index k sends to the host with index (k + i) mod num_hosts
    """
    flow_matrix = {}
    for x in range(num_hosts):
        flow_matrix[str(x)] = [(x + step) % num_hosts]
    return flow_matrix


def stride1(num_hosts):
    return strided(1, num_hosts)


def stride2(num_hosts):
    return strided(2, num_hosts)


def stride4(num_hosts):
    return strided(4, num_hosts)


def stride8(num_hosts):
    return strided(8, num_hosts)


def uniform_random(num_hosts):
    """
    Each host sends to any other host in with uniform probability.
    """
    flow_matrix = {}
    for x in list(range(num_hosts)):
        hosts = list(range(num_hosts))
        hosts.remove(x)
        flow_matrix[str(x)] = [random.choice(hosts)]
    return flow_matrix


def one_to_one(num_hosts):
    """
    Hosts get paired evenly one-to-one. This works since the number of hosts are even
    """
    flow_matrix = {}
    all_hosts = list(range(num_hosts))
    random.shuffle(all_hosts)
    dest_hosts = all_hosts[:(len(all_hosts) // 2)]
    source_hosts = all_hosts[(len(all_hosts) // 2):]
    for src, dst in zip(source_hosts, dest_hosts):
        flow_matrix[str(src)] = [dst]
    return flow_matrix


def all_to_one(num_hosts):
    """
    Every host try to send to a random host
    """
    flow_matrix = {}
    destination_host = random.choice(list(range(num_hosts)))
    sending_hosts = list(range(num_hosts))
    sending_hosts.remove(destination_host)
    for host in sending_hosts:
        flow_matrix[str(host)] = [destination_host]
    return flow_matrix


def parse_args():
    """
    Parse command line arguments
    """
    parser = argparse.ArgumentParser(description="Generate traffic flow matrices")
    parser.add_argument("k", type=int, help="Number of pods in fattree topology")
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    num_hosts = args.k ** 3 / 4  # number of hosts in fat-tree
    traffic_patterns = [
        stride1,
        stride2,
        stride4,
        stride8,
        uniform_random,
        one_to_one,
        all_to_one
    ]
    for traffic_patten in traffic_patterns:
        file_name = "fattree-" + str(args.k) + "-" + str(traffic_patten.__name__)
        with open(os.path.join('flow_matrices/', file_name + '.json'), "w") as pattern_file:
            pattern_file.write(json.dumps(traffic_patten(int(num_hosts)), sort_keys=True))


if __name__ == '__main__':
    main()
