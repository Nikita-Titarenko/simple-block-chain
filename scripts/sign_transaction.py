import argparse
import json

from ecdsa import SECP256k1, SigningKey


def build_tx_payload(sender, recipient, amount, fee, nonce):
    return {
        "sender": sender,
        "recipient": recipient,
        "amount": int(amount),
        "fee": int(fee),
        "nonce": int(nonce),
    }


def sign_transaction(sender, recipient, amount, fee, nonce, private_key_hex):
    tx_data = build_tx_payload(sender, recipient, amount, fee, nonce)
    private_key = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    signature = private_key.sign(json.dumps(tx_data, sort_keys=True).encode("utf-8")).hex()

    public_key_hex = private_key.get_verifying_key().to_string().hex()
    return {
        **tx_data,
        "signature": signature,
        "public_key_hex": public_key_hex,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a signed blockchain transaction payload for /tx")
    parser.add_argument("--sender", required=True, help="Sender wallet address")
    parser.add_argument("--recipient", required=True, help="Recipient wallet address")
    parser.add_argument("--amount", required=True, type=int, help="Amount to send")
    parser.add_argument("--fee", required=True, type=int, help="Transaction fee")
    parser.add_argument("--nonce", required=True, type=int, help="Nonce for sender")
    parser.add_argument("--private-key", required=True, help="Private key in hex format")
    args = parser.parse_args()

    tx = sign_transaction(
        args.sender,
        args.recipient,
        args.amount,
        args.fee,
        args.nonce,
        args.private_key,
    )
    print(json.dumps(tx, indent=2, sort_keys=True))
