"""Day 19 shared state: the service catalog (registry) and the credential store (Agent Auth Manager).

What Google Cloud does                                  Here (files under day19/.state/, gitignored)
------------------------------------------------------  ------------------------------------------------------
Agent Registry Services API: create_service             register_service(): name, version, interfaces[url], status
Platform team rotates an endpoint / patches a server     update_endpoint(): new URL + version, same logical name
Revoke a compromised integration                         revoke(): status -> REVOKED; resolution then fails closed
AuthProviderBinding -> Agent Auth Manager (keys, OAuth)  bind_credential(), credential(): secrets live ONLY here,
                                                         never in agent code, .env, or anything the model sees
"""
import json
import os
import secrets
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = Path(os.environ.get("DAY19_STATE", HERE / ".state"))


def _path(name: str) -> Path:
    return STATE / f"{name}.json"


def _load(name: str) -> dict:
    p = _path(name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(name: str, data: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    _path(name).write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------- registry (admin side; the agent side is registry_mcp.py, read-only) ----------

def register_service(name: str, url: str, version: str, description: str, binding: str) -> dict:
    services = _load("registry")
    services[name] = {"name": name, "description": description, "version": version, "status": "APPROVED",
                      "interfaces": [{"url": url, "protocol": "STREAMABLE_HTTP"}], "auth_binding": binding}
    _save("registry", services)
    return services[name]


def update_endpoint(name: str, url: str, version: str) -> None:
    services = _load("registry")
    services[name].update(version=version, interfaces=[{"url": url, "protocol": "STREAMABLE_HTTP"}])
    _save("registry", services)


def revoke(name: str) -> None:
    services = _load("registry")
    services[name]["status"] = "REVOKED"
    _save("registry", services)


def services() -> dict:
    return _load("registry")


# ---------- credentials (Agent Auth Manager) ----------

def bind_credential(binding: str, secret: str | None = None) -> None:
    """Stores (or rotates) the credential behind a binding. Returns nothing: callers never need the value."""
    creds = _load("credentials")
    creds[binding] = {"type": "api_key", "value": secret or secrets.token_urlsafe(24)}
    _save("credentials", creds)


def credential(binding: str) -> str:
    c = _load("credentials").get(binding)
    if c is None:
        raise KeyError(f"no credential bound as '{binding}'")
    return c["value"]
