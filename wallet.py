import hashlib
import json

from ecdsa import SECP256k1, SigningKey

from transaction import Transaction


class Wallet:
    def __init__(self):
        self.private_key = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.private_key.get_verifying_key()
        self.address = hashlib.sha256(self.public_key.to_string()).hexdigest()

    def get_public_key_hex(self):
        return self.public_key.to_string().hex()

    def create_transaction(self, recipient, amount, fee, nonce):
        tx_data = {
            "sender": self.address,
            "recipient": recipient,
            "amount": amount,
            "fee": fee,
            "nonce": nonce,
        }
        serialized = json.dumps(tx_data, sort_keys=True).encode("utf-8")
        signature = self.private_key.sign(serialized).hex()
        return Transaction(self.address, recipient, amount, fee, nonce, signature, self.get_public_key_hex())
