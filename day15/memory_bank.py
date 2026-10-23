"""Day 15 local model of Memory Bank: exact-match scopes, IAM Conditions per department, one bank per region.

What Google Cloud does                                  What this file does (teaching model)
------------------------------------------------------  ---------------------------------------------------------
Memory Bank stores durable facts per user              Bank.memories: fact + scope, kept in memory
Scope = up to 5 key/value labels                        create() rejects more than MAX_LABELS labels
Retrieval needs a 100% exact match, no wildcards        _same_scope(): same keys AND same values, nothing else
Similarity search, top_k                                retrieve(): word-overlap ranking, top_k (default 5)
roles/aiplatform.memoryUser + IAM Condition             BINDINGS: identity -> allowed bank location + lob label
403 PERMISSION_DENIED before Memory Bank runs          authorize() raises PermissionDenied before any lookup
Separate US and EU banks (GDPR)                         BANKS: us-central1 and europe-west1, separate stores
Cloud Audit Logs                                        AUDIT: who asked, which bank, which scope, allowed or not
"""
import re
from dataclasses import dataclass, field

MAX_LABELS = 5
PROJECT = "brian-local"
REGIONS = {"us": "us-central1", "eu": "europe-west1"}


def resource_name(location: str) -> str:
    return f"projects/{PROJECT}/locations/{location}/reasoningEngines/memory-bank"


def spiffe_id(agent: str) -> str:
    return f"spiffe://brian.local/agents/{agent}"


# IAM Conditions: each department/region agent may only touch its own bank and its own lob label.
BINDINGS = {
    spiffe_id("retail-us"): {"role": "memoryUser", "resource_prefix": resource_name(REGIONS["us"]), "lob": "retail_banking"},
    spiffe_id("retail-eu"): {"role": "memoryUser", "resource_prefix": resource_name(REGIONS["eu"]), "lob": "retail_banking"},
    spiffe_id("wealth-us"): {"role": "memoryUser", "resource_prefix": resource_name(REGIONS["us"]), "lob": "wealth_management"},
}

AUDIT: list[dict] = []


class PermissionDenied(Exception):
    """Mirrors the 403 PERMISSION_DENIED returned before Memory Bank runs."""


@dataclass
class Memory:
    id: str
    fact: str
    scope: dict


@dataclass
class Bank:
    location: str
    memories: list[Memory] = field(default_factory=list)

    @property
    def name(self) -> str:
        return resource_name(self.location)


BANKS = {loc: Bank(loc) for loc in REGIONS.values()}


def reset() -> None:
    for b in BANKS.values():
        b.memories.clear()
    AUDIT.clear()


def authorize(identity: str, bank: Bank, scope: dict, action: str) -> None:
    """IAM check with conditions. Runs before the bank is touched; denies by default."""
    b = BINDINGS.get(identity)
    reason = None
    if b is None:
        reason = "no memoryUser binding for this identity"
    elif not bank.name.startswith(b["resource_prefix"]):
        reason = f"condition failed: resource.name must be in {b['resource_prefix'].split('/')[3]}, not {bank.location}"
    elif scope.get("lob") != b["lob"]:
        reason = f"condition failed: memoryScope lob must be {b['lob']}"
    AUDIT.append({"identity": identity, "action": action, "bank": bank.location, "scope": dict(scope),
                  "allowed": reason is None, "reason": reason})
    if reason:
        raise PermissionDenied(f"403 PERMISSION_DENIED: {reason}")


def _check_scope(scope: dict) -> None:
    if not scope or len(scope) > MAX_LABELS:
        raise ValueError(f"a scope needs 1 to {MAX_LABELS} labels")
    if any(not isinstance(v, str) or not v or "*" in v for v in scope.values()):
        raise ValueError("scope values must be non-empty strings; wildcards are not supported")


def _same_scope(a: dict, b: dict) -> bool:
    return a == b  # every label, exactly: no subsets, no supersets, no wildcards


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def create(identity: str, location: str, scope: dict, fact: str) -> Memory:
    _check_scope(scope)
    bank = BANKS[location]
    authorize(identity, bank, scope, "create")
    m = Memory(id=f"{location}-{len(bank.memories) + 1}", fact=fact, scope=dict(scope))
    bank.memories.append(m)
    return m


def retrieve(identity: str, location: str, scope: dict, query: str = "", top_k: int = 5) -> list[Memory]:
    _check_scope(scope)
    bank = BANKS[location]
    authorize(identity, bank, scope, "retrieve")
    hits = [m for m in bank.memories if _same_scope(m.scope, scope)]
    q = _words(query)
    hits.sort(key=lambda m: len(q & _words(m.fact)), reverse=True)
    AUDIT[-1]["returned"] = [m.id for m in hits[:top_k]]
    return hits[:top_k]


def seed() -> None:
    """Demo data. Facts are invented."""
    reset()
    us, eu = REGIONS["us"], REGIONS["eu"]
    retail_us, retail_eu, wealth_us = spiffe_id("retail-us"), spiffe_id("retail-eu"), spiffe_id("wealth-us")
    for fact in ["Prefers paper statements by mail.",
                 "Saving for a house down payment in 2028.",
                 "Disputed a duplicate card charge in September; it was refunded."]:
        create(retail_us, us, {"lob": "retail_banking", "user_id": "alice"}, fact)
    create(retail_us, us, {"lob": "retail_banking", "user_id": "charlie"}, "Travels to Japan in December; card travel notice set.")
    create(wealth_us, us, {"lob": "wealth_management", "user_id": "alice"}, "Portfolio target 70/30 stocks/bonds.")
    create(retail_eu, eu, {"lob": "retail_banking", "user_id": "emile"}, "Lives in Lyon; prefers French for all letters.")
