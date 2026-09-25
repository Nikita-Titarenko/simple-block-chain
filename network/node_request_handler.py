import json
from http.server import BaseHTTPRequestHandler

from core.transaction import Transaction


class NodeRequestHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        node = self.server.node
        if self.path == "/status":
            self._send_json(200, {
                "port": node.port,
                "blocks": [node._serialize_block(block) for block in node.blockchain.blocks],
                "mempool": [tx.to_dict() for tx in node.mempool],
                "peers": node.peers,
                "last_hash": node.blockchain.blocks[-1].hash if node.blockchain.blocks else None,
            })
            return

        if self.path == "/addresses":
            self._send_json(200, {"addresses": sorted(node.known_addresses())})
            return

        if self.path == "/chain/validate":
            valid, reason = node.blockchain.validate_chain()
            self._send_json(200, {
                "valid": valid,
                "reason": reason,
                "blocks_count": len(node.blockchain.blocks),
            })
            return

        if self.path.startswith("/balance"):
            query = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = {}
            if query:
                for part in query.split("&"):
                    if "=" in part:
                        key, value = part.split("=", 1)
                        params[key] = value
            address = params.get("address")
            if not address:
                self._send_json(400, {"accepted": False, "reason": "address query parameter is required"})
                return
            if not node.address_exists(address):
                self._send_json(404, {"accepted": False, "reason": "address not found"})
                return
            balance = node.blockchain.balance_of(address, pending_transactions=node.mempool)
            self._send_json(200, {"address": address, "balance": balance})
            return

        self.send_error(404)

    def do_POST(self):
        node = self.server.node
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)

        if not raw:
            self.send_error(400, "Empty body")
            return

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        if self.path == "/tx":
            try:
                tx = Transaction.from_dict(payload)
                result = node.receive_transaction(tx)
                self._send_json(200, result if isinstance(result, dict) else {"accepted": bool(result), "reason": "transaction rejected"})
                return
            except Exception as exc:
                self._send_json(400, {"accepted": False, "reason": str(exc)})
                return

        if self.path == "/block":
            try:
                result = node.receive_block(payload)
                self._send_json(200, result if isinstance(result, dict) else {"accepted": bool(result), "reason": "block rejected"})
                return
            except Exception as exc:
                self._send_json(400, {"accepted": False, "reason": str(exc)})
                return

        if self.path == "/mine":
            try:
                miner = payload.get("miner") if isinstance(payload, dict) else None
                if not miner:
                    self._send_json(400, {"accepted": False, "reason": "miner address is required"})
                    return
                txs = list(node.mempool)
                block = node.mine_block(miner, txs)
                self._send_json(200, {"accepted": True, "reason": "block mined successfully", "block": node._serialize_block(block)})
                return
            except Exception as exc:
                self._send_json(400, {"accepted": False, "reason": str(exc)})
                return

        if self.path == "/sync":
            try:
                result = node.sync_with_peers()
                self._send_json(200, result if isinstance(result, dict) else {"accepted": bool(result), "reason": "sync failed"})
                return
            except Exception as exc:
                self._send_json(400, {"accepted": False, "reason": str(exc)})
                return

        if self.path == "/wallet/new":
            try:
                wallet = node.create_wallet()
                self._send_json(200, {"accepted": True, "reason": "wallet created", "wallet": wallet})
                return
            except Exception as exc:
                self._send_json(400, {"accepted": False, "reason": str(exc)})
                return

        if self.path == "/peers/add":
            peer_url = payload.get("peer_url") if isinstance(payload, dict) else payload
            if not peer_url:
                self._send_json(400, {"accepted": False, "reason": "peer_url is required"})
                return
            result = node.add_peer(peer_url)
            self._send_json(200, result if isinstance(result, dict) else {"accepted": bool(result), "reason": "peer add failed", "peers": node.peers})
            return

        if self.path == "/peers/remove":
            peer_url = payload.get("peer_url") if isinstance(payload, dict) else payload
            if not peer_url:
                self._send_json(400, {"accepted": False, "reason": "peer_url is required"})
                return
            result = node.remove_peer(peer_url)
            self._send_json(200, result if isinstance(result, dict) else {"accepted": bool(result), "reason": "peer remove failed", "peers": node.peers})
            return

        self.send_error(404)

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
