import json
from ecdsa import SigningKey, SECP256k1

def sign_transaction(private_key_hex, sender_pub, receiver, amount, nonce):
    message = f"{sender_pub}{receiver}{amount}{nonce}".encode()
    sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    signature = sk.sign(message).hex()
    return signature

def main():
    private_key = input("🔐 Enter sender's private key (hex): ").strip()
    sender_pub = input("🔓 Enter sender's public key (hex): ").strip()
    receiver = input("🎯 Enter receiver public key: ").strip()
    amount = int(input("💰 Enter amount: ").strip())
    nonce = int(input("🔁 Enter nonce: ").strip())

    signature = sign_transaction(private_key, sender_pub, receiver, amount, nonce)

    tx = {
        "sender": sender_pub,
        "receiver": receiver,
        "amount": amount,
        "nonce": nonce,
        "signature": signature
    }

    print("\n✅ Signed Transaction:")
    print(json.dumps(tx, indent=2))

    with open("last_transaction.json", "w") as f:
        json.dump(tx, f, indent=2)
        print("\n📦 Saved to last_transaction.json")

if __name__ == "__main__":
    main()
