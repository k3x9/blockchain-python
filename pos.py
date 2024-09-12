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
    def __init__(self, index, previous_hash, timestamp, data, hash=None, nonce=0):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.hash = hash
        self.nonce = nonce

    def to_dict(self):
        return self.__dict__

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.pending_transactions = []
        self.latest_leader = None
        self.validators = []

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), "Genesis Block", "start_hash", 0)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, new_block, leader=False):
        if leader:
            new_block.previous_hash = self.get_latest_block().hash
            new_block.hash = self.calculate_hash(new_block.index, new_block.previous_hash, new_block.timestamp, new_block.data, new_block.nonce)
            self.chain.append(new_block)
        else:
            self.chain.append(new_block)

    def add_transaction(self, sender, recipient, amount):
        self.pending_transactions.append(f"{sender} sends {amount} coins to {recipient}")

    def calculate_hash(self, index, previous_hash, timestamp, data, nonce):
        value = str(index) + str(previous_hash) + str(timestamp) + str(data) + str(nonce)
        return hashlib.sha256(value.encode('utf-8')).hexdigest()
    
    def get_latest_block(self):
        return self.chain[-1]

    def validation(self):
        for i in range(2, len(self.chain)):
            if self.chain[i].previous_hash != self.chain[i-1].hash:
                return False
        return True
    
    def select_leader(self):
        if not self.validators:
            return None
        total_stake = sum(stake for _, stake in self.validators)
        weights = [stake/total_stake for _, stake in self.validators]
        leader = random.choices(self.validators, weights=weights)[0][0]
        return leader
    
    def update_leader(self, leader):
        self.latest_leader = leader

    def add_validator(self, address, stake):
        self.validators.append((address, stake))

class Node:
    def __init__(self, address, port, is_validator=False, stake=100):
        self.blockchain = Blockchain()
        self.peers = set()
        self.server = None
        self.stake = stake
        self.address = address
        self.port = port
        self.is_validator = is_validator
        if self.is_validator:
            self.blockchain.add_validator(self.address+':'+str(self.port), self.stake)
    
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
                    if not self.validate():
                        print("Invalid blockchain. Requesting chain from peers.")
                        self.broadcast({'type': 'decrease_stake', 'amount': 10, 'leader': self.blockchain.latest_leader})
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
                        response = {
                            'type': 'peer_status',
                            'is_validator': self.is_validator,
                            'stake': self.stake
                        }
                        conn.sendall(json.dumps(response).encode())
                elif message['type'] == 'leader_announcement':
                    try:
                        leader = message['leader']
                        self.blockchain.update_leader(leader)
                        print(f"Received leader announcement: {leader}")
                        self._add_block(leader)
                    except Exception as e:
                        print(f"Oops an error occured: {e}")

                elif message['type'] == 'decrease_stake':
                    amount = message['amount']
                    leader = message['leader']
                    if leader == self.address + ':' + str(self.port):
                        self.stake -= amount
                        print(f"Stake decreased by {amount}. New stake: {self.stake}")
    
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
    
    def validate(self):
        if self.is_validator:
            if self.blockchain.validation():
                print("Blockchain is valid")
                return True
            else:
                print("Blockchain is invalid")
                return False
        else:
            return True
    
    def announce_leader(self, leader):
        self.blockchain.update_leader(leader)
        self.broadcast({
            'type': 'leader_announcement',
            'leader': leader
        })
        print(f"Announced new leader: {leader}")
    
    def _add_block(self, leader):
        try:
            if self.is_validator and leader == self.address + ':' + str(self.port):
                print("I am the leader. Adding a new block...")
                self.blockchain.add_block(Block(
                    index=len(self.blockchain.chain),
                    previous_hash=self.blockchain.get_latest_block().hash,
                    timestamp=int(time.time()),
                    data="Block data"
                ), leader=True)
                self.broadcast({
                    'type': 'new_block',
                    'data': self.blockchain.get_latest_block().to_dict()
                })
            else:
                print("I am not the leader.")
        except Exception as e:
            print(f"Error adding block: {e}")

class NodeCmd(cmd.Cmd):
    prompt = 'blockchain> '

    def __init__(self, node):
        super(NodeCmd, self).__init__()
        self.node = node

    def do_viewvalidators(self, arg):
        """View the current validators"""
        if self.node.blockchain.validators:
            print("Current validators:")
            for validator in self.node.blockchain.validators:
                print(f"  - {validator[0]} with stake {validator[1]}")
        else:
            print("There are no validators.")
    
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
        try:
            recipient, amount = arg.split()
            amount = int(amount)
            self.node.blockchain.add_transaction(self.node.address, recipient, amount)
            self.node.broadcast({
                'type': 'new_transaction',
                'data': {
                    'sender': self.node.address + ':' + str(self.node.port),
                    'recipient': recipient,
                    'amount': amount
                }
            })
            leader = self.node.blockchain.select_leader()
            if leader:
                self.node.announce_leader(leader)
            print(f"Transaction added: {self.node.address} sends {amount} coins to {recipient}")
        except Exception as e:
            print(f"Error adding transaction: {e}")

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

                response = json.loads(s.recv(1024).decode())
                is_validator = response['is_validator']
                stake = response['stake']


            print(f"Successfully notified peer {address}:{port} to add us as a peer.")
            
            return (True, is_validator, stake)

        except Exception as e:
            print(f"Error notifying peer {address}:{port}: {e}")
            return (False, False, 0)
    
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
            
            res = self._notify_peer_to_add_us(address, port)
            if res[0]:
                self.node.add_peer(address, port)
                print(f"Peer added: {address}:{port}")

                if res[1]:
                    self.node.blockchain.add_validator(address+':'+str(port), res[2])
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
    
def run_node(address, port, is_validator):
    node = Node(address, port, is_validator)
    cli_thread = threading.Thread(target=NodeCmd(node).cmdloop, args=(f"Started CLI for {address}:{port}",))
    cli_thread.start()
    node.start()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <port> <is_validator>")
        sys.exit(1)
    
    address = "127.0.0.1"
    port = int(sys.argv[1])
    is_validator = sys.argv[2].lower() == 'true'
    
    run_node(address, port, is_validator)