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
| 1 | Five phases of the Agent Development Lifecycle | [notes](notes/day01-adlc.md) | â˜ [day01/](day01/README.md) (Claude) |
| 2 | Agent security: SAIF guardrails | [notes](notes/day02-saif-guardrails.md) | â˜ [day02/](day02/README.md) (Claude, barber-shop guardrails) |
| 3 | Architecting secure multi-agent systems | [notes](notes/day03-secure-multi-agent.md) | ☑ [day03/](day03/README.md) (Claude, 3-agent trading desk) |
| 4 | Governance maturity model | [notes](notes/day04-governance-maturity.md) | â˜ [day04/assess.py](day04/assess.py) (self-assessment) |
| 5 | Agent identity: one identity per agent | [notes](notes/day05-agent-identity.md) | ☐ [day05/](day05/README.md) (local identity, deny-by-default, audit) |

## Prerequisite lookup (Seasons 1 & 2)
Don't binge the old seasons. When a Season 3 day assumes something I don't know, open **one** earlier tutorial from this table. Older seasons can have stale names and commands (S2 says "Vertex AI Agent Engine"; S3 calls it "Agent Runtime"), so prefer the S3 version when it exists.

S1 = Dec 2025 (`adventofagents.com/2025/12/DD`), S2 = Mar 2026 (`adventofagents.com/2026/03/DD`).

### ADK basics (the most likely gap)
| If I'm stuck on… | Open | Notes |
|---|---|---|
| What an ADK agent is, `root_agent`, scaffolding | [S2-02 Build ADK agents with Gemini 3.1 Pro](https://adventofagents.com/2026/03/02) | Best one-evening primer |
| Agent defined without code (YAML) | [S1-02 Hello World with YAML](https://adventofagents.com/2025/12/02) | |
| Built-in tools: Google Search grounding, computer use, streaming | [S1-03 Gemini 3 + ADK](https://adventofagents.com/2025/12/03) | Built-in Google tools are likely Gemini-only (relevant to Claude variants) |
| Context: what the model actually sees | [S1-08 Context management with ADK layers](https://adventofagents.com/2025/12/08) | |
| Rewind / edit-message / regenerate | [S1-09 Undo buttons for agents](https://adventofagents.com/2025/12/09) | |
| Long sessions: caching, compaction | [S1-10 Big context ≠ better memory](https://adventofagents.com/2025/12/10) | |
| Persistent memory across sessions | [S2-05 Long-term recall: memory plugins](https://adventofagents.com/2026/03/05) | |
| Code execution by the agent | [S1-07 LLMs can execute code](https://adventofagents.com/2025/12/07) | |

### Tools, skills, protocols
| If I'm stuck on… | Open | Notes |
|---|---|---|
| Adding MCP servers to an agent | [S2-04 MCP servers](https://adventofagents.com/2026/03/04) | |
| Google-managed MCP for Google services | [S1-11 Google Managed MCP](https://adventofagents.com/2025/12/11) | |
| ADK Skills / SKILL.md, progressive disclosure | [S2-06 ADK Skills](https://adventofagents.com/2026/03/06), [S2-07 Skill design patterns](https://adventofagents.com/2026/03/07) | Also useful for the Claude Architect cert (Camp II) |
| Tool registries (admin-approved tools) | [S1-18 Cloud API Registry](https://adventofagents.com/2025/12/18), [S2-29 ApiRegistry + BigQuery](https://adventofagents.com/2026/03/29) | Precursor to S3's Agent Registry |
| MCP vs A2A vs UCP vs AP2 vs A2UI vs AG-UI | [S2-21 Developer's guide to agent protocols](https://adventofagents.com/2026/03/21) | Read this before any A2A day |
| A2A between agents | [S1-14 Connecting agents with A2A](https://adventofagents.com/2025/12/14), [S2-28 A2A: decoupling reasoning from execution](https://adventofagents.com/2026/03/28) | S2-28 is the pattern for my Camp VI executor |
| A2A with LangGraph / any framework | [S1-16 LangGraph + A2A](https://adventofagents.com/2025/12/16), [S1-24 A2A-ify anything](https://adventofagents.com/2025/12/24) | |
| Custom data over A2A | [S1-20 A2A extensions](https://adventofagents.com/2025/12/20) | |
| Agent-generated UIs | [S1-15 Introducing A2UI](https://adventofagents.com/2025/12/15), [S2-31 A2UI & A2A](https://adventofagents.com/2026/03/31) | Optional ideas for Camp IIb (website chatbot) |

### Multi-agent patterns
| If I'm stuck on… | Open | Notes |
|---|---|---|
| Sequential pipeline | [S2-08 Sequential agents](https://adventofagents.com/2026/03/08) | |
| Coordinator / dispatcher | [S2-09 Coordinator agents](https://adventofagents.com/2026/03/09) | Like S3 Day 3's Case Manager |
| Parallel fan-out | [S2-10 Parallel fan-out](https://adventofagents.com/2026/03/10) | Backtest strategy variants in parallel (Camp II) |
| Manager agent that plans | [S2-11 Hierarchical decomposition](https://adventofagents.com/2026/03/11) | |
| Generator–critic loop | [S2-12 Generator-critic (LoopAgent)](https://adventofagents.com/2026/03/12), [S2-20 Generate-validate-refine harness](https://adventofagents.com/2026/03/20) | Strategy proposer + critic (Camp II) |
| Agent that builds agents | [S2-13 Iterative refinement](https://adventofagents.com/2026/03/13), [S2-16 ADK Dev Skills](https://adventofagents.com/2026/03/16) | |
| Human approval before sensitive actions | [S2-14 Human in the loop](https://adventofagents.com/2026/03/14) | Approval before **financial APIs**: key for Camp VI |
| Orchestration testbed (worktrees, containers) | [S2-27 Scion](https://adventofagents.com/2026/03/27) | |

### Production: data, evals, security, deploy
| If I'm stuck on… | Open | Notes |
|---|---|---|
| Agentic RAG with vector search | [S2-15 Agentic RAG with Vector Search 2.0](https://adventofagents.com/2026/03/15) | Camp IIb chatbot, Camp IV multimodal RAG |
| Multimodal embeddings | [S2-19 Live shopping agent + Gemini Embedding 2](https://adventofagents.com/2026/03/19) | Camp IV |
| Trajectory tests, rubric scoring, evals in CI | [S2-22 ADK evaluation](https://adventofagents.com/2026/03/22) | Deepens S3 Day 1's `agents-cli eval run` |
| Model Armor, guardrails | [S1-22 Security & guardrails](https://adventofagents.com/2025/12/22), [S2-23 Model Armor](https://adventofagents.com/2026/03/23) | Deepens S3 Days 2–3 |
| On-behalf-of user identity / OAuth | [S2-26 End-user identity propagation](https://adventofagents.com/2026/03/26) | The "during" checkpoint from S3 Day 2 |
| Deploying agents | [S1-04 Source-based deployment](https://adventofagents.com/2025/12/04), [S2-25 How to deploy AI agents](https://adventofagents.com/2026/03/25) | Before S3 Day 5 (names may have changed) |
| Tracing and observability | [S1-05 Production observability](https://adventofagents.com/2025/12/05), [S2-30 Hierarchical tracing (OpenTelemetry)](https://adventofagents.com/2026/03/30) | S3 Day 1's Optimize phase |
| Crash-proof, long-running agents | [S1-23 Durable agents with Restate](https://adventofagents.com/2025/12/23) | |
| Large batch workloads | [S2-24 Batch processing to 10k](https://adventofagents.com/2026/03/24) | |
| Gemini Enterprise registration and connectors | [S1-19 Register to Gemini Enterprise](https://adventofagents.com/2025/12/19), [S2-17 No-code agents](https://adventofagents.com/2026/03/17), [S2-18 ADK agents + Workspace](https://adventofagents.com/2026/03/18) | Relevant to the Google transformation at work |

Skippable: S1-01, S1-21, S1-25, S2-01 (kick-offs and recaps), S1-06 (IDE setup), S1-12/S1-13 (Live API, Interactions API) unless a later S3 day uses them, S1-17/S2-03 (model announcements).

## Running the course on Claude
I follow the course with Google ADK on my PC and **Claude as the model** (via LiteLLM and an Anthropic API key in each agent folder's gitignored `.env`). Python environment: `uv` at the repo root (`uv run ...`). Tests: `uv run pytest`.

- **Agent-building days:** run locally on Claude; the model is a one-line change.
- **Google-service days** (Model Armor, Agent Gateway, Registry, deploy): those services need a Google Cloud project whatever the model is. Either set it up then (steps below), or build the same control locally with ADK callbacks (`before_model` / `before_tool` / `after_model`) and read the Google version.

## Setup for Google-service days (Windows, personal Google account — never the work account or work laptop)
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
