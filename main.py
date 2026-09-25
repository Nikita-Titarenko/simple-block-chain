import sys
import time

from network.node import Node


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a blockchain node")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--peers", default="", help="Comma-separated peer URLs, e.g. http://127.0.0.1:5002,http://127.0.0.1:5003")
    parser.add_argument("--difficulty", type=int, default=1)
    args = parser.parse_args()

    peers = [peer.strip() for peer in args.peers.split(",") if peer.strip()]
    node = Node(port=args.port, peers=peers, difficulty=args.difficulty)
    if sys.stdout is not None:
        print(f"node started on {args.port}")
    while True:
        time.sleep(1)
