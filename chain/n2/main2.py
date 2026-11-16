# main.py
import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel
import hashlib, json, time, threading, requests, uuid
import os
from typing import List, Dict
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError

# -------------------- Config --------------------
with open('config2.json') as f:
    config = json.load(f)

NODE_TYPE = config['node_type']
PRIVATE_KEY = SigningKey.from_string(bytes.fromhex(config['private_key']), curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.verifying_key.to_string().hex()
VALIDATOR_KEYS = set(config['validator_keys'])
BOOTSTRAP_NODE = config['bootstrap_node']
HOP_LIMIT = config['hop_limit']
PORT = config['port']

# -------------------- Data Structures --------------------
app = FastAPI()
chain: List[Dict] = []
mempool: List[Dict] = []
nonces: Dict[str, int] = {}
seen_ids = set()
peers = set(config.get("known_peers", []))

# -------------------- Models --------------------
class Transaction(BaseModel):
    sender: str
    receiver: str
    amount: int
    nonce: int
    signature: str

# -------------------- Helper Functions --------------------
def hash_block(block):
    return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

def sign_block(block_data):
    block_bytes = json.dumps(block_data, sort_keys=True).encode()
    return PRIVATE_KEY.sign(block_bytes).hex()

def verify_signature(tx):
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(tx['sender']), curve=SECP256k1)
        msg = f"{tx['sender']}{tx['receiver']}{tx['amount']}{tx['nonce']}".encode()
        vk.verify(bytes.fromhex(tx['signature']), msg)
        return True
    except (BadSignatureError, Exception):
        return False

def calculate_balances():
    balances = {}
    nonces.clear()
    for block in chain:
        for tx in block['transactions']:
            sender = tx['sender']
            receiver = tx['receiver']
            amount = tx['amount']
            balances[sender] = balances.get(sender, 0) - amount
            balances[receiver] = balances.get(receiver, 0) + amount
            nonces[sender] = tx['nonce'] + 1
    return balances

def create_genesis_block():
    load_chain()
    if chain:
        return  # Local chain already exists

    print("[INFO] No local chain found. Attempting to sync from peers...")
    sync_chain()

    if chain:
        print("[INFO] Chain synced from peers.")
        return

    print("[INFO] No valid chain found on peers. Creating genesis block...")
    genesis = {
        'index': 0,
        'timestamp': time.time(),
        'transactions': [],
        'previous_hash': '0',
        'validator': PUBLIC_KEY,
    }
    tx = {
        'sender': '0',
        'receiver': PUBLIC_KEY,
        'amount': 10000,
        'nonce': 0,
        'signature': 'GENESIS'
    }
    genesis['transactions'].append(tx)
    genesis['hash'] = hash_block(genesis)
    genesis['signature'] = sign_block(genesis)
    chain.append(genesis)
    save_chain()


def load_chain():
    if os.path.exists('chain.json'):
        with open('chain.json') as f:
            data = json.load(f)
            chain.clear()
            chain.extend(data)

def save_chain():
    with open('chain.json', 'w') as f:
        json.dump(chain, f)

def verify_block_signature(block):
    validator = block.get('validator')
    signature = block.get('signature')
    if validator not in VALIDATOR_KEYS:
        return False
    try:
        block_copy = block.copy()
        block_copy.pop('signature', None)
        block_bytes = json.dumps(block_copy, sort_keys=True).encode()
        vk = VerifyingKey.from_string(bytes.fromhex(validator), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature), block_bytes)
        print("✍️")
        return True
    except (BadSignatureError, Exception):
        return False

def sync_chain():
    global chain
    candidates = list(peers) or [BOOTSTRAP_NODE]
    for peer in candidates:
        if f"http://{config['host']}:{PORT}" == peer:
            continue
        try:
            response = requests.get(f"{peer}/chain", timeout=5)
            if response.status_code == 200:
                incoming_chain = response.json()
                valid = True
                for i, block in enumerate(incoming_chain):
                    if i == 0:  # Genesis block can skip validator check if needed
                        continue
                    if not verify_block_signature(block):
                        valid = False
                        print(f"[WARN] Invalid block signature at index {i} from {peer}")
                        break
                if valid and len(incoming_chain) > len(chain):
                    chain = incoming_chain
                    save_chain()
                    print(f"[INFO] Synced chain from {peer}")
                    break
        except Exception:
            continue


def broadcast_transaction(tx):
    msg_id = str(uuid.uuid4())
    seen_ids.add(msg_id)
    for peer in peers:
        try:
            requests.post(f"{peer}/transaction", json=tx)
        except:
            pass

def create_block():
    global mempool
    print(NODE_TYPE)
    if (NODE_TYPE != 'PoA') or (not mempool):
        return
    # print("i do")
    txs = mempool[:5]
    balances = calculate_balances()
    valid_txs = []
    for tx in txs:
        if verify_signature(tx) and balances.get(tx['sender'], 0) >= tx['amount'] and tx['nonce'] == nonces.get(tx['sender'], 0):
            valid_txs.append(tx)
            balances[tx['sender']] -= tx['amount']
            balances[tx['receiver']] = balances.get(tx['receiver'], 0) + tx['amount']
            nonces[tx['sender']] = tx['nonce'] + 1
    if not valid_txs:
        return
    block = {
        'index': len(chain),
        'timestamp': time.time(),
        'transactions': valid_txs,
        'previous_hash': hash_block(chain[-1]),
        'validator': PUBLIC_KEY
    }
    block['hash'] = hash_block(block)
    block['signature'] = sign_block(block)
    chain.append(block)
    mempool = [tx for tx in mempool if tx not in valid_txs]
    save_chain()

# -------------------- Background Tasks --------------------
def background_worker():
    while True:
        sync_chain()
        create_block()
        time.sleep(10)

threading.Thread(target=background_worker, daemon=True).start()

# -------------------- API Endpoints --------------------
@app.post("/transaction")
def receive_transaction(tx: Transaction):
    tx_dict = tx.model_dump()
    if not verify_signature(tx_dict):
        return {"status": "invalid signature"}
    balances = calculate_balances()
    expected_nonce = nonces.get(tx_dict['sender'], 0)
    if tx_dict['nonce'] != expected_nonce:
        return {"status": "invalid nonce"}
    if balances.get(tx_dict['sender'], 0) < tx_dict['amount']:
        return {"status": "insufficient balance"}
    if tx_dict in mempool:
        return {"status": "already exists"}
    mempool.append(tx_dict)
    broadcast_transaction(tx_dict)
    return {"status": "transaction added"}

@app.get("/chain")
def get_chain():
    return chain

@app.get("/balance")
def get_balance(address: str):
    balances = calculate_balances()
    return {"balance": balances.get(address, 0)}
@app.get("/nonce/{account}")
def get_nonce(account: str):
    return {"nonce": nonces.get(account, 0)}
# -------------------- Init --------------------
load_chain()
if not chain:
    create_genesis_block()
calculate_balances()

if __name__ == "__main__":
    uvicorn.run(app, host=config['host'], port=PORT)


@app.get("/nonce/{account}")
def get_nonce(account: str):
    return {"nonce": nonces.get(account, 0)}
