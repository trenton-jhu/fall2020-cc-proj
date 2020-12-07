# ECMP Modes Simulation on Fat-tree Topology using POX Controller
## How to Run
POX controller is already embeded in this repo with our own custom controller implemented in `/pox/pox/controllers/`. To simulate a particular mode of ECMP (say hashed-based),
first start the controller by running
```
pox/pox.py controllers.controller --topo=ft,4 --routing=hashed
```
Here, replace `4` for the number of pods to build in the fat-tree topology and replace `hashed` for other modes of ECMP, including `rr` (round-robin) and `random`. 
If you run into the issue where controller port `6633` is already in use, you need to kill the process using that port by running the following command:
```
sudo fuser -k 6633/tcp
```
If run successfully, the controller command will not exit, so to start the experiment network, you need to open up a new terminal window. In this new terminal, first clean up
the network by running:
```
sudo mn -c
```
Then, run the python file `experiment.py` to start the experiment like so:
```
sudo python experiment.py flow_matrices/fattree-4-uniform_random.json
```
Again, you can replace `hashed` with other supported modes of ECMP. You can choose other traffic flow patterns provided in `flow_matrices`. This will build the Mininet network for
a fat-tree topology and simulate the traffic flow using the specified mode of ECMP. It will output the average throughput once the experiment is finished. Detailed results will be
output to a json file in the `throughput_stats` directory and can be used to generate plots using `plot_throughput.py`. 
