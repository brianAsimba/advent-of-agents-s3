"""Day 4: Agent Governance Maturity self-assessment (15 questions, 5 layers).

Scoring rules from the course:
  * Rate each area 1 (manual/ad hoc), 3 (standardized in production) or 5 (automated everywhere).
  * A layer scores its WEAKEST area.
  * Start at the lowest layer scoring below 3; the order is structural.
  * Phases: Foundation days 1-30, Prevention + Detection days 31-60, Response + Alignment days 61-90.

Usage (from the repo root):
  uv run python day04/assess.py                          # answer interactively
  uv run python day04/assess.py day04/my_estate.json     # score a saved answers file
"""
import json
import sys
from pathlib import Path

LAYERS = {
    "Foundation": {
        "phase": "Days 1-30",
        "question": "Is every agent cataloged, owned and identifiable?",
        "areas": {
            "identity": "Each agent has its own identity/credentials (SPIFFE at enterprise scale).",
            "inventory": "Agents and tools are cataloged in a central registry with an owner.",
            "infrastructure": "Agents deploy from templates/code (IaC), not by hand.",
        },
    },
    "Prevention": {
        "phase": "Days 31-60",
        "question": "Can you block policy violations inline?",
        "areas": {
            "prompt_shielding": "Prompts are screened inline (Model Armor at a gateway) and fail closed.",
            "data_leaks": "PII masking and domain allowlists run on output.",
            "circuit_breakers": "Iteration ceilings and rate/spend limits are enforced.",
        },
    },
    "Detection": {
        "phase": "Days 31-60",
        "question": "Can you spot anomalies with an immutable audit trail?",
        "areas": {
            "tracing": "Model and tool calls are traced (OpenTelemetry) to a queryable sink.",
            "anomalies": "Alerts fire on token-volume or trajectory anomalies.",
            "audit": "Immutable audit logs are exported and queryable.",
        },
    },
    "Response": {
        "phase": "Days 61-90",
        "question": "Can you prove containment worked?",
        "areas": {
            "containment": "One agent's credentials can be revoked quickly without affecting others.",
            "threat_alerts": "Alerts fire on anomalous API calls.",
            "playbooks": "Incident and postmortem playbooks exist and have been tested.",
        },
    },
    "Continuous Alignment": {
        "phase": "Days 61-90",
        "question": "Do escapes become better policy?",
        "areas": {
            "drift": "Automated evaluations run on a schedule.",
            "red_teaming": "Automated prompt-injection scans run continuously.",
            "policy_updates": "Policies are reviewed on a schedule; postmortems update them.",
        },
    },
}
VALID = (1, 3, 5)


def layer_scores(answers: dict) -> dict:
    """Each layer scores its weakest area."""
    return {layer: min(answers[a]["score"] for a in spec["areas"]) for layer, spec in LAYERS.items()}


def start_layer(scores: dict) -> str | None:
    """The first layer (in structural order) scoring below 3."""
    return next((layer for layer, s in scores.items() if s < 3), None)


def roadmap(answers: dict) -> list[str]:
    scores = layer_scores(answers)
    lines = []
    for layer, spec in LAYERS.items():
        gaps = [a for a in spec["areas"] if answers[a]["score"] < 3]
        if gaps:
            lines.append(f"{spec['phase']} · {layer}: raise " + ", ".join(gaps) + " to Level 3")
    first = start_layer(scores)
    return ([f"Start with: {first}"] if first else ["All layers at Level 3+. Push the weakest toward 5."]) + lines


def ask() -> dict:
    answers = {}
    for layer, spec in LAYERS.items():
        print(f"\n== {layer}: {spec['question']}")
        for key, text in spec["areas"].items():
            while True:
                raw = input(f"  {text}\n  Score 1/3/5: ").strip()
                if raw.isdigit() and int(raw) in VALID:
                    break
            answers[key] = {"score": int(raw), "note": input("  Evidence/note (optional): ").strip()}
    return answers


def report(answers: dict, title: str = "Agent estate") -> str:
    scores = layer_scores(answers)
    out = [f"# Governance maturity: {title}", "", "| Layer | Score | Weakest area |", "|---|---|---|"]
    for layer, spec in LAYERS.items():
        weakest = min(spec["areas"], key=lambda a: answers[a]["score"])
        out.append(f"| {layer} | {scores[layer]} | {weakest} |")
    out += ["", "## 90-day roadmap"] + [f"- {line}" for line in roadmap(answers)]
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        print(report(data["answers"], data.get("title", "Agent estate")))
    else:
        print(report(ask()))
