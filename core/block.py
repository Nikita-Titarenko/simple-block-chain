import hashlib
import json
import time

BLOCK_REWARD = 50


def _hash_bytes(value):
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    if value is None:
        return b""
    if isinstance(value, (int, float, bool)):
        return str(value).encode("utf-8")
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return str(value).encode("utf-8")


def merkle_root(transactions):
    if not transactions:
        return hashlib.sha256(b"").hexdigest()

    level = [hashlib.sha256(_hash_bytes(tx)).hexdigest() for tx in transactions]

    while len(level) > 1:
        if len(level) % 2 != 0:
            level.append(level[-1])

        next_level = []
        for i in range(0, len(level), 2):
            pair = level[i] + level[i + 1]
            next_level.append(hashlib.sha256(pair.encode("utf-8")).hexdigest())
        level = next_level

    return level[0]


class Block:
    def __init__(self, index, previous_hash, transactions, difficulty, timestamp=None, nonce=0):
        self.index = index
        self.timestamp = timestamp if timestamp is not None else int(time.time())
        self.previous_hash = previous_hash
        self.transactions = list(transactions)
        self.difficulty = difficulty
        self.nonce = nonce
        self.merkle_root = merkle_root(self.transactions)
        self.header = {
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "difficulty": self.difficulty,
            "nonce": self.nonce,
        }
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        payload = json.dumps(self.header, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def mine(self):
        target_prefix = "0" * self.difficulty
        while not self.hash.startswith(target_prefix):
            self.nonce += 1
            self.header["nonce"] = self.nonce
            self.hash = self.calculate_hash()
        return self

    def is_valid(self):
        return self.hash == self.calculate_hash() and self.hash.startswith("0" * self.difficulty)

    def to_dict(self):
        return {
            "header": self.header,
            "transactions": self.transactions,
            "hash": self.hash,
        }
