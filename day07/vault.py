"""A stand-in for Cloud Secret Manager: versioned secrets, readable only by authorized agents.

Each user's refresh token is a secret ("refresh-token-<user>") with versions. On every
refresh the job adds the rotated token as a new version and disables the old one.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "day05"))
import iam_lib  # noqa: E402  (Day 5 agent identity)

ALLOWED_AGENTS = {iam_lib.spiffe_id("overnight_summarizer")}

_secrets: dict[str, list[dict]] = {}   # name -> [{"data", "enabled", "created"}]
AUDIT: list[dict] = []


def _log(**e) -> None:
    AUDIT.append({"ts": time.strftime("%H:%M:%S"), **e})


def _agent(agent_token: str) -> str:
    agent = iam_lib.verify(agent_token)
    if agent not in ALLOWED_AGENTS:
        _log(event="AccessDenied", agent=agent)
        raise PermissionError(f"{agent} may not read this vault")
    return agent


def add_version(name: str, data: str) -> int:
    _secrets.setdefault(name, []).append({"data": data, "enabled": True, "created": time.time()})
    return len(_secrets[name])  # version number, 1-based


def access_latest(agent_token: str, name: str) -> tuple[int, str]:
    agent = _agent(agent_token)
    versions = _secrets.get(name, [])
    for i in range(len(versions), 0, -1):
        if versions[i - 1]["enabled"]:
            _log(event="AccessSecretVersion", agent=agent, secret=name, version=i)
            return i, versions[i - 1]["data"]
    _log(event="AccessSecretVersion", agent=agent, secret=name, version=None)
    raise LookupError(f"no enabled version of {name}")


def disable_version(name: str, version: int) -> None:
    _secrets[name][version - 1]["enabled"] = False


def versions(name: str) -> list[str]:
    return [("enabled" if v["enabled"] else "disabled") for v in _secrets.get(name, [])]
