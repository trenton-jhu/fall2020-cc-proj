"""
ECMP Modes Experiment Driver using Mininet and POX Controller
Builds a fat-tree topology and then perform network simulation using POX controller
 based on input traffic flow matrices generated from generate_flow_matrices.py

usage: experiment.py [-h] [-k PODS] [-b BANDWIDTH] [-t TRAILS] flow_matrix

Run Mininet experiment

positional arguments:
  flow_matrix           Path to generated flow matrices json file

optional arguments:
  -h, --help            show this help message and exit
  -k PODS, --pods PODS  Number of pods in fattree, should be consistent with
                        flow matrix
  -b BANDWIDTH, --bandwidth BANDWIDTH
                        Link bandwidth for fattree (Gbps)
  -t TRAILS, --trails TRAILS
                        Number of trials to run
"""

import os
import json
import argparse

from time import time, sleep
from math import sqrt

from mininet.node import RemoteController
from mininet.net import Mininet
from mininet.util import dumpNodeConnections

from src.fattreetopo import FatTreeTopo
import traceback

IPERF_PATH = '/usr/bin/iperf'
IPERF_PORT = 5001
IPERF_PORT_BASE = 5001
IPERF_SECONDS = 3600

SAMPLES_TO_SKIP = 1

popens = {}
popen_receivers = {}

SERVER_IPERF_FLOW_CMD = '%s -s -p %s &'
CLIENT_IPERF_FLOW_CMD = '%s -c %s -p %s -t %d &'

def avg(lst):
    return float(sum(lst)) / len(lst)


def var(lst):
    mean = avg(lst)
    return avg([(val - mean) ** 2 for val in lst])


class Driver:
    def __init__(self, file, k=4, bw=1.0, trials=10):
        self.flow_matrix = file
        self.topo = FatTreeTopo(k=k, speed=bw)
        self.host_list = self.topo.get_all_hosts()
        self.total_trials = trials

    def init_flows(self, net):
        # Start iperf flows for all src, dst airs in flow matrix
        with open(self.flow_matrix, "r") as f:
            flow_matrix = json.load(f)

        for curr_port, (src_idx, dst_idx) in enumerate(flow_matrix.items()):
            src_name, dst_name = self.host_list[int(src_idx)], self.host_list[dst_idx[0]]
            src, dst = net.get(src_name), net.get(dst_name)
            port = IPERF_PORT_BASE + curr_port
            dst.cmd(SERVER_IPERF_FLOW_CMD % (IPERF_PATH, port))
            src.cmd(CLIENT_IPERF_FLOW_CMD % (IPERF_PATH, dst.IP('%s-eth0' % dst_name), port, IPERF_SECONDS))
            print('Initiated flow IP: %s ---> IP: %s | Port %d' % (
            src.IP('%s-eth0' % src_name), dst.IP('%s-eth0' % dst_name), port))

    def run_trails(self, net, rxbytes, sample_durations):
        curr_timestamp = time()
        for i in range(self.total_trials):
            print('Sample %d/%d...' % (i + 1, self.total_trials))
            sample_durations.append(time() - curr_timestamp)
            curr_timestamp = time()
            self.sample_bytes(net, rxbytes)
            sleep(1.0)
        return rxbytes, sample_durations

    def net_init(self):
        os.system('killall -9 ' + IPERF_PATH)
        net = Mininet(topo=self.topo)
        net.addController(name='controller', controller=RemoteController, ip='127.0.0.1', port=6633)
        net.start()
        dumpNodeConnections(net.hosts)
        return net

    def net_clean(self, net):
        print("killing all processes with love <3")
        os.system('killall -9 ' + IPERF_PATH)
        net.stop()
        os.system('sudo mn -c')

    def normalize2gbps(self, rate):
        return rate / (2 ** 30) * 8

    def start_experiment(self):
        print("Creating network...")
        net = self.net_init()

        sleep(5)

        print('Reading flow matrix from file: ' + self.flow_matrix)
        self.init_flows(net)
        agg_mean, agg_var = self.agg_stat(*self.run_trails(net, {name:[] for name in self.host_list}, []))
        agg_stddev = sqrt(agg_var)
        mean_gbps, stddev_gbps = self.normalize2gbps(agg_mean), self.normalize2gbps(agg_stddev)
        print('avg total throughput: %f bps | %f gbps ' % (agg_mean, mean_gbps))
        print('stddev: %f bps | %f gbps' % (agg_stddev, stddev_gbps))
        self.net_clean(net)

    def sample_bytes(self, net, rxbytes):
        for name in self.host_list:
            host = net.get(name)
            for line in host.cmd('cat /proc/net/dev').split('\n'):
                if '%s-eth0:' % name in line:
                    rxbytes[name].append(int(line.split()[1]))
                    break

    def agg_stat(self, rxbytes, sample_durations):
        throughputs = self.byte2throughput(rxbytes, sample_durations)
        return sum(avg(throughputs[name]) for name in throughputs), sum(var(throughputs[name]) for name in throughputs)

    def byte2throughput(self, rxbytes, durations):
        return {
            name: [
                      (sample - rxbytes[name][i - 1]) / durations[i] for i, sample in enumerate(rxbytes[name])
                  ][SAMPLES_TO_SKIP:] for name in self.host_list
        }


def parse_args():
    parser = argparse.ArgumentParser(description="Run Mininet experiment")
    parser.add_argument("flow_matrix", type=str, help="Path to generated flow matrices json file")
    parser.add_argument("-k", "--pods", type=int,
                        help="Number of pods in fattree, should be consistent with flow matrix",
                        default=4)
    parser.add_argument("-b", "--bandwidth", type=float, help="Link bandwidth of fattree (Gbps)", default=1.0)
    parser.add_argument("-t", "--trials", type=int, help="Number of trials to run", default=10)
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    if not os.path.isfile(args.flow_matrix):
        print('Cannot find flow matrix file: ' + args.flow_matrix)
        return
    if int(args.trials) < 2:
        print('There must be at least 2 trials')
        return
    try:
        driver = Driver(args.flow_matrix, args.pods, args.bandwidth, args.trials)
        driver.start_experiment()
    except:
        print('Caught exception.  Cleaning up...')
        traceback.print_exc()
        os.system('killall -9 top bwm-ng tcpdump cat mnexec iperf; mn -c')


if __name__ == '__main__':
    main()
