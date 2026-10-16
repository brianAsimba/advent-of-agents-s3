"""A stand-in for a third-party API plus its OAuth server, with offline access.

- consent with scope "offline_access" returns a short-lived access token AND a refresh token
- access tokens expire after 15 minutes
- refresh tokens ROTATE: each exchange returns a new one and kills the old one
- replaying an already-used refresh token is treated as theft: the whole token family is revoked
"""
import secrets
import time

ACCESS_TTL = 15 * 60

REPORTS = {
    "alice": [
        {"id": "INC-881", "time": "01:12", "summary": "Checkout API latency spiked to 4 s for 9 minutes; auto-recovered."},
        {"id": "INC-882", "time": "02:40", "summary": "Nightly backup job failed on db-03; retry succeeded at 03:05."},
    ],
    "bob": [
        {"id": "INC-883", "time": "00:30", "summary": "Payroll export delayed 20 minutes by a lock on the HR database."},
    ],
}

# server-side state of the OAuth provider
_access: dict[str, dict] = {}       # access token -> {user, exp}
_refresh: dict[str, dict] = {}      # refresh token -> {user, family, used}
_revoked_families: dict[str, str] = {}   # family -> reason it was revoked


def _issue(user: str, family: str, now: float) -> dict:
    at, rt = "at_" + secrets.token_hex(8), "rt_" + secrets.token_hex(8)
    _access[at] = {"user": user, "exp": now + ACCESS_TTL}
    _refresh[rt] = {"user": user, "family": family, "used": False}
    return {"access_token": at, "expires_in": ACCESS_TTL, "refresh_token": rt}


def authorize(user: str, scopes: list[str], now: float | None = None) -> dict:
    """The user is online and consents. Only offline_access yields a refresh token."""
    now = time.time() if now is None else now
    tokens = _issue(user, family=secrets.token_hex(4), now=now)
    if "offline_access" not in scopes:
        _refresh.pop(tokens.pop("refresh_token"))
    return tokens


def refresh(refresh_token: str, now: float | None = None) -> dict:
    """grant_type=refresh_token. Rotates the refresh token; detects reuse."""
    now = time.time() if now is None else now
    rec = _refresh.get(refresh_token)
    if rec is None:
        return {"error": "invalid_grant", "error_description": "refresh token unknown"}
    if rec["family"] in _revoked_families:
        # Tell later callers WHY: the legitimate job needs to know this was a theft, not an expiry.
        return {"error": "invalid_grant", "error_description": _revoked_families[rec["family"]]}
    if rec["used"]:
        reason = "refresh token reuse detected; all tokens revoked"
        _revoked_families[rec["family"]] = reason  # someone replayed an old token: assume theft
        return {"error": "invalid_grant", "error_description": reason}
    rec["used"] = True
    return _issue(rec["user"], rec["family"], now)


def get_reports(bearer: str, now: float | None = None) -> dict:
    """GET /reports. Returns only the token owner's reports."""
    now = time.time() if now is None else now
    rec = _access.get(bearer)
    if rec is None:
        return {"status": 401, "error": "invalid token"}
    if rec["exp"] < now:
        return {"status": 401, "error": "access token expired"}
    return {"status": 200, "user": rec["user"], "reports": REPORTS.get(rec["user"], [])}
