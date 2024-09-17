import hashlib
import time
import random
import cmd
import threading
import socket
import json
import sys
import math
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
        self.target = 2**256 - 1  # Initial target (easiest)
        self.c_val = self.calculate_hash(self.chain[-1].index, self.chain[-1].hash, 0)

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), "Genesis Block", self.calculate_hash("start_hash"), 0)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, new_block):
        new_block.previous_hash = self.get_latest_block().hash
        new_block.hash = self.calculate_hash(new_block.index, new_block.previous_hash, new_block.timestamp, new_block.data, new_block.nonce)
        self.chain.append(new_block)

    @staticmethod
    def calculate_hash(*args):
        return hashlib.sha256(str(args).encode('utf-8')).hexdigest()

    def add_transaction(self, sender, recipient, amount):
        self.pending_transactions.append(f"{sender} sends {amount} coins to {recipient}")

    def update_c_val(self):
        self.c_val = self.calculate_hash(str(self.chain[-1].index) + self.chain[-1].hash + str(len(self.pending_transactions)))

    def update_target(self, nbr_cand):
        self.target = int(self.target * (10 / math.log10(nbr_cand)))

class Node:
    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.blockchain = Blockchain()
        self.peers = set()
        self.id = self.calculate_hash(address + str(port))
        self.candidacies = []
        self.new_block_received = False
        self.failed_consensus_received = False

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
                elif message['type'] == 'get_chain':
                    chain_data = [block.to_dict() for block in self.blockchain.chain]
                    conn.sendall(json.dumps(chain_data).encode())
                elif message['type'] == 'add_peer':
                    peer_address = message['address']
                    peer_port = message['port']
                    if (peer_address, peer_port) not in self.peers:
                        self.add_peer(peer_address, peer_port)
                        print(f"Added peer: {peer_address}:{peer_port}")
                elif message['type'] == 'candidacy':
                    self.handle_candidacy(message['id'])

    def add_peer(self, address, port):
        self.peers.add((address, port))

    @staticmethod
    def calculate_hash(*args):
        return hashlib.sha256(str(args).encode('utf-8')).hexdigest()

    def poch_consensus(self):
        if int(self.calculate_hash(self.blockchain.c_val + self.id), 16) > self.blockchain.target:
            print("Starting PoCh consensus...")
            self.broadcast({'type': 'candidacy', 'id': self.id})
            
            # Wait for p1 time and collect candidacies
            time.sleep(1)  # p1 waiting time
            candidacies = self.collect_candidacies()
            print(f"Candidacies collected: {candidacies}")
            
            if len(candidacies) > 15:
                print("Too many candidacies. Restarting consensus...")
                self.blockchain.update_target(len(candidacies))
                self.broadcast({'type': 'failed_consensus', 'new_target': self.blockchain.target})
                return self.poch_consensus()
            
            if len(candidacies) < 0:
                print("Too few candidacies. Restarting consensus...")
                time.sleep(1)  # p2 waiting time
                candidacies = self.collect_candidacies()
                print(f"Candidacies collected: {candidacies}")
            
            if 0 <= len(candidacies) <= 15:
                print("Calculating new block...")
                result = 0
                d = 1
                sorted_candidates = sorted(candidacies)
                while result == 0:
                    result = (self.blockchain.chain[-1].index + sum(int(cand, 16)**d for cand in sorted_candidates)) % (len(candidacies) + 1)
                    d += 1
                
                if self.id == sorted_candidates[result - 1]:
                    print("I am the winner!")
                    new_block = self.create_new_block()
                    self.blockchain.add_block(new_block)
                    self.blockchain.update_c_val()
                    self.blockchain.update_target(len(candidacies))
                    self.broadcast({'type': 'new_block', 'data': new_block.to_dict()})
                    print("New block broadcasted.")
                else:
                    print("I am not the winner.")
                    # Wait for p3 time to receive new block
                    time.sleep(1)  # p3 waiting time
                    if not self.received_new_block():
                        print("No new block received..")
                        if len(candidacies) > 6:
                            candidacies.remove(sorted_candidates[result - 1])
                            return self.poch_consensus()
                        else:
                            self.blockchain.update_target(len(candidacies))
                            self.broadcast({'type': 'failed_consensus', 'new_target': self.blockchain.target})
                            return self.poch_consensus()
        else:
            # Wait to receive new block or failed consensus message
            time.sleep(2)  # Arbitrary waiting time
            if self.received_new_block():
                print("New block received.")
                self.blockchain.update_c_val()
            elif self.received_failed_consensus():
                print("Failed consensus received.")
                return self.poch_consensus()

    def collect_candidacies(self):
        """Collect candidacies from other nodes"""
        collection_start = time.time()
        collection_duration = 5  # Collect for 5 seconds

        while time.time() - collection_start < collection_duration:
            # Process incoming messages
            self.process_incoming_messages()

        # Clear the candidacies after collection for the next round
        collected = self.candidacies.copy()
        self.candidacies.clear()
        return collected

    def create_new_block(self):
        """Create a new block with pending transactions"""
        index = len(self.blockchain.chain)
        previous_hash = self.blockchain.get_latest_block().hash
        timestamp = int(time.time())
        data = self.blockchain.pending_transactions
        nonce = 0
        new_hash = self.calculate_hash(index, previous_hash, timestamp, data, nonce)

        new_block = Block(index, previous_hash, timestamp, data, new_hash, nonce)
        self.blockchain.pending_transactions = []  # Clear pending transactions
        return new_block

    def received_new_block(self):
        """Check if a new block was received"""
        result = self.new_block_received
        self.new_block_received = False  # Reset for next check
        return result

    def received_failed_consensus(self):
        """Check if a failed consensus message was received"""
        result = self.failed_consensus_received
        self.failed_consensus_received = False  # Reset for next check
        return result

    def process_incoming_messages(self):
        """Process incoming messages from peers"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.1)  # Set a short timeout
                s.bind((self.address, self.port))
                while True:
                    try:
                        data, addr = s.recvfrom(1024)
                        message = json.loads(data.decode())
                        self.handle_message(message)
                    except socket.timeout:
                        break  # No more messages to process
        except Exception as e:
            print(f"Error processing messages: {e}")

    def handle_message(self, message):
        """Handle different types of incoming messages"""
        if message['type'] == 'candidacy':
            self.candidacies.append(message['id'])
        elif message['type'] == 'new_block':
            new_block = Block(**message['data'])
            self.blockchain.add_block(new_block)
            self.new_block_received = True
        elif message['type'] == 'failed_consensus':
            self.blockchain.target = message['new_target']
            self.failed_consensus_received = True

    def broadcast(self, message):
        """Broadcast a message to all peers"""
        for peer in self.peers:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                try:
                    s.sendto(json.dumps(message).encode(), peer)
                except Exception as e:
                    print(f"Failed to send to peer {peer}: {e}")

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
            self.node.blockchain.add_transaction(self.node.address + ':' + str(self.node.port), recipient, amount)
            self.node.broadcast({
                'type': 'new_transaction',
                'data': {
                    'sender': self.node.address + ':' + str(self.node.port),
                    'recipient': recipient,
                    'amount': amount
                }
            })
            print(f"Transaction added: {self.node.address}:{self.node.port} sends {amount} coins to {recipient}")
        except ValueError:
            print("Invalid input. Use format: addtx <recipient> <amount>")

    def do_consensus(self, arg):
        """Initiate the PoCh consensus algorithm"""
        self.node.poch_consensus()

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

def run_node(address, port):
    node = Node(address, port)
    cli_thread = threading.Thread(target=NodeCLI(node).cmdloop, args=(f"Started CLI for {address}:{port}",))
    cli_thread.start()
    node.start()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <port>")
        sys.exit(1)
    
    address = "127.0.0.1"
    port = int(sys.argv[1])
    
    run_node(address, port)