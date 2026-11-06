"""Day 27 local control plane: data boundaries that hold whatever the model does.

Course (Google Cloud)                                  Here
-----------------------------------------------------  ---------------------------------------------------------
Organization Policies                                  org_policy.json, checked when a resource is created or used
CMEK; region must match; disabling is a kill switch    boundary_kms.py, real AES-256-GCM envelope encryption
Access level first, so admins aren't locked out        enforce_perimeter() refuses to lock its own admin out
VPC-SC perimeter with no egress rules                  Perimeter, checked on every call below the agent's tools
restricted.googleapis.com, no public routes            fetch(): only routes that exist can be reached
Private Service Connect                                PSC_ENDPOINTS, one named private bridge
*(my addition)*                                        dry-run mode, to see what would break before enforcing

The caller's project, network and address are set here, never by the model. This all runs in one Python process, so it
shows the rules, not the isolation: in Google Cloud they sit in front of the API, where the agent's code can't reach.
"""
import ipaddress
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from boundary_kms import DESTROYED, DISABLED, ENABLED, KMS, KeyUnavailable

POLICY_FILE = Path(__file__).resolve().parent / "org_policy.json"
VALUE_GROUPS = {"in:us-locations": {"us", "us-central1", "us-east1", "us-east4", "us-west1"}}
US_ENDPOINTS = VALUE_GROUPS["in:us-locations"]
RESTRICTED_VIP = "restricted.googleapis.com"
PSC_ENDPOINTS = {"crm.psc.internal": "onprem-crm"}
PRIVATE_NETWORK = "prod-vpc"


class Denied(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Caller:
    principal: str
    project: str
    network: str
    ip: str


@dataclass
class Perimeter:
    projects: set[str]
    services: set[str]
    access_levels: list[dict] = field(default_factory=list)  # each: {"principals": [...], "ip_ranges": [...]}
    enforced: bool = False  # False = dry run: log what would be denied, block nothing


@dataclass
class Bucket:
    name: str
    project: str
    location: str
    key: str | None
    objects: dict = field(default_factory=dict)


class Cloud:
    def __init__(self, db: str = ":memory:"):
        self.kms = KMS()
        self.policies: dict[str, dict] = {}  # project -> org policy
        self.iam: dict[str, dict[str, set[str]]] = {}  # principal -> project -> roles
        self.buckets: dict[str, Bucket] = {}
        self.perimeter: Perimeter | None = None
        self.audit_db = sqlite3.connect(db)
        self.audit_db.executescript("""
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, ts TEXT DEFAULT CURRENT_TIMESTAMP,
                outcome TEXT, code TEXT, principal TEXT, source TEXT, action TEXT);
            CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'append-only'); END;
        """)

    # ---------- plumbing ----------

    def _log(self, outcome: str, code: str, caller: Caller, action: str) -> None:
        self.audit_db.execute("INSERT INTO events (outcome, code, principal, source, action) VALUES (?,?,?,?,?)",
                              (outcome, code, caller.principal, f"{caller.project}/{caller.ip}", action))
        self.audit_db.commit()

    def audit_rows(self) -> list[tuple]:
        return self.audit_db.execute("SELECT outcome, code, principal, source, action FROM events ORDER BY seq").fetchall()

    def _deny(self, code: str, detail: str, caller: Caller, action: str):
        self._log("DENIED", code, caller, action)
        raise Denied(code, detail)

    def grant(self, principal: str, project: str, *roles: str) -> None:
        self.iam.setdefault(principal, {}).setdefault(project, set()).update(roles)

    def _require_role(self, caller: Caller, project: str, role: str, action: str) -> None:
        if role not in self.iam.get(caller.principal, {}).get(project, set()):
            self._deny("IAM_DENIED", f"{caller.principal} lacks {role} on {project}", caller, action)

    # ---------- org policies ----------

    def set_org_policy(self, caller: Caller, project: str, policy: dict) -> None:
        self._require_role(caller, project, "orgpolicy.admin", f"set org policy on {project}")
        self.policies[project] = policy
        self._log("OK", "", caller, f"set org policy on {project}")

    def _check_location(self, caller: Caller, project: str, location: str, action: str) -> None:
        policy = self.policies.get(project, {}).get("gcp.resourceLocations")
        if policy and location not in set().union(*(VALUE_GROUPS[g] for g in policy["allow"])):
            self._deny("ORG_POLICY_LOCATION", f"{location} is outside the locations allowed for {project}", caller, action)

    def _check_cmek(self, caller: Caller, project: str, service: str, key: str | None, location: str, action: str) -> None:
        policy = self.policies.get(project, {}).get("gcp.restrictNonCmekServices")
        if policy and service in policy["deny"] and key is None:
            self._deny("ORG_POLICY_CMEK", f"{service} on {project} requires a customer-managed key", caller, action)
        if key is not None:
            if key not in self.kms.keys:
                self._deny("KEY_NOT_FOUND", f"no key named {key}", caller, action)
            region = self.kms.keys[key]["region"]
            if region != location:
                self._deny("KEY_REGION_MISMATCH", f"key is in {region}, resource is in {location}", caller, action)

    def create_sa_key(self, caller: Caller, project: str) -> None:
        action = f"create service account key in {project}"
        if self.policies.get(project, {}).get("iam.disableServiceAccountKeyCreation", {}).get("enforce"):
            self._deny("ORG_POLICY_SA_KEYS", "downloadable service account keys are disabled", caller, action)
        self._log("OK", "", caller, action)

    def call_model(self, caller: Caller, project: str, endpoint: str, prompt: str = "") -> str:
        """Simulated model endpoint. The demo's real Claude calls do not go through this: see the README."""
        action = f"call model endpoint {endpoint}"
        policy = self.policies.get(project, {}).get("gcp.restrictEndpointUsage")
        if policy and "in:non-us-aiplatform-endpoints" in policy["deny"] and endpoint not in US_ENDPOINTS:
            self._deny("ORG_POLICY_ENDPOINT", f"endpoint {endpoint} is not allowed for {project}", caller, action)
        self._check_perimeter(caller, "aiplatform", {project}, action)
        self._log("OK", "", caller, action)
        return "simulated model reply"

    # ---------- the perimeter ----------

    def _meets_access_level(self, caller: Caller, perimeter: Perimeter) -> bool:
        return any(caller.principal in level["principals"] and
                   any(ipaddress.ip_address(caller.ip) in ipaddress.ip_network(r) for r in level["ip_ranges"])
                   for level in perimeter.access_levels)

    def set_perimeter(self, caller: Caller, perimeter: Perimeter) -> None:
        """Starts in dry run. Enforcing is a separate step, because enforcing can lock you out."""
        self._require_role(caller, "org", "perimeter.admin", "set perimeter")
        perimeter.enforced = False
        self.perimeter = perimeter
        self._log("OK", "", caller, "set perimeter (dry run)")

    def enforce_perimeter(self, caller: Caller) -> None:
        self._require_role(caller, "org", "perimeter.admin", "enforce perimeter")
        p = self.perimeter
        if p is None:
            raise Denied("NO_PERIMETER", "create a perimeter first")
        if caller.project not in p.projects and not self._meets_access_level(caller, p):
            self._deny("WOULD_LOCK_OUT", "you are outside the perimeter and meet no access level; add one first",
                       caller, "enforce perimeter")
        p.enforced = True
        self._log("OK", "", caller, "enforce perimeter")

    def _check_perimeter(self, caller: Caller, service: str, targets: set[str], action: str) -> None:
        p = self.perimeter
        if p is None or service not in p.services:
            return
        inside = targets & p.projects
        code, detail = None, ""
        if inside and targets - p.projects:  # a request spanning the line is egress, whoever makes it
            code, detail = "VPC_SC_EGRESS", f"this crosses the perimeter to {sorted(targets - p.projects)}; no egress rules exist"
        elif not inside and caller.project in p.projects:
            code, detail = "VPC_SC_EGRESS", f"{sorted(targets)} is outside the perimeter; no egress rules exist"
        elif inside and caller.project not in p.projects and not self._meets_access_level(caller, p):
            code, detail = "VPC_SC_INGRESS", f"{caller.ip} is outside the perimeter and meets no access level"
        if code is None:
            return
        if not p.enforced:
            self._log("WOULD_DENY", code, caller, action)
            return
        self._deny(code, detail, caller, action)

    # ---------- storage ----------

    def create_bucket(self, caller: Caller, name: str, project: str, location: str, key: str | None = None) -> None:
        action = f"create bucket {name} in {location}"
        self._check_perimeter(caller, "storage", {project}, action)
        self._require_role(caller, project, "storage.admin", action)
        self._check_location(caller, project, location, action)
        self._check_cmek(caller, project, "storage.googleapis.com", key, location, action)
        self.buckets[name] = Bucket(name, project, location, key)
        self._log("OK", "", caller, action)

    def _bucket(self, caller: Caller, name: str, action: str) -> Bucket:
        if name not in self.buckets:
            self._deny("NOT_FOUND", f"no bucket named {name}", caller, action)
        return self.buckets[name]

    def _seal(self, bucket: Bucket, name: str, data: bytes):
        aad = f"{bucket.name}/{name}".encode()  # ties the ciphertext to this object, so it can't be moved
        return self.kms.encrypt(bucket.key, data, aad) if bucket.key else data

    def _open(self, bucket: Bucket, name: str) -> bytes:
        stored = bucket.objects[name]
        return self.kms.decrypt(stored, f"{bucket.name}/{name}".encode()) if bucket.key else stored

    def put(self, caller: Caller, bucket_name: str, name: str, data: bytes) -> None:
        action = f"write {bucket_name}/{name}"
        b = self._bucket(caller, bucket_name, action)
        self._check_perimeter(caller, "storage", {b.project}, action)
        self._require_role(caller, b.project, "storage.writer", action)
        try:
            b.objects[name] = self._seal(b, name, data)
        except KeyUnavailable as e:
            self._deny(e.code, e.detail, caller, action)
        self._log("OK", "", caller, action)

    def list_objects(self, caller: Caller, bucket_name: str) -> list[str]:
        action = f"list {bucket_name}"
        b = self._bucket(caller, bucket_name, action)
        self._check_perimeter(caller, "storage", {b.project}, action)
        self._require_role(caller, b.project, "storage.reader", action)
        self._log("OK", "", caller, action)
        return sorted(b.objects)

    def get(self, caller: Caller, bucket_name: str, name: str) -> bytes:
        action = f"read {bucket_name}/{name}"
        b = self._bucket(caller, bucket_name, action)
        self._check_perimeter(caller, "storage", {b.project}, action)
        self._require_role(caller, b.project, "storage.reader", action)
        if name not in b.objects:
            self._deny("NOT_FOUND", f"no object {name} in {bucket_name}", caller, action)
        try:
            data = self._open(b, name)
        except KeyUnavailable as e:
            self._deny(e.code, e.detail, caller, action)
        self._log("OK", "", caller, action)
        return data

    def copy(self, caller: Caller, src_bucket: str, name: str, dst_bucket: str) -> None:
        action = f"copy {src_bucket}/{name} to {dst_bucket}"
        src, dst = self._bucket(caller, src_bucket, action), self._bucket(caller, dst_bucket, action)
        self._check_perimeter(caller, "storage", {src.project, dst.project}, action)
        self._require_role(caller, src.project, "storage.reader", action)
        self._require_role(caller, dst.project, "storage.writer", action)
        if name not in src.objects:
            self._deny("NOT_FOUND", f"no object {name} in {src_bucket}", caller, action)
        try:
            dst.objects[name] = self._seal(dst, name, self._open(src, name))
        except KeyUnavailable as e:
            self._deny(e.code, e.detail, caller, action)
        self._log("OK", "", caller, action)

    # ---------- keys: a job for security admins, not for agents ----------

    def set_key_state(self, caller: Caller, project: str, key: str, version: int, state: str) -> None:
        action = f"set {key} version {version} to {state}"
        self._check_perimeter(caller, "kms", {project}, action)
        self._require_role(caller, project, "kms.admin", action)
        try:
            self.kms.set_state(key, version, state)
        except KeyUnavailable as e:
            self._deny(e.code, e.detail, caller, action)
        self._log("OK", "", caller, action)

    # ---------- the network ----------

    def fetch(self, caller: Caller, url: str) -> str:
        """Simulated: nothing leaves this machine. From the private network, only routes that exist can be reached."""
        host = urlsplit(url).hostname or ""
        action = f"fetch {host or url}"
        if caller.network == PRIVATE_NETWORK and host != RESTRICTED_VIP and host not in PSC_ENDPOINTS:
            self._deny("NO_ROUTE", f"no route from {caller.network} to {host or url}", caller, action)
        self._log("OK", "", caller, action)
        return f"simulated response from {PSC_ENDPOINTS.get(host, host)}"


# ---------- the demo's world ----------

ADMIN = Caller("sec-admin@corp.example", "corp-admin", "corp", "10.20.0.5")
AGENT = Caller("backup-agent@prod-agents.iam", "prod-agents", PRIVATE_NETWORK, "10.128.0.4")
STOLEN = Caller("backup-agent@prod-agents.iam", "attacker-laptop", "internet", "203.0.113.9")
RECORDS = b"customer_id,name,card_last4\n1001,Ana Fake,4242\n1002,Sam Sample,1111\n"
KEY = "records-key"


def build_world(enforce: bool = True, access_level: bool = True) -> Cloud:
    """The agent's identity is deliberately over-granted on the outside project: this shows what IAM alone would allow."""
    c = Cloud()
    c.grant(ADMIN.principal, "org", "perimeter.admin")
    c.grant(ADMIN.principal, "prod-data", "orgpolicy.admin", "storage.admin", "storage.writer", "storage.reader", "kms.admin")
    c.grant(ADMIN.principal, "prod-agents", "orgpolicy.admin")
    c.grant(AGENT.principal, "prod-data", "storage.reader", "storage.writer", "storage.admin")
    c.grant(AGENT.principal, "partner-external", "storage.reader", "storage.writer", "storage.admin")
    policy = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    c.set_org_policy(ADMIN, "prod-data", policy)
    c.set_org_policy(ADMIN, "prod-agents", policy)
    c.kms.create_key(KEY, "us-central1")
    c.create_bucket(ADMIN, "prod-records", "prod-data", "us-central1", KEY)
    c.put(ADMIN, "prod-records", "customers.csv", RECORDS)
    c.buckets["partner-drop"] = Bucket("partner-drop", "partner-external", "europe-west1", None)
    levels = [{"principals": [ADMIN.principal], "ip_ranges": ["10.20.0.0/16"]}] if access_level else []
    c.set_perimeter(ADMIN, Perimeter({"prod-agents", "prod-data"}, {"storage", "aiplatform", "kms"}, levels))
    if enforce:
        c.enforce_perimeter(ADMIN)
    return c


__all__ = ["ADMIN", "AGENT", "Bucket", "Caller", "Cloud", "DESTROYED", "DISABLED", "Denied", "ENABLED", "KEY", "Perimeter",
           "RECORDS", "STOLEN", "build_world"]
