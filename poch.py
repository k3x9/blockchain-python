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
    def __init__(self, index, previous_hash, timestamp, data, hash, nonce, mined_by=None):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.hash = hash
        self.nonce = nonce
        self.mined_by = mined_by

    def to_dict(self):
        return self.__dict__

class Blockchain:
    def __init__(self, difficulty=4):
        self.chain = [self.create_genesis_block()]
        self.difficulty = difficulty
        self.pending_transactions = []
        self.target = 2**256 - 1
        self.c_val = self.calculate_hash(self.chain[-1].index, self.chain[-1].hash, 0)
        self.candidancies = {}

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
        temp = ''.join(str(arg) for arg in args)
        return hashlib.sha256(str(temp).encode('utf-8')).hexdigest()

    def add_transaction(self, sender, recipient, amount):
        self.pending_transactions.append(f"{sender} sends {amount} coins to {recipient}")

    def update_c_val(self):
        self.c_val = self.calculate_hash(str(self.chain[-1].index) + self.chain[-1].hash + str(len(self.pending_transactions)))

    def update_target(self, nbr_cand):
        self.target = self.target/math.log10(nbr_cand + 1)

class Node:
    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.blockchain = Blockchain()
        self.peers = set()
        self.id = port
        self.candidacies = []
        self.new_block_received = False
        self.failed_consensus_received = False
        self.messages_id = set()
        self.blockchain.candidancies = {self.port : self.id}
        self._is_running = True

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.address, self.port))
            s.listen()
            # print(f"Node listening on {self.address}:{self.port}")
            with ThreadPoolExecutor(max_workers=10) as executor:
                while self._is_running:
                    conn, addr = s.accept()
                    executor.submit(self.handle_connection, conn, addr)

    def stop(self):
        # print("Stopping node...")
        self._is_running = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as dummy_sock:
            dummy_sock.connect((self.address, self.port))

    # def handle_connection(self, conn, addr):
    #     with conn:
    #         data = conn.recv(1024)
    #         print(data)
            
    #         if data:
    #             message = json.loads(data.decode())
    #             if message['type'] == 'new_block':
    #                 new_block = Block(**message['data'])
    #                 self.blockchain.add_block(new_block)
    #             elif message['type'] == 'new_transaction':
    #                 self.blockchain.add_transaction(**message['data'])
    #             elif message['type'] == 'get_chain':
    #                 chain_data = [block.to_dict() for block in self.blockchain.chain]
    #                 conn.sendall(json.dumps(chain_data).encode())
    #             elif message['type'] == 'add_peer':
    #                 peer_address = message['address']
    #                 peer_port = message['port']
    #                 if (peer_address, peer_port) not in self.peers:
    #                     self.add_peer(peer_address, peer_port)
    #                     print(f"Added peer: {peer_address}:{peer_port}")
    #             elif message['type'] == 'candidacy':
    #                 self.handle_candidacy(message['id'])

    def handle_connection(self, conn, addr):
        with conn:
            data = conn.recv(4096)
            if data:
                message = json.loads(data.decode())
                if message['type'] == 'new_block':
                    self.blockchain.pending_transactions = []
                    self.probabilities = set()
                    self.blockchain.c_val = message['cval']
                    self.blockchain.target = message['target']
                    # print(message['id'], self.messages_id)
                    if message['id'] in self.messages_id:
                        return
                    # print('Received new block')
                    new_block = Block(**message['data'])
                    new_block.previous_hash = self.blockchain.get_latest_block().hash
                    self.blockchain.chain.append(new_block)
                    # self.blockchain.add_block(new_block)

                    # print(f"Block added: {new_block.index}")
                    self.broadcast(message)
                elif message['type'] == 'candidacy':
                    self.handle_candidacy(message['id'])
                elif message['type'] == 'new_transaction':
                    if message['id'] in self.messages_id:
                        # print(f"Transaction message ID: {message['id']} already visited")
                        conn.sendall(json.dumps({'status': -1}))
                        return
                    # print('Received new transaction')
                    self.blockchain.add_transaction(**message['data'])
                    self.broadcast(message)
                    self.poch_consensus()
                    conn.sendall(json.dumps({'status': 1}))
                elif message['type'] == 'get_chain':
                    chain_data = [block.to_dict() for block in self.blockchain.chain]
                    conn.sendall(json.dumps(chain_data).encode())
                elif message['type'] == 'add_peer':
                    peer_address = message['address']
                    peer_port = message['port']
                    if (peer_address, peer_port) not in self.peers:
                        self.add_peer(peer_address, peer_port)
                        # print(f"Added peer: {peer_address}:{peer_port}")
                elif message['type'] == 'get_stake':
                    stake = random.randint(1, 100)
                    conn.sendall(json.dumps({'stake': stake}).encode())
                elif message['type'] == 'model_update':
                    self.handle_model_update(message['data'])
                elif message['type'] == 'get_model':
                    self.send_model(conn)
                elif message['type'] == 'store_candidancies':
                    if message['id'] in self.messages_id:
                        conn.sendall(json.dumps({'candidancies': list(self.blockchain.candidancies)}).encode())
                        return
                    # print(f"Store candidancies called from {addr}")
                    temp = {int(k): v for k, v in message['candidancies'].items()}
                    self.blockchain.candidancies.update(temp)
                    # print(f"After message: {self.blockchain.candidancies}")
                    if len(self.messages_id) != 0:
                        max_msg_id = max(self.messages_id)
                    else:
                        max_msg_id = 0
                    self.broadcast({
                        'type': 'store_candidancies',
                        'candidancies': self.blockchain.candidancies,
                        'id': max_msg_id + 1
                    })
                    
                    conn.sendall(json.dumps({'candidancies': self.blockchain.candidancies}).encode())
                elif message['type'] == 'probabilities':
                    if message['id'] in self.messages_id:
                        # print(f"Probabilities message ID: {message['id']} already visited, data: {eval(message['data'])}")
                        self.probabilities.update(eval(message['data']))
                        conn.sendall(json.dumps({'data': str(self.probabilities)}).encode())
                        return
                    # print(f"Probabilities received from {addr}")
                    self.probabilities.update(eval(message['data']))
                    # print(f"Updated probabilities: {self.probabilities}")
                    self.broadcast(message)
                    conn.sendall(json.dumps({'data': str(self.probabilities)}).encode())

    def add_peer(self, address, port):
        self.peers.add((address, port))
        
    def broadcast_transaction(self, sender, recipient, amount):
        # Broadcast the transaction to all peers
        transaction_data = {
            'type': 'new_transaction',
            'data': {
                'sender': sender,
                'recipient': recipient,
                'amount': amount
            }
        }
        message = json.dumps(transaction_data).encode()
        for peer in self.peers:
            peer_address, peer_port = peer
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((peer_address, peer_port))
                    s.sendall(message)
            except Exception as e:
                print(f"Failed to broadcast to {peer_address}:{peer_port} - {str(e)}")

    @staticmethod
    def calculate_hash(*args):
        temp = ''.join(str(arg) for arg in args)
        return hashlib.sha256(str(temp).encode('utf-8')).hexdigest()

    def poch_consensus(self):
        # print("Starting PoCh consensus...")
        tv = int(self.calculate_hash(int(self.blockchain.c_val, 16) + self.id), 16)
        # print(f"{self.port} -> {tv} <= {self.blockchain.target}")
        # print(tv <= self.blockchain.target)
        while True:
            # Wait for p1 time and collect candidacies
            # time.sleep(2)  # p1 waiting time
            p_candidacies = self.blockchain.candidancies.copy()
            candidacies = [v for k, v in p_candidacies.items() if int(self.calculate_hash(int(self.blockchain.c_val, 16) + v), 16) <= self.blockchain.target]
            
            if len(candidacies) > 15:
                # print("Too many candidacies. Restarting consensus...")
                # time.sleep(2)
                self.blockchain.update_target(len(candidacies))
                continue
            
            if len(candidacies) < 6:
                # print("Too few candidacies. Restarting consensus...")
                # time.sleep(2)
                self.blockchain.update_target(len(candidacies))
                continue
            
            if 6 <= len(candidacies) <= 15:
                result = 0
                d = 1
                sorted_candidates = sorted(candidacies)
                while result == 0:
                    result = (self.blockchain.chain[-1].index + sum(cand**d for cand in sorted_candidates)) % (len(candidacies) + 1)
                    d += 1
                
                if self.id == sorted_candidates[result - 1]:
                    # print(f"{self.port} -> I am the winner!")
                    latest_block = self.blockchain.get_latest_block()
                    block = Block(len(self.blockchain.chain), latest_block.hash, int(time.time()), self.blockchain.pending_transactions, "", random.randint(0, 1000), self.port)
                    self.blockchain.pending_transactions = []
                    self.blockchain.add_block(block)
                    # print(f"Block mined by {self.port}")
                    if len(self.messages_id) != 0:
                        max_msg_id = max(self.messages_id)
                    else:
                        max_msg_id = 0
                    self.blockchain.update_c_val()
                    self.blockchain.update_target(len(candidacies))
                    self.broadcast({
                        'type': 'new_block',
                        'data': block.to_dict(),
                        'cval': self.blockchain.c_val,
                        'target': self.blockchain.target,
                        'id': max_msg_id + 1
                    })
                    # print("New block broadcasted.")
                
                break

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
        nonce = random.randint(0, 1000000)
        new_hash = self.calculate_hash(index, previous_hash, timestamp, data, nonce)

        new_block = Block(index, previous_hash, timestamp, data, new_hash, nonce)
        self.blockchain.pending_transactions = []
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

    # def process_incoming_messages(self):
    #     """Process incoming messages from peers"""
    #     try:
    #         with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    #             s.settimeout(0.1)  # Set a short timeout
    #             s.bind((self.address, self.port))
    #             while True:
    #                 try:
    #                     data, addr = s.recvfrom(1024)
    #                     message = json.loads(data.decode())
    #                     self.handle_message(message)
    #                 except socket.timeout:
    #                     break  # No more messages to process
    #     except Exception as e:
    #         print(f"Error processing messages: {e}")

    # def handle_message(self, message):
    #     """Handle different types of incoming messages"""
    #     if message['type'] == 'candidacy':
    #         self.candidacies.append(message['id'])
    #     elif message['type'] == 'new_block':
    #         new_block = Block(**message['data'])
    #         self.blockchain.add_block(new_block)
    #         self.new_block_received = True
    #     elif message['type'] == 'failed_consensus':
    #         self.blockchain.target = message['new_target']
    #         self.failed_consensus_received = True
    
    def broadcast_to_peer(self, peer, message):
        # print(f"Broadcasting to peer {peer}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(peer)
                # print(f"Connected to peer {peer}")
                if(message['type'] == 'probabilities'):
                    # print(f"Message : {message}")
                    pass
                s.sendall(json.dumps(message).encode())
                if message['type'] == 'store_candidancies':
                    response_data = s.recv(4096)
                    # print(f"Received validators response, message id: {message['id']}")
                    response = json.loads(response_data.decode())
                    val = {int(k): v for k, v in response['candidancies'].items()}
                    self.blockchain.candidancies.update(val)
                    # print(f"Response from peer {peer}: {response}")
                elif message['type'] == 'new_transaction':
                    response_data = s.recv(4096)
                    # print(f"Received transaction response, message id: {message['id']}")
                elif message['type'] == 'probabilities':
                    response_data = s.recv(4096)
                    # print(f"Received probabilities response, message id: {message['id']}")
                    response = json.loads(response_data.decode())
                    self.probabilities.update(eval(response['data']))
                    # print(f"Probability Response from peer {peer}: {response}")
                    # print(f"Updated probabilities: {self.probabilities}")
            except Exception as e:
                # print(f"Failed to connect to peer {peer}: {e}")
                pass
            finally:
                self.visited = False

    def broadcast(self, message):
        if message['id'] in self.messages_id:
            # print(f"Cannot broadcast message with ID {message['id']} and type {message['type']}")
            return
        # print(f"Messaged ID: {self.messages_id}")
        self.messages_id.add(message['id'])
        # print(f"Messaged ID: {self.messages_id}")
        # print(f"Broadcasting message type: {message['type']}")
        with ThreadPoolExecutor() as executor:
            executor.map(lambda peer: self.broadcast_to_peer(peer, message), self.peers)

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

    def do_listpendingtx(self, arg):
        print(self.node.blockchain.pending_transactions)

    def do_cval(self, arg):
        """Store the candidancies"""
        if len(self.node.messages_id) != 0:
            max_msg_id = max(self.node.messages_id)
        else:
            max_msg_id = 0
        self.node.broadcast({
            'type': 'store_candidancies',
            'candidancies': self.node.blockchain.candidancies,
            'id': max_msg_id + 1
        })
        # print("\n\nDONE\n\n")
        max_msg_id = max(self.node.messages_id)
        self.node.broadcast({
            'type': 'store_candidancies',
            'candidancies': self.node.blockchain.candidancies,
            'id': max_msg_id + 1
        })
    
    def do_cand(self, arg):
        print(self.node.blockchain.candidancies)

    def do_addtx(self, arg):
        """Add a new transaction: addtx <recipient> <amount>"""
        try:
            recipient, amount = arg.split()
            amount = int(amount)
            if len(self.node.messages_id) != 0:
                max_msg_id = max(self.node.messages_id)
            else:
                max_msg_id = 0
            time.sleep(1)
            # print(f"Brodcasting from {self.node.port}")
            self.node.blockchain.add_transaction(str(self.node.address) + str(self.node.port), recipient, amount)
            self.node.broadcast({
                'type': 'new_transaction',
                'data': {
                    'sender': str(self.node.address) + str(self.node.port),
                    'recipient': recipient,
                    'amount': amount
                },
                'id': max_msg_id + 1
            })
            self.node.poch_consensus()
            # print(f"Transaction added: {str(self.node.address) + str(self.node.port)} sends {amount} coins to {recipient}")
        except ValueError:
            print("Invalid input. Use format: addtx <recipient> <amount>")

    def do_consensus(self, arg):
        """Initiate the PoCh consensus algorithm"""
        print("HERE")
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
                # print("Cannot connect to self.")
                return
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                try:
                    s.connect((address, port))
                except Exception as e:
                    # print(f"Failed to connect to peer {address}:{port}: {e}")
                    return
            
            if self._notify_peer_to_add_us(address, port):
                self.node.add_peer(address, port)
                # print(f"Peer added: {address}:{port}")
            else:
                # print(f"Failed to add peer: {address}:{port}")
                pass
            
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

            # print(f"Successfully notified peer {address}:{port} to add us as a peer.")
            return True

        except Exception as e:
            # print(f"Error notifying peer {address}:{port}: {e}")
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
        self.node.stop()
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