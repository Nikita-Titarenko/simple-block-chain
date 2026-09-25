import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.block import Block  # noqa: E402
from core.transaction import Transaction  # noqa: E402


def _load_payload(input_path):
    with open(input_path, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def _payload_value(payload, key, default=None):
    if key in payload:
        return payload[key]
    header = payload.get("header", {})
    return header.get(key, default)


def _deserialize_transactions(items):
    transactions = []
    for item in items:
        if isinstance(item, dict) and {"sender", "recipient", "amount"}.issubset(item.keys()):
            transactions.append(Transaction.from_dict(item))
        else:
            transactions.append(item)
    return transactions


def _serialize_transactions(items):
    serialized = []
    for item in items:
        if hasattr(item, "to_dict"):
            serialized.append(item.to_dict())
        else:
            serialized.append(item)
    return serialized


def mine_block_payload(payload):
    index = _payload_value(payload, "index")
    previous_hash = _payload_value(payload, "previous_hash")
    difficulty = _payload_value(payload, "difficulty")
    timestamp = _payload_value(payload, "timestamp")
    transactions = _deserialize_transactions(payload.get("transactions", []))

    missing = [
        name
        for name, value in (
            ("index", index),
            ("previous_hash", previous_hash),
            ("difficulty", difficulty),
        )
        if value is None
    ]
    if missing:
        raise ValueError(f"missing required block fields: {', '.join(missing)}")

    nonce = _payload_value(payload, "nonce", 0)

    block = Block(
        index=index,
        previous_hash=previous_hash,
        transactions=transactions,
        difficulty=difficulty,
        timestamp=timestamp,
        nonce=nonce,
    )
    block.mine()

    return {
        "index": block.index,
        "timestamp": block.timestamp,
        "previous_hash": block.previous_hash,
        "merkle_root": block.merkle_root,
        "difficulty": block.difficulty,
        "nonce": block.nonce,
        "hash": block.hash,
        "transactions": _serialize_transactions(block.transactions),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Load a block from JSON, recalculate merkle_root, and mine a valid nonce."
    )
    parser.add_argument("input", help="Path to the input block JSON file")
    parser.add_argument("--output", help="Optional path to save the mined block JSON")
    args = parser.parse_args()

    result = mine_block_payload(_load_payload(args.input))
    rendered = json.dumps(result, indent=2, sort_keys=True)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(rendered)
            file.write("\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()