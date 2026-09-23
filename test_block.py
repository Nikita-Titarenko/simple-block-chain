import hashlib
import os
import tempfile
import unittest

from block import BLOCK_REWARD, Block, merkle_root
from blockchain import Blockchain
from transaction import Transaction


class TestMerkleAndBlock(unittest.TestCase):
    def test_merkle_root_with_odd_transaction_count_duplicates_last_hash(self):
        txs = ["tx1", "tx2", "tx3"]
        tx_hashes = [hashlib.sha256(tx.encode("utf-8")).hexdigest() for tx in txs]

        level = tx_hashes[:]
        if len(level) % 2 != 0:
            level.append(level[-1])

        next_level = []
        for i in range(0, len(level), 2):
            pair = level[i] + level[i + 1]
            next_level.append(hashlib.sha256(pair.encode("utf-8")).hexdigest())

        expected = hashlib.sha256(
            (next_level[0] + next_level[1]).encode("utf-8")
        ).hexdigest()

        self.assertEqual(merkle_root(txs), expected)

    def test_block_header_hash_is_sha256_of_header(self):
        block = Block(
            index=1,
            previous_hash="prevhash",
            transactions=["tx1", "tx2"],
            difficulty=2,
            timestamp=1234567890,
            nonce=7,
        )

        expected_header = {
            "index": 1,
            "timestamp": 1234567890,
            "previous_hash": "prevhash",
            "merkle_root": block.merkle_root,
            "difficulty": 2,
            "nonce": 7,
        }
        expected_hash = hashlib.sha256(str(expected_header).encode("utf-8")).hexdigest()

        self.assertEqual(block.header, expected_header)
        self.assertEqual(block.hash, expected_hash)

    def test_block_mining_requires_hash_with_leading_zeros(self):
        block = Block(
            index=1,
            previous_hash="0" * 64,
            transactions=[Transaction("a", "b", 10, 1, 0)],
            difficulty=2,
            timestamp=1,
            nonce=0,
        )

        mined_block = block.mine()

        self.assertTrue(mined_block.hash.startswith("00"))
        self.assertTrue(mined_block.is_valid())

    def test_coinbase_transaction_is_first_and_includes_block_fees(self):
        blockchain = Blockchain(difficulty=1, difficulty_adjustment_interval=10, target_block_time=10)
        blockchain.mine_block("alice", [])

        tx1 = Transaction("alice", "bob", 10, 2, 0)
        tx2 = Transaction("alice", "dave", 20, 3, 1)

        mined_block = blockchain.mine_block("miner", [tx1, tx2])

        self.assertEqual(mined_block.transactions[0].sender, "coinbase")
        self.assertEqual(mined_block.transactions[0].recipient, "miner")
        self.assertEqual(mined_block.transactions[0].amount, BLOCK_REWARD + 5)

    def test_difficulty_adjustment_uses_average_block_time(self):
        blockchain = Blockchain(difficulty=2, difficulty_adjustment_interval=2, target_block_time=10)
        blockchain.blocks = [
            Block(index=0, previous_hash="0" * 64, transactions=[], difficulty=2, timestamp=0, nonce=0),
            Block(index=1, previous_hash="0" * 64, transactions=[], difficulty=2, timestamp=5, nonce=0),
        ]

        blockchain.adjust_difficulty()

        self.assertGreater(blockchain.difficulty, 2)

    def test_validate_chain_accepts_valid_chain_and_rejects_tampering(self):
        blockchain = Blockchain(difficulty=1, difficulty_adjustment_interval=10, target_block_time=10)
        blockchain.mine_block("alice", [])

        tx = Transaction("alice", "bob", 25, 1, 0)
        blockchain.mine_block("miner", [tx])

        self.assertTrue(blockchain.validate_chain())

        blockchain.blocks[2].transactions[1].amount = 999
        self.assertFalse(blockchain.validate_chain())

    def test_chain_persistence_round_trip_and_balance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "chain.json")
            blockchain = Blockchain(chain_path=path, difficulty=1, difficulty_adjustment_interval=10, target_block_time=10)
            blockchain.mine_block("alice", [])
            blockchain.mine_block("miner", [Transaction("alice", "bob", 20, 1, 0)])
            blockchain.save_to_file()

            loaded = Blockchain(chain_path=path, difficulty=1, difficulty_adjustment_interval=10, target_block_time=10)
            loaded.load_from_file()

            self.assertEqual(len(loaded.blocks), len(blockchain.blocks))
            self.assertEqual(loaded.balance_of("bob"), 20)
            self.assertTrue(loaded.validate_chain())


if __name__ == "__main__":
    unittest.main()
