from mempool import Mempool
from wallet import Wallet


if __name__ == "__main__":
    wallet_sender = Wallet()
    wallet_recipient = Wallet()

    current_balance = 100.0
    current_nonce = 0
    chain_transactions = []

    mempool = Mempool()

    tx = wallet_sender.create_transaction(
        recipient=wallet_recipient.address,
        amount=30.0,
        fee=1.0,
        nonce=0
    )

    success, message = mempool.add_transaction(
        tx=tx,
        sender_public_key_hex=wallet_sender.get_public_key_hex(),
        current_balance=current_balance,
        current_nonce=current_nonce,
        chain_txs=chain_transactions
    )

    print(f"Status: {success}, Message: {message}")