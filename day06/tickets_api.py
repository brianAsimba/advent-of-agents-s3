"""A stand-in for a third-party ticket system (the course uses Jira/GitHub).

It enforces its own access rules: a user's OAuth token sees only that user's tickets.
It also has a shared service token that sees everything: the anti-pattern Day 6 warns about.
"""
import base64
import hashlib
import hmac
import json

_TRACKER_SECRET = b"tracker-private-signing-key"  # belongs to the ticket system, never to the agent
SERVICE_TOKEN = "svc-shared-helpdesk-token"        # one token for the whole agent: sees every ticket

TICKETS = [
    {"id": "T-101", "owner": "alice", "title": "VPN drops every hour", "status": "open"},
    {"id": "T-102", "owner": "alice", "title": "Laptop battery swelling", "status": "open"},
    {"id": "T-103", "owner": "bob", "title": "Payroll portal shows the wrong salary", "status": "open"},
    {"id": "T-104", "owner": "bob", "title": "Request: access to the HR folder", "status": "closed"},
    {"id": "T-105", "owner": "carol", "title": "Reported a phishing email", "status": "open"},
]


def _sign(body: str) -> str:
    return hmac.new(_TRACKER_SECRET, body.encode(), hashlib.sha256).hexdigest()


def oauth_authorize(user: str, scopes: str = "tickets:read") -> str:
    """The OAuth consent result: an access token for exactly this user."""
    body = base64.urlsafe_b64encode(json.dumps({"sub": user, "scope": scopes}).encode()).decode()
    return f"{body}.{_sign(body)}"


def _user_from(token: str) -> str | None:
    """Returns the user for a valid user token, '*' for the service token, None otherwise."""
    if token == SERVICE_TOKEN:
        return "*"
    try:
        body, sig = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    return json.loads(base64.urlsafe_b64decode(body))["sub"]


def list_tickets(bearer: str, status: str | None = None) -> dict:
    """GET /tickets with an Authorization: Bearer header. The tracker decides what you can see."""
    who = _user_from(bearer)
    if who is None:
        return {"status": 401, "error": "invalid token"}
    rows = [t for t in TICKETS if who == "*" or t["owner"] == who]
    if status:
        rows = [t for t in rows if t["status"] == status]
    return {"status": 200, "tickets": rows}
