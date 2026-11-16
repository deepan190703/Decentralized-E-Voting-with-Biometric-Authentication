import json
import os
from ecdsa import SigningKey, SECP256k1

WALLET_FILE = "wallet.json"

def load_wallet():
    if os.path.exists(WALLET_FILE):
        with open(WALLET_FILE, "r") as f:
            return json.load(f)
    return {}

def save_wallet(wallet):
    with open(WALLET_FILE, "w") as f:
        json.dump(wallet, f, indent=2)

def create_account(name):
    sk = SigningKey.generate(curve=SECP256k1)
    pk = sk.verifying_key

    account = {
        "private_key": sk.to_string().hex(),
        "public_key": pk.to_string().hex()
    }
    return account

def main():
    wallet = load_wallet()
    name = input("Enter a name for the new account: ").strip()

    if name in wallet:
        print(f"❌ Account '{name}' already exists.")
        return

    new_account = create_account(name)
    wallet[name] = new_account
    save_wallet(wallet)

    print(f"✅ Account '{name}' created successfully.")
    print(f"🔐 Private Key: {new_account['private_key']}")
    print(f"🔓 Public Key:  {new_account['public_key']}")

if __name__ == "__main__":
    main()
