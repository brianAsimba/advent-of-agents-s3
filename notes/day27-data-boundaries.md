# Day 27 — Data Boundaries: VPC-SC, CMEK & Data Residency
[Page](https://adventofagents.com/2026/10/27) · [Video (15 min)](https://www.youtube.com/embed/HkTv2uQfy0Q) · [Companion repo](https://g.dev/cloud/adventofagents-season3-day27-demo) · [VPC-SC](https://g.dev/cloud/adventofagents-season3-docs-vpc-service-controls) · [CMEK](https://g.dev/cloud/adventofagents-season3-docs-cmek) · [Assured Workloads](https://g.dev/cloud/adventofagents-season3-docs-assured-workloads)

## Core idea
Keep agents inside an approved data perimeter, using controls at the infrastructure and control-plane layers. They hold **regardless of model behavior or prompt instructions**, which also answers Day 26's question: controls have to live outside the agent's reach.

## The layers (course)
1. **CMEK:** Cloud KMS keys your security team controls protect storage, BigQuery and Gemini resources. Keys must match the resource's region. Disabling a key version is a kill switch.
2. **Org policies:** restrict resource locations and model endpoints, require CMEK, and disable downloadable service account keys.
3. **VPC-SC:** create an access level first so admins aren't locked out, then put Gemini, Storage and KMS inside a perimeter with no egress rules.
4. **PSC and Assured Workloads:** run on `restricted.googleapis.com` with no public routes, use PSC as a private bridge, and use Assured Workloads for HIPAA, FedRAMP or ITAR.

## What I built (2026-11-05, Claude + a stand-in control plane)
Real AES-256-GCM envelope encryption; the rest is simulated.
- With identical permissions, the copy out succeeded with no perimeter and was refused with one.
- Claude, told to get the data out three ways, was blocked on the first and declined the other two (its prompt says not to work around errors).
- A valid identity from the wrong place was refused.
- Disabling the key stopped everyone, including the admin; destroying it was permanent, but a copy that had already left stayed readable.

## Lessons
- **Who you are isn't enough; where you are and where the data goes matter too.** IAM said yes, and the perimeter said no.
- **Boundaries limit the blast radius of a failure you can't predict.** You don't have to detect the injection if the data has nowhere to go.
- **Roll out in dry run first, and know what it means.** It shows what would break, but the data still leaves while you watch.
- **Lockout is a real failure mode:** create the access level before enforcing.
- **A key is a kill switch only for data still under it.** It can't recall what was already read or copied, so the perimeter and the key do different jobs.
- **Separate the duties:** the agent can use data, security admins control keys, and neither alone controls policy.
- **The model is part of the data path.** Tool results go to the model's provider, so a perimeter around the storage is incomplete if the model sits outside.
- **Perimeters guard APIs, not replies.** What an agent can read, it can say.

## Connections
- **Day 26:** the answer to "what if the agent had a shell?": put the controls below it. Disabling a key is another reset that also causes an outage.
- **Day 15:** scoped memory and regional banks are residency at the data level.
- **Day 22:** logs and traces hold this data too, so they need the same boundary.
- **Day 16 / 24:** detection and approvals work above the boundary; this is what's left if they miss.
- **SMB clients:** most won't run VPC-SC, but the questions carry over: where does the data live, who holds the keys, which provider sees the prompts, and how do you turn it off? Have answers before the first client asks.
- **GM / regulated work:** this is the vocabulary those security reviews use. Nothing here uses employer data or systems.

## Check yourself
The course page has no questions, so these are mine.
- Why did the same copy work with no perimeter, when the agent's permissions never changed?
- Why create the access level before enforcing?
- Why does destroying the key not protect the copy that already left?
- What can a perimeter not stop?
- Why doesn't this demo's own Claude agent count as being inside the perimeter?
