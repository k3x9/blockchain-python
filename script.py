import hashlib
import time
import random
import cmd
import threading
import socket
import json
import sys
from concurrent.futures import ThreadPoolExecutor

class Transaction:
    def __init__(self, sender, recipient, amount, timestamp=None):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.timestamp = timestamp or time.time()
        self.id = self.calculate_hash()

    def calculate_hash(self):
        return hashlib.sha256(f"{self.sender}{self.recipient}{self.amount}{self.timestamp}".encode()).hexdigest()

    def to_dict(self):
        return self.__dict__

class Block:
    def __init__(self, index, previous_hash, transactions, poh_sequence, validator):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.poh_sequence = poh_sequence
        self.validator = validator
        self.timestamp = time.time()
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data = f"{self.index}{self.previous_hash}{self.transactions}{self.poh_sequence}{self.validator}{self.timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "poh_sequence": self.poh_sequence,
            "validator": self.validator,
            "timestamp": self.timestamp,
            "hash": self.hash
        }

class ProofOfHistory:
    def __init__(self, difficulty=4):
        self.difficulty = difficulty
        self.sequence = []

    def hash_value(self, value):
        return hashlib.sha256(str(value).encode()).hexdigest()

    def generate_sequence(self, previous_hash, transaction):
        nonce = 0
        while True:
            hash_result = self.hash_value(previous_hash + str(nonce) + transaction.id)
            if hash_result.startswith('0' * self.difficulty):
                break
            nonce += 1
        return (previous_hash, nonce, hash_result)

class Blockchain:
    def __init__(self, difficulty=4):
        self.chain = [self.create_genesis_block()]
        self.difficulty = difficulty
        self.poh = ProofOfHistory(difficulty)
        self.validators = set()
        self.lock = threading.Lock()

    def create_genesis_block(self):
        return Block(0, "0", [], [], "Genesis")

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, new_block):
        with self.lock:
            if self.is_valid_new_block(new_block):
                self.chain.append(new_block)
                return True
            return False

    def is_valid_new_block(self, new_block):
        latest_block = self.get_latest_block()
        if latest_block.index + 1 != new_block.index:
            return False
        if latest_block.hash != new_block.previous_hash:
            return False
        if new_block.calculate_hash() != new_block.hash:
            return False
        return True

    def add_validator(self, address):
        self.validators.add(address)

    def remove_validator(self, address):
        self.validators.discard(address)

    def is_validator(self, address):
        return address in self.validators

    def create_new_block(self, transaction, validator_address):
        if not self.is_validator(validator_address):
            raise ValueError("Only validators can create new blocks")
        
        latest_block = self.get_latest_block()
        poh_sequence = self.poh.generate_sequence(latest_block.hash, transaction)
        
        new_block = Block(
            latest_block.index + 1,
            latest_block.hash,
            [transaction],
            poh_sequence,
            validator_address
        )
        
        return new_block

    def resolve_conflicts(self, chains):
        longest_chain = None
        max_length = len(self.chain)
        for chain in chains:
            if len(chain) > max_length and self.is_valid_chain(chain):
                max_length = len(chain)
                longest_chain = chain
        
        if longest_chain:
            self.chain = longest_chain
            return True
        return False
    
    def is_valid_chain(self, chain):
        if chain[0].to_dict() != self.create_genesis_block().to_dict():
            return False
        
        for i in range(1, len(chain)):
            block = chain[i]
            prev_block = chain[i-1]
            if block.previous_hash != prev_block.hash:
                return False
            if not self.is_valid_new_block(block):
                return False
        return True

class Node:
    def __init__(self, address, port, is_validator=False):
        self.address = address
        self.port = port
        self.blockchain = Blockchain()
        self.peers = set()
        self.is_validator = is_validator
        if is_validator:
            self.blockchain.add_validator(f"{address}:{port}")
        self.unconfirmed_transactions = []
        self.lock = threading.Lock()

    def start(self):
        server_thread = threading.Thread(target=self.run_server)
        server_thread.start()
        if self.is_validator:
            validator_thread = threading.Thread(target=self.validator_loop)
            validator_thread.start()

    def run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.address, self.port))
            s.listen()
            print(f"Node listening on {self.address}:{self.port}")
            with ThreadPoolExecutor(max_workers=10) as executor:
                while True:
                    conn, addr = s.accept()
                    executor.submit(self.handle_connection, conn, addr)

    def handle_connection(self, conn, addr):
        with conn:
            data = conn.recv(4096)
            if data:
                message = json.loads(data.decode())
                if message['type'] == 'new_block':
                    new_block = Block(**message['data'])
                    self.handle_new_block(new_block)
                elif message['type'] == 'new_transaction':
                    transaction = Transaction(**message['data'])
                    self.handle_new_transaction(transaction)
                elif message['type'] == 'get_chain':
                    chain_data = [block.to_dict() for block in self.blockchain.chain]
                    conn.sendall(json.dumps(chain_data).encode())

    def broadcast(self, message):
        for peer in self.peers:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect(peer)
                    s.sendall(json.dumps(message).encode())
                except Exception as e:
                    print(f"Failed to connect to peer {peer}: {e}")

    def handle_new_transaction(self, transaction):
        with self.lock:
            self.unconfirmed_transactions.append(transaction)
        self.broadcast({
            'type': 'new_transaction',
            'data': transaction.to_dict()
        })

    def handle_new_block(self, new_block):
        if self.blockchain.add_block(new_block):
            with self.lock:
                self.unconfirmed_transactions = [tx for tx in self.unconfirmed_transactions 
                                                 if tx.id not in [t.id for t in new_block.transactions]]
            self.broadcast({
                'type': 'new_block',
                'data': new_block.to_dict()
            })
        else:
            self.resolve_conflicts()

    def validator_loop(self):
        while True:
            time.sleep(1)  # Wait for 1 second between block creations
            with self.lock:
                if self.unconfirmed_transactions:
                    transaction = self.unconfirmed_transactions.pop(0)
                    new_block = self.blockchain.create_new_block(transaction, f"{self.address}:{self.port}")
                    if self.blockchain.add_block(new_block):
                        self.broadcast({
                            'type': 'new_block',
                            'data': new_block.to_dict()
                        })

    def resolve_conflicts(self):
        chains = []
        for peer in self.peers:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect(peer)
                    s.sendall(json.dumps({'type': 'get_chain'}).encode())
                    response = s.recv(16384)
                    chain_data = json.loads(response.decode())
                    chain = [Block(**block_data) for block_data in chain_data]
                    chains.append(chain)
                except Exception as e:
                    print(f"Error getting chain from peer {peer}: {e}")
        
        if self.blockchain.resolve_conflicts(chains):
            print("Blockchain was updated after resolving conflicts")
        else:
            print("Our chain is authoritative")

class NodeCLI(cmd.Cmd):
    prompt = 'blockchain> '

    def __init__(self, node):
        super().__init__()
        self.node = node

    def do_viewchain(self, arg):
        """View the current state of the blockchain"""
        for block in self.node.blockchain.chain:
            print(f"Block {block.index}:")
            print(f"  Timestamp: {block.timestamp}")
            print(f"  Transactions: {[tx.to_dict() for tx in block.transactions]}")
            print(f"  Validator: {block.validator}")
            print(f"  Hash: {block.hash}")
            print(f"  Previous Hash: {block.previous_hash}")
            print(f"  PoH Sequence: {block.poh_sequence}")
            print()

    def do_addpeer(self, arg):
        """Add a new peer: addpeer <address> <port>"""
        try:
            address, port = arg.split()
            port = int(port)
            self.node.add_peer(address, port)
            print(f"Peer added: {address}:{port}")
        except ValueError:
            print("Invalid input. Use format: addpeer <address> <port>")

    def do_listpeers(self, arg):
        """List all peers"""
        if self.node.peers:
            print("Connected peers:")
            for peer in self.node.peers:
                print(f"  - {peer[0]}:{peer[1]}")
        else:
            print("This node has no connected peers.")

    def do_togglevalidator(self, arg):
        """Toggle validator status for this node"""
        self.node.is_validator = not self.node.is_validator
        if self.node.is_validator:
            self.node.blockchain.add_validator(f"{self.node.address}:{self.node.port}")
            print("This node is now a validator.")
        else:
            self.node.blockchain.remove_validator(f"{self.node.address}:{self.node.port}")
            print("This node is no longer a validator.")

    def do_resolveconflicts(self, arg):
        """Resolve any conflicts in the blockchain"""
        if self.node.resolve_conflicts():
            print("Blockchain was replaced")
        else:
            print("Our chain is authoritative")

    def do_exit(self, arg):
        """Exit the CLI"""
        print("Exiting CLI...")
        return True

    def do_addtx(self, arg):
        """Add a new transaction: addtx <recipient> <amount>"""
        try:
            recipient, amount = arg.split()
            amount = float(amount)
            tx = Transaction(f"{self.node.address}:{self.node.port}", recipient, amount)
            self.node.handle_new_transaction(tx)
            print(f"Transaction added: {self.node.address}:{self.node.port} sends {amount} coins to {recipient}")
            print(f"Transaction ID: {tx.id}")
        except ValueError:
            print("Invalid input. Use format: addtx <recipient> <amount>")

def run_node(address, port, is_validator, peers):
    node = Node(address, port, is_validator)
    for peer in peers:
        node.peers.add(peer)
    cli_thread = threading.Thread(target=NodeCLI(node).cmdloop, args=(f"Started CLI for {address}:{port}",))
    cli_thread.start()
    node.start()

if __name__ == "__main__":
    nodes = [
        ("127.0.0.1", 5000, True),   # Validator 1
        ("127.0.0.1", 5001, True),   # Validator 2
        ("127.0.0.1", 5002, False),  # Regular node 1
        ("127.0.0.1", 5003, False)   # Regular node 2
    ]

    peers = [("127.0.0.1", port) for _, port, _ in nodes]

    if len(sys.argv) != 2:
        print("Usage: python script.py <node_index>")
        sys.exit(1)

    node_index = int(sys.argv[1])
    if node_index < 0 or node_index >= len(nodes):
        print(f"Invalid node index. Must be between 0 and {len(nodes)-1}")
        sys.exit(1)

    address, port, is_validator = nodes[node_index]
    run_node(address, port, is_validator, [p for p in peers if p != (address, port)])