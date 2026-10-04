# Advent of Agents — Season 3 (October 2026)

My follow-along repo for Google Cloud's [Advent of Agents S3](https://adventofagents.com/): 31 daily tutorials on production-safe agents with Gemini, ADK and Google Cloud.

Part of Camp I of my learning roadmap. Wiki notes live in my second brain (`wiki/sources/advent-of-agents-s3-*`).

## Layout
```
notes/      one study note per day (concepts, code walkthrough, how it applies to my projects)
dayNN/      code for each day (scaffolds, scripts, outputs)
```

## Progress
| Day | Topic | Notes | Code run |
|---|---|---|---|
| 0 | Kick-off: agent governance & security (video) | | |
| 1 | Five phases of the Agent Development Lifecycle | [notes](notes/day01-adlc.md) | ☐ |
| 2 | Agent security: SAIF guardrails | [notes](notes/day02-saif-guardrails.md) | ☐ |
| 3 | Architecting secure multi-agent systems | [notes](notes/day03-secure-multi-agent.md) | n/a (architecture day) |

## Setup (Windows, personal Google account — never the work account or work laptop)
1. **Google Cloud account:** sign in at https://console.cloud.google.com with a personal Google account and start the free trial (new accounts get trial credits; a card is needed for verification).
2. **Project:** create one named `advent-agents-s3` and copy its **Project ID**.
3. **Budget alert first:** Billing → Budgets & alerts → create a budget (e.g. $25) with email alerts at 50/90/100%.
4. **gcloud CLI:** `winget install Google.CloudSDK` (or the installer from https://cloud.google.com/sdk/docs/install), then open a new terminal.
5. **Log in and point at the project:**
   ```bash
   gcloud init                               # pick the advent-agents-s3 project
   gcloud auth application-default login     # credentials for local code (ADK, Agents CLI)
   gcloud services enable aiplatform.googleapis.com
   ```
6. **Shell:** run the course's bash scripts in **Git Bash** (`C:\Program Files\Git\bin\bash.exe`) or WSL.
7. Already installed on this PC: Python, `uv`/`uvx`, Node.js 20, Git.

## Cost hygiene
- `agents-cli eval run` uses an LLM judge (billable but small).
- Deploys (Day 5+) create cloud resources. Delete them after each day, or delete the whole project at the end of October.
