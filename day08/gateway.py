"""Day 8 local model of Agent Gateway: a checkpoint between agents and the tools they call.

Course (Google Cloud)                                Here
---------------------------------------------------  -----------------------------------------------
Agent Gateway inspects every outbound request         call() is the only path from agents to tool servers
Default deny on egress                                 unmatched requests are denied
IAM Access Policy: DENY rules evaluated first          decide(): DENY, then ALLOW, then default deny
Principals = agent SPIFFE identities (Day 5)          caller identity verified from its Day 5 token
CEL: destination.agent_registry.mcp_server.tool.name  condition {"tool_name_in": [...]} (no eval(), just data)
Agent Registry (approved MCP servers)                 REGISTRY
HTTP 403 Forbidden at the proxy                        {"status": 403, ...}; the backend never sees the call
"""
import fnmatch
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "day05"))
import iam_lib  # noqa: E402

POLICY_FILE = HERE / "policy.json"
AUDIT: list[dict] = []
BACKEND_CALLS: list[str] = []  # what actually reached the tool server

REGISTRY = {"orders-mcp": "https://orders.internal/mcp"}  # approved servers (Agent Registry)

ORDERS = {"O-1001": {"customer": "C-77", "status": "shipped", "carrier": "UPS", "eta": "Oct 18", "total": 129.00}}


# ---------- the tool server (only reachable through the gateway) ----------

def _backend(tool: str, args: dict) -> dict:
    BACKEND_CALLS.append(tool)
    if tool == "lookup_order":
        order = ORDERS.get(args.get("order_id", ""))
        return {"status": 200, "order": order} if order else {"status": 404, "error": "no such order"}
    if tool == "issue_refund":
        return {"status": 200, "refunded": args.get("amount"), "order_id": args.get("order_id")}
    if tool == "delete_account":
        return {"status": 200, "deleted": args.get("customer_id")}
    return {"status": 404, "error": f"unknown tool {tool}"}


# ---------- policy ----------

def _matches(rule: dict, principal: str, server: str, tool: str) -> bool:
    if not any(fnmatch.fnmatch(principal, p) for p in rule["principals"]):
        return False
    cond = rule.get("condition", {})
    if "tool_name_in" in cond and tool not in cond["tool_name_in"]:
        return False
    if "destination_is_registered" in cond and (server in REGISTRY) != cond["destination_is_registered"]:
        return False
    return True


def decide(principal: str, server: str, tool: str) -> tuple[str, str]:
    """Returns (ALLOW|DENY, reason). DENY rules first, then ALLOW, else default deny."""
    rules = json.loads(POLICY_FILE.read_text())["rules"]
    for r in (r for r in rules if r["effect"] == "DENY"):
        if _matches(r, principal, server, tool):
            return "DENY", r["description"]
    for r in (r for r in rules if r["effect"] == "ALLOW"):
        if _matches(r, principal, server, tool):
            return "ALLOW", r["description"]
    return "DENY", "default deny (no ALLOW rule matched)"


def call(agent_token: str, server: str, tool: str, args: dict) -> dict:
    """Every tool call goes through here. Blocked calls never reach the server."""
    try:
        principal = iam_lib.verify(agent_token)
    except PermissionError as e:
        principal, verdict, reason = "unknown", "DENY", f"identity rejected: {e}"
    else:
        verdict, reason = decide(principal, server, tool)
    AUDIT.append({"ts": time.strftime("%H:%M:%S"), "agent": principal.rsplit("/", 1)[-1],
                  "server": server, "tool": tool, "verdict": verdict, "reason": reason})
    if verdict == "DENY":
        return {"status": 403, "error": "Forbidden: blocked by Agent Gateway policy", "reason": reason}
    return _backend(tool, args)
