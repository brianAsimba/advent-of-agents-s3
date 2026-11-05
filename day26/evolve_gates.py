"""The fixed gates. The agent has no tool that reaches this file, the policy, or the signing key.

Gate 1 ingress shield   a regex stand-in for Model Armor, screening alerts before the model reads them
Gate 2 AST + behavior   static rules on the source, then behavior tests in a child process with no secrets
Gate 3 policy as code   limits checked on declared AND measured behavior, a replay, and an action deny-list
Gate 4 provenance       Ed25519 here (Cloud KMS in the course): the gateway verifies before mounting anything
Gate 5 tiered approval  lives in evolve_platform.py, because it needs tickets and a person

Python can't truly sandbox Python. The AST rules and restricted builtins are depth, not a boundary: the real protection
here is that this code runs in a child process with no secrets and a timeout. Production needs a VM or gVisor.
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

RUNNER = Path(__file__).resolve().parent / "evolve_runner.py"
MAX_SOURCE, MAX_ALERT = 8000, 2000
INJECTION = re.compile(
    r"ignore (all |any )?(your |the )?(previous |prior |above )?(instructions|rules|policy|policies)"
    r"|disregard (your|the|all|previous)|override (the |your )?(policy|gates?|rules)|system prompt|you are now"
    r"|(disable|bypass|skip|turn off|remove) (the |your |all )?(gates?|policy|policies|guardrails|signing|approval)"
    r"|pre-?approved|new instructions", re.I)
BANNED_NAMES = {"eval", "exec", "compile", "open", "input", "globals", "locals", "vars", "dir", "getattr", "setattr",
                "delattr", "hasattr", "type", "object", "super", "memoryview", "breakpoint", "help", "print", "id"}
BANNED_ATTR_PREFIXES = ("__", "gi_", "f_", "cr_", "tb_", "ag_")
BANNED_ATTRS = {"format", "format_map", "mro"}
BANNED_NODES = (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom, ast.Await, ast.AsyncFunctionDef, ast.AsyncFor,
                ast.AsyncWith, ast.Delete)
ALLOWED_IMPORTS = {"math"}
TOP_LEVEL = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Assign)


class GateError(RuntimeError):
    pass


# ---------- Gate 1 ----------

def ingress_shield(alert: str) -> list[str]:
    """Returns why this alert may not reach the model (empty = pass). Known patterns only: it thins attacks, no more."""
    reasons = []
    if len(alert) > MAX_ALERT:
        reasons.append(f"alert is over {MAX_ALERT} characters")
    if any(unicodedata.category(ch) == "Cf" for ch in alert):
        reasons.append("hidden formatting characters")
    if m := INJECTION.search(alert):
        reasons.append(f"prompt-injection pattern: '{m.group(0)}'")
    return reasons


# ---------- Gate 2 ----------

def ast_gate(source: str) -> list[str]:
    """Static rules. Only parses the code, never runs it."""
    if len(source) > MAX_SOURCE:
        return [f"source is over {MAX_SOURCE} characters"]
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as e:
        return [f"does not parse: {e}"]
    reasons = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            reasons += [f"import not allowed: {a.name}" for a in node.names if a.name not in ALLOWED_IMPORTS]
        elif isinstance(node, ast.ImportFrom):
            if node.module not in ALLOWED_IMPORTS or node.level:
                reasons.append(f"import not allowed: {node.module}")
        elif isinstance(node, ast.Name) and (node.id in BANNED_NAMES or node.id.startswith("__")):
            reasons.append(f"name not allowed: {node.id}")
        elif isinstance(node, ast.Attribute) and (node.attr.startswith(BANNED_ATTR_PREFIXES) or node.attr in BANNED_ATTRS):
            reasons.append(f"attribute not allowed: {node.attr}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
            reasons.append("string containing a double underscore")
        elif isinstance(node, ast.FunctionDef) and node.name.startswith("__") and node.name != "__init__":
            reasons.append(f"method not allowed: {node.name}")
        elif isinstance(node, BANNED_NODES):
            reasons.append(f"construct not allowed: {type(node).__name__}")
    for stmt in tree.body:
        is_doc = isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
        if not isinstance(stmt, TOP_LEVEL) and not is_doc:
            reasons.append(f"top-level code not allowed: {type(stmt).__name__}")
    cls = next((s for s in tree.body if isinstance(s, ast.ClassDef) and s.name == "RateLimiter"), None)
    methods = {s.name for s in cls.body if isinstance(s, ast.FunctionDef)} if cls else set()
    if not {"__init__", "allow"} <= methods:
        reasons.append("must define class RateLimiter with __init__ and allow")
    return list(dict.fromkeys(reasons))


def run_child(source: str | None, rate: float = 0, burst: int = 0, timeout: int = 15) -> dict:
    """Runs the agent's code in a child process: no secrets in its environment, a timeout, no import path."""
    env = {k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if k in os.environ}
    try:
        done = subprocess.run([sys.executable, "-I", str(RUNNER)], capture_output=True, text=True, encoding="utf-8",
                              env=env, timeout=timeout, input=json.dumps({"source": source, "rate": rate, "burst": burst}))
    except subprocess.TimeoutExpired as e:
        raise GateError(f"timed out after {timeout}s") from e
    if done.returncode != 0:
        tail = done.stderr.strip().splitlines()[-1:] or ["no error output"]
        raise GateError(f"code failed to run: {tail[0][:200]}")
    return json.loads(done.stdout)


# ---------- Gate 3 ----------

def policy_gate(policy: dict, rate: float, burst: int, actions: list[str], result: dict) -> list[str]:
    """The model can't argue with this. Checks what it declared and what its code actually did."""
    reasons = []
    if rate < policy["min_rate_per_sec"]:
        reasons.append(f"rate {rate} is below the floor {policy['min_rate_per_sec']}")
    if burst > policy["max_burst"]:
        reasons.append(f"burst {burst} is above the ceiling {policy['max_burst']}")
    reasons += [f"action on the deny-list: {a}" for a in actions if a in policy["denied_actions"]]
    measured, tolerance = result["measured"], policy["rate_tolerance"]
    if abs(measured["rate"] - rate) > rate * tolerance:
        reasons.append(f"declared {rate} req/s but measured {measured['rate']:.2f}")
    if measured["burst"] != burst:
        reasons.append(f"declared burst {burst} but measured {measured['burst']}")
    replay = result["replay"]
    if replay["surge_availability"] < policy["min_surge_availability"]:
        reasons.append(f"replay: surge availability {replay['surge_availability']:.0%} is below "
                       f"{policy['min_surge_availability']:.0%}")
    if replay["calm_block_rate"] > policy["max_calm_block_rate"]:
        reasons.append(f"replay: blocks {replay['calm_block_rate']:.1%} of calm traffic")
    return reasons


# ---------- Gate 4 ----------

def _canonical(statement: dict) -> bytes:
    return json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()


def source_digest(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


class SigningService:
    """Stand-in for KMS: the private key stays in here, and the agent is never given this object."""

    def __init__(self):
        self._key = Ed25519PrivateKey.generate()
        self.public_key = self._key.public_key()

    def sign(self, statement: dict) -> bytes:
        return self._key.sign(_canonical(statement))


def verify_statement(public_key: Ed25519PublicKey, statement: dict, signature: bytes) -> bool:
    try:
        public_key.verify(signature, _canonical(statement))
        return True
    except InvalidSignature:
        return False
