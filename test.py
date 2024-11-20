import threading
import time
import random
import poem_global as poem
import aasc as aasc
from tabulate import tabulate

class Test:
    def __init__(self, test_type = 'throughput'):
        self.test_type = test_type
        self.number_of_transactions = 200

    def create_network(self, num_nodes, num_miners):
        assert num_nodes >= num_miners
        nodes = [6000 + i for i in range(num_nodes)]
        validators = random.sample(nodes, num_miners)

        edges = []
        shuffled_nodes = nodes[:]
        random.shuffle(shuffled_nodes)
        
        for i in range(1, num_nodes):
            u = shuffled_nodes[i]
            v = shuffled_nodes[random.randint(0, i - 1)]
            edges.append((u, v))
        
        possible_edges = [
            (u, v) for i, u in enumerate(nodes) for v in nodes[i + 1:]
            if (u, v) not in edges and (v, u) not in edges
        ]
        
        random.shuffle(possible_edges)
        extra_edges = random.randint(0, len(possible_edges))
        
        for _ in range(extra_edges):
            edges.append(possible_edges.pop())   

        print("Nodes: ", nodes)
        print("Validators: ", validators)
        print("Edges: ", edges)
        return nodes, validators, edges
    
    def run_node(self, port, is_validator, address = '127.0.0.1', algo = aasc):
        print(f"Running node on port {port}, is_validator: {is_validator}, address: {address}")
        node = algo.Node(address, port, is_validator)
        cli = algo.NodeCLI(node)
        
        node_thread = threading.Thread(target=node.start)
        node_thread.start()
        
        return node, cli
    
    def run_test(self, num_nodes, num_miners):
        nodes, validators, edges = self.create_network(num_nodes, num_miners)
        
        print(f"Running test for {num_nodes} nodes and {num_miners} miners")
        poem_result = self.PoEM_test(nodes, validators, edges)
        print("PoEM Test Completed")
        aasc_result = self.AASC_test(nodes, validators, edges)
        print("AASC Test Completed")

        result = {
            'AASC' : aasc_result,
            'PoEM' : poem_result
        }

        table = []
        for algo, result in result.items():
            table.append([algo, result['throughput'], result['latency']])
        
        print(f"Test Results for {num_nodes} nodes and {num_miners} miners")
        print("-" * 50)
        print(tabulate(table, headers = ['Algorithm', 'Throughput', 'Latency']))
        print("-" * 50)

        

    def AASC_test(self, nodes, validators, edges):
        print(f"AASC Nodes {nodes}")
        for node in nodes:
            print(node)
        active_nodes = {node : self.run_node(node, node in validators, algo = aasc) for node in nodes}
        print("Attempting to connect nodes")
        for u, v in edges:
            active_nodes[u][1].do_addpeer(f"127.0.0.1 {v}")
            time.sleep(1)
        
        time.sleep(2)
        print("Collecting validators")
        active_nodes[nodes[0]][1].do_sval("")
        time.sleep(2)
        transaction_nodes = random.sample(nodes, len(nodes) // 2)
        transaction_per_nodes = self.number_of_transactions//len(transaction_nodes)
        total_transactions = 0
        print("Starting transactions")
        start_time = time.time()
        for node in transaction_nodes:
            for _ in range(transaction_per_nodes):
                recipient = f"user{random.randint(1, 100)}"
                amount = random.randint(1, 10)
                active_nodes[node][1].do_addtx(f"{recipient} {amount}")
                total_transactions += 1
                print(f"Transaction {total_transactions} completed", end = '\r')
        end_time = time.time()
        total_time = end_time - start_time
        throughput = total_transactions / total_time
        latency = total_time / total_transactions

        result = {
            'throughput' : throughput,
            'latency' : latency
        }

        time.sleep(2)
        for node in nodes:
            active_nodes[node][1].do_exit("")

        return result


    def PoEM_test(self, nodes, validators, edges):
        active_nodes = {node : self.run_node(node, node in validators, algo = poem) for node in nodes}
        print("Attempting to connect nodes")
        for u, v in edges:
            active_nodes[u][1].do_addpeer(f"127.0.0.1 {v}")

        time.sleep(2)
        print("Collecting validators")
        active_nodes[nodes[0]][1].do_sval("")
        time.sleep(2)

        transaction_nodes = random.sample(nodes, len(nodes) // 2)
        transaction_per_nodes = self.number_of_transactions//len(transaction_nodes)
        total_transactions = 0
        print("Starting transactions")
        start_time = time.time()
        for node in transaction_nodes:
            for _ in range(transaction_per_nodes):
                recipient = f"user{random.randint(1, 100)}"
                amount = random.randint(1, 10)
                active_nodes[node][1].do_addtx(f"{recipient} {amount}")
                total_transactions += 1
                print(f"Transaction {total_transactions} completed", end = '\r')
        end_time = time.time()
        total_time = end_time - start_time
        throughput = total_transactions / total_time
        latency = total_time / total_transactions

        result = {
            'throughput' : throughput,
            'latency' : latency
        }

        time.sleep(2)
        for node in nodes:
            active_nodes[node][1].do_exit("")

        return result


if __name__ == "__main__":
    test = Test()
    test.run_test(10, 4)