"""Day 17 pipeline: the local stand-in for cloudbuild.yaml. Run from the repo root.

  uv run python day17/pipeline.py plan      pull request: plan both layers + guard, change nothing (CI runs this)
  uv run python day17/pipeline.py deploy    merge to main: 1 foundation apply -> 2 build image -> 3 runtime apply
  uv run python day17/pipeline.py drift     compare the "cloud" with state (catches console edits)
Exit code 1 when the guard blocks a plan or drift is found.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import iac  # noqa: E402

SYMBOL = {"+": "+ create ", "-": "- DESTROY", "~": "~ change "}


def build_id() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip() or "local"
    except (OSError, subprocess.CalledProcessError):
        return "local"


def show(layer: str, changes: list, violations: list[str]) -> None:
    print(f"[{layer}] {len(changes)} change(s)" + ("" if changes else ": up to date"))
    for op, path, old, new in changes:
        val = new if op != "-" else old
        if isinstance(val, dict):
            val = val.get("type", "")
        print(f"   {SYMBOL[op]} {path}" + (f": {old!r} -> {new!r}" if op == "~" else f" ({val})"))
    for v in violations:
        print(f"   GUARD BLOCKED: {v}")


def plan() -> int:
    """PR mode: nothing is written. Downstream refs use the foundation's planned outputs."""
    blocked = 0
    want, changes, v = iac.plan("foundation", {})
    show("foundation", changes, v)
    blocked += bool(v)
    refs = iac._outputs("foundation", want)
    image = iac.build(build_id(), refs, write=False)["build.image"]
    deployed = iac.state("runtime")["resources"].get("agent", {}).get("image", "")
    if deployed.split("@")[-1] == image.split("@")[-1]:
        image = deployed  # same bytes as what is running: no rollout needed
    refs["build.image"] = image
    _, changes, v = iac.plan("runtime", refs)
    show("runtime", changes, v)
    blocked += bool(v)
    print("\nPLAN BLOCKED by guard." if blocked else "\nPlan OK.")
    return 1 if blocked else 0


def deploy(bid: str | None = None) -> int:
    bid = bid or build_id()
    try:
        print("Stage 1/3  foundation apply")
        out = iac.apply("foundation", {})
        print(f"   gateways: {out['foundation.ingress_gateway.id']}, {out['foundation.egress_gateway.id']}")
        print("Stage 2/3  build + push image")
        img = iac.build(bid, out)
        print(f"   image: {img['build.image']}")
        print("Stage 3/3  runtime apply (identity, least-privilege roles, gateways)")
        iac.apply("runtime", {**out, **img})
        print("   agent live: terraform-demo-agent\nSTATUS: SUCCESS")
        return 0
    except iac.GuardFailed as e:
        for v in e.violations:
            print(f"   GUARD BLOCKED: {v}")
        print("STATUS: FAILURE (nothing after the failed stage was applied)")
        return 1


def drift() -> int:
    found = 0
    for layer in iac.LAYERS:
        changes = iac.drift(layer)
        found += len(changes)
        print(f"[{layer}] " + ("no drift" if not changes else f"DRIFT: {len(changes)} change(s) made outside code"))
        for op, path, old, new in changes:
            print(f"   {SYMBOL[op]} {path}: {old!r} -> {new!r}")
    return 1 if found else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    sys.exit({"plan": plan, "deploy": deploy, "drift": drift}[cmd]())
