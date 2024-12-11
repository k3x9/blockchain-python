# Activity Adjusted Stake Consensus Algorithm
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
        self.stakes = {}

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
        self.parameters = None
        self.active = 0
        self._is_running = True
        self.logs = []
        if is_validator:
            self.blockchain.validators.add(port)
            self.blockchain.stakes = {self.port: random.randint(1, 2**64)}
    
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
                # print(f"Failed to get stake from {address}:{port}: {e}")
                return 0
            
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
        # print("Stopping node...")
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
                    if self.is_validator:
                        self.blockchain.stakes = {self.port: random.randint(1, 2**64)}
                    else:
                        self.blockchain.stakes = {}
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
                        # print(f"Added peer: {peer_address}:{peer_port}")
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
                elif message['type'] == 'node_stake':
                    if message['id'] in self.messages_id:
                        conn.sendall(json.dumps({'stakes': self.blockchain.stakes}).encode())
                        return
                    # print(f"Stakes received from {addr}")
                    temp = {int(key): message['stakes'][key] for key in message['stakes']}
                    # print(f"{self.port} -> Received stakes: {temp}")
                    self.blockchain.stakes.update(temp)
                    # print(f"{self.port} -> Updated stakes: {self.blockchain.stakes}")
                    # print(f"Updated stakes: {self.blockchain.stakes}")
                    if len(self.messages_id) != 0:
                        max_msg_id = max(self.messages_id)
                    else:
                        max_msg_id = 0
                    self.broadcast({
                        'type': 'node_stake',
                        'stakes': self.blockchain.stakes,
                        'id': max_msg_id + 1
                    })
                    conn.sendall(json.dumps({'stakes': self.blockchain.stakes}).encode())

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
                elif message['type'] == 'node_stake':
                    response_data = s.recv(4096)
                    # print(f"Received stakes response, message id: {message['id']}")
                    response = json.loads(response_data.decode())
                    temp = {int(key): response['stakes'][key] for key in response['stakes']}
                    # print(f"{self.port} -> Received stakesRR: {temp}")
                    self.blockchain.stakes.update(temp)
                    # print(f"{self.port} -> Updated stakes: {self.blockchain.stakes}")
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

    def POS(self, message):
        # print(f"{self.port} Leader {message['leader']}")
        if message['leader'] == self.port:
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
            self.broadcast({
                'type': 'new_block',
                'data': block.to_dict(),
                'id': max_msg_id + 1
            })
        else:
            # print(f"Node {message['leader']} is the leader")
            pass

    def score(self, params):
        """
        Consensus Score (CS) = [α * AIST * (1 - CST/TST) * log(1 + 1/LIT)] / [β * (CBM + 1)]
        """
        alpha = 3
        beta = 1
        aist = params['aist']
        cst = params['cst']
        tst = params['tst']
        lit = params['lit']
        cbm = params['cbm']
        
        if cst == 0:
            aist = len(self.blockchain.validators) * 2
        if cst == 1:
            aist = len(self.blockchain.validators)

        CS = (alpha * aist * (1 - cst/tst) * np.log(1 + 1/(lit + 0.000001))) / (beta * (cbm + 1)**2)
        # CS = (alpha * params['aist'] * (1 - params['cst']/params['tst']) * np.log(1 + 1/params['lit'])) / (beta * (params['cbm'] + 1))
        return CS
    
    def number_calculation(self):
        xored = 0
        # print(f"STAKES: {self.blockchain.stakes}")
        log = f"STAKES: {self.blockchain.stakes}"
        self.logs.append(log)
        for i in self.blockchain.stakes.values():
            xored ^= i
        xored /= 2**64
        log = f"XORED: {xored}"
        self.logs.append(log)
        return xored
    
    def mine(self, message=None):
        """
        Activity Adjusted Stake Consensus (AASC) mining function
        """
        if self.parameters == None:
            self.parameters = {port : {'ss': 0, 'lit': 0, 'aist': 0, 'cst': 0, 'tst': 0, 'cbm': 0} for port in self.blockchain.validators}
        
        # print(f"{self.port} Blockchain length: {len(self.blockchain.chain)}")
        if len(self.blockchain.chain) <= 3:
            self.POS(message)
            return
        
        # print("\n\n")
        # print("Mining new block using AASC...")
        block_pos = len(self.blockchain.chain) - 3
        mined_by = self.blockchain.chain[block_pos].mined_by
        self.parameters[mined_by]['aist'] = (self.parameters[mined_by]['aist'] * self.parameters[mined_by]['cst'] + block_pos + 1 - self.parameters[mined_by]['lit']) / (self.parameters[mined_by]['cst'] + 1)
        self.parameters[mined_by]['cst'] += 1
        self.parameters[mined_by]['tst'] = block_pos + 1 - self.active
        self.parameters[mined_by]['lit'] = block_pos + 1
        self.parameters[mined_by]['cbm'] += 1
        for port in self.blockchain.validators:
            if port != mined_by:
                self.parameters[port]['cbm'] = 0
                self.parameters[port]['tst'] = block_pos + 1 - self.active

        # print(f"Parameters: {self.parameters}")
        CS = {val: self.score(self.parameters[val]) for val in self.blockchain.validators}
        # print(f"{self.port} Consensus Scores: {CS}")
        PORTS = sorted(list(self.blockchain.validators))
        VALS = [CS[port] for port in PORTS]
        CUMMULATIVE = np.cumsum(VALS)
        CUMMULATIVE /= CUMMULATIVE[-1]
        # print(f"{self.port} VALS: {VALS}")
        # print(f"{self.port} CUMMULATIVE: {CUMMULATIVE}")
        log = f"{self.port} VALS: {VALS}"
        self.logs.append(log)
        log = f"{self.port} CUMMULATIVE: {CUMMULATIVE}"
        self.logs.append(log)

        value = self.number_calculation()
        block_producer_index = np.searchsorted(CUMMULATIVE, value)
        block_producer = PORTS[block_producer_index]
        # print(f"{self.port} Block producer: {block_producer}")

        if self.port == block_producer:
            latest_block = self.blockchain.get_latest_block()
            block = Block(len(self.blockchain.chain), latest_block.hash, int(time.time()), self.blockchain.pending_transactions, "", 0, self.port)
            self.blockchain.pending_transactions = []
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

class NodeCLI(cmd.Cmd):
    prompt = 'blockchain> '

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.response = None

    def do_params(self, arg):
        """View the current parameters"""
        print(f"Parameters: {self.node.parameters}")
    
    def do_messages(self, arg):
        """View the current messages"""
        print(f"Messages: {self.node.messages_id}")

    def do_scores(self, arg):
        """View the current scores"""
        params = self.node.parameters
        scores = {port: self.node.score(params[port]) for port in params}
        print(f"Scores: {scores}")

    def do_count(self, arg):
        """Count the number of blocks in the blockchain"""
        return len(self.node.blockchain.chain)

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
        print(f"Validators: {self.node.blockchain.validators}")
        
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

    def do_logs(self, arg):
        """View the logs"""
        for log in self.node.logs:
            print(log)

    def do_addtx(self, arg):
        """Add a new transaction: addtx <recipient> <amount>"""
        try:
            recipient, amount = arg.split()
            amount = int(amount)
            if len(self.node.blockchain.chain) <= 3:
                leader = self.node.select_leader()
            else: 
                leader = None
            # self.node.blockchain.add_transaction(self.node.address, recipient, amount)
            if len(self.node.messages_id) != 0:
                max_msg_id = max(self.node.messages_id)
            else:
                max_msg_id = 0
            
            if len(self.node.blockchain.chain) > 3:
                self.node.broadcast({
                    'type': 'node_stake',
                    'stakes' : self.node.blockchain.stakes,
                    'id': max_msg_id + 1
                })

                
                max_msg_id = max(self.node.messages_id)
                self.node.broadcast({
                    'type': 'node_stake',
                    'stakes' : self.node.blockchain.stakes,
                    'id': max_msg_id + 1
                })

            # print(self.node.blockchain.stakes)

            max_msg_id = max(self.node.messages_id)
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
            # print("Invalid input. Use format: addtx <recipient> <amount>")
            pass

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

            # print(f"Successfully notified peer {address}:{port} to add us as a peer.")
            return True

        except Exception as e:
            # print(f"Error notifying peer {address}:{port}: {e}")
            return False
    def do_resources(self, arg):
        cpu_usage = psutil.cpu_percent()
        per_core_usage = sum(psutil.cpu_percent(percpu=True))/psutil.cpu_count()
        physical_cores = psutil.cpu_count(logical=False)
        logical_cpus = psutil.cpu_count(logical=True)
        res = {
            'cpu_usage': cpu_usage,
            'per_core_usage': per_core_usage,
            'physical_cores': physical_cores,
            'logical_cpus': logical_cpus
        }
        return res

    def do_mine(self, arg):
        """Mine a new block"""
        if self.node.is_validator:
            # print("Mining a new block...")
            self.node.mine()
            # print("Block mined and added to the chain.")
        else:
            # print("This node is not a miner.")
            pass

    def do_addpeer(self, arg):
        """Add a new peer: addpeer <address> <port>"""
        try:
            address, port = arg.split()
            port = int(port)
            if (address, port) in self.node.peers:
                # print("This peer is already connected.")
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

                # print(f"Peer added: {address}:{port}")
            else:
                # print(f"Failed to add peer: {address}:{port}")
                pass
            
        except ValueError:
            # print("Invalid input. Use format: addpeer <address> <port>")
            pass

    def do_listpeers(self, arg):
        """List all peers"""
        if self.node.peers:
            print("Connected peers:")
            for peer in self.node.peers:
                print(f"  - {peer[0]}:{peer[1]}")
        else:
            print("This node has no connected peers.")

    def do_add(self, arg):
        """Add this node to the PoEM model"""
        global poem_model
        if self.node.is_validator:
            poem_model.add_node(self.node)
            print(f"Added node {self.node.address}:{self.node.port} to PoEM model")
    
    def do_listnodes(self, arg):
        """List all nodes in the PoEM model"""
        global poem_model
        if poem_model.nodes:
            print("Nodes in PoEM model:")
            for node in poem_model.nodes:
                print(f"  - {node.address}:{node.port}")
        else:
            print("No nodes in PoEM model")
    
    def do_exit(self, arg):
        """Exit the CLI"""
        self.node.stop()
        return True

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
    
    run_node(address, port, is_validator)
