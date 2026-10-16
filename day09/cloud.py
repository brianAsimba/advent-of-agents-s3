"""Day 9 local model of a cloud resource hierarchy with IAM inheritance and Principal Access Boundaries.

    org
    └── folders/manufacturing          ← IAM grant here is inherited by every project below
        ├── projects/stamping          ← the agent's home project
        │     bucket stamping-press-data
        └── projects/hr-payroll        ← another team's project
              bucket hr-payroll-exports

Two independent checks, as in Google Cloud. A request succeeds only if BOTH allow it:
  * IAM allow policy: what the principal may do (inherited down the hierarchy)
  * Principal Access Boundary (PAB): which resources the principal may EVER reach (bound to principals)
"""
import fnmatch
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "day05"))
import iam_lib  # noqa: E402  (Day 5 identities)

PARENT = {
    "projects/stamping": "folders/manufacturing",
    "projects/hr-payroll": "folders/manufacturing",
    "folders/manufacturing": "org",
}
BUCKETS = {
    "stamping-press-data": {"project": "projects/stamping",
                            "objects": ["press-07_tonnage_2026-10.csv", "die-4411_tryout_notes.pdf", "springback_runs.parquet"]},
    "hr-payroll-exports": {"project": "projects/hr-payroll",
                           "objects": ["salaries_2026-Q3.csv", "bonus_plan_2027.xlsx", "ssn_lookup.csv"]},
}
# Which project each agent identity belongs to (Google: attribute.container on the SPIFFE ID).
AGENT_HOME = {"spiffe://brian.local/agents/storage_inspector": "projects/stamping"}

IAM: list[dict] = []        # {"resource", "member", "role"}
PAB_POLICIES: dict = {}     # name -> {"allowed_resources": [...]}
PAB_BINDINGS: list[dict] = []  # {"policy", "principal_set"}  e.g. "agents-in:projects/stamping"
AUDIT: list[dict] = []


def reset() -> None:
    IAM.clear(); PAB_POLICIES.clear(); PAB_BINDINGS.clear(); AUDIT.clear()


def ancestors(resource: str) -> list[str]:
    chain = [resource]
    while chain[-1] in PARENT:
        chain.append(PARENT[chain[-1]])
    return chain


def grant(resource: str, principal: str, role: str) -> None:
    IAM.append({"resource": resource, "member": principal, "role": role})


def iam_allows(principal: str, project: str, role: str) -> str | None:
    """Returns where the grant came from (inheritance), or None."""
    for node in ancestors(project):
        for b in IAM:
            if b["resource"] == node and b["role"] == role and fnmatch.fnmatch(principal, b["member"]):
                return node
    return None


def create_pab(name: str, allowed_resources: list[str]) -> None:
    PAB_POLICIES[name] = {"allowed_resources": allowed_resources}


def bind_pab(policy: str, home_project: str) -> None:
    """Bind a PAB policy to every agent identity whose home is home_project."""
    PAB_BINDINGS.append({"policy": policy, "principal_set": f"agents-in:{home_project}"})


def pab_allows(principal: str, project: str) -> tuple[bool, str]:
    home = AGENT_HOME.get(principal)
    bound = [b["policy"] for b in PAB_BINDINGS if home and b["principal_set"] == f"agents-in:{home}"]
    if not bound:
        return True, "no boundary bound"
    for name in bound:
        if any(r in ancestors(project) for r in PAB_POLICIES[name]["allowed_resources"]):
            return True, f"inside boundary '{name}'"
    return False, "Principal Access Boundary violation"


def list_objects(agent_token: str, bucket: str) -> dict:
    """Lists a bucket's objects as the calling agent. Both IAM and PAB must allow it."""
    principal = iam_lib.verify(agent_token)
    b = BUCKETS.get(bucket)
    if b is None:
        return {"status": 404, "error": f"no bucket {bucket}"}
    via = iam_allows(principal, b["project"], "storage.objectViewer")
    pab_ok, pab_reason = pab_allows(principal, b["project"])
    allowed = via is not None and pab_ok
    AUDIT.append({"ts": time.strftime("%H:%M:%S"), "agent": principal.rsplit("/", 1)[-1], "bucket": bucket,
                  "iam": f"ALLOW (granted on {via})" if via else "DENY", "pab": pab_reason, "result": "ALLOW" if allowed else "DENY"})
    if via is None:
        return {"status": 403, "error": "Forbidden: no IAM permission"}
    if not pab_ok:
        return {"status": 403, "error": "403 Forbidden: Principal Access Boundary violation"}
    return {"status": 200, "bucket": bucket, "objects": b["objects"]}
