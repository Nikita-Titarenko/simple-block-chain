import json

from ecdsa import SECP256k1, VerifyingKey


class Mempool:
    def __init__(self):
        self.transactions = []

    def add_transaction(self, tx, sender_public_key_hex, current_balance, current_nonce, chain_txs):
        is_valid, reason = self.validate(tx, sender_public_key_hex, current_balance, current_nonce, chain_txs)
        if not is_valid:
            return False, reason
        self.transactions.append(tx)
        return True, "Transaction added to mempool successfully."

    def validate(self, tx, sender_public_key_hex, current_balance, current_nonce, chain_txs):
        signable_data = tx.get_signable_data()
        serialized = json.dumps(signable_data, sort_keys=True).encode('utf-8')

        try:
            vk = VerifyingKey.from_string(bytes.fromhex(sender_public_key_hex), curve=SECP256k1)
            is_sig_valid = vk.verify(bytes.fromhex(tx.signature), serialized)
        except Exception:
            is_sig_valid = False

        if not is_sig_valid:
            return False, "Invalid transaction signature."

        pending_for_sender = [t for t in self.transactions if t.sender == tx.sender]
        total_cost = tx.amount + tx.fee
        pending_amount = sum(t.amount + t.fee for t in pending_for_sender)

        if current_balance < (pending_amount + total_cost):
            return False, "Insufficient funds including pending mempool transactions."

        expected_nonce = current_nonce + len(pending_for_sender)
        if tx.nonce != expected_nonce:
            return False, f"Invalid nonce. Expected {expected_nonce}, got {tx.nonce}."

        for t in self.transactions:
            if t.sender == tx.sender and t.nonce == tx.nonce:
                return False, "Duplicate transaction found in mempool."

        for t in chain_txs:
            if t.sender == tx.sender and t.nonce == tx.nonce:
                return False, "Duplicate transaction found in blockchain."

        return True, "Validation passed."
