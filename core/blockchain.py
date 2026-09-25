import json
import os
import tempfile
import time
import uuid

from core.block import BLOCK_REWARD, Block, merkle_root
from core.transaction import Transaction


class BlockchainValidationError(ValueError):
    pass


class ValidationResult(tuple):
    def __new__(cls, valid, reason=None):
        return super().__new__(cls, (bool(valid), reason))

    def __bool__(self):
        return bool(self[0])


class Blockchain:
    MAX_BLOCK_TRANSACTIONS = 10
    MAX_BLOCK_SIZE = 4096

    def __init__(self, difficulty=1, difficulty_adjustment_interval=10, target_block_time=10, chain_path=None):
        self.difficulty = difficulty
        self.difficulty_adjustment_interval = difficulty_adjustment_interval
        self.target_block_time = target_block_time
        self.chain_path = chain_path
        if self.chain_path is None:
            self.chain_path = os.path.join(tempfile.gettempdir(), f"blockchain_{uuid.uuid4().hex}.json")
        self.blocks = []

        if os.path.exists(self.chain_path):
            self.load_from_file()
        else:
            self.create_genesis_block()

    def _serialize_transaction_for_size(self, tx):
        return json.dumps(tx.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    def select_transactions_for_block(self, transactions):
        grouped = {}
        for tx in list(transactions):
            if getattr(tx, "sender", None) == "coinbase":
                continue
            grouped.setdefault(tx.sender, []).append(tx)

        sender_groups = []
        for sender, txs in grouped.items():
            ordered = sorted(
                txs,
                key=lambda tx: (tx.nonce, getattr(tx, "fee", 0), getattr(tx, "amount", 0)),
            )
            sender_groups.append((
                max(getattr(tx, "fee", 0) for tx in ordered),
                sender,
                ordered,
            ))

        sender_groups.sort(key=lambda item: item[0], reverse=True)

        chosen = []
        total_size = 0
        for _, _, txs in sender_groups:
            for tx in txs:
                tx_size = len(self._serialize_transaction_for_size(tx))
                if len(chosen) >= self.MAX_BLOCK_TRANSACTIONS:
                    break
                if total_size + tx_size > self.MAX_BLOCK_SIZE:
                    continue
                chosen.append(tx)
                total_size += tx_size
            if len(chosen) >= self.MAX_BLOCK_TRANSACTIONS:
                break

        return chosen

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
        self.save_to_file()
        return block

    def get_balances_snapshot(self, blocks, pending_transactions=None):
        balances = {}
        for block in blocks:
            for tx in block.transactions:
                if tx.sender == "coinbase":
                    balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
                else:
                    balances[tx.sender] = balances.get(tx.sender, 0) - (tx.amount + tx.fee)
                    balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount

        if pending_transactions:
            for tx in pending_transactions:
                if tx.sender == "coinbase":
                    continue
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
            return True, None

        if getattr(tx, "public_key_hex", None) and getattr(tx, "signature", None):
            if not tx.verify_signature():
                return False, "transaction signature is invalid"

        if sender_nonces is not None:
            expected_nonce = sender_nonces.get(tx.sender, 0)
            if tx.nonce != expected_nonce:
                return False, f"nonce mismatch for {tx.sender}: expected {expected_nonce}, got {tx.nonce}"
            sender_nonces[tx.sender] = expected_nonce + 1

        total_cost = tx.amount + tx.fee
        if balances.get(tx.sender, 0) < total_cost:
            return False, f"insufficient funds for {tx.sender}: needs {total_cost}, has {balances.get(tx.sender, 0)}"

        balances[tx.sender] = balances.get(tx.sender, 0) - total_cost
        balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
        return True, None

    def _apply_block_transactions(self, block, balances, sender_nonces=None):
        for tx in block.transactions:
            if tx.sender == "coinbase":
                continue
            if getattr(tx, "public_key_hex", None) and getattr(tx, "signature", None):
                if not tx.verify_signature():
                    return False, "transaction signature is invalid"

        for tx in block.transactions:
            if tx.sender == "coinbase":
                continue
            ok, reason = self._apply_transaction_balances(balances, tx, sender_nonces)
            if not ok:
                return False, reason or "transaction validation failed"

        if not self._is_valid_coinbase_transaction(block.transactions):
            return False, "coinbase transaction is invalid"

        coinbase_tx = next((tx for tx in block.transactions if tx.sender == "coinbase"), None)
        if coinbase_tx is not None:
            ok, reason = self._apply_transaction_balances(balances, coinbase_tx, sender_nonces)
            if not ok:
                return False, reason or "coinbase transaction validation failed"

        return True, None

    def _validate_block_structure(self, block, previous_hash, expected_index):
        if block is None:
            raise BlockchainValidationError("block is None")
        if block.index != expected_index:
            raise BlockchainValidationError(f"block index mismatch: expected {expected_index}, got {block.index}")
        if block.previous_hash != previous_hash:
            raise BlockchainValidationError("previous_hash mismatch")
        if block.hash != block.calculate_hash():
            raise BlockchainValidationError("block hash does not match calculated hash")
        if not block.hash.startswith("0" * block.difficulty):
            raise BlockchainValidationError(f"block does not satisfy difficulty target {block.difficulty}")
        if block.merkle_root != merkle_root(block.transactions):
            raise BlockchainValidationError("merkle root mismatch")
        return True

    def validate_block(self, block):
        try:
            previous_hash = self.blocks[-1].hash if self.blocks else "0" * 64
            self._validate_block_structure(block, previous_hash, len(self.blocks))
            balances = self.get_balances_snapshot(self.blocks)
            sender_nonces = self.get_sender_nonces(self.blocks) or {}
            valid, reason = self._apply_block_transactions(block, balances, sender_nonces)
            if not valid:
                return False, reason or "block transactions are invalid for current chain state"
            return True, None
        except BlockchainValidationError as exc:
            return False, str(exc)

    def add_block(self, block):
        valid, reason = self.validate_block(block)
        if not valid:
            raise ValueError(reason)
        self.blocks.append(block)
        if len(self.blocks) % self.difficulty_adjustment_interval == 0:
            self.adjust_difficulty()
        self.save_to_file()
        return block

    def mine_block(self, miner_address, transactions):
        selected_transactions = self.select_transactions_for_block(transactions)
        if len(selected_transactions) > self.MAX_BLOCK_TRANSACTIONS:
            selected_transactions = selected_transactions[: self.MAX_BLOCK_TRANSACTIONS]

        fees = sum(getattr(tx, "fee", 0) for tx in selected_transactions)
        coinbase_tx = Transaction(
            sender="coinbase",
            recipient=miner_address,
            amount=BLOCK_REWARD + fees,
            fee=0,
            nonce=0,
        )
        all_transactions = [coinbase_tx] + list(selected_transactions)

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

    def _is_valid_chain(self, blocks):
        if not blocks:
            return ValidationResult(False, "chain is empty")
        if blocks[0].index != 0:
            return ValidationResult(False, "genesis block index is not 0")
        if blocks[0].previous_hash != "0" * 64:
            return ValidationResult(False, "genesis previous_hash is invalid")
        if blocks[0].transactions:
            return ValidationResult(False, "genesis block must be empty")

        balances = {}
        sender_nonces = {}
        for idx, block in enumerate(blocks):
            previous_hash = blocks[idx - 1].hash if idx > 0 else "0" * 64
            try:
                self._validate_block_structure(block, previous_hash, idx)
            except BlockchainValidationError as exc:
                return ValidationResult(False, str(exc))
            valid, reason = self._apply_block_transactions(block, balances, sender_nonces)
            if not valid:
                return ValidationResult(False, reason or "transaction validation failed while replaying chain")

        return ValidationResult(True, None)

    def validate_chain(self):
        return self._is_valid_chain(self.blocks)

    def total_work(self, blocks=None):
        chain = blocks if blocks is not None else self.blocks
        return sum((2 ** max(1, block.difficulty)) for block in chain)

    def replace_chain(self, candidate_blocks):
        if not candidate_blocks:
            return False, "candidate chain is empty"
        valid, reason = self._is_valid_chain(candidate_blocks)
        if not valid:
            return False, reason
        if self.total_work(candidate_blocks) <= self.total_work(self.blocks):
            return False, "candidate chain has insufficient total work"
        self.blocks = candidate_blocks
        self.save_to_file()
        return True, "chain replaced successfully"

    def balance_of(self, address, pending_transactions=None):
        return self.get_balances_snapshot(self.blocks, pending_transactions=pending_transactions).get(address, 0)

    def save_to_file(self, path=None):
        target = path or self.chain_path
        if target is None:
            return None
        directory = os.path.dirname(target)
        if directory:
            os.makedirs(directory, exist_ok=True)
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

        valid, _ = self._is_valid_chain(self.blocks)
        if not valid:
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

        original_difficulty = self.difficulty
        latest = self.blocks[-1]
        previous = self.blocks[-self.difficulty_adjustment_interval]
        elapsed = latest.timestamp - previous.timestamp
        if elapsed <= 0:
            elapsed = self.target_block_time

        if elapsed < self.target_block_time:
            self.difficulty += 1
        elif elapsed > self.target_block_time:
            self.difficulty = max(1, self.difficulty - 1)

        if self.difficulty != original_difficulty:
            self.save_to_file()

        return self.difficulty
