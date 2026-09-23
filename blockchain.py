import json
import os
import time

from block import BLOCK_REWARD, Block, merkle_root
from transaction import Transaction


class Blockchain:
    def __init__(self, difficulty=1, difficulty_adjustment_interval=10, target_block_time=10, chain_path=None):
        self.difficulty = difficulty
        self.difficulty_adjustment_interval = difficulty_adjustment_interval
        self.target_block_time = target_block_time
        self.chain_path = chain_path or "blockchain.json"
        self.blocks = []

        if os.path.exists(self.chain_path):
            self.load_from_file()
        else:
            self.create_genesis_block()

    def create_genesis_block(self):
        block = Block(
            index=0,
            previous_hash="0" * 64,
            transactions=[],
            difficulty=self.difficulty,
            timestamp=0,
            nonce=0,
        )
        block.mine()
        self.blocks = [block]
        return block

    def get_balances_snapshot(self, blocks):
        balances = {}
        for block in blocks:
            for tx in block.transactions:
                if tx.sender == "coinbase":
                    balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
                else:
                    balances[tx.sender] = balances.get(tx.sender, 0) - (tx.amount + tx.fee)
                    balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
        return balances

    def get_sender_nonces(self, blocks):
        nonces = {}
        for block in blocks:
            for tx in block.transactions:
                if tx.sender == "coinbase":
                    continue
                current = nonces.get(tx.sender, 0)
                if tx.nonce != current:
                    return None
                nonces[tx.sender] = current + 1
        return nonces

    def _coinbase_reward_for_block(self, transactions):
        if not transactions:
            return 0
        return BLOCK_REWARD + sum(getattr(tx, "fee", 0) for tx in transactions[1:])

    def _is_valid_coinbase_transaction(self, transactions):
        if not transactions:
            return True
        if transactions[0].sender != "coinbase":
            return False
        return transactions[0].amount == self._coinbase_reward_for_block(transactions)

    def _apply_transaction_balances(self, balances, tx, sender_nonces=None):
        if tx.sender == "coinbase":
            balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
            return True

        if getattr(tx, "public_key_hex", None) and getattr(tx, "signature", None):
            if not tx.verify_signature():
                return False

        if sender_nonces is not None:
            expected_nonce = sender_nonces.get(tx.sender, 0)
            if tx.nonce != expected_nonce:
                return False
            sender_nonces[tx.sender] = expected_nonce + 1

        total_cost = tx.amount + tx.fee
        if balances.get(tx.sender, 0) < total_cost:
            return False

        balances[tx.sender] = balances.get(tx.sender, 0) - total_cost
        balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
        return True

    def _apply_block_transactions(self, block, balances, sender_nonces=None):
        if not self._is_valid_coinbase_transaction(block.transactions):
            return False

        for tx in block.transactions:
            if not self._apply_transaction_balances(balances, tx, sender_nonces):
                return False

        return True

    def _validate_block_structure(self, block, previous_hash, expected_index):
        if block is None:
            return False
        if block.index != expected_index:
            return False
        if block.previous_hash != previous_hash:
            return False
        if block.hash != block.calculate_hash():
            return False
        if not block.hash.startswith("0" * block.difficulty):
            return False
        if block.merkle_root != merkle_root(block.transactions):
            return False
        return True

    def validate_block(self, block):
        previous_hash = self.blocks[-1].hash if self.blocks else "0" * 64
        if not self._validate_block_structure(block, previous_hash, len(self.blocks)):
            return False

        balances = self.get_balances_snapshot(self.blocks)
        sender_nonces = self.get_sender_nonces(self.blocks) or {}
        return self._apply_block_transactions(block, balances, sender_nonces)

    def add_block(self, block):
        if not self.validate_block(block):
            raise ValueError("Invalid block")
        self.blocks.append(block)
        if len(self.blocks) % self.difficulty_adjustment_interval == 0:
            self.adjust_difficulty()
        return block

    def mine_block(self, miner_address, transactions):
        fees = sum(getattr(tx, "fee", 0) for tx in transactions)
        coinbase_tx = Transaction(
            sender="coinbase",
            recipient=miner_address,
            amount=BLOCK_REWARD + fees,
            fee=0,
            nonce=0,
        )
        all_transactions = [coinbase_tx] + list(transactions)
        previous_hash = self.blocks[-1].hash
        block = Block(
            index=len(self.blocks),
            previous_hash=previous_hash,
            transactions=all_transactions,
            difficulty=self.difficulty,
            timestamp=int(time.time()),
            nonce=0,
        )
        block.mine()
        self.add_block(block)
        return block

    def validate_chain(self):
        if not self.blocks:
            return False
        if self.blocks[0].index != 0:
            return False
        if self.blocks[0].previous_hash != "0" * 64:
            return False
        if self.blocks[0].transactions:
            return False

        balances = {}
        sender_nonces = {}
        for idx, block in enumerate(self.blocks):
            previous_hash = self.blocks[idx - 1].hash if idx > 0 else "0" * 64
            if not self._validate_block_structure(block, previous_hash, idx):
                return False
            if not self._apply_block_transactions(block, balances, sender_nonces):
                return False

        return True

    def balance_of(self, address):
        return self.get_balances_snapshot(self.blocks).get(address, 0)

    def save_to_file(self, path=None):
        target = path or self.chain_path
        payload = {
            "difficulty": self.difficulty,
            "difficulty_adjustment_interval": self.difficulty_adjustment_interval,
            "target_block_time": self.target_block_time,
            "blocks": [self._serialize_block(block) for block in self.blocks],
        }
        with open(target, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
        return target

    def load_from_file(self, path=None):
        target = path or self.chain_path
        if not os.path.exists(target):
            self.create_genesis_block()
            return self

        with open(target, "r", encoding="utf-8") as file:
            payload = json.load(file)

        self.difficulty = payload.get("difficulty", self.difficulty)
        self.difficulty_adjustment_interval = payload.get("difficulty_adjustment_interval", self.difficulty_adjustment_interval)
        self.target_block_time = payload.get("target_block_time", self.target_block_time)

        self.blocks = []
        for item in payload.get("blocks", []):
            txs = [Transaction.from_dict(tx) for tx in item.get("transactions", [])]
            block = Block(
                index=item["index"],
                previous_hash=item["previous_hash"],
                transactions=txs,
                difficulty=item["difficulty"],
                timestamp=item["timestamp"],
                nonce=item["nonce"],
            )
            block.header = {
                "index": item["index"],
                "timestamp": item["timestamp"],
                "previous_hash": item["previous_hash"],
                "merkle_root": item["merkle_root"],
                "difficulty": item["difficulty"],
                "nonce": item["nonce"],
            }
            block.hash = item["hash"]
            block.merkle_root = item["merkle_root"]
            self.blocks.append(block)

        if not self.blocks:
            self.create_genesis_block()
        return self

    def _serialize_block(self, block):
        return {
            "index": block.index,
            "timestamp": block.timestamp,
            "previous_hash": block.previous_hash,
            "merkle_root": block.merkle_root,
            "difficulty": block.difficulty,
            "nonce": block.nonce,
            "hash": block.hash,
            "transactions": [tx.to_dict() for tx in block.transactions],
        }

    def adjust_difficulty(self):
        if len(self.blocks) < self.difficulty_adjustment_interval:
            return self.difficulty

        recent = self.blocks[-self.difficulty_adjustment_interval:]
        if len(recent) < 2:
            return self.difficulty

        total_time = recent[-1].timestamp - recent[0].timestamp
        if total_time <= 0:
            return self.difficulty

        average_time = total_time / (len(recent) - 1)
        expected_time = self.target_block_time * (len(recent) - 1)
        ratio = expected_time / max(average_time, 1)
        self.difficulty = max(1, int(self.difficulty * ratio))
        for block in recent:
            block.difficulty = self.difficulty
            block.header["difficulty"] = self.difficulty
        return self.difficulty
