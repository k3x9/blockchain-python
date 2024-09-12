import hashlib
import time
import random
import cmd
import threading
import socket
import json
import sys
from concurrent.futures import ThreadPoolExecutor

class Block:
    def __init__(self, index, previous_hash, timestamp, data, hash, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.hash = hash
        self.nonce = nonce

    def to_dict(self):
        return self.__dict__

class Blockchain:
    def __init__(self, difficulty=4):
        self.chain = [self.create_genesis_block()]
        self.difficulty = difficulty
        self.pending_transactions = []

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), "Genesis Block", self.calculate_hash(0, "0", int(time.time()), "Genesis Block", 0), 0)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, new_block):
        new_block.previous_hash = self.get_latest_block().hash
        new_block.hash = self.calculate_hash(new_block.index, new_block.previous_hash, new_block.timestamp, new_block.data, new_block.nonce)
        self.chain.append(new_block)

    @staticmethod
    def calculate_hash(index, previous_hash, timestamp, data, nonce):
        value = str(index) + str(previous_hash) + str(timestamp) + str(data) + str(nonce)
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def add_transaction(self, sender, recipient, amount):
        self.pending_transactions.append(f"{sender} sends {amount} coins to {recipient}")

    def mine_pending_transactions(self, miner_address):
        block = Block(len(self.chain), self.get_latest_block().hash, int(time.time()), self.pending_transactions, "", 0)
        block.nonce = self.proof_of_work(block)
        block.hash = self.calculate_hash(block.index, block.previous_hash, block.timestamp, block.data, block.nonce)
        self.chain.append(block)
        self.pending_transactions = [f"Miner Reward: {miner_address} receives 1 coin"]

    def proof_of_work(self, block):
        nonce = 0
        while True:
            hash = self.calculate_hash(block.index, block.previous_hash, block.timestamp, block.data, nonce)
            if hash.startswith('0' * self.difficulty):
                return nonce
            nonce += 1

class Node:
    def __init__(self, address, port, is_miner=False):
        self.address = address
        self.port = port
        self.blockchain = Blockchain()
        self.is_miner = is_miner
        self.peers = set()

    def start(self):
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
            data = conn.recv(1024)
            if data:
                message = json.loads(data.decode())
                if message['type'] == 'new_block':
                    new_block = Block(**message['data'])
                    self.blockchain.add_block(new_block)
                elif message['type'] == 'new_transaction':
                    self.blockchain.add_transaction(**message['data'])
                    if self.is_miner:
                        print("Mining new block to include transaction...")
                        self.mine()
                elif message['type'] == 'get_chain':
                    chain_data = [block.to_dict() for block in self.blockchain.chain]
                    conn.sendall(json.dumps(chain_data).encode())
                elif message['type'] == 'add_peer':
                    peer_address = message['address']
                    peer_port = message['port']
                    if (peer_address, peer_port) not in self.peers:
                        self.add_peer(peer_address, peer_port)
                        print(f"Added peer: {peer_address}:{peer_port}")

    def broadcast(self, message):
        for peer in self.peers:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect(peer)
                    s.sendall(json.dumps(message).encode())
                except Exception as e:
                    print(f"Failed to connect to peer {peer}: {e}")

    def add_peer(self, address, port):
        self.peers.add((address, port))

    def mine(self):
        if self.is_miner:
            self.blockchain.mine_pending_transactions(self.address)
            latest_block = self.blockchain.get_latest_block()
            self.broadcast({
                'type': 'new_block',
                'data': latest_block.to_dict()
            })

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
            print(f"  Data: {block.data}")
            print(f"  Hash: {block.hash}")
            print(f"  Previous Hash: {block.previous_hash}")
            print()

    def do_addtx(self, arg):
        """Add a new transaction: addtx <recipient> <amount>"""
        try:
            recipient, amount = arg.split()
            amount = int(amount)
            self.node.blockchain.add_transaction(self.node.address, recipient, amount)
            self.node.broadcast({
                'type': 'new_transaction',
                'data': {
                    'sender': self.node.address + self.node.port,
                    'recipient': recipient,
                    'amount': amount
                }
            })
            print(f"Transaction added: {self.node.address} sends {amount} coins to {recipient}")
        except ValueError:
            print("Invalid input. Use format: addtx <recipient> <amount>")

    def _notify_peer_to_add_us(self, address, port):
        """Notify the peer to add this node as a peer"""
        try:
            message = {
                'type': 'add_peer',
                'address': self.node.address,
                'port': self.node.port
            }

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((address, port))
                s.sendall(json.dumps(message).encode())

            print(f"Successfully notified peer {address}:{port} to add us as a peer.")
            return True

        except Exception as e:
            print(f"Error notifying peer {address}:{port}: {e}")
            return False

    def do_mine(self, arg):
        """Mine a new block"""
        if self.node.is_miner:
            print("Mining a new block...")
            self.node.mine()
            print("Block mined and added to the chain.")
        else:
            print("This node is not a miner.")

    def do_addpeer(self, arg):
        """Add a new peer: addpeer <address> <port>"""
        try:
            address, port = arg.split()
            port = int(port)
            if (address, port) in self.node.peers:
                print("This peer is already connected.")
                return
            
            if address == self.node.address and port == self.node.port:
                print("Cannot connect to self.")
                return
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                try:
                    s.connect((address, port))
                except Exception as e:
                    print(f"Failed to connect to peer {address}:{port}: {e}")
                    return
            
            if self._notify_peer_to_add_us(address, port):
                self.node.add_peer(address, port)
                print(f"Peer added: {address}:{port}")
            else:
                print(f"Failed to add peer: {address}:{port}")
            
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

    def do_exit(self, arg):
        """Exit the CLI"""
        print("Exiting CLI...")
        return True

def run_node(address, port, is_miner):
    node = Node(address, port, is_miner)
    cli_thread = threading.Thread(target=NodeCLI(node).cmdloop, args=(f"Started CLI for {address}:{port}",))
    cli_thread.start()
    node.start()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <port> <is_miner>")
        sys.exit(1)
    
    address = "127.0.0.1"
    port = int(sys.argv[1])
    is_miner = sys.argv[2].lower() == 'true'
    
    run_node(address, port, is_miner)