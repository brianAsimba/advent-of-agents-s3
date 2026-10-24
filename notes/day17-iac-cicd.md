# Day 17 — Infrastructure as Code with Terraform and Cloud Build CI/CD
[Page](https://adventofagents.com/2026/10/17) · [Video: Joyce Chen (15 min)](https://www.youtube.com/watch?v=cTRYWzMmV1s) · [Demo repo](https://github.com/chjoyce/advent-of-agents-s3-terraform-day17) · [Provision agents with Terraform](https://g.dev/cloud/adventofagents-season3-docs-use-terraform) · [Terraform + Cloud Build GitOps](https://g.dev/cloud/adventofagents-season3-docs-managing-infrastructure-as-code)

## Core idea
Every guardrail from Days 5–16 is only as durable as the way it was set up. Click it into a console and you get **drift** between dev/staging/prod, **unreviewed changes** (a widened role, a bypassed gateway) and **slow recovery**. Infrastructure as code puts the whole stack in version-controlled files, reviewed in a pull request, applied by a pipeline.

## How it works
- **Two state layers** in a remote bucket: **foundation** (network, registry, ingress gateway + Model Armor, egress gateway) and **runtime** (the agent).
- **On a PR:** `terraform plan` shows exactly what would change. **On merge to main:** three stages:
  1. **Foundation apply** → outputs gateway IDs and TLS root certs.
  2. **Build + push** the agent image with those certs, tagged with the build ID.
  3. **Runtime apply:** deploy the agent on the new image, mint its SPIFFE identity, grant least-privilege roles, route traffic through both gateways.
- Works for any framework or runtime (ADK on Agent Runtime, Cloud Run).

## What I built (2026-10-23)
- **Real CI** for my advent repo (GitHub Actions): every PR and push to main runs all model-free tests and the plan + guard, with `contents: read` permission and no secrets.
- A **Terraform-style engine** for my stack: plan (`+ ~ -`), apply, state, stage outputs wired by `${...}`, a deterministic build, drift detection, and a **guard (policy as code)** that blocks broad roles, open egress, a shield that fails open, a cap above $100, a missing agent identity, and destroying a security layer.
- Run: a one-line allowlist change produced a one-line plan; "grant owner" and "delete the spend cap" were blocked before apply; a console-style IAM edit showed up as drift and was reverted by redeploying; a full rebuild from Git gave the same image digest.

## Key distinctions
- **Plan vs apply:** review the diff, not the intent.
- **State vs reality:** drift is the gap between what Terraform last applied and what's actually running.
- **Human review vs policy as code:** reviewers miss things in big diffs; a guard in CI never skips the rule "no `owner` for agents".

## Connections
- **Barber pilot / SMB clients:** keep each client's n8n workflows, credentials references (never values) and webhook config in a repo; a new client = copy + plan + apply. Recovery after a broken workflow = redeploy from Git.
- **Trading agent:** the same CI (tests + a guard: paper endpoint only, max position cap present) on `brianAsimba/trading_agent`.
- **Databricks DE cert (Camp V):** Databricks Asset Bundles are the same idea (declarative jobs/pipelines deployed from CI).
- **GM governance forum:** "all agent infrastructure changes go through a reviewed plan with policy checks" is an easy, auditable control to propose.

## Check yourself
- What three problems does IaC solve that console setup causes?
- Why split foundation and runtime into separate state layers?
- What does stage 1 hand to stage 2, and why does the image need it?
- What's the difference between a plan diff and drift?
