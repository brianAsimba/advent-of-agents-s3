"""Day 5 local model of Agent Identity: one identity per agent, deny by default, audited.

What Google Cloud does                         What this file does (teaching model, not real crypto infra)
---------------------------------------------  ------------------------------------------------------------
Agent Runtime mints a SPIFFE ID per agent      mint() issues a signed token: spiffe://brian.local/agents/<name>
X.509 cert rotated every 24 h, no key file     token expires after 24 h; it lives in memory, never on disk
IAM binding on principal://<agent identity>    iam.json maps each principal to roles
New identity has no data access by default     check() denies unless a binding grants the role
Cloud Logging principalSubject                 audit.jsonl records which principal did what, allowed or not
"""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
IAM_FILE = HERE / "iam.json"
AUDIT_FILE = HERE / "audit.jsonl"
DB_FILE = HERE / "warehouse.db"
TRUST_DOMAIN = "brian.local"
TTL_SECONDS = 24 * 3600


def _secret() -> bytes:
    s = os.environ.get("ISSUER_SECRET")
    if not s:
        raise RuntimeError("ISSUER_SECRET is not set (see day05/.env.example).")
    return s.encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------- identity ----------

def spiffe_id(agent_name: str) -> str:
    return f"spiffe://{TRUST_DOMAIN}/agents/{agent_name}"


def mint(agent_name: str, ttl: int = TTL_SECONDS, now: float | None = None) -> str:
    """Issues a short-lived identity token for exactly one agent."""
    now = time.time() if now is None else now
    claims = {"sub": spiffe_id(agent_name), "iat": int(now), "exp": int(now + ttl)}
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token: str, now: float | None = None) -> str:
    """Returns the agent's SPIFFE ID if the token is genuine and unexpired; raises otherwise."""
    now = time.time() if now is None else now
    try:
        body, sig = token.split(".")
    except ValueError:
        raise PermissionError("malformed token")
    expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise PermissionError("bad signature")
    claims = json.loads(_unb64(body))
    if claims["exp"] < now:
        raise PermissionError("token expired")
    return claims["sub"]


# ---------- IAM ----------

def load_policy() -> dict:
    return json.loads(IAM_FILE.read_text()) if IAM_FILE.exists() else {"bindings": []}


def grant(principal: str, role: str) -> None:
    policy = load_policy()
    b = {"member": f"principal://{principal}", "role": role}
    if b not in policy["bindings"]:
        policy["bindings"].append(b)
    IAM_FILE.write_text(json.dumps(policy, indent=2))


def revoke(principal: str, role: str | None = None) -> None:
    policy = load_policy()
    policy["bindings"] = [b for b in policy["bindings"]
                          if not (b["member"] == f"principal://{principal}" and (role is None or b["role"] == role))]
    IAM_FILE.write_text(json.dumps(policy, indent=2))


def has_role(principal: str, role: str) -> bool:
    return {"member": f"principal://{principal}", "role": role} in load_policy()["bindings"]


def audit(principal: str, action: str, resource: str, allowed: bool, detail: str = "") -> None:
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "principalSubject": principal,
             "action": action, "resourceName": resource, "allowed": allowed, "detail": detail}
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ---------- the "warehouse" (stands in for BigQuery) ----------

REQUIRED_ROLES = ("warehouse.jobUser", "warehouse.dataViewer")  # like bigquery.jobUser + bigquery.dataViewer


def run_query(token: str, sql: str) -> dict:
    """Runs a read-only SQL query as the agent that owns the token."""
    try:
        principal = verify(token)
    except PermissionError as e:
        audit("unknown", "query", "datasets/sample_data", False, f"identity rejected: {e}")
        return {"status": "error", "error_message": f"Identity rejected: {e}"}
    missing = [r for r in REQUIRED_ROLES if not has_role(principal, r)]
    if missing:
        audit(principal, "query", "datasets/sample_data", False, "missing " + ", ".join(missing))
        return {"status": "error", "error_message": f"Permission denied for {principal}: missing {', '.join(missing)}."}
    if not sql.strip().lower().startswith("select"):
        audit(principal, "query", "datasets/sample_data", False, "non-SELECT statement")
        return {"status": "error", "error_message": "Only SELECT queries are allowed."}
    con = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
    try:
        cur = con.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    except sqlite3.Error as e:
        audit(principal, "query", "datasets/sample_data", False, f"sql error: {e}")
        return {"status": "error", "error_message": str(e)}
    finally:
        con.close()
    audit(principal, "query", "datasets/sample_data", True, f"{len(rows)} rows")
    return {"status": "success", "rows": rows}
