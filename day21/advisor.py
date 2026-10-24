"""Day 21: governance archetype advisor + two-tier identity policy (generate and evaluate).

Course (governance_archetype_advisor.py)               Here
-----------------------------------------------------  ------------------------------------------------------
Topology dataclass                                      Topology
recommend_archetype(): multi-region + crown jewels -> C recommend(): same rule, plus the reasons and one extra
                       multi-region or autonomous  -> B   advisory note the course rule doesn't cover
                       otherwise                   -> A
generate_two_tier_hub_policy() -> central_hub_uap.json  two_tier_policy() (same shape, simplified), written to
                                                          .out/central_hub_uap.json by the demo
(Agent Gateway evaluates the policy)                    evaluate(): Tier 1 coarse, Tier 2 fine, default deny
"""
from dataclasses import dataclass, field

ARCHETYPES = {
    "A": "Single Central Governance Hub",
    "B": "Federated per LOB or Region",
    "C": "Hybrid Hub-of-Hubs",
}
GOOGLE_APIS = ["aiplatform.googleapis.com", "logging.googleapis.com", "modelarmor.googleapis.com"]


@dataclass
class Topology:
    org_id: str
    governance_project: str
    spoke_projects: list[str]
    regions: list[str]
    autonomous_lobs: bool
    shared_crown_jewel_tools: bool
    notes: list[str] = field(default_factory=list)


def recommend(t: Topology) -> tuple[str, list[str]]:
    multi_region = len(set(t.regions)) > 1
    reasons = [f"{len(set(t.regions))} region(s)", "autonomous LOBs" if t.autonomous_lobs else "centrally run LOBs",
               "shared crown-jewel tools" if t.shared_crown_jewel_tools else "no shared crown-jewel tools"]
    if multi_region and t.shared_crown_jewel_tools:
        choice = "C"
    elif multi_region or t.autonomous_lobs:
        choice = "B"
    else:
        choice = "A"
    if choice == "B" and t.shared_crown_jewel_tools:
        reasons.append("advisory: shared crown-jewel tools still need ONE owner and ONE kill switch -> consider C")
    return choice, reasons


def _spiffe(org: str, project: str, sa: str = "*") -> str:
    return f"spiffe://{org}.svc.id.goog/ns/{project}/sa/{sa}"


def two_tier_policy(t: Topology, agent_project: str, agent_sa: str) -> dict:
    """Unified Access Policy, simplified. Tier 1: every workload in the spoke gets baseline Google APIs.
    Tier 2: one named agent may call MCP servers only if they are REGISTERED and owned by its service account."""
    apis = GOOGLE_APIS + [a.replace(".googleapis.com", ".mtls.googleapis.com") for a in GOOGLE_APIS]
    return {
        "name": f"{t.governance_project}/central-hub-uap",
        "destinationGroups": {"google-apis": apis},
        "rules": [
            {"name": "tier1-spoke-baseline", "tier": 1, "action": "ALLOW",
             "principalSet": _spiffe(t.org_id, agent_project), "destinations": "google-apis"},
            {"name": "tier2-concierge-registered-tools", "tier": 2, "action": "ALLOW",
             "principal": _spiffe(t.org_id, agent_project, agent_sa), "destinations": "mcp_servers",
             "condition": {"cel": f"destination.registered && destination.owner == '{agent_sa}'",
                           "registered": True, "owner": agent_sa}},
        ],
        "default": "DENY",
    }


def _matches(rule: dict, principal: str) -> bool:
    if "principal" in rule:
        return principal == rule["principal"]
    prefix = rule["principalSet"].removesuffix("*")
    return principal.startswith(prefix)


def evaluate(policy: dict, principal: str, destination: dict) -> tuple[str, str]:
    """destination: {"host": ...} for APIs, or {"type": "mcp_server", "name", "registered", "owner"}."""
    for rule in policy["rules"]:
        if not _matches(rule, principal):
            continue
        if rule["destinations"] == "mcp_servers" and destination.get("type") == "mcp_server":
            c = rule["condition"]
            if destination.get("registered") is c["registered"] and destination.get("owner") == c["owner"]:
                return "ALLOW", rule["name"]
        elif rule["destinations"] in policy["destinationGroups"] and \
                destination.get("host") in policy["destinationGroups"][rule["destinations"]]:
            return "ALLOW", rule["name"]
    return "DENY", "default deny"
