"""Day 17 demo: why infrastructure as code beats console clicks. No model, no cloud, nothing outside a temp folder.

  uv run python day17/demo.py
Works on a temporary copy of stack/ so the real files are never edited.
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import iac  # noqa: E402
import pipeline  # noqa: E402


def edit(path: Path, fn) -> None:
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data, indent=2))


def run(title: str, fn, *args) -> int:
    print(f"\n=== {title} ===")
    return fn(*args)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="day17-"))
    shutil.copytree(HERE / "stack", tmp / "stack")
    iac.STACK, iac.WORK = tmp / "stack", tmp / ".iac"
    fnd, rt = iac.STACK / "foundation.json", iac.STACK / "runtime.json"
    try:
        run("1. First deploy from code (merge to main)", pipeline.deploy, "b001")
        image1 = iac.state("runtime")["resources"]["agent"]["image"]
        run("2. Plan again: nothing to do", pipeline.plan)

        edit(fnd, lambda d: d["resources"]["egress_gateway"]["allow"].append("starlight.example"))
        run("3. Reviewed change: allow one more merchant (the PR shows exactly this)", pipeline.plan)
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.deploy("b002")
        print("   merged and deployed")

        edit(rt, lambda d: d["resources"]["agent_roles"]["roles"].append("owner"))
        run("4a. Bad PR: grant the agent 'owner'", pipeline.plan)
        edit(rt, lambda d: d["resources"]["agent_roles"]["roles"].remove("owner"))
        edit(fnd, lambda d: d["resources"].pop("spend_policy"))
        run("4b. Bad PR: delete the spend cap", pipeline.plan)
        shutil.copy(HERE / "stack" / "foundation.json", fnd)
        edit(fnd, lambda d: d["resources"]["egress_gateway"]["allow"].append("starlight.example"))

        edit(iac.WORK / "cloud" / "runtime.json", lambda d: d["agent_roles"]["roles"].append("owner"))
        run("5. Someone widens IAM in the console", pipeline.drift)
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.deploy("b003")
        run("   ...re-running the pipeline puts code back in charge", pipeline.drift)

        shutil.rmtree(iac.WORK / "cloud")
        shutil.copy(HERE / "stack" / "foundation.json", fnd)
        for layer in iac.LAYERS:
            (iac.WORK / "state" / f"{layer}.json").unlink()
        print("\n=== 6. Disaster: the whole environment is gone. Rebuild from Git ===")
        with contextlib.redirect_stdout(io.StringIO()):
            code = pipeline.deploy("b001")
        image2 = iac.state("runtime")["resources"]["agent"]["image"]
        print(f"   rebuilt: {'SUCCESS' if code == 0 else 'FAILURE'}; same commit -> same image digest: {image1 == image2}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
