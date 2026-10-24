"""Day 20 ingress gateway (the course's Apigee role): expose the legacy REST CRM as a governed MCP tool.

  python day20/ingress_gateway.py --port 8300 --backend http://127.0.0.1:8301 [--no-mediation]

Apigee does                                   Here
--------------------------------------------  ----------------------------------------------------------
REST/SOAP -> MCP JSON-RPC, no backend rewrite  lookup_customer_account() calls GET /crm/v2/accounts/{id}
Schema mediation (lean responses)              mediate(): keep 6 agreed fields, drop the rest
Spike Arrest (stop runaway loops)              SpikeArrest: per client, at most RATE tools/call per WINDOW s -> 429
Payload limits                                 request bodies over MAX_BODY bytes -> 413
The agent never sees the backend's address     only the gateway knows --backend
"""
import argparse
import json
import time
from collections import defaultdict, deque

import httpx
import uvicorn
from mcp.server.mcpserver import MCPServer

KEEP = ("customer_id", "name", "tier", "status", "open_tickets", "balance_due_usd")
RATE, WINDOW = 2, 10.0  # Spike Arrest: 2 tool calls per 10 seconds per client
MAX_BODY = 16_384
STATS = {"backend_calls": 0, "bytes_from_backend": 0, "bytes_to_agent": 0, "rejected_429": 0}


def mediate(record: dict) -> dict:
    return {k: record[k] for k in KEEP if k in record}


def build_server(backend: str, mediation: bool = True) -> MCPServer:
    server = MCPServer("crm-accounts-mcp", version="1.0.0")

    @server.tool()
    def lookup_customer_account(customer_id: str) -> dict:
        """Looks up a customer account by ID (e.g. 'CUST-9921'): name, tier, status, open tickets, balance due."""
        r = httpx.get(f"{backend}/crm/v2/accounts/{customer_id}", timeout=10)
        STATS["backend_calls"] += 1
        STATS["bytes_from_backend"] += len(r.content)
        if r.status_code != 200:
            return {"error": f"account {customer_id} not found"}
        out = mediate(r.json()) if mediation else r.json()
        STATS["bytes_to_agent"] += len(json.dumps(out))
        return out

    return server


class SpikeArrest:
    def __init__(self, rate: int = RATE, window: float = WINDOW, clock=time.monotonic):
        self.rate, self.window, self.clock = rate, window, clock
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, client: str) -> bool:
        now, q = self.clock(), self.hits[client]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.rate:
            return False
        q.append(now)
        return True


def protect(app, arrest: SpikeArrest):
    """ASGI wrapper in front of the MCP endpoint: body limit, then Spike Arrest on tools/call."""
    async def reply(send, status, payload, extra=()):
        body = json.dumps(payload).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), *extra]})
        await send({"type": "http.response.body", "body": body})

    async def guarded(scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await app(scope, receive, send)
        body, more = b"", True
        while more:
            msg = await receive()
            body += msg.get("body", b"")
            more = msg.get("more_body", False)
            if len(body) > MAX_BODY:
                return await reply(send, 413, {"error": "payload too large"})
        try:
            rpc = json.loads(body or b"{}")
        except ValueError:
            rpc = {}
        if rpc.get("method") == "tools/call":
            client = dict(scope["headers"]).get(b"x-client-id", b"anonymous").decode()
            if not arrest.allow(client):
                STATS["rejected_429"] += 1
                return await reply(send, 429, {"jsonrpc": "2.0", "id": rpc.get("id"), "error": {
                    "code": -32029, "message": f"Spike Arrest: more than {arrest.rate} tool calls in "
                                               f"{arrest.window:g}s for client '{client}'"}},
                                   [(b"retry-after", str(int(arrest.window)).encode())])
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await app(scope, replay, send)
    return guarded


def build_app(backend: str, mediation: bool = True, arrest: SpikeArrest | None = None):
    mcp_app = build_server(backend, mediation).streamable_http_app(
        streamable_http_path="/v1/mcp", stateless_http=True, json_response=True)
    return protect(mcp_app, arrest or SpikeArrest())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--no-mediation", action="store_true")
    ap.add_argument("--rate", type=int, default=RATE)
    a = ap.parse_args()
    uvicorn.run(build_app(a.backend, not a.no_mediation, SpikeArrest(rate=a.rate)), host="127.0.0.1", port=a.port,
                log_level="warning")
