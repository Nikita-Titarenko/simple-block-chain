import json

from ecdsa import SECP256k1, VerifyingKey


class Transaction:
    def __init__(self, sender, recipient, amount, fee, nonce, signature=None, public_key_hex=None):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.fee = fee
        self.nonce = nonce
        self.signature = signature
        self.public_key_hex = public_key_hex

    @staticmethod
    def from_dict(data):
        return Transaction(
            sender=data.get("sender"),
            recipient=data.get("recipient"),
            amount=data.get("amount"),
            fee=data.get("fee", 0),
            nonce=data.get("nonce", 0),
            signature=data.get("signature"),
            public_key_hex=data.get("public_key_hex"),
        )

    def to_dict(self):
        payload = {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "fee": self.fee,
            "nonce": self.nonce,
            "signature": self.signature,
        }
        if self.public_key_hex is not None:
            payload["public_key_hex"] = self.public_key_hex
        return payload

    def get_signable_data(self):
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "fee": self.fee,
            "nonce": self.nonce,
        }

    def verify_signature(self):
        if not self.signature or not getattr(self, "public_key_hex", None):
            return False

        try:
            vk = VerifyingKey.from_string(bytes.fromhex(self.public_key_hex), curve=SECP256k1)
            signable = json.dumps(self.get_signable_data(), sort_keys=True).encode("utf-8")
            vk.verify(bytes.fromhex(self.signature), signable)
            return True
        except Exception:
            return False
