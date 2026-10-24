"""Day 21 simulation: run the SAME workload through archetypes A, B and C and measure the tradeoffs.

Workload: 3 lines of business (each its own region), each registers N new agents/tools, plus 2 shared
Tier-0 MCP servers everyone uses. Then a Tier-0 server is compromised and must be shut off everywhere.

Measured per archetype:
  central approvals     work queued on the central team (the developer-bottleneck risk)
  central visibility    how many of the org's agents the central SecOps inventory can see (blind spots)
  cross-LOB leaks       registry entries one LOB can read about another LOB (metadata leakage)
  kill-switch actions   how many registries must change to stop the compromised Tier-0 server everywhere
  still exposed         LOBs that can still resolve it after ONE central action
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import advisor  # noqa: E402

LOBS = {"retail": "us-central1", "wealth": "europe-west1", "insurance": "asia-southeast1"}
TIER0 = ["enterprise-search-mcp", "identity-directory-mcp"]


@dataclass
class Registry:
    name: str
    entries: dict[str, dict] = field(default_factory=dict)

    def add(self, name: str, owner: str, tier0: bool = False) -> None:
        self.entries[name] = {"owner": owner, "tier0": tier0, "status": "APPROVED"}

    def approved(self, name: str) -> bool:
        return self.entries.get(name, {}).get("status") == "APPROVED"


@dataclass
class Org:
    archetype: str
    registries: dict[str, Registry]
    central_approvals: int = 0

    def registry_for(self, lob: str) -> Registry:
        return self.registries["central"] if self.archetype == "A" else self.registries[lob]

    def visible_to(self, lob: str) -> set[str]:
        """What an agent in this LOB can discover."""
        if self.archetype == "A":
            return set(self.registries["central"].entries)  # one shared catalog: everyone sees everything
        own = set(self.registries[lob].entries)
        return own | (set(self.registries["central"].entries) if self.archetype == "C" else set())

    def resolves(self, lob: str, name: str) -> bool:
        if self.archetype == "A":
            return self.registries["central"].approved(name)
        if self.archetype == "B":
            return self.registries[lob].approved(name)
        return self.registries[lob].approved(name) or self.registries["central"].approved(name)

    def central_inventory(self) -> set[str]:
        if self.archetype == "A":
            return set(self.registries["central"].entries)
        if self.archetype == "B":
            return set()  # no hub; only org-wide floor settings, no inventory
        inv = set(self.registries["central"].entries)
        for k, r in self.registries.items():
            if k != "central":
                inv |= set(r.entries)  # C: LOB registries publish inventory upward (metadata only)
        return inv


def build(archetype: str, agents_per_lob: int) -> Org:
    regs = {"central": Registry("central")} if archetype in "AC" else {}
    if archetype in "BC":
        regs.update({lob: Registry(lob) for lob in LOBS})
    org = Org(archetype, regs)
    for lob in LOBS:
        for i in range(agents_per_lob):
            org.registry_for(lob).add(f"{lob}-agent-{i:02d}", owner=lob)
            if archetype == "A":
                org.central_approvals += 1  # every new agent waits on the central team
    for t in TIER0:
        if archetype == "B":
            for lob in LOBS:
                org.registries[lob].add(t, owner="platform", tier0=True)  # each LOB keeps its own copy
        else:
            org.registries["central"].add(t, owner="platform", tier0=True)
            org.central_approvals += 1
    return org


def kill(org: Org, name: str) -> int:
    """Revokes a compromised server. Returns how many registries had to change."""
    if org.archetype == "B":
        changed = 0
        for r in org.registries.values():
            if name in r.entries:
                r.entries[name]["status"] = "REVOKED"
                changed += 1
        return changed
    org.registries["central"].entries[name]["status"] = "REVOKED"
    return 1


def measure(archetype: str, agents_per_lob: int = 10) -> dict:
    org = build(archetype, agents_per_lob)
    total_agents = agents_per_lob * len(LOBS)
    leaks = sum(len({e for e in org.visible_to(lob) if e.split("-agent-")[0] in LOBS and not e.startswith(lob)})
                for lob in LOBS)
    inventory = org.central_inventory()
    central_seen = sum(1 for e in inventory if "-agent-" in e)
    org_b = build(archetype, agents_per_lob)
    one_action_exposed = 0
    if archetype == "B":
        # one central team action can't reach LOB registries: simulate revoking in ONE registry only
        first = next(iter(org_b.registries.values()))
        first.entries[TIER0[0]]["status"] = "REVOKED"
        one_action_exposed = sum(org_b.resolves(lob, TIER0[0]) for lob in LOBS)
    actions = kill(org, TIER0[0])
    return {"archetype": archetype, "name": advisor.ARCHETYPES[archetype],
            "central_approvals": org.central_approvals,
            "central_visibility": f"{central_seen}/{total_agents}",
            "cross_lob_leaks": leaks,
            "kill_switch_actions": actions,
            "exposed_after_one_action": one_action_exposed,
            "still_resolves_after_kill": sum(org.resolves(lob, TIER0[0]) for lob in LOBS)}
