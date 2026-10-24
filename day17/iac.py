"""Day 17: a tiny Terraform-style engine for the agent stack: plan, guard, apply, drift, build.

What the course does (Terraform + Cloud Build)             What this file does (teaching model)
---------------------------------------------------------  -------------------------------------------------------
*.tf files, peer-reviewed in Git                            stack/foundation.json, stack/runtime.json
Two state layers in a remote GCS bucket                     .iac/state/<layer>.json (gitignored)
The real cloud resources                                    .iac/cloud/<layer>.json, editable by hand = "the console"
terraform plan on a pull request                            plan(): + create, ~ change, - destroy, per attribute
Stage outputs (gateway IDs, TLS certs) passed downstream    outputs + "${foundation.egress_gateway.id}" references
Container image tagged with the build ID                     build(): tar.gz of agent/ + wiring.json, sha256 digest
(policy-as-code, e.g. OPA/Conftest in CI)                   guard(): blocks plans that weaken a security layer
Drift (console edits)                                       drift(): cloud vs state
"""
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STACK = HERE / "stack"
WORK = HERE / ".iac"
LAYERS = ("foundation", "runtime")
REF = re.compile(r"\$\{([a-z_]+)\.([a-z_.]+)\}")
BROAD_ROLES = {"owner", "editor", "*"}
SECURITY_RESOURCES = {"agent_gateway", "governance_policy"}


class GuardFailed(Exception):
    def __init__(self, violations: list[str]):
        super().__init__("; ".join(violations))
        self.violations = violations


def _read(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _write(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def desired(layer: str, refs: dict) -> dict:
    """The layer's resources from code, with ${...} references resolved from upstream outputs."""
    def res(v):
        if isinstance(v, str):
            def sub(m):
                key = f"{m.group(1)}.{m.group(2)}"
                if key not in refs:
                    raise KeyError(f"unresolved reference ${{{key}}}")
                return refs[key]
            return REF.sub(sub, v)
        if isinstance(v, dict):
            return {k: res(x) for k, x in v.items()}
        if isinstance(v, list):
            return [res(x) for x in v]
        return v
    return res(_read(STACK / f"{layer}.json")["resources"])


def state(layer: str) -> dict:
    return _read(WORK / "state" / f"{layer}.json", {"resources": {}, "outputs": {}})


def cloud(layer: str) -> dict:
    return _read(WORK / "cloud" / f"{layer}.json", {})


def _flat(resources: dict) -> dict:
    out = {}
    def walk(prefix, v):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(f"{prefix}.{k}" if prefix else k, x)
        else:
            out[prefix] = v
    walk("", resources)
    return out


def diff(old: dict, new: dict) -> list[tuple[str, str, object, object]]:
    changes = [("+", r, None, new[r]) for r in new if r not in old]
    changes += [("-", r, old[r], None) for r in old if r not in new]
    fo = _flat({r: old[r] for r in old if r in new})
    fn = _flat({r: new[r] for r in new if r in old})
    changes += [("~", k, fo.get(k), fn.get(k)) for k in sorted(set(fo) | set(fn)) if fo.get(k) != fn.get(k)]
    return changes


def guard(resources: dict, changes: list) -> list[str]:
    """Policy as code: rules a reviewer would otherwise have to catch by eye."""
    v = []
    for name, r in resources.items():
        t = r.get("type")
        if t == "iam_binding":
            bad = [x for x in r.get("roles", []) if x in BROAD_ROLES or x.endswith(".admin")]
            if bad:
                v.append(f"{name}: broad IAM role(s) {bad}; grant least privilege")
        if t == "agent_gateway" and r.get("direction") == "agent_to_anywhere":
            if r.get("default") != "deny" or "*" in r.get("allow", []):
                v.append(f"{name}: egress must be deny-by-default with no wildcard")
        if t == "agent_gateway" and r.get("direction") == "client_to_agent":
            s = r.get("shield", {})
            if s.get("prompt_injection") != "block" or s.get("fail_mode") != "closed":
                v.append(f"{name}: ingress shield must block prompt injection and fail closed")
        if t == "governance_policy" and r.get("max_cents", 0) > 10000:
            v.append(f"{name}: spend cap above $100 needs a separate approved change")
        if t == "agent_runtime" and not r.get("identity", "").startswith("spiffe://"):
            v.append(f"{name}: agent must run with its own SPIFFE identity")
    for op, name, old, _ in changes:
        if op == "-" and isinstance(old, dict) and old.get("type") in SECURITY_RESOURCES:
            v.append(f"{name}: plan would DESTROY a security layer ({old['type']})")
    return v


def plan(layer: str, refs: dict) -> tuple[dict, list, list[str]]:
    want = desired(layer, refs)
    changes = diff(state(layer)["resources"], want)
    return want, changes, guard(want, changes)


def _outputs(layer: str, resources: dict) -> dict:
    out = {}
    for name, r in resources.items():
        rid = f"projects/brian-local/{layer}/{name}"
        out[f"{layer}.{name}.id"] = rid
        if r.get("type") == "agent_gateway":
            out[f"{layer}.{name}.tls_root"] = "sha256:" + hashlib.sha256(rid.encode()).hexdigest()[:16]
    return out


def apply(layer: str, refs: dict) -> dict:
    want, changes, violations = plan(layer, refs)
    if violations:
        raise GuardFailed(violations)
    outputs = _outputs(layer, want)
    _write(WORK / "cloud" / f"{layer}.json", want)
    _write(WORK / "state" / f"{layer}.json", {"resources": want, "outputs": outputs})
    return outputs


def drift(layer: str) -> list:
    """What changed in the 'cloud' that code and state don't know about (e.g. a console edit)."""
    return diff(state(layer)["resources"], cloud(layer))


def build(build_id: str, refs: dict, write: bool = True) -> dict:
    """Stage 2: package agent code + gateway wiring into an 'image' tagged with the build ID.
    write=False only computes the image name (for plans)."""
    wiring = {k: v for k, v in refs.items() if "gateway" in k}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for p in sorted((HERE / "agent").rglob("*.py")):
            info = tar.gettarinfo(str(p), arcname=f"agent/{p.name}")
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, "", ""
            with p.open("rb") as f:
                tar.addfile(info, f)
        data = json.dumps(wiring, sort_keys=True).encode()
        info = tarfile.TarInfo("agent/wiring.json")
        info.size, info.mtime = len(data), 0
        tar.addfile(info, io.BytesIO(data))
    blob = gzip.compress(buf.getvalue(), mtime=0)  # fixed timestamps: same code -> same digest
    digest = hashlib.sha256(blob).hexdigest()
    if write:
        out = WORK / "build" / f"agent-{build_id}.tar.gz"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
    return {"build.image": f"localhost/agents/terraform-demo-agent:{build_id}@sha256:{digest[:12]}"}
