import random
import numpy as np
from sklearn.linear_model import LogisticRegression
import joblib
import socket
import io
import json
import numpy as np
import hashlib
import time
import cmd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys
import psutil


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
        self.validators = set()

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), "Genesis Block", self.calculate_hash(0, "0", int(time.time()), "Genesis Block", 0), 0)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, new_block):
        new_block.previous_hash = self.get_latest_block().hash
        new_block.hash = self.calculate_hash(new_block.index, new_block.previous_hash, new_block.timestamp, new_block.data, new_block.nonce)
        self.chain.append(new_block)
        # print(len(self.chain))

    @staticmethod
    def calculate_hash(index, previous_hash, timestamp, data, nonce):
        value = str(index) + str(previous_hash) + str(timestamp) + str(data) + str(nonce)
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def add_transaction(self, sender, recipient, amount):
        self.pending_transactions.append(f"{sender} sends {amount} coins to {recipient}")

    

    def mine_pending_transactions(self, leader = 0):
        global poem_model
        # print("Entered mine_pending_transactions function")
        # if poem_model.version <= 5:
        #     print("PoEM model not trained yet. Mining with PoS...")
        #     poem_model.features.extend([poem_model.extract_features(node, self) for node in poem_model.nodes])
        #     labels = np.zeros(len(poem_model.nodes))


        #     print(poem_model.nodes)
        #     nounces_blocks = []
        #     for node in poem_model.nodes:
        #         block = Block(len(node.blockchain.chain), node.blockchain.get_latest_block().hash, int(time.time()), node.blockchain.pending_transactions, "", 0)
        #         nonce = 0
        #         while True:
        #             hash = self.calculate_hash(block.index, block.previous_hash, block.timestamp, block.data, nonce)
        #             print(nonce, end='\r')
        #             if hash.startswith('0' * 1):
        #                 break
        #             nonce += 1
        #         nounces_blocks.append((nonce, block))
        #     # nounces_blocks = [node.proof_of_work() for node in poem_model.nodes]
        #     print("PoW done")
        #     nounces = [nounce_block[0] for nounce_block in nounces_blocks]
        #     blocks = [nounce_block[1] for nounce_block in nounces_blocks]
        #     selected_node_index = np.argmax(nounces)
        #     print(f"Selected node index: {selected_node_index}")
        #     selected_node = poem_model.nodes[selected_node_index]
        #     block = blocks[selected_node_index]

        #     labels[selected_node_index] = 1
        #     poem_model.labels.extend(labels)
        #     poem_model.version += 1
        #     if poem_model.version == 5:
        #         poem_model.train()
        #         time.sleep(2)
        #         print("PoEM model trained")
            
        #     self.chain.append(block)
        #     self.pending_transactions = [f"Miner Reward: {selected_node.address} receives 1 coin"]
        #     return selected_node

        # Use PoEM to select the block producer
        
        features = [poem_model.extract_features(node, self) for node in poem_model.nodes]
        print(features)
        try:
            probabilities = poem_model.predict(features)
        except ValueError:
            print("Error predicting probabilities")
            return None
        print(probabilities)
        selected_node_index = np.argmax(probabilities)
        selected_node = poem_model.nodes[selected_node_index]

        block = Block(len(self.chain), self.get_latest_block().hash, int(time.time()), self.pending_transactions, "", selected_node_index)
        block.hash = self.calculate_hash(block.index, block.previous_hash, block.timestamp, block.data, block.nonce)
        self.chain.append(block)
        self.pending_transactions = [f"Miner Reward: {selected_node.address} receives 1 coin"]

        # Update the PoEM model
        X = np.array(features)
        y = np.zeros(len(poem_model.nodes))
        y[selected_node_index] = 1
        poem_model.update(X, y)

        return selected_node
            
    def verify_model(self, new_model):
        # Generate test data from current blockchain state
        test_features = [self.poem_model.extract_features(node, self) for node in self.nodes]
        test_data = np.array(test_features)
        
        # Verify the new model
        return new_model.verify(test_data)

class PoEMModel:
    def __init__(self):
        self.model = LogisticRegression()
        self.nodes = []
        self.features = []
        self.labels = []
        self.version = 0
        self.difficulty = 4

    def serialize(self):
        model_data = {
            'version': self.version,
            'model': joblib.dumps(self.model)
        }
        return model_data
    
    def train(self):
        # print(f"Lenght of features: {len(self.features)}")
        # print(f"Lenght of labels: {len(self.labels)}")
        if len(self.features) > 0 and len(self.labels) > 0:
            X = np.array(self.features)
            y = np.array(self.labels)
            # print(f"Training model with {len(X)} samples...")
            # print(X)
            # print(y)
            self.model.fit(X, y)
            # print("Model traineddddd")
            self.version += 1
            # print(f"Model trained. New version: {self.version}")

    def predict(self, X):
        return self.model.predict_proba(X)[:, 1]

    def update(self, new_X, new_y):
        self.features.extend(new_X.tolist())
        self.labels.extend(new_y.tolist())
        if self.version == 0:
            self.train()
        else:
            self.model.partial_fit(new_X, [new_y])
            self.version += 1

    def extract_features(self, node, blockchain):
        return [
            len(blockchain.chain),
            len(node.peers),
            1 if node.is_validator else 0,
            len(blockchain.pending_transactions)
        ]

    def add_node(self, node):
        if node not in self.nodes:
            self.nodes.append(node)
            # print(f"Added node to PoEM model: {node.address}:{node.port}")

poem_model = PoEMModel()

class Node:
    def __init__(self, address, port, is_validator=False):
        self.address = address
        self.port = port
        self.blockchain = Blockchain()
        self.is_validator = is_validator
        self.peers = set()
        self.model_version = 0
        self.nodes = []
        self.difficulty = 4
        self.visited = False
        self.messages_id = set()
        self.probabilities = set()
        self._is_running = True
        global poem_model
        if is_validator:
            poem_model.add_node(self)
            self.blockchain.validators.add(port)
    
    def select_leader(self):
        if not self.blockchain.validators:
            return None
        
        stakes = [self.ask_stake('127.0.0.1', port) for port in self.blockchain.validators]
        total_stake = sum(stakes)
        weights = [stake/total_stake for stake in stakes]
        leader = random.choices(list(self.blockchain.validators), weights=weights)[0]
        return leader

    def ask_stake(self, address, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((address, port))
                s.sendall(json.dumps({'type': 'get_stake'}).encode())
                data = s.recv(4096)
                if data:
                    message = json.loads(data.decode())
                    return message['stake']
            except Exception as e:
                print(f"Failed to get stake from {address}:{port}: {e}")
                return 0
            
    def proof_of_work(self):
        block = Block(len(self.blockchain.chain), self.blockchain.get_latest_block().hash, int(time.time()), self.blockchain.pending_transactions, "", 0)
        nonce = 0
        while True:
            hash = self.calculate_hash(block.index, block.previous_hash, block.timestamp, block.data, nonce)
            print(hash)
            if hash.startswith('0' * self.difficulty):
                return (nonce, block)
            nonce += 1

    def add_node(self, node):
        self.nodes.append(node)

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
        print("Stopping node...")
        self._is_running = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as dummy_sock:
            dummy_sock.connect((self.address, self.port))

    def handle_connection(self, conn, addr):
        with conn:
            data = conn.recv(4096)
            if data:
                message = json.loads(data.decode())
                if message['type'] == 'new_block':
                    self.blockchain.pending_transactions = []
                    self.probabilities = set()
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
                elif message['type'] == 'new_transaction':
                    if message['id'] in self.messages_id:
                        # print(f"Transaction message ID: {message['id']} already visited")
                        conn.sendall(json.dumps({'status': -1}))
                        return
                    # print('Received new transaction')
                    self.blockchain.add_transaction(**message['data'])
                    self.broadcast(message)
                    if self.is_validator:
                        # print("Mining new block to include transaction...")
                        self.mine(message)
                    conn.sendall(json.dumps({'status': 1}))
                elif message['type'] == 'get_chain':
                    chain_data = [block.to_dict() for block in self.blockchain.chain]
                    conn.sendall(json.dumps(chain_data).encode())
                elif message['type'] == 'add_peer':
                    peer_address = message['address']
                    peer_port = message['port']
                    is_validator = message['is_validator']
                    if (peer_address, peer_port) not in self.peers:
                        if is_validator:
                            self.add_node((peer_address, peer_port))
                        self.add_peer(peer_address, peer_port)
                        print(f"Added peer: {peer_address}:{peer_port}")
                        response = {
                            'is_validator': self.is_validator,
                            'nodes': self.nodes
                        }
                elif message['type'] == 'get_stake':
                    stake = random.randint(1, 100)
                    conn.sendall(json.dumps({'stake': stake}).encode())
                elif message['type'] == 'model_update':
                    self.handle_model_update(message['data'])
                elif message['type'] == 'get_model':
                    self.send_model(conn)
                elif message['type'] == 'store_validators':
                    if message['id'] in self.messages_id:
                        conn.sendall(json.dumps({'validators': list(self.blockchain.validators)}).encode())
                        return
                    # print(f"Store validators called from {addr}")
                    self.blockchain.validators = self.blockchain.validators.union(set(message['validators']))
                    # print(f"After message: {self.blockchain.validators}")
                    if len(self.messages_id) != 0:
                        max_msg_id = max(self.messages_id)
                    else:
                        max_msg_id = 0
                    self.broadcast({
                        'type': 'store_validators',
                        'validators': list(self.blockchain.validators),
                        'id': max_msg_id + 1
                    })
                    
                    conn.sendall(json.dumps({'validators': list(self.blockchain.validators)}).encode())
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

    def calculate_probabilities(self):
        cpu_usage = psutil.cpu_percent()
        per_core_usage = sum(psutil.cpu_percent(percpu=True))/psutil.cpu_count()
        physical_cores = psutil.cpu_count(logical=False)
        logical_cpus = psutil.cpu_count(logical=True)
        # print(f"CPU Usage: {cpu_usage}, Per Core Usage: {per_core_usage}, Physical Cores: {physical_cores}, Logical CPUs: {logical_cpus}")
        poem_model.features.append([cpu_usage, per_core_usage, physical_cores, logical_cpus])
        proba = poem_model.predict([[cpu_usage, per_core_usage, physical_cores, logical_cpus]])[0]
        # print(f"Probability: {proba}")
        self.probabilities.add((proba, self.port))
        return proba
    
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
                if message['type'] == 'store_validators':
                    response_data = s.recv(4096)
                    # print(f"Received validators response, message id: {message['id']}")
                    response = json.loads(response_data.decode())
                    self.blockchain.validators = self.blockchain.validators.union(set(response['validators']))
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
            
            # for future in as_completed(future_to_peer):
            #     result = future.result()
            
    
    def add_peer(self, address, port):
        self.peers.add((address, port))

    def handle_model_update(self, model_data):
        if model_data['version'] > self.model_version:
            new_model = PoEMModel()
            new_model.deserialize(model_data)
            
            # Verify the new model
            test_data = np.random.rand(10, 4)  # Generate some random test data
            if new_model.verify(test_data):
                self.blockchain.poem_model = new_model
                self.model_version = model_data['version']
                # print(f"Updated to model version {self.model_version}")
            else:
                # print("Model verification failed")
                pass

    def send_model(self, conn):
        model_data = self.blockchain.poem_model.serialize()
        conn.sendall(json.dumps({'type': 'model_update', 'data': model_data}).encode())

    def synchronize_model(self):
        for peer in self.peers:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect(peer)
                    s.sendall(json.dumps({'type': 'get_model'}).encode())
                    data = s.recv(4096)
                    if data:
                        message = json.loads(data.decode())
                        if message['type'] == 'model_update':
                            self.handle_model_update(message['data'])
                except Exception as e:
                    print(f"Failed to synchronize model with peer {peer}: {e}")

    def mine(self, message = None):
        # print("\n")
        # print("Entered mine function")
        if self.is_validator:
            # print("I am a validator")
            leader = message['leader']
            if poem_model.version < 100:
                if leader != self.port:
                    cpu_usage = psutil.cpu_percent()
                    per_core_usage = sum(psutil.cpu_percent(percpu=True))/psutil.cpu_count()
                    physical_cores = psutil.cpu_count(logical=False)
                    logical_cpus = psutil.cpu_count(logical=True)
                    poem_model.features.append([cpu_usage, per_core_usage, physical_cores, logical_cpus])
                    poem_model.labels.append(0)
                else:
                    # print("Mining new block...")
                    latest_block = self.blockchain.get_latest_block()
                    block = Block(len(self.blockchain.chain), latest_block.hash, int(time.time()), self.blockchain.pending_transactions, "", 0, self.port)
                    self.blockchain.pending_transactions = []
                    self.blockchain.add_block(block)
                    # print(f"Block mined by {self.port}")
                    if len(self.messages_id) != 0:
                        max_msg_id = max(self.messages_id)
                    else:
                        max_msg_id = 0
                    cpu_usage = psutil.cpu_percent()
                    per_core_usage = sum(psutil.cpu_percent(percpu=True))/psutil.cpu_count()
                    physical_cores = psutil.cpu_count(logical=False)
                    logical_cpus = psutil.cpu_count(logical=True)
                    poem_model.features.append([cpu_usage, per_core_usage, physical_cores, logical_cpus])
                    poem_model.labels.append(1)
                    self.broadcast({
                        'type': 'new_block',
                        'data': block.to_dict(),
                        'id': max_msg_id + 1
                    })
                poem_model.version += 1
                if poem_model.version == 100:
                    poem_model.train()
                    # print("PoEM model trained")
            else:
                # print("Using PoEM model to mine...")
                proba = self.calculate_probabilities()
                # print(f"Probability: {proba}")
                if len(self.messages_id) != 0:
                    max_msg_id = max(self.messages_id)
                else:
                    max_msg_id = 0

                self.broadcast({
                    'type': 'probabilities',
                    'data': str(self.probabilities),
                    'id': max_msg_id + 1
                })

                max_pair = max(self.probabilities, key=lambda x: x[0])
                self.probabilities = set()
                # print(f"Max pair: {max_pair}")
                if max_pair[1] == self.port:
                    poem_model.labels.append(1)
                    # print("Mining new block...")
                    latest_block = self.blockchain.get_latest_block()
                    block = Block(len(self.blockchain.chain), latest_block.hash, int(time.time()), self.blockchain.pending_transactions, "", 0, self.port)
                    self.blockchain.add_block(block)
                    # print(f"Block mined by {self.port}")
                    if len(self.messages_id) != 0:
                        max_msg_id = max(self.messages_id)
                    else:
                        max_msg_id = 0
                    self.broadcast({
                        'type': 'new_block',
                        'data': block.to_dict(),
                        'id': max_msg_id + 1
                    })
                else:
                    poem_model.labels.append(0)
                self.probabilities = set()
                # print("\n")
                return True
            # print("\n")
            # else:
            #     selected_node = self.blockchain.mine_pending_transactions()
            #     print(f"Block mined by {selected_node.address}")
            #     print(f"Selected node port: {selected_node.port}")
            #     print(f"My port: {self.port}")
            #     if selected_node.port == self.port:
            #         latest_block = self.blockchain.get_latest_block()
            #         if len(self.messages_id) != 0:
            #             max_msg_id = max(self.messages_id)
            #         else:
            #             max_msg_id = 0
            #         self.broadcast({
            #             'type': 'new_block',
            #             'data': latest_block.to_dict(),
            #             'id': max_msg_id + 1
            #         })
            #         return True
        return False
    

class NodeCLI(cmd.Cmd):
    prompt = 'blockchain> '

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.response = None

    def do_sval(self, arg):
        """Store the validators"""
        if len(self.node.messages_id) != 0:
            max_msg_id = max(self.node.messages_id)
        else:
            max_msg_id = 0
        self.node.broadcast({
            'type': 'store_validators',
            'validators': list(self.node.blockchain.validators),
            'id': max_msg_id + 1
        })
        # print("\n\nDONE\n\n")
        max_msg_id = max(self.node.messages_id)
        self.node.broadcast({
            'type': 'store_validators',
            'validators': list(self.node.blockchain.validators),
            'id': max_msg_id + 1
        })
        # print("\n\nDONE\n\n")
    
    def do_val(self, arg):
        """View the validators"""
        # print(f"Validators: {self.node.blockchain.validators}")
    
    def do_train(self, arg):
        """Train the PoEM model"""
        poem_model.train()

    def do_syncmodel(self, arg):
        """Synchronize the PoEM model with peers"""
        # print("Synchronizing PoEM model with peers...")
        self.node.synchronize_model()
        # print("Model synchronization complete.")

    def do_viewchain(self, arg):
        """View the current state of the blockchain"""
        for block in self.node.blockchain.chain:
            print(f"Block {block.index}:")
            print(f"  Timestamp: {block.timestamp}")
            print(f"  Data: {block.data}")
            print(f"  Hash: {block.hash}")
            print(f"  Previous Hash: {block.previous_hash}")
            print(f"  Mined by: {block.mined_by}")
            print()

    def do_addtx(self, arg):
        """Add a new transaction: addtx <recipient> <amount>"""
        try:
            recipient, amount = arg.split()
            amount = int(amount)
            leader = self.node.select_leader()
            # self.node.blockchain.add_transaction(self.node.address, recipient, amount)
            if len(self.node.messages_id) != 0:
                max_msg_id = max(self.node.messages_id)
            else:
                max_msg_id = 0
            self.node.broadcast({
                'type': 'new_transaction',
                'data': {
                    'sender': str(self.node.address) + str(self.node.port),
                    'recipient': recipient,
                    'amount': amount
                },
                'leader': leader,
                'id': max_msg_id + 1
            })
            # print(f"Transaction added: {str(self.node.address) + str(self.node.port)} sends {amount} coins to {recipient}")
        except ValueError:
            print("Invalid input. Use format: addtx <recipient> <amount>")

    def _notify_peer_to_add_us(self, address, port):
        """Notify the peer to add this node as a peer"""
        try:
            message = {
                'type': 'add_peer',
                'address': self.node.address,
                'port': self.node.port,
                'is_validator': self.node.is_validator
            }

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((address, port))
                s.sendall(json.dumps(message).encode())

                response = s.recv(4096)
                if response:
                    response = json.loads(response.decode())
                    self.response = response

            print(f"Successfully notified peer {address}:{port} to add us as a peer.")
            return True

        except Exception as e:
            # print(f"Error notifying peer {address}:{port}: {e}")
            return False

    def do_mine(self, arg):
        """Mine a new block"""
        if self.node.is_validator:
            # print("Mining a new block...")
            self.node.mine()
            # print("Block mined and added to the chain.")
        else:
            pass
            # print("This node is not a miner.")

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
                response = self.response
                if response and response['is_validator']:
                    self.node.add_node((address, port))

                print(f"Peer added: {address}:{port}")
            else:
                # print(f"Failed to add peer: {address}:{port}")
                pass
            
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
        self.node.stop()
        return True

    def do_add(self, arg):
        """Add this node to the PoEM model"""
        global poem_model
        if self.node.is_validator:
            poem_model.add_node(self.node)
            # print(f"Added node {self.node.address}:{self.node.port} to PoEM model")
    
    def do_listnodes(self, arg):
        """List all nodes in the PoEM model"""
        global poem_model
        if poem_model.nodes:
            print("Nodes in PoEM model:")
            for node in poem_model.nodes:
                print(f"  - {node.address}:{node.port}")
        else:
            print("No nodes in PoEM model")

def run_node(address, port, is_validator):
    node = Node(address, port, is_validator)
    cli_thread = threading.Thread(target=NodeCLI(node).cmdloop, args=(f"Started CLI for {address}:{port}",))
    cli_thread.daemon = True
    cli_thread.start()
    node.start()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <port> <is_validator>")
        sys.exit(1)
    
    address = "127.0.0.1"
    port = int(sys.argv[1])
    is_validator = sys.argv[2].lower() == "true"
    
    poem_model = PoEMModel()
    run_node(address, port, is_validator)
