# Day 27 locally: data boundaries (VPC-SC, CMEK, residency)

Prompts and guardrails ask a model to behave. Data boundaries work below the model, at the infrastructure layer, so they hold even if it's prompt-injected or over-permissioned. These are real Google Cloud controls with no true local equivalent, so this builds a stand-in control plane that shows the rules, with **real AES-256-GCM encryption** and a live Claude agent. The data is fake.

| Course (Google Cloud) | Here |
|---|---|
| Org policies: US locations, US endpoints, require CMEK, no downloadable keys | `org_policy.json`, checked by `Cloud` |
| CMEK: your keys; the region must match; disabling is a kill switch | `boundary_kms.py`: a separate data key per object, wrapped by your key |
| Access level first, so admins aren't locked out | `enforce_perimeter()` refuses if it would lock out its own caller |
| VPC-SC perimeter with no egress rules | `Perimeter`, checked on every call beneath the agent's tools |
| `restricted.googleapis.com`, no public routes; PSC as a private bridge | `fetch()`: simulated, only routes that exist can be reached |
| Assured Workloads | Not rebuilt: it's a preconfigured bundle of these controls for regulated work |
| *(my additions)* | dry-run mode before enforcing; ciphertext tied to its object; an agent deliberately over-granted to show IAM alone isn't enough |

Claude calls use `claude-opus-5-5` with server-side `fallbacks: "default"`.

## Run (repo root)
```bash
uv run pytest day27 -q
```
```bash
uv run python day27/demo.py
```

## What my run showed (2026-11-05)
- **Org policies:** a bucket in Europe, a bucket with no key, a key in the wrong region, a downloadable service account key and a model endpoint in Europe were all denied.
- **Rollout:** enforcing with no access level was refused as a lockout. Dry run logged the violation, **and the data still left**, because dry run only observes.
- **Same agent, same permissions:** with no perimeter, the copy to the outside bucket succeeded on IAM alone. With the perimeter, `VPC_SC_EGRESS`.
- **Live Claude:** asked to copy the data out, then post it to a URL, then make a bucket in Europe. The copy was blocked, and Claude **stopped there** and flagged the other two as routes around a security control. Its system prompt does tell it to report errors and not work around them, so this is partly prompted restraint, and the other two routes were only tested by script.
- **Stolen credentials:** the agent's valid identity from an attacker's laptop got `VPC_SC_INGRESS`.
- **Kill switch:** disabling the key stopped reads for the agent and the admin alike, and re-enabling restored them. Destroying it made the data unrecoverable.
- **What the key can't do:** the copy that left in the no-perimeter run stayed readable after the key was destroyed.

## Limits
- **This shows the rules, not the isolation.** Everything runs in one Python process, so code in it could reach around the checks. In Google Cloud, they sit in front of the API, which is why they hold. The caller's network and project are set by this code here, and by the infrastructure there.
- **A perimeter guards APIs, not conversations.** Anything an agent is allowed to read can still appear in its reply, or be written to somewhere allowed inside the perimeter. This needs Days 3, 22 and 24 too.
- **This demo sits outside its own perimeter.** Claude runs on the Anthropic API, so any tool result it reads leaves this "perimeter". In this run Claude never read the file, but it could have. For a real boundary, the model has to be inside too: check which cloud platform and region can offer that before promising a client residency.
- **The kill switch isn't magic.** Data already read or copied is beyond it, and real services may cache keys for a short time, so check each service's docs.
- **Disabling a key is also an outage,** and destroying one loses the data. Both need the same care as Day 26's reset.
- **Not rebuilt:** Assured Workloads and real network routing. No GCP resources were created, and the page's `gcloud` commands were not run.
