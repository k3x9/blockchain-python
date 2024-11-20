import threading
import time
import random
from poem import Node, NodeCLI, PoEMModel

def run_node(address, port, is_miner):
    node = Node(address, port, is_miner)
    cli = NodeCLI(node)
    
    node_thread = threading.Thread(target=node.start)
    node_thread.start()
    
    return node, cli

def simulate_transactions(cli, num_transactions):
    for _ in range(num_transactions):
        recipient = f"user{random.randint(1, 100)}"
        amount = random.randint(1, 10)
        cli.do_addtx(f"{recipient} {amount}")
        time.sleep(0.5)  # Wait a bit between transactions

def test_poem_blockchain():
    model = PoEMModel()
    model_thread = threading.Thread(target=model.start)
    model_thread.start()

    nodes = [
        run_node("127.0.0.1", 5000, True),
        run_node("127.0.0.1", 5001, True),
        run_node("127.0.0.1", 5002, False)
    ]

    # Connect nodes
    for i, (node, cli) in enumerate(nodes):
        for j, (peer_node, _) in enumerate(nodes):
            if i != j:
                cli.do_addpeer(f"127.0.0.1 {5000 + j}")

    # Wait for connections to establish
    time.sleep(2)

    # Simulate transactions on each node
    for _, cli in nodes:
        simulate_transactions(cli, 5)

    # Mine blocks
    for _, cli in nodes:
        cli.do_mine("")

    # Synchronize models
    for _, cli in nodes:
        cli.do_syncmodel("")

    # Display chain and model info for each node
    for i, (_, cli) in enumerate(nodes):
        print(f"\nNode {i} Chain:")
        cli.do_viewchain("")
        print(f"\nNode {i} Model Info:")
        cli.do_modelinfo("")

    # Simulate more transactions and mining
    for _ in range(3):
        for _, cli in nodes:
            simulate_transactions(cli, 3)
            cli.do_mine("")
            cli.do_syncmodel("")

    # Display final chain and model info
    for i, (_, cli) in enumerate(nodes):
        print(f"\nFinal Node {i} Chain:")
        cli.do_viewchain("")
        print(f"\nFinal Node {i} Model Info:")
        cli.do_modelinfo("")

if __name__ == "__main__":
    test_poem_blockchain()