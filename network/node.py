import json
import logging
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from core.block import Block
from core.blockchain import Blockchain
from core.transaction import Transaction
from core.wallet import Wallet
from network.node_request_handler import NodeRequestHandler


class Node:
    def __init__(self, port, peers=None, difficulty=1, chain_path=None):
        self.port = port
        self.peers = peers or []
        data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
        os.makedirs(data_dir, exist_ok=True)
        default_chain_path = os.path.join(data_dir, f"node_{port}.json")
        self.blockchain = Blockchain(
            difficulty=difficulty,
            difficulty_adjustment_interval=10,
            target_block_time=10,
            chain_path=chain_path or default_chain_path,
        )
        self.mempool = []
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"blockchain.node.{port}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            log_path = os.path.join(data_dir, f"node_{port}.log")
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(handler)
        self.server = ThreadingHTTPServer(("127.0.0.1", port), NodeRequestHandler)
        self.server.node = self
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def known_addresses(self):
        addresses = set()

        for block in self.blockchain.blocks:
            for tx in block.transactions:
                if getattr(tx, "sender", None):
                    addresses.add(tx.sender)
                if getattr(tx, "recipient", None):
                    addresses.add(tx.recipient)

        for tx in self.mempool:
            if getattr(tx, "sender", None):
                addresses.add(tx.sender)
            if getattr(tx, "recipient", None):
                addresses.add(tx.recipient)

        return addresses

    def address_exists(self, address):
        return address in self.known_addresses()

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

    def _deserialize_block(self, payload):
        txs = [Transaction.from_dict(tx) for tx in payload.get("transactions", [])]
        block = Block(
            index=payload["index"],
            previous_hash=payload["previous_hash"],
            transactions=txs,
            difficulty=payload["difficulty"],
            timestamp=payload["timestamp"],
            nonce=payload["nonce"],
        )
        block.header = {
            "index": payload["index"],
            "timestamp": payload["timestamp"],
            "previous_hash": payload["previous_hash"],
            "merkle_root": payload["merkle_root"],
            "difficulty": payload["difficulty"],
            "nonce": payload["nonce"],
        }
        block.hash = payload["hash"]
        block.merkle_root = payload["merkle_root"]
        return block

    def _post_json(self, peer_url, endpoint, payload):
        url = peer_url.rstrip("/") + endpoint
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None

    def _fetch_peer_status(self, peer_url):
        url = peer_url.rstrip("/") + "/status"
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None

    def broadcast_transaction(self, tx):
        payload = tx.to_dict()
        for peer in self.peers:
            self._post_json(peer, "/tx", payload)

    def broadcast_block(self, block):
        payload = self._serialize_block(block)
        for peer in self.peers:
            self._post_json(peer, "/block", payload)

    def add_peer(self, peer_url):
        peer_url = peer_url.rstrip("/")
        if not peer_url:
            return {"accepted": False, "reason": "peer_url is required"}
        if peer_url not in self.peers:
            self.peers.append(peer_url)
        return {"accepted": True, "reason": "peer added", "peers": self.peers}

    def remove_peer(self, peer_url):
        peer_url = peer_url.rstrip("/")
        if not peer_url:
            return {"accepted": False, "reason": "peer_url is required"}
        if peer_url in self.peers:
            self.peers.remove(peer_url)
            return {"accepted": True, "reason": "peer removed", "peers": self.peers}
        return {"accepted": False, "reason": "peer not found", "peers": self.peers}

    def receive_transaction(self, tx):
        with self._lock:
            if not isinstance(tx, Transaction):
                return {"accepted": False, "reason": "transaction object is invalid"}
            if not Transaction.is_valid_address(tx.sender):
                return {"accepted": False, "reason": "sender wallet address is invalid"}
            if not Transaction.is_valid_address(tx.recipient):
                return {"accepted": False, "reason": "recipient wallet address is invalid"}
            if tx.sender == "coinbase":
                return {"accepted": False, "reason": "coinbase transactions cannot be sent through mempool"}
            if tx.amount is None or tx.fee is None or tx.nonce is None:
                return {"accepted": False, "reason": "transaction amount, fee and nonce are required"}
            if tx.amount < 0 or tx.fee < 0:
                return {"accepted": False, "reason": "transaction amount and fee must be non-negative"}
            if not tx.signature or not tx.public_key_hex or not tx.verify_signature():
                return {"accepted": False, "reason": "transaction signature is invalid or missing"}

            current_balance = self.blockchain.balance_of(tx.sender, pending_transactions=self.mempool)
            total_cost = tx.amount + tx.fee
            if current_balance < total_cost:
                return {"accepted": False, "reason": "sender does not have enough funds to pay transaction"}

            pending_for_sender = sorted(
                [pending for pending in self.mempool if pending.sender == tx.sender],
                key=lambda pending: pending.nonce,
            )
            sender_nonces = self.blockchain.get_sender_nonces(self.blockchain.blocks) or {}
            expected_nonce = sender_nonces.get(tx.sender, 0)
            for pending in pending_for_sender:
                if pending.nonce == expected_nonce:
                    expected_nonce += 1
                elif pending.nonce > expected_nonce:
                    break

            if tx.nonce != expected_nonce:
                return {"accepted": False, "reason": f"invalid nonce for sender: expected {expected_nonce}, got {tx.nonce}"}

            for pending in self.mempool:
                if pending.sender == tx.sender and pending.nonce == tx.nonce:
                    return {"accepted": False, "reason": "duplicate transaction nonce for sender"}
            for block in self.blockchain.blocks:
                for existing_tx in block.transactions:
                    if existing_tx.sender == tx.sender and existing_tx.nonce == tx.nonce:
                        return {"accepted": False, "reason": "transaction nonce already used in blockchain"}
            self.mempool.append(tx)
        self.broadcast_transaction(tx)
        return {"accepted": True, "reason": "transaction accepted to mempool"}

    def _reinsert_lost_transactions(self, lost_blocks):
        for block in lost_blocks:
            for tx in block.transactions:
                if tx.sender == "coinbase":
                    continue
                duplicate = any(
                    pending.sender == tx.sender and pending.nonce == tx.nonce
                    for pending in self.mempool
                )
                if duplicate:
                    continue
                duplicate_in_chain = any(
                    existing_tx.sender == tx.sender and existing_tx.nonce == tx.nonce
                    for existing_block in self.blockchain.blocks
                    for existing_tx in existing_block.transactions
                    if existing_tx.sender != "coinbase"
                )
                if not duplicate_in_chain:
                    self.mempool.append(tx)

    def _candidate_chain_for_block(self, block):
        for idx, existing_block in enumerate(self.blockchain.blocks):
            if existing_block.hash == block.previous_hash:
                candidate = list(self.blockchain.blocks[: idx + 1])
                candidate.append(block)
                return candidate

        if block.index == 0 and block.previous_hash == "0" * 64:
            return [block]

        return None

    def _best_valid_peer_chain(self, current_total_work=None):
        if current_total_work is None:
            current_total_work = self.blockchain.total_work(self.blockchain.blocks)

        best_chain = None
        best_total_work = current_total_work

        for peer in list(self.peers):
            status = self._fetch_peer_status(peer)
            if not status or not status.get("blocks"):
                continue

            remote_chain = [self._deserialize_block(item) for item in status["blocks"]]
            remote_total_work = self.blockchain.total_work(remote_chain)
            if remote_total_work <= best_total_work:
                continue

            valid, _ = self.blockchain._is_valid_chain(remote_chain)
            if not valid:
                continue

            best_chain = remote_chain
            best_total_work = remote_total_work

        return best_chain, best_total_work

    def receive_block(self, payload):
        block = self._deserialize_block(payload)
        self.logger.info("accept")
        if block.hash in {existing.hash for existing in self.blockchain.blocks}:
            self.logger.info("block already exists in current chain")
            return {"accepted": False, "reason": "block already exists in current chain"}

        candidate = self._candidate_chain_for_block(block)
        if candidate is not None:
            valid, reason = self.blockchain._is_valid_chain(candidate)
            if not valid:
                self.logger.warning("candidate chain is invalid: %s; checking peer sync", reason)
                sync_result = self.sync_with_peers()
                if sync_result.get("accepted"):
                    self.logger.info("synchronized with a better peer after invalid candidate chain: %s", sync_result.get("reason"))
                    return sync_result
                return {"accepted": False, "reason": reason or "candidate chain is invalid and no better peer chain was found"}

            current_total_work = self.blockchain.total_work(self.blockchain.blocks)
            candidate_total_work = self.blockchain.total_work(candidate)
            self.logger.info(
                "total_work check: current=%s candidate=%s",
                current_total_work,
                candidate_total_work,
            )

            if candidate_total_work <= current_total_work:
                self.logger.warning(
                    "insufficient total work: candidate=%s is not greater than current=%s; checking peer sync",
                    candidate_total_work,
                    current_total_work,
                )
                sync_result = self.sync_with_peers()
                if sync_result.get("accepted"):
                    self.logger.info("synchronized with a better peer after insufficient total work: %s", sync_result.get("reason"))
                    return sync_result
                return {"accepted": False, "reason": "candidate chain has insufficient total work and no better peer chain was found"}

            self.logger.info(
                "sufficient total work: candidate=%s is greater than current=%s; continuing block acceptance",
                candidate_total_work,
                current_total_work,
            )

            old_chain = list(self.blockchain.blocks)
            replaced, reason = self.blockchain.replace_chain(candidate)
            if replaced:
                lost = [existing for existing in old_chain if existing.hash not in {item.hash for item in candidate}]
                self._reinsert_lost_transactions(lost)
                self.broadcast_block(block)
                return {"accepted": True, "reason": reason or "block accepted and chain replaced if needed"}

            return {"accepted": False, "reason": reason or "replace_chain rejected candidate block"}

        self.logger.info("block does not attach to current chain or genesis; checking peer sync")
        sync_result = self.sync_with_peers()
        if sync_result.get("accepted"):
            self.logger.info("synchronized with a better peer after unattached block: %s", sync_result.get("reason"))
            return sync_result
        self.logger.warning("peer sync did not improve chain after unattached block")
        return {"accepted": False, "reason": "block does not attach to current chain or genesis and no better peer chain was found"}

    def sync_with_peers(self):
        with self._lock:
            best_chain, _ = self._best_valid_peer_chain()
            if best_chain is None:
                return {"accepted": False, "reason": "no better valid chain found"}

            old_chain = list(self.blockchain.blocks)
            replaced, reason = self.blockchain.replace_chain(best_chain)
            if not replaced:
                return {"accepted": False, "reason": reason or "replacement rejected"}

            lost = [existing for existing in old_chain if existing.hash not in {item.hash for item in best_chain}]
            self._reinsert_lost_transactions(lost)
            return {"accepted": True, "reason": "chain synced successfully", "blocks": len(best_chain)}

    def create_wallet(self):
        return Wallet().to_dict()

    def mine_block(self, miner_address, transactions):
        with self._lock:
            candidate_transactions = list(transactions)
            if not candidate_transactions:
                candidate_transactions = list(self.mempool)
            selected = self.blockchain.select_transactions_for_block(candidate_transactions)
            block = self.blockchain.mine_block(miner_address, selected)
            included_user_transactions = [tx for tx in block.transactions if getattr(tx, "sender", None) != "coinbase"]
            self.mempool = [tx for tx in self.mempool if tx not in included_user_transactions]
            self.broadcast_block(block)
            return block

    def shutdown(self):
        self.server.shutdown()
        self.server.server_close()
