# Day 2 — Agent Security: Implementing SAIF Guardrails
[Page](https://adventofagents.com/2026/10/02) · [Video (13 min)](https://www.youtube.com/watch?v=TA7lhezND7M) · [SAIF](https://g.dev/cloud/adventofagents-season3-google-saif) · [OWASP Top 10 for LLMs](https://owasp.org/projects/top-10-for-large-language-model-applications)

## Core idea
Agents read **untrusted input** and **take actions**. Together, that means a malicious sentence in a document can become a real action. SAIF (Google's Secure AI Framework) is a threat-modeling approach for defense in depth: several independent controls, so no single failure is fatal.

## The three checkpoints
| Checkpoint | Threat | Control |
|---|---|---|
| **In** | Prompt injection, malformed input (OWASP LLM #1) | Sanitize/filter before the reasoning loop |
| **During** | Rogue actions / excessive agency | Restrict tools by caller credentials and on-behalf-of user role |
| **Out** | Sensitive data disclosure | Scan responses; redact or mask before returning |

The "during" control still protects you when the model is completely fooled. **Permissions, not prompts, are the real boundary.**

## Code
```bash
export CLOUDSDK_METRICS_ENVIRONMENT="advent-of-agents-s3-day02"
gcloud auth application-default login
git clone https://github.com/google/saif-data.git
./launch_saif_demo.sh --serve
```
Clones Google's SAIF data repo and serves a local demo that scans an agent for defense-in-depth gaps. Run in Git Bash/WSL. When it runs, record which risks it flags and at which layer each defense sits.

## Applied
| Threat | Trading agent | Barber pilot |
|---|---|---|
| In | Camp IV news/10-K text is an injection surface; treat it as data | Inbound customer messages are untrusted |
| During | LLM has no order tools; keep it that way in Camp VI | Only message his customers, never arbitrary numbers |
| Out | Alpaca keys never in prompts or logs | No customer phone numbers in generated posts |

## Check yourself
- Which checkpoint protects you even if the model is fully fooled, and why?
