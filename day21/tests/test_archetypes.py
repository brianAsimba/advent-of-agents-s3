"""Day 21 tests: advisor rule, two-tier policy evaluation, archetype simulation."""
import pytest

import advisor
import mesh


def topo(regions, autonomous, crown):
    return advisor.Topology("o", "o-gov", ["s"], regions, autonomous, crown)


@pytest.mark.parametrize("regions,autonomous,crown,want", [
    (["us"], False, False, "A"),
    (["us"], True, False, "B"),
    (["us", "eu"], False, False, "B"),
    (["us", "eu"], True, True, "C"),
    (["us", "eu"], False, True, "C"),
])
def test_course_rule(regions, autonomous, crown, want):
    assert advisor.recommend(topo(regions, autonomous, crown))[0] == want


def test_advisory_when_rule_says_b_but_crown_jewels_are_shared():
    choice, reasons = advisor.recommend(topo(["us"], True, True))
    assert choice == "B" and any("consider C" in r for r in reasons)


@pytest.fixture
def policy():
    return advisor.two_tier_policy(topo(["us"], False, False), "eng", "concierge")


C = "spiffe://o.svc.id.goog/ns/eng/sa/concierge"
OTHER = "spiffe://o.svc.id.goog/ns/eng/sa/batch"
MCP = {"type": "mcp_server", "name": "m", "registered": True, "owner": "concierge"}


def test_tier1_is_coarse_project_wide(policy):
    assert advisor.evaluate(policy, OTHER, {"host": "logging.googleapis.com"})[0] == "ALLOW"
    assert advisor.evaluate(policy, OTHER, {"host": "logging.mtls.googleapis.com"})[0] == "ALLOW"
    assert advisor.evaluate(policy, OTHER, {"host": "evil.example.com"}) == ("DENY", "default deny")


def test_tier2_is_one_principal_and_registered_destinations_only(policy):
    assert advisor.evaluate(policy, C, MCP) == ("ALLOW", "tier2-concierge-registered-tools")
    assert advisor.evaluate(policy, OTHER, MCP)[0] == "DENY"
    assert advisor.evaluate(policy, C, {**MCP, "registered": False})[0] == "DENY"
    assert advisor.evaluate(policy, C, {**MCP, "owner": "someone-else"})[0] == "DENY"


def test_other_project_gets_nothing(policy):
    assert advisor.evaluate(policy, "spiffe://o.svc.id.goog/ns/other/sa/concierge",
                            {"host": "aiplatform.googleapis.com"})[0] == "DENY"


def test_archetype_tradeoffs():
    a, b, c = (mesh.measure(x) for x in "ABC")
    assert a["central_approvals"] > c["central_approvals"] > b["central_approvals"] == 0   # bottleneck
    assert a["central_visibility"] == c["central_visibility"] == "30/30" and b["central_visibility"] == "0/30"
    assert a["cross_lob_leaks"] > 0 and b["cross_lob_leaks"] == c["cross_lob_leaks"] == 0
    assert (a["kill_switch_actions"], b["kill_switch_actions"], c["kill_switch_actions"]) == (1, 3, 1)
    assert all(m["still_resolves_after_kill"] == 0 for m in (a, b, c))
    assert b["exposed_after_one_action"] == 2


def test_hub_of_hubs_lob_sees_own_plus_shared_never_other_lob():
    org = mesh.build("C", 2)
    seen = org.visible_to("retail")
    assert "retail-agent-00" in seen and "enterprise-search-mcp" in seen and "wealth-agent-00" not in seen
    assert org.resolves("retail", "identity-directory-mcp") and not org.resolves("retail", "wealth-agent-00")
