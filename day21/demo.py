"""Day 21 demo: pick an archetype, generate and test the two-tier policy, then compare A/B/C on one workload.
No model, no cloud.  Run from the repo root:
  uv run python day21/demo.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import advisor  # noqa: E402
import mesh  # noqa: E402

TOPOLOGIES = {
    "Startup, one product team": advisor.Topology("acme", "acme-gov", ["acme-agents"], ["us-central1"], False, False),
    "Global bank, autonomous LOBs": advisor.Topology(
        "bank", "bank-gov", ["retail", "wealth", "insurance"], ["us-central1", "europe-west1", "asia-southeast1"],
        True, False),
    "Global manufacturer, shared PLM/ERP tools": advisor.Topology(
        "mfg", "mfg-gov", ["plants", "engineering", "supply"], ["us-central1", "europe-west1"], True, True),
    "My consulting practice (one client per spoke)": advisor.Topology(
        "brian", "brian-gov", ["client-barber", "client-dentist", "client-gym"], ["us-central1"], True, True),
}


def main() -> None:
    print("=== 1. Which archetype? ===")
    for label, t in TOPOLOGIES.items():
        choice, reasons = advisor.recommend(t)
        print(f"  {label:<48} -> {choice}: {advisor.ARCHETYPES[choice]}")
        for r in reasons[3:]:
            print(f"  {'':<48}    {r}")

    print("\n=== 2. Two-tier identity policy (central hub) ===")
    t = TOPOLOGIES["Global manufacturer, shared PLM/ERP tools"]
    policy = advisor.two_tier_policy(t, agent_project="engineering", agent_sa="concierge-agent")
    out = HERE / ".out" / "central_hub_uap.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    for r in policy["rules"]:
        who = r.get("principal") or r.get("principalSet")
        print(f"  Tier {r['tier']}: {r['name']:<34} {who}")
    print(f"  written to {out.relative_to(HERE.parent)}")
    concierge = "spiffe://mfg.svc.id.goog/ns/engineering/sa/concierge-agent"
    batch_job = "spiffe://mfg.svc.id.goog/ns/engineering/sa/nightly-batch"
    outsider = "spiffe://mfg.svc.id.goog/ns/supply/sa/concierge-agent"
    mcp = {"type": "mcp_server", "name": "plm-search-mcp", "registered": True, "owner": "concierge-agent"}
    cases = [
        ("concierge -> Vertex AI API", concierge, {"host": "aiplatform.googleapis.com"}),
        ("batch job (same spoke) -> Vertex AI API", batch_job, {"host": "aiplatform.mtls.googleapis.com"}),
        ("concierge -> registered PLM MCP server", concierge, mcp),
        ("batch job -> same MCP server", batch_job, mcp),
        ("concierge -> UNREGISTERED MCP server", concierge, {**mcp, "name": "random-mcp", "registered": False}),
        ("same agent name, other spoke -> Vertex AI API", outsider, {"host": "aiplatform.googleapis.com"}),
    ]
    for label, who, dest in cases:
        verdict, rule = advisor.evaluate(policy, who, dest)
        print(f"  {label:<46} {verdict:<5} ({rule})")

    print("\n=== 3. Same workload, three archetypes (3 LOBs x 10 agents, 2 shared Tier-0 servers, one compromised) ===")
    cols = ["central_approvals", "central_visibility", "cross_lob_leaks", "kill_switch_actions", "still_resolves_after_kill"]
    heads = ["central approvals", "central sees", "cross-LOB leaks", "kill actions", "still exposed"]
    print(f"  {'':<34}" + "".join(f"{h:>18}" for h in heads))
    for a in "ABC":
        m = mesh.measure(a)
        print(f"  {a}: {m['name']:<31}" + "".join(f"{str(m[c]):>18}" for c in cols))
    b = mesh.measure("B")
    print(f"\n  In B, if the security team revokes the server in only one registry, "
          f"{b['exposed_after_one_action']} of 3 LOBs can still call it.")


if __name__ == "__main__":
    main()
