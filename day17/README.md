# Day 17 locally: infrastructure as code + CI/CD for the agent stack

Console clicks are fine for a prototype, but they cause **drift** (dev ≠ prod), **unreviewed changes** (someone widens IAM or bypasses a gateway) and **slow recovery** after an incident. The course defines the whole stack (identity, gateways, Model Armor) in Terraform and deploys it with a three-stage Cloud Build pipeline. With no GCP here, this day has two parts:

1. **Real CI for this repo:** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs every model-free test plus the plan + guard below on each pull request and push to main. It runs with `contents: read` permission and **no secrets**.
2. **A tiny Terraform-style engine** (`iac.py`, `pipeline.py`) for the stack built on earlier days, to make plan, apply, state, drift and stage outputs concrete.

| Course (Terraform + Cloud Build) | Here |
|---|---|
| `terraform/foundation`, `terraform/runtime` (reviewed in Git) | `stack/foundation.json`, `stack/runtime.json` |
| Remote state in a GCS bucket, two layers | `.iac/state/<layer>.json` (gitignored) |
| The actual cloud resources | `.iac/cloud/<layer>.json`; editing it by hand = a console change |
| `terraform plan` on a PR | `pipeline.py plan`: `+` create, `~` change, `- DESTROY`, per attribute |
| Stage 1 foundation: VPC, registry, ingress gateway + Model Armor, egress gateway | same resources, plus Day 16's spend cap |
| Stage 2: image with gateway TLS certs, tagged with the build ID | `iac.build()`: tar.gz of `agent/` + `wiring.json`; same code = same digest |
| Stage 3 runtime: agent + SPIFFE identity + least-privilege roles + both gateways | `runtime.json`, wired with `${foundation.egress_gateway.id}` etc. |
| *(policy as code, e.g. OPA/Conftest; the course leaves review to humans)* | `iac.guard()`: blocks broad roles (`owner`, `editor`, `*.admin`), wildcard or allow-by-default egress, a shield that fails open, a cap above $100, a missing SPIFFE identity, and destroying a gateway or policy |

## Run (repo root)
```bash
uv run python day17/demo.py
```
```bash
uv run python day17/pipeline.py plan
```
```bash
uv run python day17/pipeline.py deploy
```
```bash
uv run python day17/pipeline.py drift
```
`demo.py` works in a temp folder: first deploy → replan (no changes) → a reviewed allowlist change → two bad PRs blocked → a console IAM edit caught as drift and reverted by redeploying → full rebuild from Git with the same image digest.

## What my run showed (2026-10-23)
- The plan for a one-line allowlist change showed exactly one `~` line, which is what a reviewer reads.
- "Grant `owner`" and "delete the spend cap" were both **blocked before apply**. With the bad role, the pipeline stopped at stage 3 and left stages 1–2 as they were.
- A hand-added `owner` role in the "cloud" showed up as **drift**; re-running the pipeline removed it.
- Deleting everything and redeploying from the same commit gave the **same image digest**, so recovery is one command.
